"""Deterministic scaffolding for a generated widget.

Everything in this module is authored by us, not by the model. That split is the
point: the model designs the *interface*, while lead capture, brand tokens, and
telemetry are hand-written and injected. Previously both were left to the prompt,
with two consequences that made the product structurally broken:

* Nothing told the generated app to submit a lead, and it had no widget id or API
  URL to submit to — so ``leads_count`` could only ever be zero.
* The Stitcher's ``css_variables`` were described in the prompt but never written
  into a ``:root`` block, so every ``var(--color-primary)`` reference resolved to
  nothing and branded elements rendered uncoloured.

Both are now generated from data rather than requested from a model.
"""

from __future__ import annotations

import json
import re

from app.platform.pipeline.schemas import DesignTokens

# Fonts the scaffold can request from Google Fonts. A brand font outside this set
# is still emitted as a CSS variable and will resolve if the visitor has it;
# otherwise the stack falls back to a sane system family.
_FONT_FALLBACKS = {
    "heading": "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
    "body": "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
}

_SAFE_FONT_NAME = re.compile(r"^[A-Za-z0-9 ]{2,40}$")
# Blocks CSS injection through a token value: no braces, semicolons, or comments.
_UNSAFE_CSS_VALUE = re.compile(r"[{};<>]|/\*|\*/|@import|expression\s*\(", re.IGNORECASE)


def _sanitize_css_value(value: str) -> str | None:
    """Return a CSS-safe token value, or ``None`` if it must be dropped.

    Token values originate from a model, so they are untrusted input that ends up
    inside a stylesheet. Anything that could terminate the declaration and inject
    new rules is rejected rather than escaped.
    """
    candidate = str(value).strip()
    if not candidate or len(candidate) > 200:
        return None
    if _UNSAFE_CSS_VALUE.search(candidate):
        return None
    return candidate


def _quote_font_stack(name: str, role: str) -> str:
    """Build a CSS font stack from a font name, always with a fallback."""
    fallback = _FONT_FALLBACKS[role]
    clean = str(name or "").strip().strip("\"'")
    if not clean or not _SAFE_FONT_NAME.match(clean):
        return fallback
    return f"'{clean}', {fallback}"


def google_fonts_href(css_variables: dict[str, str]) -> str | None:
    """Google Fonts URL for the brand's actual fonts, or ``None``.

    The scaffold used to hardcode four unrelated families, so any other brand font
    silently fell back. This requests what the brand actually uses.
    """
    families = []
    for key in ("--font-heading", "--font-body"):
        raw = str(css_variables.get(key, "")).strip().strip("\"'")
        if raw and _SAFE_FONT_NAME.match(raw) and raw not in families:
            families.append(raw)

    if not families:
        return None

    query = "&".join(f"family={f.replace(' ', '+')}:wght@300;400;500;600;700;800" for f in families)
    return f"https://fonts.googleapis.com/css2?{query}&display=swap"


def render_tokens_css(design_tokens: DesignTokens) -> str:
    """Render the design tokens as a real ``:root`` block.

    Also maps the component theme onto the variable names the base stylesheet
    already references (``--button-bg``, ``--input-border``, …) so those component
    classes are themed instead of using their hardcoded blue defaults.
    """
    lines: list[str] = [
        "/* Generated from the widget's design tokens. Do not edit by hand. */",
        ":root {",
    ]

    declared: set[str] = set()
    for name, value in (design_tokens.css_variables or {}).items():
        key = str(name).strip()
        if not key.startswith("--"):
            key = f"--{key.lstrip('-')}"
        safe = _sanitize_css_value(value)
        if safe is None:
            continue

        if key == "--font-heading":
            safe = _quote_font_stack(safe, "heading")
        elif key == "--font-body":
            safe = _quote_font_stack(safe, "body")

        lines.append(f"  {key}: {safe};")
        declared.add(key)

    # Component-theme values the base stylesheet consumes.
    theme = design_tokens.component_theme or {}
    for theme_key, css_var in (
        ("button_bg", "--button-bg"),
        ("button_text", "--button-text"),
        ("input_border", "--input-border"),
        ("card_bg", "--card-bg"),
        ("card_shadow", "--card-shadow"),
        ("border_radius", "--radius"),
        ("spacing", "--spacing"),
    ):
        if css_var in declared:
            continue
        safe = _sanitize_css_value(theme.get(theme_key, ""))
        if safe is not None:
            lines.append(f"  {css_var}: {safe};")
            declared.add(css_var)

    # Guarantee the variables the scaffold and prompt rely on always exist, so a
    # missing token degrades to a readable default instead of an invalid value.
    for css_var, default in (
        ("--color-primary", "#2563eb"),
        ("--color-secondary", "#1e293b"),
        ("--color-background", "#ffffff"),
        ("--color-accent", "#7c3aed"),
        ("--color-surface", "#ffffff"),
        ("--color-muted", "#64748b"),
        ("--font-heading", _FONT_FALLBACKS["heading"]),
        ("--font-body", _FONT_FALLBACKS["body"]),
    ):
        if css_var not in declared:
            lines.append(f"  {css_var}: {default};")

    lines.append("}")
    lines.append("")
    lines.append("body {")
    lines.append("  background: var(--color-background);")
    lines.append("  color: var(--color-secondary);")
    lines.append("  font-family: var(--font-body);")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def render_runtime_config(
    widget_id: str,
    api_base_url: str,
    decision_spec: dict | None = None,
    outcomes: dict | None = None,
) -> str:
    """Emit the widget's identity and its baked configuration as an importable module.

    Injected at build time rather than read from an env var so the deployed static
    bundle is self-contained and cannot be pointed at the wrong backend.

    The decision spec and outcome copy are baked in as well as fetched at runtime
    (see the SDK below). That redundancy is deliberate: the bundle has to render a
    complete, correct tool with no network at all, because it is sitting on a
    customer's page and an API blip must not turn their lead magnet into a blank
    rectangle.
    """
    payload = json.dumps(
        {
            "widgetId": widget_id,
            "apiBaseUrl": api_base_url.rstrip("/"),
            "decisionSpec": decision_spec,
            "outcomes": outcomes,
        },
        indent=2,
    )
    return (
        "// Generated at build time. Do not edit by hand.\n"
        f"export const MAGNITAI_CONFIG = {payload};\n"
    )


