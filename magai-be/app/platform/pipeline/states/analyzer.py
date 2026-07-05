import json
import logging
import re

from google.antigravity.types import CapabilitiesConfig, BuiltinTools

from app.platform.pipeline.schemas import Blueprint, BlueprintList

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a lead generation strategist and web analyst.

Your job:
1. Visit the given URL using the read_url_content tool.
2. Analyze the business: what they sell, their audience, pricing model, value prop.
3. Propose 3 interactive lead magnet widgets that would convert their audience.

Each blueprint must include:
- type: one of roi_calculator, readiness_quiz, competitive_comparison, audit_tool, interactive_checklist
- title: A compelling name for the widget
- description: What it does and how it works
- rationale: Why this specific type will convert for this specific business

Return ONLY valid JSON matching this structure, no other text:
{"blueprints": [{"type": "...", "title": "...", "description": "...", "rationale": "..."}]}"""


def analyzer_capabilities() -> CapabilitiesConfig:
    return CapabilitiesConfig(
        enabled_tools=[
            BuiltinTools.READ_URL_CONTENT,
        ]
    )


async def run(agent, url: str) -> BlueprintList:
    logger.info("Analyzer: scraping %s and proposing blueprints", url)
    prompt = (
        f"Visit {url} and analyze the business model, target audience, "
        f"and value proposition. Then propose 3 interactive lead magnet "
        f"widgets that would generate qualified leads for this business. "
        f"Return ONLY valid JSON."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    if data is not None:
        return BlueprintList(**data)

    text = await response.text()
    logger.info("Analyzer: parsing text response (structured_output unavailable)")
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return BlueprintList(**parsed)
    raise ValueError(f"Could not parse blueprints from response: {text[:500]}")
