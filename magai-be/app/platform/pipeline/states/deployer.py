import logging

from app.platform.pipeline.schemas import DeploymentResult, WidgetCode

logger = logging.getLogger(__name__)


DEPLOYER_SYSTEM_PROMPT = """You are a deployment engineer with access to Vercel APIs.

Given a complete React+Tailwind widget component:
1. Create a minimal deployment package (index.html with inlined React via CDN, or a Next.js page)
2. Call the Vercel deploy API to push it live
3. Return the production URL

The deployment must produce a publicly accessible URL that can be embedded in an iframe."""


async def run(agent, widget_code: WidgetCode, widget_id: str) -> DeploymentResult:
    logger.info("Deployer: pushing widget %s to Vercel", widget_id)
    prompt = (
        f"Deploy this React+Tailwind widget to Vercel:\n\n"
        f"{widget_code.source_code}\n\n"
        f"Widget ID: {widget_id}\n"
        f"Use the Vercel MCP or API tools to deploy and return the URL."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    return DeploymentResult(**data)
