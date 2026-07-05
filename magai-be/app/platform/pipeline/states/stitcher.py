import json
import logging
import re

from app.platform.pipeline.schemas import ArchitectOutput, DesignTokens

logger = logging.getLogger(__name__)


STITCHER_SYSTEM_PROMPT = """You are a design token engineer connected to Google Stitch via MCP.

Given brand extraction data (colors, fonts, tone), use the Stitch MCP tools to:
1. Generate a complete set of CSS design tokens matching the brand.
2. Define component theme variables for a React+Tailwind widget.

The tokens must make the generated widget visually consistent with the
user's existing website.

Return ONLY valid JSON matching this exact structure:
{
  "css_variables": {
    "--color-primary": "#hex",
    "--color-secondary": "#hex",
    "--color-background": "#hex",
    "--color-accent": "#hex",
    "--font-heading": "font name",
    "--font-body": "font name"
  },
  "component_theme": {
    "button_bg": "var(--color-primary)",
    "button_text": "#ffffff",
    "input_border": "var(--color-secondary)",
    "card_bg": "#ffffff",
    "card_shadow": "0 2px 8px rgba(0,0,0,0.1)",
    "border_radius": "8px",
    "spacing": "16px"
  }
}"""


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
        f"Return ONLY valid JSON."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    if data is not None:
        return DesignTokens(**data)

    text = await response.text()
    logger.info("Stitcher: parsing text response")
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return DesignTokens(**parsed)
    raise ValueError(f"Could not parse DesignTokens from response: {text[:500]}")
