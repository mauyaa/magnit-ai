import asyncio
import logging
import os
from dataclasses import dataclass

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy
from google.antigravity.types import McpStdioServer

from sqlalchemy import select

from app.features.widgets.models import Widget
from app.platform.clients.deployment import deploy_directory
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory
from app.platform.pipeline.builder import build_project
from app.platform.pipeline.events import events as event_manager
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    BlueprintList,
    DeploymentResult,
    DesignTokens,
    WidgetCode,
)
from app.platform.pipeline.states.analyzer import (
    SYSTEM_PROMPT as ANALYZER_SYSTEM_PROMPT,
    run as run_analyzer,
)
from app.platform.pipeline.states.architect import (
    ARCHITECT_SYSTEM_PROMPT,
    run as run_architect,
)
from app.platform.pipeline.states.stitcher import (
    STITCHER_SYSTEM_PROMPT,
    run as run_stitcher,
)
from app.platform.pipeline.states.codegen import (
    CODEGEN_SYSTEM_PROMPT,
    run as run_codegen,
)

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
    extra_tools: list | None = None,
    response_schema=None,
) -> Agent:
    mcp_servers = []
    mcp_command = getattr(settings, "stitch_mcp_command", None)
    mcp_args = getattr(settings, "stitch_mcp_args", None)
    if mcp_command and mcp_args:
        mcp_servers.append(
            McpStdioServer(name="stitch", command=mcp_command, args=mcp_args)
        )

    config = LocalAgentConfig(
        system_instructions=system_instructions,
        tools=extra_tools or [],
        mcp_servers=mcp_servers,
        response_schema=response_schema,
        model=settings.agy_model,
        api_key=settings.gemini_api_key if settings.gemini_api_key else None,
        policies=[policy.allow_all()],
    )
    return Agent(config)


async def analyze(url: str) -> BlueprintList:
    async with _make_agent(
        system_instructions=ANALYZER_SYSTEM_PROMPT,
    ) as agent:
        return await run_analyzer(agent, url)


async def _update_build_progress(widget_id: str, **kwargs) -> None:
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
    widget_type,
    max_retries: int = 2,
) -> WidgetCode:
    async def _gen(feedback: str | None = None) -> WidgetCode:
        async with _make_agent(
            system_instructions=CODEGEN_SYSTEM_PROMPT,
        ) as agent:
            return await asyncio.wait_for(
                run_codegen(
                    agent, architect_output, design_tokens, widget_type, feedback=feedback
                ),
                timeout=AGENT_TIMEOUT,
            )

    await event_manager.publish_stage(
        widget_id, "codegen", "active", "Generating app component...",
        progress=55.0,
    )
    widget_code = await _gen()

    async def _retry_callback(build_errors: str) -> list[dict]:
        nonlocal widget_code
        logger.warning("Codegen retry with build errors:\n%s", build_errors[:2000])
        await event_manager.publish_stage(
            widget_id, "codegen", "active",
            f"Fixing build errors: {build_errors[:120]}...",
            progress=60.0,
        )
        widget_code = await _gen(feedback=build_errors)
        return [f.model_dump() for f in widget_code.files]

    project_dir = os.path.join(settings.widgets_dir, f"build_{widget_type.value}")

    await event_manager.publish_stage(
        widget_id, "codegen", "active", "Installing dependencies and building...",
        progress=65.0,
    )
    success, build_output = await build_project(
        project_dir,
        [f.model_dump() for f in widget_code.files],
        max_retries=max_retries,
        gen_callback=_retry_callback,
    )

    if not success:
        err = build_output if isinstance(build_output, str) else "unknown error"
        logger.error("Codegen failed for app %s:\n%s", widget_id, err)
        await event_manager.publish_stage(
            widget_id, "codegen", "failed", f"Build error: {err[:300]}",
        )
        raise RuntimeError(f"App build failed after {max_retries} attempts - {err[:500]}")

    await event_manager.publish_stage(
        widget_id, "codegen", "complete", "App code generated and built successfully",
        progress=80.0,
    )
    return widget_code, project_dir


async def build(
    blueprint: Blueprint, url: str, widget_id: str, skip_deploy: bool = False
) -> BuildResult:
    await _update_build_progress(widget_id, build_stage="architect", build_progress=5.0)

    await event_manager.publish_stage(
        widget_id, "architect", "active",
        "Extracting brand identity and visual design language...",
        progress=5.0,
    )
    async with _make_agent(
        system_instructions=ARCHITECT_SYSTEM_PROMPT,
    ) as architect_agent:
        architect_output = await asyncio.wait_for(
            run_architect(architect_agent, blueprint, url),
            timeout=AGENT_TIMEOUT,
        )

    await _update_build_progress(widget_id, build_stage="architect", build_progress=30.0)

    await event_manager.publish_stage(
        widget_id, "architect", "complete",
        "Brand and visual language extracted",
        data={
            "brand": architect_output.brand.model_dump(),
            "widget_type": blueprint.type.value,
        },
        progress=30.0,
    )

    await _update_build_progress(widget_id, build_stage="stitcher", build_progress=35.0)

    await event_manager.publish_stage(
        widget_id, "stitcher", "active",
        "Generating design tokens and component theme...",
        progress=35.0,
    )
    async with _make_agent(
        system_instructions=STITCHER_SYSTEM_PROMPT,
    ) as stitcher_agent:
        design_tokens = await asyncio.wait_for(
            run_stitcher(stitcher_agent, architect_output),
            timeout=AGENT_TIMEOUT,
        )

    await _update_build_progress(widget_id, build_stage="stitcher", build_progress=50.0)

    await event_manager.publish_stage(
        widget_id, "stitcher", "complete",
        "Design tokens generated",
        data={"css_variables": design_tokens.css_variables},
        progress=50.0,
    )

    await _update_build_progress(widget_id, build_stage="codegen", build_progress=55.0)

    widget_code, project_dir = await _codegen_with_retry(
        widget_id, architect_output, design_tokens, blueprint.type
    )

    serve_dir = os.path.join(settings.widgets_dir, "_serve", widget_id)
    os.makedirs(os.path.dirname(serve_dir), exist_ok=True)
    if os.path.islink(serve_dir) or os.path.isdir(serve_dir):
        os.remove(serve_dir)
    os.symlink(os.path.join(project_dir, "dist", "assets"), serve_dir)

    if skip_deploy:
        deployment = DeploymentResult(url="", widget_id=widget_id)
        await _update_build_progress(widget_id, build_stage="deploy", build_progress=100.0)
        await event_manager.publish_stage(
            widget_id, "deploy", "complete",
            "Build complete (deploy skipped)",
            progress=100.0,
        )
    else:
        await _update_build_progress(widget_id, build_stage="deploy", build_progress=85.0)
        await event_manager.publish_stage(
            widget_id, "deploy", "active",
            "Deploying to Vercel...",
            progress=85.0,
        )
        deployment = await deploy_directory(f"{project_dir}/dist", widget_id)
        await _update_build_progress(widget_id, build_stage="deploy", build_progress=100.0)
        await event_manager.publish_stage(
            widget_id, "deploy", "complete",
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
