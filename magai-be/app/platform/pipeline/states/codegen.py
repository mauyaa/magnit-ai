import json
import logging
import re

from app.platform.pipeline.schemas import (
    ArchitectOutput,
    DesignTokens,
    ProjectFile,
    WidgetType,
    WidgetCode,
)

logger = logging.getLogger(__name__)


CODEGEN_SYSTEM_PROMPT = """You are a senior React + Tailwind CSS engineer.

Generate a complete React widget component using Tailwind CSS.
The widget will be part of a Vite + React project with Tailwind CSS v3.

Rules:
- Use standard ES module imports: `import React, { useState, useMemo } from 'react'`
- Import icons from 'lucide-react' as needed
- Use Tailwind utility classes only (no custom CSS files)
- The widget must be interactive and fully functional
- Handle all states: loading, empty, error, success
- The component must render inside an iframe without CSS bleeding
- Export default the main component
- NO TypeScript — plain .jsx only, no type annotations
- Name the main file src/App.jsx and export default

Return ONLY valid JSON matching this exact structure:
{
  "files": [
    {
      "path": "src/App.jsx",
      "content": "import React, { useState } from 'react';\\nconst Widget = () => { ... };\\nexport default Widget;"
    }
  ],
  "entry_point": "src/App.jsx",
  "design_tokens": {
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
      "card_shadow": "box-shadow value",
      "border_radius": "8px",
      "spacing": "16px"
    }
  }
}

Only generate the actual widget code — scaffolding files (package.json, vite.config, index.html, tailwind.config) will be provided automatically."""


async def run(
    agent,
    architect_output: ArchitectOutput,
    design_tokens: DesignTokens,
    widget_type: WidgetType,
    feedback: str | None = None,
) -> WidgetCode:
    logger.info("Codegen: generating React+Tailwind component for %s", widget_type)
    prompt = (
        f"Generate a {widget_type.value} React+Tailwind component.\n\n"
        f"Brand tokens: {design_tokens.model_dump_json()}\n"
        f"Widget logic: {architect_output.logic.model_dump_json()}\n"
        f"Copy: {architect_output.copywriting}\n\n"
    )
    if feedback:
        prompt += f"Previous attempt had these build errors. Fix them:\n{feedback}\n\n"
    prompt += "Return ONLY valid JSON."

    response = await agent.chat(prompt)
    data = await response.structured_output()
    if data is not None:
        return WidgetCode(**data)

    text = await response.text()
    logger.info("Codegen: parsing text response")
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return WidgetCode(**parsed)
    raise ValueError(f"Could not parse WidgetCode from response: {text[:500]}")
