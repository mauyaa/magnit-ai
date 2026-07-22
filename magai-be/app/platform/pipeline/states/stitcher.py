import json
import logging
import re

from app.platform.pipeline.schemas import ArchitectOutput, DesignTokens

logger = logging.getLogger(__name__)


STITCHER_SYSTEM_PROMPT = """You are a design token engineer who creates design systems that precisely match a parent site's visual language.

Given brand extraction data (colors, fonts, tone) and visual language analysis, generate CSS design tokens and component theme variables that make the generated app look like it was designed by the same team as the parent site.

COLOR SYSTEM:
- Primary: Main brand color for CTAs and key elements
- Secondary: Supporting color for secondary actions and borders
- Background: Main background (MUST match the parent site's background)
- Accent: Highlight color for emphasis and decorative elements
- Surface: Card and component backgrounds (MUST match the parent site's card style)
- Muted: Subtle backgrounds and borders

TYPOGRAPHY:
- Heading font: MUST be the actual font-family from the parent site's CSS
- Body font: MUST be the actual font-family from the parent site's CSS
- If the parent site uses system fonts, use system fonts
- If it uses Inter, use Inter. If it uses Poppins, use Poppins.

VISUAL EFFECTS — MATCH THE PARENT SITE:
- Shadows: Match the parent site's shadow depth (none → no shadows, dramatic → shadow-2xl)
- Borders: Match the parent site's border style (subtle/none/bold)
- Gradients: Only if the parent site uses gradients
- Glass effects: Only if the parent site uses glassmorphism

COMPONENT THEME — MATCH THE PARENT SITE'S COMPONENT STYLE:
- Buttons: Match the parent site's button style (gradient, solid, outline, ghost, pill)
- Inputs: Match the parent site's input style (clean borders, no borders, underlined)
- Cards: Match the parent site's card style (solid, glass, dark, borderless)
- Results: Bold typography matching the site's energy level

Return ONLY valid JSON matching this exact structure:
{
  "css_variables": {
    "--color-primary": "#hex",
    "--color-secondary": "#hex",
    "--color-background": "#hex",
    "--color-accent": "#hex",
    "--color-surface": "#hex",
    "--color-muted": "#hex",
    "--font-heading": "font name from parent site",
    "--font-body": "font name from parent site"
  },
  "component_theme": {
    "button_bg": "matching parent site button style",
    "button_text": "#ffffff",
    "button_hover_shadow": "matching shadow depth",
    "input_bg": "matching parent site input style",
    "input_border": "matching parent site border style",
    "input_focus_ring": "var(--color-primary)",
    "card_bg": "matching parent site card background",
    "card_shadow": "matching parent site shadow depth",
    "card_shadow_hover": "matching parent site shadow depth",
    "border_radius": "matching parent site border radius",
    "border_radius_lg": "larger variant",
    "spacing": "matching parent site spacing",
    "spacing_lg": "larger variant"
  }
}"""


async def run(agent, architect_output: ArchitectOutput) -> DesignTokens:
    logger.info("Stitcher: generating design tokens for brand")
    visual = architect_output.visual_language
    prompt = (
        f"Generate design tokens for a single-page app that matches the parent site's visual language.\n"
        f"Brand colors and fonts MUST come from the parent site's actual CSS.\n"
        f"\n"
        f"Parent site brand:\n"
        f"- Primary: {architect_output.brand.primary_color}\n"
        f"- Secondary: {architect_output.brand.secondary_color}\n"
        f"- Background: {architect_output.brand.background_color}\n"
        f"- Accent: {architect_output.brand.accent_color}\n"
        f"- Font heading: {architect_output.brand.font_headings}\n"
        f"- Font body: {architect_output.brand.font_body}\n"
        f"- Tone: {architect_output.brand.tone}\n"
        f"\n"
        f"Parent site visual language:\n"
        f"- Layout: {visual.layout}\n"
        f"- Spacing: {visual.spacing}\n"
        f"- Card style: {visual.card_style}\n"
        f"- Border radius: {visual.border_radius}\n"
        f"- Shadow depth: {visual.shadow_depth}\n"
        f"- Button style: {visual.button_style}\n"
        f"- Decorative elements: {visual.decorative_elements}\n"
        f"- Visual energy: {visual.visual_energy}\n"
        f"\n"
        f"CRITICAL: The background color MUST match the parent site. "
        f"The card background MUST match the parent site's card style. "
        f"The button style MUST match the parent site's button style.\n"
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
