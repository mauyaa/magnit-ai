import logging

from app.platform.pipeline.schemas import (
    ArchitectOutput,
    DesignTokens,
    WidgetType,
    WidgetCode,
)

logger = logging.getLogger(__name__)


CODEGEN_SYSTEM_PROMPT = """You are a senior React + Tailwind CSS engineer.

Given design tokens, widget logic, and copy, generate a complete,
self-contained React functional component using Tailwind CSS.

Requirements:
- Single .tsx file, no external imports beyond React
- Use Tailwind utility classes, not custom CSS
- Inline the design tokens as CSS variables in a <style> tag
- The component must be interactive and functional
- Handle all states: loading, empty, error, success
- Use proper TypeScript types for all props and state
- The component must render inside an iframe without CSS bleeding
- Wrap in a root div with class matching the widget container

Return the complete source code."""


async def run(
    agent,
    architect_output: ArchitectOutput,
    design_tokens: DesignTokens,
    widget_type: WidgetType,
) -> WidgetCode:
    logger.info("Codegen: generating React+Tailwind component for %s", widget_type)
    prompt = (
        f"Generate a {widget_type.value} React+Tailwind component.\n\n"
        f"Brand tokens: {design_tokens.model_dump_json()}\n"
        f"Widget logic: {architect_output.logic.model_dump_json()}\n"
        f"Copy: {architect_output.copywriting}\n\n"
        f"Return the complete source code and design tokens as WidgetCode."
    )
    response = await agent.chat(prompt)
    data = await response.structured_output()
    return WidgetCode(**data)
