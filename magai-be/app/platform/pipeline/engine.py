import logging
from typing import Callable

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy
from google.antigravity.types import McpStdioServer

from app.platform.config.settings import settings
from app.platform.pipeline.schemas import (
    Blueprint,
    BlueprintList,
    DeploymentResult,
    PipelineStatus,
)
from app.platform.pipeline.states.analyzer import (
    SYSTEM_PROMPT as ANALYZER_SYSTEM_PROMPT,
    analyzer_capabilities,
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
from app.platform.pipeline.states.deployer import (
    DEPLOYER_SYSTEM_PROMPT,
    run as run_deployer,
)

logger = logging.getLogger(__name__)


def _make_agent(
    system_instructions: str,
    extra_tools: list[Callable] | None = None,
    response_schema=None,
) -> Agent:
    mcp_servers = []
    mcp_command = getattr(settings, "stitch_mcp_command", None)
    mcp_args = getattr(settings, "stitch_mcp_args", None)
    if mcp_command and mcp_args:
        mcp_servers.append(
            McpStdioServer(name="stitch", command=mcp_command, args=mcp_args)
        )

    tools = extra_tools or []
    config = LocalAgentConfig(
        system_instructions=system_instructions,
        tools=tools,
        mcp_servers=mcp_servers,
        response_schema=response_schema,
        model=settings.agy_model,
        policies=[policy.allow_all()],
    )
    return Agent(config)


async def analyze(url: str) -> BlueprintList:
    async with _make_agent(
        system_instructions=ANALYZER_SYSTEM_PROMPT,
        response_schema=BlueprintList,
    ) as agent:
        return await run_analyzer(agent, url)


async def build(blueprint: Blueprint, url: str, widget_id: str) -> DeploymentResult:
    status = PipelineStatus(state="architecting", progress=0.2)

    async with _make_agent(
        system_instructions=ARCHITECT_SYSTEM_PROMPT,
    ) as architect_agent:
        architect_output = await run_architect(architect_agent, blueprint, url)

    status.state = "stitching"
    status.progress = 0.4

    async with _make_agent(
        system_instructions=STITCHER_SYSTEM_PROMPT,
    ) as stitcher_agent:
        design_tokens = await run_stitcher(stitcher_agent, architect_output)

    status.state = "coding"
    status.progress = 0.6

    async with _make_agent(
        system_instructions=CODEGEN_SYSTEM_PROMPT,
    ) as codegen_agent:
        widget_code = await run_codegen(
            codegen_agent, architect_output, design_tokens, blueprint.type
        )

    status.state = "deploying"
    status.progress = 0.8

    async with _make_agent(
        system_instructions=DEPLOYER_SYSTEM_PROMPT,
    ) as deployer_agent:
        deployment = await run_deployer(deployer_agent, widget_code, widget_id)

    return deployment
