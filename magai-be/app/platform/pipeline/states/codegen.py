import json
import logging
import re
from typing import Any

from app.platform.pipeline.schemas import (
    ArchitectOutput,
    DesignTokens,
    WidgetCode,
    WidgetType,
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
- These variables are defined for you in src/tokens.css from the design tokens
  below; every one listed there is guaranteed to exist at runtime
- Available: --color-primary, --color-secondary, --color-background,
  --color-accent, --color-surface, --color-muted, --font-heading, --font-body
- Use semantic mapping: primary for CTAs, accent for highlights, muted for subtle elements
- Ensure readable contrast on all backgrounds — WCAG AA (4.5:1) for body text
- Match the parent site's color usage patterns

INTERACTION & MOTION:
- Animated number counters for results (useState + useEffect)
- Transition specific properties, never `transition-all`: use transition-colors,
  transition-opacity, transition-transform. `transition-all` animates layout
  properties too and causes visible jank on mid-range phones.
- Hover effects matching the site's energy level
- Focus states with ring-2 ring-offset-2
- Progress indicators for multi-step flows

MOTION MUST BE OPTIONAL — THIS IS ENFORCED:
Some visitors get symptoms from motion, and their operating system already says
so. Every animation and transition you write MUST have a reduced-motion escape,
using Tailwind's `motion-reduce:` variant:

    <div className="transition-transform duration-500 motion-reduce:transition-none">
    <span className="animate-pulse motion-reduce:animate-none">

For an animated counter, skip the tween entirely and set the final value:

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) { setDisplayed(target); return; }   // no interval, land on the answer

A generated app that animates without a reduced-motion fallback is rejected and
regenerated, the same way a missing submitLead() is.

RESPONSIVE:
- Mobile-first: full-width on small screens
- Touch-friendly: min-h-[44px] on buttons
- Readable text at all breakpoints

APP TYPE PATTERNS (starting points, not a menu):
- ROI Calculator: Animated result display with progress bars or charts
- Quiz: Step-by-step with progress indicator, animated transitions
- Comparison: Side-by-side cards with visual scoring
- Checklist: Interactive checkboxes with completion animations
- Audit Tool: Results dashboard with charts, scores, recommendations
- Anything else: the app type may be "custom", meaning the customer described a
  tool that is none of the above — a pricing configurator, a symptom checker, an
  affordability estimator. Do not force it into the nearest pattern above. Build
  the shape the WIDGET LOGIC and DECISION SPEC describe, and borrow whichever of
  the interaction ideas above genuinely fit it.

THE TWO MOMENTS THAT DECIDE WHETHER THIS WORKS:
1. THE FIRST SCREEN. A visitor decides in about a second whether this is worth
   their time. Open with the question the tool answers for *them* — not with the
   company's name, not with instructions. One clear heading, one sentence of
   what they get, and the first input immediately visible without scrolling.
2. THE RESULT. This is the payoff and the reason they gave you anything. Lead
   with the number or verdict at display size, then what it means, then what to
   do about it. A result that is a paragraph of text has wasted the entire
   interaction.

LEAD CAPTURE — MANDATORY, THIS IS THE ENTIRE POINT OF THE APP:
The app MUST earn the visitor's email after delivering value, and it MUST submit
using the provided runtime SDK. Do not write your own fetch call.

    import { submitLead, isValidEmail } from './lib/magnitai.js';

    const [email, setEmail] = useState('');
    const [status, setStatus] = useState('idle');   // idle | sending | done | error
    const [error, setError] = useState(null);

    async function handleSubmit(event) {
      event.preventDefault();
      setStatus('sending');
      const result = await submitLead({
        email,
        name: name || undefined,     // if your app collects a name
        score: computedScore,        // the number/score your app produced
        answers: { ...inputs },      // the inputs the visitor supplied
      });
      if (result.ok) {
        setStatus('done');
      } else {
        setError(result.error);
        setStatus('error');
      }
    }

Requirements:
- A visible email input with a matching <label> and type="email"
- A submit button that is disabled while status === 'sending'
- Render result.error text when submission fails, and a confirmation when it succeeds
- Show the useful score/result title and short explanation before asking for email
- Gate only the detailed recommendation or next-step plan after successful capture
- submitLead() never throws; always branch on result.ok

A build that does not call submitLead() is rejected and regenerated.

