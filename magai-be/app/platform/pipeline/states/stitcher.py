import logging

from app.platform.pipeline.schemas import ArchitectOutput, DesignTokens

logger = logging.getLogger(__name__)


STITCHER_SYSTEM_PROMPT = """You are a design token engineer connected to Google Stitch via MCP.

Given brand extraction data (colors, fonts, tone), use the Stitch MCP tools to:
1. Generate a complete set of CSS design tokens matching the brand.
2. Define component theme variables for a React+Tailwind widget.
3. Return the design tokens as structured DesignTokens output.

The tokens must make the generated widget visually consistent with the
user's existing website."""


async def run(agent, architect_output: ArchitectOutput) -> DesignTokens:
    logger.info("Stitcher: generating design assets for brand")
    prompt = (
        f"Generate design tokens for a widget with these brand parameters:\n"
        f"Primary: {architect_output.brand.primary_color}\n"
        f"Secondary: {architect_output.brand.secondary_color}\n"
        f"Background: {architect_output.brand.background_color}\n"
        f"Accent: {architect_output.brand.accent_color}\n"
        f"Font heading: {architect_output.brand.font_headings}\n"
        f"Font body: {architect_output.brand.font_body}\n"
        f"Tone: {architect_output.brand.tone}\n"
        f"Use the Stitch MCP tools to produce design tokens, "
        f"then return them as structured DesignTokens output."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    return DesignTokens(**data)
