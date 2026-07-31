import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy
from google.antigravity.types import McpStdioServer
from sqlalchemy import select

from app.features.widgets.models import Widget
from app.features.widgets.outcomes import derive_outcome_config
from app.platform.clients.deployment import deploy_directory
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory
from app.platform.observability.metrics import generation_provider_total
from app.platform.pipeline.builder import build_project
from app.platform.pipeline.events import events as event_manager
from app.platform.pipeline.fallback_widget import (
    fallback_design_tokens,
    fallback_widget_code,
)
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    BlueprintList,
    CreationBrief,
    DeploymentResult,
    DesignTokens,
    SiteEvidence,
    WidgetCode,
    WidgetType,
)
from app.platform.pipeline.states.analyzer import (
    SYSTEM_PROMPT as ANALYZER_SYSTEM_PROMPT,
)
from app.platform.pipeline.states.analyzer import (
    run as run_analyzer,
)
from app.platform.pipeline.states.architect import (
    ARCHITECT_SYSTEM_PROMPT,
)
from app.platform.pipeline.states.architect import (
    run as run_architect,
)
from app.platform.pipeline.states.codegen import (
    CODEGEN_SYSTEM_PROMPT,
)
from app.platform.pipeline.states.codegen import (
    run as run_codegen,
)
from app.platform.pipeline.states.stitcher import (
    STITCHER_SYSTEM_PROMPT,
)
from app.platform.pipeline.states.stitcher import (
    run as run_stitcher,
)
from app.platform.pipeline.usage import record_generation_usage

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 120


@dataclass
class BuildResult:
    deployment: DeploymentResult
    architect_output: ArchitectOutput
    design_tokens: DesignTokens
    widget_code: WidgetCode
    project_dir: str = ""


def _make_agent(
    system_instructions: str,
    extra_tools: list[Any] | None = None,
    response_schema: Any | None = None,
    *,
    allow_tools: bool = False,
) -> Agent:
    mcp_servers: list[McpStdioServer] = []
    mcp_command = settings.stitch_mcp_command
    mcp_args = settings.stitch_mcp_args
    if allow_tools and mcp_command and mcp_args:
        mcp_servers.append(McpStdioServer(name="stitch", command=mcp_command, args=mcp_args))

    api_key = (
        settings.stitch_api_key
        if (allow_tools and settings.stitch_api_key)
        else settings.gemini_api_key
    )

    config = LocalAgentConfig(
        system_instructions=system_instructions,
        tools=extra_tools or [],
        mcp_servers=mcp_servers,
        response_schema=response_schema,
        model=settings.agy_model,
        api_key=api_key if api_key else None,
        # Analysis, architecture and code generation receive structured inputs
        # and never need ambient filesystem, shell, browser or network access.
        # Stitch can opt in explicitly when a configured MCP server is required.
        policies=[policy.allow_all() if allow_tools else policy.deny_all()],
    )
    return Agent(config)


