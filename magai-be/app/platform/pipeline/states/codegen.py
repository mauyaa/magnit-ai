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


CODEGEN_SYSTEM_PROMPT = """You are a senior React + Tailwind CSS engineer who builds premium single-page applications for lead generation.

Your job: generate a complete React single-page application using Tailwind CSS v3 that looks and feels like it was designed by the SAME TEAM that built the parent site. The app must match the parent site's visual language — not look like a generic form.

CRITICAL: DO NOT generate a "widget" or "embedded component". Generate a FULL single-page application that fills the viewport and looks like a standalone page from the parent site.

VISUAL LANGUAGE — MATCH THE PARENT SITE:
The design_tokens and brand info describe the parent site's visual language. You MUST follow it:
- If card_style is "glass" → use backdrop-blur and bg-white/10
- If card_style is "dark" → use dark backgrounds with light text
- If card_style is "borderless" → no borders, rely on shadow and spacing
- If button_style is "pill" → use rounded-full
- If button_style is "outline" → use border-2 with transparent background
- If button_style is "filled-gradient" → use bg-gradient-to-r
- If border_radius is "sharp" → use rounded-none or rounded-sm
- If border_radius is "pill" → use rounded-full
- If shadow_depth is "dramatic" → use shadow-2xl
- If spacing is "spacious" → use p-8 to p-12, gap-6 to gap-8
- If visual_energy is "bold" → large type, strong colors, high contrast
- If visual_energy is "calm" → subtle colors, generous whitespace

LAYOUT:
- The app must fill the viewport: use min-h-screen
- Center content appropriately based on the layout pattern
- Use responsive design: w-full on mobile, max-w-* on desktop

TYPOGRAPHY — USE THE PARENT SITE'S FONTS:
- Import the heading font from Google Fonts in index.html (it's already configured)
- Use `font-[var(--font-heading)]` for headlines
- Use `font-[var(--font-body)]` for body text
- Headlines: text-3xl to text-5xl, font-bold, tracking-tight
- Body: text-base to text-lg, leading-relaxed

COLORS — USE CSS VARIABLES:
- Apply brand colors via CSS variables: bg-[var(--color-primary)], text-[var(--color-secondary)]
- Use semantic mapping: primary for CTAs, accent for highlights, muted for subtle elements
- Ensure readable contrast on all backgrounds
- Match the parent site's color usage patterns

INTERACTION & MOTION:
- Animated number counters for results (useState + useEffect)
- Smooth state transitions (transition-all duration-500)
- Hover effects matching the site's energy level
- Focus states with ring-2 ring-offset-2
- Progress indicators for multi-step flows

RESPONSIVE:
- Mobile-first: full-width on small screens
- Touch-friendly: min-h-[44px] on buttons
- Readable text at all breakpoints

APP TYPE PATTERNS:
- ROI Calculator: Animated result display with progress bars or charts
- Quiz: Step-by-step with progress indicator, animated transitions
- Comparison: Side-by-side cards with visual scoring
- Checklist: Interactive checkboxes with completion animations
- Audit Tool: Results dashboard with charts, scores, recommendations

RULES:
- Import React, useState, useEffect, useMemo from 'react'
- Import icons from 'lucide-react'
- Tailwind utility classes ONLY — NO inline styles, NO custom CSS
- Fully functional — handle all states: loading, empty, error, success
- Export default the main component
- NO TypeScript — plain .jsx only
- Name the main file src/App.jsx

Return ONLY valid JSON matching this exact structure:
{
  "files": [
    {
      "path": "src/App.jsx",
      "content": "import React, { useState } from 'react';\\nconst App = () => { ... };\\nexport default App;"
    }
  ],
  "entry_point": "src/App.jsx",
  "design_tokens": {
    "css_variables": {
      "--color-primary": "#hex",
      "--color-secondary": "#hex",
      "--color-background": "#hex",
      "--color-accent": "#hex",
      "--color-surface": "#hex",
      "--color-muted": "#hex",
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

Only generate the app component code — scaffolding files (package.json, vite.config, index.html, tailwind.config) are provided automatically."""


async def run(
    agent,
    architect_output: ArchitectOutput,
    design_tokens: DesignTokens,
    widget_type: WidgetType,
    feedback: str | None = None,
) -> WidgetCode:
    logger.info("Codegen: generating React+Tailwind component for %s", widget_type)
    
    copy = architect_output.copywriting
    copy_summary = ""
    if isinstance(copy, dict):
        copy_summary = "\n".join([f"- {k}: {v}" for k, v in copy.items() if v])
    else:
        copy_summary = str(copy)
    
    visual = architect_output.visual_language
    prompt = f"""Generate a {widget_type.value} single-page React+Tailwind application.

THIS APP MUST LOOK LIKE IT BELONGS ON THE PARENT SITE — match the visual language exactly.

DESIGN TOKENS:
{design_tokens.model_dump_json(indent=2)}

VISUAL LANGUAGE (from parent site):
- Layout: {visual.layout}
- Spacing: {visual.spacing}
- Card style: {visual.card_style}
- Border radius: {visual.border_radius}
- Shadow depth: {visual.shadow_depth}
- Button style: {visual.button_style}
- Decorative elements: {visual.decorative_elements}
- Icon style: {visual.icon_style}
- Visual energy: {visual.visual_energy}

WIDGET LOGIC:
{architect_output.logic.model_dump_json(indent=2)}

COPYWRITING:
{copy_summary}

BRAND INFO:
- Tone: {architect_output.brand.tone}
- Primary color: {architect_output.brand.primary_color}
- Secondary color: {architect_output.brand.secondary_color}
- Background color: {architect_output.brand.background_color}
- Accent color: {architect_output.brand.accent_color}
- Font headings: {architect_output.brand.font_headings}
- Font body: {architect_output.brand.font_body}

INSTRUCTIONS:
1. Follow the VISUAL LANGUAGE exactly — if card_style is "dark", use dark backgrounds
2. Use the design tokens CSS variables throughout (var(--color-primary), etc.)
3. Match the parent site's color usage patterns, not generic "premium" styling
4. Apply the brand tone in all copy
5. Include animations matching the visual_energy level
6. Use the copywriting fields for headlines, CTAs, and results
7. The app must be fully functional and handle all states
8. DO NOT generate a generic widget — generate an app that looks like the parent site

"""
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