# The runtime SDK. Hand-written so lead capture is never a function of prompt
# adherence — the model only decides when to call it and what the form looks like.
RUNTIME_SDK_JS = """// Magnitai widget runtime. Hand-written and injected at build time.
// The generated UI must call submitLead() to capture a lead; do not re-implement
// the network call in generated code.
import { useSyncExternalStore } from 'react';
import { MAGNITAI_CONFIG } from '../config.js';

const { widgetId, apiBaseUrl } = MAGNITAI_CONFIG;
const sessionKey = `magnit:${widgetId}:session`;

/**
 * The configuration actually in force.
 *
 * Starts as what was baked in at build time, so the widget is complete and
 * correct before any network call, then is replaced by the owner's current
 * version once the overlay resolves. This is what lets someone rename a score
 * band or change where the final button points and see it live in seconds,
 * instead of waiting for a rebuild and redeploy of the whole bundle.
 *
 * Mutable module state rather than a React context because the generated UI is
 * model-authored: it cannot be relied on to thread a provider through, but it
 * does call calculateDecision() at the moment the visitor finishes — by which
 * time this has long since resolved.
 */
let live = {
  decisionSpec: MAGNITAI_CONFIG.decisionSpec,
  outcomes: MAGNITAI_CONFIG.outcomes,
  consentText: null,
  ctaUrl: null,
  acceptingLeads: true,
};

const configListeners = new Set();

/** Subscribe to overlay updates. Returns an unsubscribe function. */
export function onConfigChange(listener) {
  configListeners.add(listener);
  return () => configListeners.delete(listener);
}

export const getDecisionSpec = () => live.decisionSpec;
export const getOutcomes = () => live.outcomes;
export const isAcceptingLeads = () => live.acceptingLeads !== false;
export const getLiveConfig = () => live;

/**
 * The configuration, as a React value that updates itself.
 *
 * This is the hook every generated app must render from, and it is the entire
 * reason the product can promise that editing a question is live. `live` is
 * replaced once the overlay resolves; a component that read it during its first
 * render and kept the value would show the questions as they were when the tool
 * was last built, while calculateDecision() scored the visitor against the
 * owner's current ones — the two silently disagreeing is worse than either.
 *
 * useSyncExternalStore rather than useState + useEffect: the store is module
 * state that can change before a component mounts, and this is the one hook
 * that reads it without tearing.
 */
export function useLiveConfig() {
  return useSyncExternalStore(onConfigChange, getLiveConfig, getLiveConfig);
}

async function loadRuntimeConfig() {
  try {
    const response = await fetch(`${apiBaseUrl}/api/widgets/${widgetId}/runtime-config`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) return;
    const payload = await response.json();
    // A new object every time: useSyncExternalStore compares by identity, so
    // mutating the existing one would leave every subscriber on stale copy.
    live = {
      decisionSpec: payload.decision || live.decisionSpec,
      outcomes: payload.outcomes || live.outcomes,
      consentText: payload.consent_text ?? null,
      ctaUrl: payload.cta_url ?? null,
      acceptingLeads: payload.accepting_leads !== false,
    };
    for (const listener of configListeners) {
      try {
        listener(live);
      } catch {
        // One misbehaving listener must not stop the others.
      }
    }
  } catch {
    // Offline, blocked, or the API is down. The baked configuration stands and
    // the visitor sees a working tool either way.
  }
}

function createSessionId() {
  try {
    const existing = sessionStorage.getItem(sessionKey);
    if (existing) return existing;
    const value = crypto.randomUUID
      ? crypto.randomUUID()
      : [
          Date.now(),
          Math.random().toString(36).slice(2),
          Math.random().toString(36).slice(2),
        ].join("-");
    sessionStorage.setItem(sessionKey, value);
    return value;
  } catch {
    return [
      Date.now(),
      Math.random().toString(36).slice(2),
      Math.random().toString(36).slice(2),
    ].join("-");
  }
}

const sessionId = createSessionId();

function inputScore(question, answer) {
  if (question.input_type === 'boolean') return answer ? question.true_score : 0;
  if (question.input_type === 'single_choice') {
    const index = question.options.indexOf(String(answer));
    if (index < 0) return 0;
    return question.option_scores[index] ??
      (index / Math.max(1, question.options.length - 1)) * 100;
  }
  const value = Number(answer);
  if (!Number.isFinite(value)) return 0;
  if (question.minimum != null && question.maximum != null) {
    return ((value - question.minimum) / (question.maximum - question.minimum)) * 100;
  }
  return value;
}

/**
 * Deterministic renderer contract. Generated code never evaluates a formula.
 *
 * Reads the live spec rather than the baked one so an owner's edit to the
 * questions or the score bands is reflected the moment a visitor finishes.
 */
export function calculateDecision(answers) {
  const decisionSpec = live.decisionSpec;
  if (!decisionSpec) return { value: 0, result: null, qualified: false };
  const calculation = decisionSpec.calculation;
  let value = calculation.constant || 0;
  if (calculation.kind === 'weighted_score') {
    let totalWeight = 0;
    value = 0;
    for (const question of decisionSpec.questions) {
      if (answers?.[question.id] === undefined) continue;
      value += inputScore(question, answers[question.id]) * question.weight;
      totalWeight += question.weight;
    }
    value = totalWeight ? value / totalWeight : 0;
  } else {
    for (const term of calculation.terms) {
      const question = decisionSpec.questions.find((item) => item.id === term.question_id);
      const answer = answers?.[term.question_id];
      if (!question || answer === undefined) continue;
      const raw = question.input_type === 'number' ? Number(answer) : inputScore(question, answer);
      value += (Number.isFinite(raw) ? raw : 0) * term.multiplier;
    }
  }
  if (calculation.clamp_min != null) value = Math.max(calculation.clamp_min, value);
  if (calculation.clamp_max != null) value = Math.min(calculation.clamp_max, value);
  const result = decisionSpec.results.find((item) =>
    (item.minimum_score == null || value >= item.minimum_score) &&
    (item.maximum_score == null || value <= item.maximum_score)
  ) || decisionSpec.results[0] || null;
  return {
    value,
    result,
    // The owner-configured band for this score, when one has been set up. Carries
    // the label, colour and advice the result screen should actually show, which
    // the model-authored `result` above does not know about.
    band: bandFor(value),
    advice: adviceFor(value),
    qualified: value >= decisionSpec.qualification_threshold,
    spec: decisionSpec,
  };
}

/** The configured score band a value falls in, or null if none are configured. */
export function bandFor(value) {
  const bands = live.outcomes?.bands;
  if (!Array.isArray(bands) || bands.length === 0) return null;
  const ordered = [...bands].sort((a, b) => a.minimum_score - b.minimum_score);
  const match = ordered.find(
    (band) => value >= band.minimum_score && value <= band.maximum_score
  );
  if (match) return match;
  // Bands are validated server-side to cover 0-100 without gaps, but a
  // calculation with its own clamp can still overshoot. Clamping to the nearest
  // band beats showing a result screen with no result on it.
  return value > ordered[ordered.length - 1].maximum_score
    ? ordered[ordered.length - 1]
    : ordered[0];
}

/** Advice lines for a score: the band's own, plus anything shown to everyone. */
export function adviceFor(value) {
  const advice = live.outcomes?.advice;
  if (!Array.isArray(advice)) return [];
  const band = bandFor(value);
  return advice
    .filter((item) => !item.band_key || (band && item.band_key === band.key))
    .map((item) => item.text);
}

function attribution() {
  if (typeof location === 'undefined') return {};
  const query = new URLSearchParams(location.search);
  return Object.fromEntries(
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content']
      .map((key) => [key, query.get(key)])
      .filter(([, value]) => value)
  );
}

async function sendInteraction(event, details = {}) {
  try {
    await fetch(`${apiBaseUrl}/api/widgets/${widgetId}/interactions`, {
      method: 'POST',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event,
        session_id: sessionId,
        source_url: typeof document !== 'undefined' ? document.referrer || null : null,
        attribution: attribution(),
        ...details,
      }),
    });
  } catch {
    // Analytics never interrupts the visitor.
  }
}

export const trackStart = () => sendInteraction('started', { step: 'started' });
export const trackProgress = (step) =>
  sendInteraction('progressed', { step: String(step || 'in_progress').slice(0, 100) });
export const trackComplete = (resultKey) =>
  sendInteraction('completed', {
    step: 'completed',
    result_key: resultKey ? String(resultKey).slice(0, 100) : null,
  });
export const trackResult = (resultKey) =>
  sendInteraction('result_viewed', {
    step: 'result',
    result_key: resultKey ? String(resultKey).slice(0, 100) : null,
  });
export const trackCta = () => sendInteraction('cta_clicked', { step: 'cta' });

/** Truthy for a syntactically plausible email. Server-side is authoritative. */
export function isValidEmail(value) {
  return typeof value === 'string' && /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(value.trim());
}

/**
 * Submit a captured lead.
 *
 * Resolves to { ok: true } or { ok: false, error } — it never throws, so a
 * network failure cannot blank the widget mid-interaction.
 *
 * @param {{email: string, name?: string, score?: number, answers?: object}} lead
 */
export async function submitLead(lead) {
  if (!isValidEmail(lead?.email)) {
    return { ok: false, error: 'Please enter a valid email address.' };
  }

  try {
    const response = await fetch(`${apiBaseUrl}/api/leads/${widgetId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: String(lead.email).trim(),
        name: lead.name ? String(lead.name).trim() : null,
        score: typeof lead.score === 'number' ? Math.round(lead.score) : null,
        answers: lead.answers ?? null,
        metadata: {
          ...(lead.metadata || {}),
          magnit_session_id: sessionId,
          // Referrer identifies which host page the widget is embedded on.
          referrer: typeof document !== 'undefined' ? document.referrer || null : null,
          submitted_at: new Date().toISOString(),
        },
      }),
    });

    if (response.ok) return { ok: true };

    if (response.status === 409) {
      return { ok: false, error: 'This form is no longer accepting responses.' };
    }
    if (response.status === 429) {
      return { ok: false, error: 'Too many submissions right now. Please try again shortly.' };
    }
    return { ok: false, error: 'We could not save your details. Please try again.' };
  } catch {
    return { ok: false, error: 'Network error. Please check your connection and try again.' };
  }
}

/**
 * Record one view, so submissions have a denominator and conversion rate is real.
 * Fire-and-forget: failure is silent and never blocks rendering. Sent once per
 * page load, guarded so React StrictMode's double-invoke does not double-count.
 */
let impressionSent = false;

export function trackImpression() {
  if (impressionSent || typeof fetch === 'undefined') return;
  impressionSent = true;

  const url = `${apiBaseUrl}/api/widgets/${widgetId}/impression`;
  try {
    // The host page's address travels with the view. It is what proves the
    // snippet is actually on a customer's site — a visitor who scrolls past
    // without touching anything still counts as installed — and it is what
    // keeps the owner's own preview screens out of their numbers.
    fetch(url, {
      method: 'POST',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_url:
          typeof document !== 'undefined' ? document.referrer || null : null,
      }),
    }).catch(() => {});
  } catch {
    // Never surface telemetry failures to a visitor.
  }
}

function reportHeight() {
  if (typeof window === 'undefined' || window.parent === window) return;
  const height = Math.max(
    document.documentElement?.scrollHeight || 0,
    document.body?.scrollHeight || 0,
  );
  window.parent.postMessage({ type: 'magnit:resize', height }, '*');
}

if (typeof window !== 'undefined') {
  trackImpression();
  // Kicked off immediately, not awaited: the widget renders from its baked
  // configuration straight away and adopts the owner's current version as soon
  // as it arrives, which is always well before a visitor has answered anything.
  void loadRuntimeConfig();
  window.addEventListener('load', reportHeight);
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(reportHeight).observe(document.documentElement);
  }
}
"""

# Appended to the base stylesheet: styling for the lead form the SDK expects, so
# the capture step looks intentional even if the model styles it minimally.
LEAD_FORM_CSS = """
@layer components {
  .magnitai-lead-form {
    @apply flex w-full flex-col gap-3 sm:flex-row;
  }

  .magnitai-lead-error {
    @apply mt-2 text-sm font-semibold;
    color: #dc2626;
  }

  .magnitai-lead-success {
    @apply mt-2 text-sm font-semibold;
    color: #059669;
  }
}
"""
