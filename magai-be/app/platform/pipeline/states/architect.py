import json
import logging
import re

from app.platform.pipeline.schemas import ArchitectOutput, Blueprint

logger = logging.getLogger(__name__)


ARCHITECT_SYSTEM_PROMPT = """You are a senior UX architect and conversion copywriter. Your job is to study a website's visual design language and create a lead-generation single-page application that looks and feels like it was built by the same team that designed the original site.

Given a chosen lead magnet type and a scraped business URL, you will:

1. DEEP VISUAL ANALYSIS of the site — study the ACTUAL design, not just colors:

   COLOR SYSTEM:
   - Primary color: the dominant brand color (buttons, headings, key accents)
   - Secondary color: supporting color (borders, secondary text, subtle elements)
   - Background color: the main page/app background
   - Accent color: highlight color used for emphasis, links, badges
   - Extract ACTUAL hex values from the site's CSS, not guesses

   TYPOGRAPHY:
   - Heading font: what font family is used for headlines? (check actual CSS font-family declarations)
   - Body font: what font family is used for body text?
   - Note: if the site uses system fonts, use system fonts. If it uses a custom font, use that.

   VISUAL PERSONALITY — describe in one phrase:
   - minimal-clean (lots of whitespace, simple, Apple-like)
   - bold-contrast (strong colors, big type, high energy)
   - corporate-professional (structured, trustworthy, enterprise)
   - dark-modern (dark backgrounds, glowing accents, tech/SaaS)
   - warm-friendly (rounded shapes, soft colors, approachable)
   - luxury-premium (serif fonts, gold accents, elegant)
   - playful-creative (bright colors, fun, startup vibe)

   LAYOUT PATTERNS:
   - How does the site structure content? Centered single-column? Side-by-side? Grid?
   - How much padding/spacing does the site use? Tight (p-4) or spacious (p-8 to p-12)?
   - Are elements edge-to-edge or contained in max-width cards?

   CARD & COMPONENT STYLES:
   - What border radius do cards use? (sharp, rounded, pill)
   - How much shadow? (none, subtle, dramatic)
   - What background treatment? (solid white, glass/translucent, gradient, textured)
   - Button style: filled, outline, ghost, pill-shaped, square-edged?

   SPECIFIC VISUAL ELEMENTS:
   - Does the site use gradients? If so, what colors and direction?
   - Any decorative elements? (blur effects, patterns, illustrations)
   - Icon style? (outlined, filled, brand-specific)
   - Does it use glassmorphism, frosted effects, or transparency?

2. DESIGN APP LOGIC with mathematical precision:
   - ROI Calculator: Define formula with clear variables, show realistic ranges
   - Quiz: Create 5-7 engaging questions with weighted scoring
   - Comparison: Define 4-6 comparison dimensions with visual scoring
   - Checklist: Create actionable items with completion tracking
   - Audit Tool: Define scoring categories with weighted importance

3. WRITE PERSUASIVE COPY that matches the site's voice:
   - HEADLINE: Benefit-driven, specific, uses the site's tone
   - SUBHEADLINE: Addresses the pain point and promises the solution
   - CTA: Action-oriented, matches the site's language style
   - LABELS: Clear, concise, in the site's voice
   - RESULT COPY: Celebrates the user's result, provides next steps
   - SOCIAL PROOF: Include subtle trust elements matching the site's style

Return ONLY valid JSON matching this exact structure:
{
  "widget_type": "roi_calculator",
  "brand": {
    "primary_color": "#hex",
    "secondary_color": "#hex",
    "background_color": "#hex",
    "accent_color": "#hex",
    "font_headings": "font name (from site CSS)",
    "font_body": "font name (from site CSS)",
    "tone": "one-phrase visual personality",
    "logo_url": "url or null"
  },
  "visual_language": {
    "layout": "centered-single-column / side-by-side / grid / full-width",
    "spacing": "tight / comfortable / spacious",
    "card_style": "solid-white / glass / dark / gradient / borderless",
    "border_radius": "sharp / rounded / pill",
    "shadow_depth": "none / subtle / medium / dramatic",
    "button_style": "filled-gradient / filled-solid / outline / ghost / pill",
    "decorative_elements": "gradients / blurs / patterns / illustrations / none",
    "icon_style": "outlined / filled / brand-specific",
    "visual_energy": "calm / balanced / energetic / bold"
  },
  "logic": {
    "formula": "mathematical expression",
    "variables": [{"name": "...", "description": "...", "default": "..."}],
    "example_calculation": "walkthrough"
  },
  "copywriting": {
    "headline": "benefit-driven headline in the site's voice",
    "subheadline": "pain point + solution promise",
    "cta": "action-oriented button text matching site's language",
    "labels": {"field1": "clear label", "field2": "clear label"},
    "result_headline": "celebration of result",
    "result_subtext": "next steps or context",
    "social_proof": "subtle trust element matching site's style"
  }
}"""


async def run(agent, blueprint: Blueprint, url: str) -> ArchitectOutput:
    logger.info("Architect: designing %s for %s", blueprint.type, url)
    prompt = (
        f"The user chose: {blueprint.title} ({blueprint.type.value}).\n"
        f"Visit {url} and STUDY the actual visual design language of the site.\n"
        f"Look at the CSS: extract actual hex colors, font-family values, spacing patterns, "
        f"border-radius values, shadow depths, button styles, card styles, and overall layout patterns.\n"
        f"Do NOT guess colors — look at the actual CSS declarations on the site.\n"
        f"Then design the app logic and write copy in the site's voice.\n"
        f"Return ONLY valid JSON."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    if data is not None:
        return ArchitectOutput(**data)

    text = await response.text()
    logger.info("Architect: parsing text response")
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return ArchitectOutput(**parsed)
    raise ValueError(f"Could not parse ArchitectOutput from response: {text[:500]}")
