from collections.abc import Callable

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy
from google.antigravity.types import McpStdioServer

from app.platform.config.settings import settings


def build_agent(
    system_instructions: str | None = None,
    tools: list[Callable] | None = None,
    mcp_servers: list[McpStdioServer] | None = None,
    response_schema=None,
) -> Agent:
    config = LocalAgentConfig(
        system_instructions=system_instructions or "",
        tools=tools or [],
        mcp_servers=mcp_servers or [],
        response_schema=response_schema,
        model=settings.agy_model,
        api_key=settings.gemini_api_key or None,
        policies=[policy.allow_all()],
    )
    return Agent(config)
