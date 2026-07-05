import logging
import os
from dataclasses import dataclass

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy
from google.antigravity.types import McpStdioServer

from app.platform.clients.deployment import deploy_directory
from app.platform.config.settings import settings
from app.platform.pipeline.builder import build_project
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


async def _codegen_with_retry(
    architect_output: ArchitectOutput,
    design_tokens: DesignTokens,
    widget_type,
    max_retries: int = 3,
) -> WidgetCode:
    async def _gen(feedback: str | None = None) -> WidgetCode:
        async with _make_agent(
            system_instructions=CODEGEN_SYSTEM_PROMPT,
        ) as agent:
            return await run_codegen(
                agent, architect_output, design_tokens, widget_type, feedback=feedback
            )

    widget_code = await _gen()

    async def _retry_callback(build_errors: str) -> list[dict]:
        nonlocal widget_code
        logger.info("Codegen retry with build errors: %s", build_errors[:200])
        widget_code = await _gen(feedback=build_errors)
        return [f.model_dump() for f in widget_code.files]

    project_dir = os.path.join(settings.widgets_dir, f"build_{widget_type.value}")
    success, project_dir = await build_project(
        project_dir,
        [f.model_dump() for f in widget_code.files],
        max_retries=max_retries,
        gen_callback=_retry_callback,
    )

    if not success:
        raise RuntimeError(f"Widget build failed after {max_retries} attempts")

    return widget_code, project_dir


async def build(
    blueprint: Blueprint, url: str, widget_id: str, skip_deploy: bool = False
) -> BuildResult:
    async with _make_agent(
        system_instructions=ARCHITECT_SYSTEM_PROMPT,
    ) as architect_agent:
        architect_output = await run_architect(architect_agent, blueprint, url)

    async with _make_agent(
        system_instructions=STITCHER_SYSTEM_PROMPT,
    ) as stitcher_agent:
        design_tokens = await run_stitcher(stitcher_agent, architect_output)

    widget_code, project_dir = await _codegen_with_retry(
        architect_output, design_tokens, blueprint.type
    )

    serve_dir = os.path.join(settings.widgets_dir, "_serve", widget_id)
    os.makedirs(os.path.dirname(serve_dir), exist_ok=True)
    if os.path.islink(serve_dir) or os.path.isdir(serve_dir):
        os.remove(serve_dir)
    os.symlink(os.path.join(project_dir, "dist", "assets"), serve_dir)

    if skip_deploy:
        deployment = DeploymentResult(url="", widget_id=widget_id)
    else:
        deployment = await deploy_directory(f"{project_dir}/dist", widget_id)

    return BuildResult(
        deployment=deployment,
        architect_output=architect_output,
        design_tokens=design_tokens,
        widget_code=widget_code,
        project_dir=project_dir,
    )
