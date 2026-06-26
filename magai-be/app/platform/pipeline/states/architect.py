import logging

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
4. Return all of this as a structured ArchitectOutput."""


async def run(agent, blueprint: Blueprint, url: str) -> ArchitectOutput:
    logger.info("Architect: designing %s for %s", blueprint.type, url)
    prompt = (
        f"The user chose: {blueprint.title} ({blueprint.type.value}).\n"
        f"They are at {url}. "
        f"Extract the brand identity from their site, design the widget logic, "
        f"and write the copy. Return structured output matching ArchitectOutput."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    return ArchitectOutput(**data)
