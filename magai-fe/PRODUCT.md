# Product

## Register

brand

## Users

Small-business owners and marketers (not developers) who want interactive tools — ROI calculators,
quizzes, audits — embedded on their website, plus the technical buyers/agencies evaluating Magnitai
on their behalf. Both audiences land on this page; when a decision is close, default toward the
non-technical reader: concrete, reassuring, not clever-for-cleverness's-sake.

## Product Purpose

Magnitai reads a business's brand from a URL, builds an on-brand interactive widget in minutes, and
then keeps it working — on a schedule, it re-checks the source site's brand and the widget's own
deployment, and repairs either automatically: re-syncing colors/fonts when the site rebrands,
redeploying when the live URL goes unreachable. (Each widget renders in a sandboxed iframe, so this
is deliberately scoped to brand drift and deployment health, not host-page DOM/layout changes, which
can't reach into the iframe in the first place.) The generation is table stakes; the differentiator
is the ongoing self-healing layer. Success is a visitor believing, within one scroll, that this
widget won't quietly go stale six weeks from now like everything else on their site has.

## Brand Personality

Precise, dependable, quietly alive. Confident without being cold; warm without being soft. The tone
is an engineer who explains things plainly to someone who isn't one — never condescending, never
hyping. Emotional goal: relief ("something on my site that just keeps working") plus a little delight
at how fast and tailored the output looks.

## Anti-references

- Generic purple-to-blue "AI product" gradient wash — the single most common tell in this category,
  and notably what Magnitai's own logo marks lean on, so the UI must deliberately not repeat it as a
  dominant surface color.
- Cold enterprise SaaS dashboards (heavy navy, dense chrome, intimidating to a non-technical owner).
- Generic startup cheerfulness (illustration-heavy, bouncy mascots, exclamation points).
- Templated "3 equal feature cards + eyebrow + gradient text" landing page scaffolding.

## Design Principles

1. Show the healing, don't just claim it — the before/after repair moment is the single most
   important piece of evidence on the page; every other section supports it.
2. One accent, used on purpose — color should mark meaning (the thing being fixed, the thing that's
   healthy), not decorate.
3. Warm precision over cold authority — engineering credibility expressed through restraint and
   real detail (real timings, real diffs), not through navy-and-chrome enterprise signaling.
4. Practice what it preaches — a page selling "brand-matched, self-healing interfaces" has to be
   the best-crafted, least-generic page in its own category.

## How Deployment Works

Every widget deploys to exactly one place: its own static project on Vercel's
global edge network, built from the generated React+Tailwind source with a real
Vite build (not a CDN-script/in-browser-transpile shortcut). The customer's embed
snippet is a plain `<iframe src="https://magai-widget-xxxxxxxx.vercel.app" ...>`
pointing directly at that Vercel URL — the same URL used for the live preview in
the widget's dashboard page, so what the customer previews is exactly what they
embed. SSO/auth protection is programmatically disabled on each project at deploy
time so the public iframe loads without a login wall.

Two distinct actions exist on a widget once it's live, and they do different
things:

- **Redeploy** — re-publishes the widget's last-built code to a fresh Vercel
  deployment. Use this if the live URL goes stale or unreachable; it does not
  regenerate anything.
- **Regenerate** — re-runs brand extraction and code generation from the source
  site and deploys the result. Use this if the source site's brand/copy has
  changed, or as part of the self-healing sweep described below.

## Accessibility & Inclusion

WCAG 2.1 AA minimum: body text ≥4.5:1 contrast, large/bold text ≥3:1, visible focus rings on every
interactive element, full `prefers-reduced-motion` fallback (already present in styles.css), no
color-only status indicators (pair color with icon/label, as the existing Live/healed/broken states
already do).
