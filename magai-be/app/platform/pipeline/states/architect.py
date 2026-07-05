import json
import logging
import re

from app.platform.pipeline.schemas import ArchitectOutput, Blueprint

logger = logging.getLogger(__name__)


ARCHITECT_SYSTEM_PROMPT = """You are a senior UX architect and conversion copywriter.

Given a chosen lead magnet type and a scraped business URL, you will:
1. Extract the brand identity from the site: primary/secondary/accent colors, 
   font pairings, overall tone, logo.
2. Design the mathematical logic for the interactive widget.
   For an ROI calculator: define the formula with clear variables.
   For a quiz: define scoring logic and result tiers.
   For a comparison: define comparison dimensions and scoring.
3. Write the copy: headings, subheadings, CTAs, label text — match the brand tone.

Return ONLY valid JSON matching this exact structure:
{
  "widget_type": "roi_calculator",
  "brand": {
    "primary_color": "#hex",
    "secondary_color": "#hex",
    "background_color": "#hex",
    "accent_color": "#hex",
    "font_headings": "font name",
    "font_body": "font name",
    "tone": "professional/friendly/etc",
    "logo_url": "url or null"
  },
  "logic": {
    "formula": "mathematical expression",
    "variables": [{"name": "...", "description": "...", "default": "..."}],
    "example_calculation": "walkthrough"
  },
  "copywriting": {
    "headline": "...",
    "subheadline": "...",
    "cta": "...",
    "labels": {"field1": "...", "field2": "..."}
  }
}"""


async def run(agent, blueprint: Blueprint, url: str) -> ArchitectOutput:
    logger.info("Architect: designing %s for %s", blueprint.type, url)
    prompt = (
        f"The user chose: {blueprint.title} ({blueprint.type.value}).\n"
        f"They are at {url}. "
        f"Extract the brand identity from their site, design the widget logic, "
        f"and write the copy. Return ONLY valid JSON."
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