MEASUREMENT - USE THE PROVIDED ACTIONS:
Import `trackStart`, `trackProgress`, `trackComplete`, `trackResult`, and
`trackCta` from `./lib/magnitai.js`. Call them only at real user milestones:
- trackStart() on the visitor's first answer, not on page load
- trackProgress(questionId) after each later answer
- trackComplete(resultKey) when all required inputs are complete
- trackResult(resultKey) when the result becomes visible
- trackCta() immediately before the result CTA is followed
The runtime handles impressions, visitor sessions, attribution, and iframe height.

TRUTH AND CALCULATION:
- The `DECISION SPEC` is authoritative. Render its exact questions and results.
- Import and call `calculateDecision(answers)` from `./lib/magnitai.js`; its
  returned value/result/qualified fields are authoritative.
- Do not reimplement the calculation or invent benchmarks, uplift, savings,
  percentages, scores, or customer evidence.
- Preserve answer ids and submit the full answer map through submitLead().
- Include `qualification_status` and `result_key` in lead.metadata.
- If the output is directional, label it "estimate" and explain its assumptions.

RULES:
- Import React, useState, useEffect, useMemo from 'react'
- Import icons from 'lucide-react'
- Tailwind utility classes ONLY — NO inline styles, NO custom CSS
- Fully functional — handle all states: loading, empty, error, success
- Export default the main component
- NO TypeScript — plain .jsx only
- Name the main file src/App.jsx
- You may add extra components under src/ (e.g. src/ResultCard.jsx) and import them
- Do NOT create or overwrite: index.html, src/main.jsx, src/index.css,
  src/tokens.css, src/config.js, src/lib/magnitai.js — these are provided

ACCESSIBILITY — WCAG 2.1 AA, NOT A CHECKLIST AT THE END:
- Label every input with a real <label htmlFor>. A placeholder is not a label:
  it disappears the moment someone types, taking the question with it.
- One <h1>, then headings in order. Never skip a level to get a font size.
- The result appears without a page load, so a screen-reader user is never told
  it arrived. Put it in a container with aria-live="polite" so it is announced.
- In a multi-step flow, move focus to the new step's heading when the step
  changes (tabIndex={-1} + ref.focus()), or keyboard users are dropped back at
  the top of the document on every question.
- Every control reachable and operable by keyboard, in a sensible tab order.
  If you build a custom option button, it is a real <button>, not a <div>.
- Body text at 4.5:1 against its own background, large text at 3:1. The brand
  colours are given to you — if the accent is too light to carry the label on
  it, put the label on the dark colour instead of shipping it unreadable.
- Never signal state with colour alone: pair it with an icon, or a word.
- Buttons have a visible focus ring, and hit areas are at least 44x44px.
- Respect prefers-reduced-motion, as specified above.

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
    agent: Any,
    architect_output: ArchitectOutput,
    design_tokens: DesignTokens,
    widget_type: WidgetType,
    widget_title: str | None = None,
    feedback: str | None = None,
) -> WidgetCode:
    logger.info("Codegen: generating React+Tailwind component for %s", widget_type)

    copy = architect_output.copywriting
    copy_summary = ""
    if isinstance(copy, dict):
        copy_summary = "\n".join([f"- {k}: {v}" for k, v in copy.items() if v])
    else:
        copy_summary = str(copy)

    # Name the tool, don't just classify it.
    #
    # The opening line used to be the bare type — "Generate a roi_calculator
    # …" — which is the least specific thing known about the app by this point.
    # For a CUSTOM tool it degrades to "Generate a custom …", which says
    # nothing at all. The title is what the customer approved, so it leads; the
    # type follows as a hint where one exists, and for custom the structure is
    # carried entirely by the logic and decision spec below, which is where it
    # has really lived all along.
    title = (widget_title or "").strip()
    if widget_type is WidgetType.CUSTOM:
        opening = (
            f'Generate a single-page React+Tailwind application: "{title or "a bespoke tool"}".\n'
            "It does not belong to a named category — build exactly the shape described by "
            "WIDGET LOGIC and DECISION SPEC below."
        )
    elif title:
        opening = (
            f'Generate a {widget_type.value} single-page React+Tailwind application: "{title}".'
        )
    else:
        opening = f"Generate a {widget_type.value} single-page React+Tailwind application."

    visual = architect_output.visual_language
    prompt = f"""{opening}

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

DECISION SPEC:
{architect_output.decision.model_dump_json(indent=2) if architect_output.decision else "No structured decision spec was produced; use WIDGET LOGIC without adding claims."}

GROUNDED CLAIMS:
{json.dumps([claim.model_dump(mode="json") for claim in architect_output.claims], indent=2)}

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
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return WidgetCode(**parsed)
    raise ValueError(f"Could not parse WidgetCode from response: {text[:500]}")