async def analyze(
    url: str,
    evidence: SiteEvidence,
    brief: CreationBrief | None = None,
) -> BlueprintList:
    started = time.perf_counter()
    try:
        async with _make_agent(
            system_instructions=ANALYZER_SYSTEM_PROMPT,
        ) as agent:
            output = await run_analyzer(agent, url, evidence, brief)
        await record_generation_usage(
            stage="analyzer",
            input_value={
                "evidence": evidence.compact_context(),
                "brief": brief.model_dump(mode="json") if brief else None,
            },
            output_value=output,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return output
    except Exception as exc:
        await record_generation_usage(
            stage="analyzer",
            input_value={
                "evidence": evidence.compact_context(),
                "brief": brief.model_dump(mode="json") if brief else None,
            },
            duration_ms=round((time.perf_counter() - started) * 1000),
            succeeded=False,
            error_code=type(exc).__name__,
        )
        raise


async def _update_build_progress(widget_id: str, **kwargs: Any) -> None:
    try:
        async with async_session_factory() as session:
            stmt = select(Widget).where(Widget.id == widget_id)
            result = await session.execute(stmt)
            widget = result.scalar_one_or_none()
            if widget:
                for k, v in kwargs.items():
                    setattr(widget, k, v)
                await session.commit()
    except Exception:
        logger.warning("Failed to persist build progress for %s", widget_id, exc_info=True)


async def _codegen_with_retry(
    widget_id: str,
    architect_output: ArchitectOutput,
    design_tokens: DesignTokens,
    widget_type: WidgetType,
    widget_title: str,
    max_attempts: int = 3,
    force_fallback: bool = False,
) -> tuple[WidgetCode, str]:
    """Generate the app, then prove it builds and captures leads before accepting it.

    Feedback from a rejected attempt — a compiler error, a missing entry point, or a
    missing ``submitLead`` call — is passed back into the next generation, so the
    model is corrected with specifics rather than asked again blindly.
    """

    async def _gen(feedback: str | None = None) -> WidgetCode:
        started = time.perf_counter()
        input_value = {
            "architect": architect_output.model_dump(mode="json"),
            "tokens": design_tokens.model_dump(mode="json"),
            "type": widget_type.value,
            "feedback": feedback,
        }
        try:
            async with _make_agent(
                system_instructions=CODEGEN_SYSTEM_PROMPT,
            ) as agent:
                output = await asyncio.wait_for(
                    run_codegen(
                        agent,
                        architect_output,
                        design_tokens,
                        widget_type,
                        widget_title=widget_title,
                        feedback=feedback,
                    ),
                    timeout=AGENT_TIMEOUT,
                )
            await record_generation_usage(
                stage="codegen",
                input_value=input_value,
                output_value=output,
                duration_ms=round((time.perf_counter() - started) * 1000),
                widget_id=widget_id,
            )
            return output
        except Exception as exc:
            await record_generation_usage(
                stage="codegen",
                input_value=input_value,
                duration_ms=round((time.perf_counter() - started) * 1000),
                widget_id=widget_id,
                succeeded=False,
                error_code=type(exc).__name__,
            )
            raise

    await event_manager.publish_stage(
        widget_id,
        "codegen",
        "active",
        "Generating app component...",
        progress=55.0,
    )
    using_fallback = False

    async def _fallback(reason: str) -> WidgetCode:
        nonlocal using_fallback
        if not using_fallback:
            generation_provider_total.labels("codegen", "fallback").inc()
        using_fallback = True
        logger.warning(
            "Code generation unavailable for widget %s; using verified fallback: %s",
            widget_id,
            reason[:500],
        )
        await event_manager.publish_stage(
            widget_id,
            "codegen",
            "active",
            "Building the verified visitor experience...",
            progress=60.0,
        )
        return fallback_widget_code(design_tokens)

    if force_fallback:
        widget_code = await _fallback("The generation provider is unavailable for this build.")
    else:
        try:
            widget_code = await _gen()
            generation_provider_total.labels("codegen", "model").inc()
        except Exception as exc:
            widget_code = await _fallback(str(exc))

    async def _retry_callback(reason: str) -> list[dict]:
        nonlocal widget_code
        logger.warning("Codegen retry. Reason:\n%s", reason[:2000])
        await event_manager.publish_stage(
            widget_id,
            "codegen",
            "active",
            "Fixing issues found while validating the generated app...",
            progress=60.0,
        )
        if not using_fallback:
            try:
                widget_code = await _gen(feedback=reason)
                generation_provider_total.labels("codegen", "model").inc()
            except Exception as exc:
                widget_code = await _fallback(str(exc))
        return [f.model_dump() for f in widget_code.files]

    project_dir = os.path.join(settings.widgets_dir, f"build_{widget_id}")

    await event_manager.publish_stage(
        widget_id,
        "codegen",
        "active",
        "Installing dependencies and building...",
        progress=65.0,
    )
    success, build_output = await build_project(
        project_dir,
        [f.model_dump() for f in widget_code.files],
        widget_id=widget_id,
        widget_title=widget_title,
        api_base_url=settings.site_url,
        design_tokens=design_tokens,
        decision_spec=(
            architect_output.decision.model_dump(mode="json") if architect_output.decision else None
        ),
        # Baked in so the deployed bundle can render a complete result screen with
        # no network at all. The runtime overlay then replaces it with whatever
        # the owner has since edited.
        outcomes=derive_outcome_config(
            architect_output.decision, architect_output.copywriting
        ).model_dump(mode="json"),
        max_attempts=1 if using_fallback else max_attempts,
        gen_callback=None if using_fallback else _retry_callback,
    )

    if not success:
        err = build_output if isinstance(build_output, str) else "unknown error"
        logger.error("Codegen failed for widget %s:\n%s", widget_id, err)
        await event_manager.publish_stage(
            widget_id,
            "codegen",
            "failed",
            f"Build error: {err[:300]}",
        )
        raise RuntimeError(f"App build failed after {max_attempts} attempts - {err[:500]}")

    await event_manager.publish_stage(
        widget_id,
        "codegen",
        "complete",
        "App built and lead capture verified",
        progress=80.0,
    )
    return widget_code, project_dir


async def run_architect_stage(
    blueprint: Blueprint,
    url: str,
    evidence: SiteEvidence,
    widget_id: str | None = None,
    brief: CreationBrief | None = None,
) -> ArchitectOutput:
    started = time.perf_counter()
    input_value = {
        "blueprint": blueprint.model_dump(mode="json"),
        "evidence": evidence.compact_context(),
        "brief": brief.model_dump(mode="json") if brief else None,
    }
    try:
        async with _make_agent(
            system_instructions=ARCHITECT_SYSTEM_PROMPT,
        ) as architect_agent:
            output = await asyncio.wait_for(
                run_architect(architect_agent, blueprint, url, evidence, brief),
                timeout=AGENT_TIMEOUT,
            )
        await record_generation_usage(
            stage="architect",
            input_value=input_value,
            output_value=output,
            duration_ms=round((time.perf_counter() - started) * 1000),
            widget_id=widget_id,
        )
        return output
    except Exception as exc:
        await record_generation_usage(
            stage="architect",
            input_value=input_value,
            duration_ms=round((time.perf_counter() - started) * 1000),
            widget_id=widget_id,
            succeeded=False,
            error_code=type(exc).__name__,
        )
        raise


async def generate_and_deploy(
    widget_id: str,
    architect_output: ArchitectOutput,
    widget_type: WidgetType,
    widget_title: str,
    skip_deploy: bool = False,
    token_overrides: dict[str, str] | None = None,
) -> BuildResult:
    await _update_build_progress(widget_id, build_stage="stitcher", build_progress=35.0)

    await event_manager.publish_stage(
        widget_id,
        "stitcher",
        "active",
        "Generating design tokens and component theme...",
        progress=35.0,
    )
    stitch_started = time.perf_counter()
    generation_provider_unavailable = False
    try:
        async with _make_agent(
            system_instructions=STITCHER_SYSTEM_PROMPT,
            allow_tools=True,
        ) as stitcher_agent:
            design_tokens = await asyncio.wait_for(
                run_stitcher(stitcher_agent, architect_output),
                timeout=AGENT_TIMEOUT,
            )
        await record_generation_usage(
            stage="stitcher",
            input_value=architect_output,
            output_value=design_tokens,
            duration_ms=round((time.perf_counter() - stitch_started) * 1000),
            widget_id=widget_id,
        )
    except Exception as exc:
        generation_provider_unavailable = True
        await record_generation_usage(
            stage="stitcher",
            input_value=architect_output,
            duration_ms=round((time.perf_counter() - stitch_started) * 1000),
            widget_id=widget_id,
            succeeded=False,
            error_code=type(exc).__name__,
        )
        generation_provider_total.labels("stitcher", "fallback").inc()
        logger.warning(
            "Design-token generation unavailable for widget %s; preserving observed brand",
            widget_id,
        )
        design_tokens = fallback_design_tokens(architect_output)
        await event_manager.publish_stage(
            widget_id,
            "stitcher",
            "active",
            "Applying the confirmed brand directly...",
            progress=45.0,
        )
    else:
        generation_provider_total.labels("stitcher", "model").inc()

    if token_overrides:
        # The workspace brand kit wins over what the Stitcher chose. Applied here
        # rather than inside the Stitcher prompt because a hard override has to be
        # a guarantee, not a request a model may or may not honour.
        design_tokens = design_tokens.model_copy(
            update={"css_variables": {**design_tokens.css_variables, **token_overrides}}
        )

    await _update_build_progress(widget_id, build_stage="stitcher", build_progress=50.0)

    await event_manager.publish_stage(
        widget_id,
        "stitcher",
        "complete",
        "Design tokens generated",
        data={"css_variables": design_tokens.css_variables},
        progress=50.0,
    )

    await _update_build_progress(widget_id, build_stage="codegen", build_progress=55.0)

    widget_code, project_dir = await _codegen_with_retry(
        widget_id,
        architect_output,
        design_tokens,
        widget_type,
        widget_title,
        force_fallback=generation_provider_unavailable,
    )

    # No local serving step: widgets are served from their own Vercel deployment,
    # so the former workspace/_serve symlink had nothing reading it. It also could
    # not work on Windows, where os.symlink needs elevated privileges.

    if skip_deploy:
        deployment = DeploymentResult(url="", widget_id=widget_id)
        await _update_build_progress(widget_id, build_stage="deploy", build_progress=100.0)
        await event_manager.publish_stage(
            widget_id,
            "deploy",
            "complete",
            "Build complete (deploy skipped)",
            progress=100.0,
        )
    else:
        await _update_build_progress(widget_id, build_stage="deploy", build_progress=85.0)
        await event_manager.publish_stage(
            widget_id,
            "deploy",
            "active",
            "Deploying to Vercel...",
            progress=85.0,
        )
        deployment = await deploy_directory(f"{project_dir}/dist", widget_id)
        await _update_build_progress(widget_id, build_stage="deploy", build_progress=100.0)
        await event_manager.publish_stage(
            widget_id,
            "deploy",
            "complete",
            "App deployed to Vercel",
            data={"url": deployment.url},
            progress=100.0,
        )

    return BuildResult(
        deployment=deployment,
        architect_output=architect_output,
        design_tokens=design_tokens,
        widget_code=widget_code,
        project_dir=project_dir,
    )


async def build(
    blueprint: Blueprint,
    url: str,
    widget_id: str,
    skip_deploy: bool = False,
    architect_override: ArchitectOutput | None = None,
    source_evidence: SiteEvidence | None = None,
    creation_brief: CreationBrief | None = None,
    brand_overrides: dict[str, str] | None = None,
    token_overrides: dict[str, str] | None = None,
) -> BuildResult:
    """Run a build.

    ``brand_overrides`` and ``token_overrides`` arrive as plain dictionaries, not
    as a workspace-brand object, so this module keeps depending only on the
    pipeline's own schemas. Resolving a customer's brand kit into these two maps
    is the caller's job — see ``tasks._workspace_brand_overrides``.
    """
    if architect_override is not None:
        architect_output = architect_override
        await _update_build_progress(widget_id, build_stage="architect", build_progress=30.0)
        await event_manager.publish_stage(
            widget_id,
            "architect",
            "complete",
            "Using confirmed brand and visual language",
            data={
                "brand": architect_output.brand.model_dump(),
                "widget_type": blueprint.type.value,
            },
            progress=30.0,
        )
    else:
        if source_evidence is None:
            raise RuntimeError("source evidence is required for a grounded build")
        await _update_build_progress(widget_id, build_stage="architect", build_progress=5.0)
        await event_manager.publish_stage(
            widget_id,
            "architect",
            "active",
            "Extracting brand identity and visual design language...",
            progress=5.0,
        )
        architect_output = await run_architect_stage(
            blueprint,
            url,
            source_evidence,
            widget_id,
            creation_brief,
        )

        await _update_build_progress(widget_id, build_stage="architect", build_progress=30.0)
        await event_manager.publish_stage(
            widget_id,
            "architect",
            "complete",
            "Brand and visual language extracted",
            data={
                "brand": architect_output.brand.model_dump(),
                "widget_type": blueprint.type.value,
            },
            progress=30.0,
        )

    if brand_overrides:
        architect_output = architect_output.model_copy(
            update={"brand": architect_output.brand.model_copy(update=brand_overrides)}
        )

    return await generate_and_deploy(
        widget_id,
        architect_output,
        blueprint.type,
        blueprint.title,
        skip_deploy,
        token_overrides=token_overrides,
    )
