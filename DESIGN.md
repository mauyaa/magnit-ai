# Design

## Visual Theme

Warm-precision tech. A deep, near-neutral ink canvas and one committed coral accent — not the
purple/blue "AI gradient" the logo itself uses. Violet appears only as a rare, deliberate accent tied
directly to the logo mark (never as a wash or gradient). Restrained color strategy: tinted neutrals +
one accent carrying emphasis, matching the "practice what it preaches" principle in PRODUCT.md.

## Color System (OKLCH)

| Token | Light | Dark | Role |
|---|---|---|---|
| `--background` | `oklch(0.985 0.006 45)` | `oklch(0.16 0.018 45)` | Canvas — warm-neutral, not blue-tinted, not cream |
| `--foreground` | `oklch(0.22 0.02 40)` | `oklch(0.97 0.006 45)` | Ink text |
| `--primary` | `oklch(0.56 0.19 35)` | `oklch(0.7 0.17 36)` | Coral accent — CTAs, links, active state, brand mark (L tuned so white button text clears 4.5:1 AA) |
| `--accent-violet` | `oklch(0.52 0.19 300)` | `oklch(0.62 0.17 300)` | Rare accent tied to logo mark only (never dominant) |
| `--success` | `oklch(0.68 0.15 155)` | `oklch(0.72 0.14 155)` | Healed / passing state (teal) |
| `--warning` | `oklch(0.76 0.16 85)` | `oklch(0.78 0.15 85)` | Amber — deliberately distinct hue from primary coral |
| `--destructive` | `oklch(0.58 0.22 25)` | `oklch(0.62 0.2 25)` | Broken / failing state (red, distinct from coral) |
| `--info` | `oklch(0.58 0.16 250)` | `oklch(0.68 0.15 250)` | Semantic info only — never used as primary UI color |

Neutrals (`--card`, `--muted`, `--border`, etc.) all tint toward hue 40-45 at low chroma (≤0.02),
replacing the previous blue-tinted (hue 248-255) neutral ramp.

`--success`/`--warning`/`--info` are tuned as vivid swatches for icons, chart series, and tinted
badge backgrounds — they do not clear 4.5:1 as plain text on `--background`. Where a status needs
to render as small readable text (not just an icon + tinted chip), hand-pick a darker shade of the
same hue, the way the existing "Live" badge already does (`#177e63` teal text, not raw `--success`).

## Typography

- Headings: Sora (existing), tight tracking (`-0.055em` to `-0.075em` display), `text-wrap: balance`.
- Body: Manrope (existing), 65-75ch measure.
- No gradient text (removed `.hero-gradient`). Emphasis via solid coral color or weight, never
  `background-clip: text` gradients.

## Layout

- Hero: centered, golden-ratio browser mockup (`0.618fr/1fr` — kept, it's a genuine
  differentiator).
- 3-step process: connected timeline (through-line + nodes), not an equal 3-card grid — the
  numbers are load-bearing (a real ordered sequence) so they stay; the container they sit in is no
  longer the generic "3 equal cards" scaffold.
- Diptych before/after repair section is the strongest asset on the page (maps directly to the
  RabinnFX "Diptych" principle) — kept and sharpened, not replaced.
- Section intros vary in device: not every section gets the same tracked-caps eyebrow. At most one
  deliberate kicker style survives per the anti-slop rule against repeating it as default scaffolding.

## Motion

- Ease-out cubic-bezier for entrances (`[0.16, 1, 0.3, 1]`, already in use — kept).
- Stagger 30-80ms between related items.
- Buttons: `active:scale-[0.97]` press feedback (Emil Kowalski component principle).
- `prefers-reduced-motion` fallback already global in styles.css — kept.

## Components

- Logo: new mark (`public/new-logo.jpg`, replaced asset), shown in a small rounded badge in
  Navigation and footer, unchanged container treatment.
- Buttons, cards, nav: existing shadcn/Radix component set kept as-is; only token values change,
  not component architecture (redesign-existing-projects rule: improve what's there, don't rewrite).
