# Magnitai product design doctrine

This document is the visual and interaction contract for Magnitai. It replaces the
older token narrative, which no longer matched the application or the two approved
landing sections.

## The idea: editorial utility

Magnitai should feel authored without making the product unfamiliar.

- Marketing may be asymmetric, oversized and surprising.
- Product screens must be calm, conventional and fast to scan.
- Decoration never stands in for product proof.
- A saturated colour must communicate a role, not fill an empty space.
- Every page gets one dominant idea and one dominant next action.

The `MADE TO BE / USED.` output showcase is the reference quality bar and is
preserved as-is. The landing hero has one additional responsibility: let a
visitor enter their real website without first navigating through another
screen.

## Evidence behind the system

The system is based on current product references and established usability
guidance rather than mood-board preference:

- Linear, Relume, Attio, Lovable and Typeform lead with a concise promise and put
  a real product interaction or product result directly beneath it.
- Linear's workflow is shown as a numbered sequence rather than a generic bento
  grid. Relume surrounds the promise with real artifacts, not feature icons.
- Framer's pricing preserves the expected buying model: recognisable plans,
  one highlighted recommendation, a detailed comparison and an FAQ.
- GOV.UK recommends mobile-first layout, restrained reading measures, consistent
  vertical rhythm and one clear question or decision at a time.
- USWDS recommends common chart forms, one central message, direct labels and a
  narrative or table alternative instead of interaction-only meaning.
- Carbon's empty states explain what will appear and provide a productive next
  step.
- WCAG 2.2 sets 4.5:1 body-text contrast, 3:1 graphical contrast and a 24px
  minimum target size. Magnitai uses 44px as the default interactive target.
- Baymard's form research shows perceived effort is driven more by visible fields
  than by the number of steps. Optional fields are disclosed only when relevant.

Reference links:

- https://www.w3.org/TR/WCAG22/
- https://design-system.service.gov.uk/styles/layout/
- https://design-system.service.gov.uk/patterns/question-pages/
- https://design-system.service.gov.uk/components/tabs/
- https://designsystem.digital.gov/components/data-visualizations/
- https://designsystem.digital.gov/components/table/
- https://carbondesignsystem.com/patterns/empty-states-pattern/
- https://carbondesignsystem.com/patterns/forms-pattern/
- https://carbondesignsystem.com/patterns/loading-pattern/
- https://m3.material.io/foundations/layout/canonical-examples/overview
- https://baymard.com/blog/checkout-flow-average-form-fields

## Colour

The product has three brand planes. Everything else is semantic.

| Plane | Token                               | Role                                                       |
| ----- | ----------------------------------- | ---------------------------------------------------------- |
| Paper | `--cream`, `--background`, `--card` | Calm reading and working surface                           |
| Ink   | `--ink`, `--inverse`                | Text, navigation, primary controls and dark stages         |
| Lime  | `--brand`, `--landing-cta`          | Forward motion, generated results and the recommended plan |

Hot red belongs only to the approved `USED.` marketing wordmark and destructive
or error semantics. Blue may appear inside a customer-generated widget preview,
but it is not part of the Magnitai application chrome or core marketing palette.

Rules:

1. Default buttons are ink. Lime is reserved for the single forward action or a
   generated result surface.
2. Do not place white text on lime. Use ink.
3. Do not use decorative colour gradients.
4. Success, warning and destructive colours always include text or an icon; colour
   is never the only signal.
5. Dark sections use the inverse neutral ramp, not hand-authored opacity values.

## Type

- Public-page display headlines use the editorial serif stack.
- Product, navigation and supporting marketing use Geist Variable.
- Code, steps, timestamps and compact metadata use Geist Mono.
- Display headings use approximately `-0.02em` to `-0.055em` tracking and a
  `0.9–1.05` line height.
- Body copy is 16–18px with `1.55–1.7` line height.
- Legal copy is 18px on desktop with a 65–75 character measure.
- Labels are sentence case. Uppercase mono is reserved for indices and metadata.

## Spacing and layout

Use the existing 4px spacing scale. Pages should read as a sequence of deliberate
blocks, not a field of equally weighted cards.

- Marketing measure: `max-w-6xl` with 24px mobile and 32px desktop gutters.
- Product measure: `max-w-[76rem]`.
- Reading measure: `max-w-[72ch]`.
- Legal measure: `max-w-[70ch]` plus an optional desktop contents rail.
- Section spacing: 80–112px desktop, 56–72px mobile.
- A border or surface change may group regions. Avoid stacking border + shadow +
  tint for the same grouping.
- Use cards only for movable, selectable or independently meaningful objects.
  Ordinary content belongs in sections, rows or tables.

## Marketing pages

Every supporting marketing page uses this order:

1. A precise promise and short explanation.
2. Real product proof or a working specimen.
3. A numbered explanation of how the outcome is produced.
4. Evidence: safeguards, numbers, comparisons or customer outcomes.
5. One final action.

Avoid:

- generic icon-and-copy bento grids;
- abstract mock dashboards with invented metrics;
- repeated pill labels and badges;
- three adjacent sections with identical card geometry;
- excessive rounded containers around plain text.

The landing hero is the product's only public URL entry:

- the website field and `See my directions` action are visible in the first
  viewport;
- validation happens before navigation and the accepted address is carried into
  the builder;
- the reassurance beside it states that previewing needs no account and nothing
  publishes automatically;
- later demonstrations link back to this journey rather than introducing
  another competing form.

### Examples

The examples page is a specimen lab, not a gallery of decorative cards. One large
interactive preview demonstrates the selected format. A structured comparison
below explains when to use each format.

### How it works

The process is a visible sequence. Each step contains the evidence Magnitai uses,
the decision it makes and the user-visible output. The system's self-healing is
shown as a before/change/repaired story.

### Pricing

Pricing follows buying conventions:

- three plans, with only Studio highlighted;
- monthly terms and limits visible without tooltips;
- a scannable comparison table with numeric values right-aligned;
- an FAQ for billing, ownership, hosting, cancellation and self-healing;
- no fake discounts or countdown urgency.

### Legal

Legal pages are reading tools:

- title, effective date and plain-language introduction;
- anchored contents at the top or in a desktop rail;
- numbered H2/H3 hierarchy;
- no ornamental cards, accordions or hidden clauses;
- persistent access to the other legal document and support.

## Product application

The workspace is deliberately more conventional than marketing.

### Frame

- A stable 16rem rail contains identity, primary navigation, creation and plan
  status.
- A 4rem top bar contains breadcrumb/context and account controls.
- The rail collapses to a sheet on smaller screens.
- Page actions live in one shared `PageHeader`, not repeated in cards.

### Overview

The overview answers three questions in order:

1. What changed?
2. Which tool needs attention?
3. What should I do next?

Use a restrained KPI row, one common chart with a written takeaway, and a sortable
tool list. Empty states explain the missing content and offer one productive action.

### Analytics

- Use bars or lines only when they represent a clear relationship over time.
- Direct-label data when possible; place any legend above or below the chart.
- State the reporting period and comparison period.
- Never hide essential values behind hover.
- Follow the chart with a table or written takeaway.

### Leads

Leads use a list-detail pattern: searchable/sortable list on the left or main
plane, contextual detail on the right. Opening a lead must not erase list position
or filter state.

### Tool detail

Overview, outcomes, embed and health are URL-addressable tabs with a heading inside
each panel. Tabs never wrap and are used only for quick switching between peer
views.

### Builder and checkout

- One clear decision block per stage.
- Show only fields necessary for the current decision.
- Labels remain visible above inputs; placeholders are examples, not labels.
- Mark optional fields explicitly and explain sensitive requests.
- Preserve entered data after validation errors.
- The summary and total remain visible before payment.
- Publish readiness is a checklist with explicit blockers, not a vague progress
  percentage.

The URL-first entry is a focused question page, not a marketing explainer:

- use a restrained two-thirds-width reading column rather than a split hero;
- show simple `Step 1 of 3` context instead of a full-width navigable stepper;
- autopilot is the single dominant action and uses the user's language,
  `Build for me`;
- guided control is a secondary action, `Build with me`, with one sentence
  explaining the difference;
- explain the real next steps in plain text below the decision;
- reassurance states what is read and that nothing publishes automatically;
- never use simulated websites, generated-tool mockups or decorative
  `source → signal → output` diagrams on an input screen.

Authentication is a familiar product utility, not a marketing composition:

- use one centered, single-column form with a clear page title;
- keep Google, email, password and the primary action in one reading direction;
- switch between sign-in and account creation with a text action below the form;
- show journey handoff context as a compact status message, never as a mock
  workspace or decorative preview;
- keep branding restrained to typography, colour, spacing and the shared
  navigation—do not place a second hero beside the login form.

Generation states continue the task instead of becoming a waiting-room
illustration:

- retain the same reading width, step context and background as the input state;
- use one labelled loading indicator and an `aria-live` status message;
- distinguish autopilot's one selected direction from guided mode's two
  recommendations in the copy;
- explain the real work in a restrained list without pretending to measure
  backend stages that are not measured;
- use skeletons only when they preserve the structure of the actual content that
  will replace them;
- never use fake devices, placeholder tool previews or a dark presentation panel
  as loading decoration.

## Interaction and accessibility

- Default target size: 44×44px.
- Focus rings are visible and never covered by sticky UI.
- Hover may enhance meaning but may not reveal essential meaning.
- Respect `prefers-reduced-motion`; no required interaction depends on animation.
- Page content reflows at 320 CSS pixels without horizontal scrolling.
- Toasts announce saved/error states; inline feedback remains near the control.
- Empty, loading, success and failure states are designed for every data surface.
- Icon-only buttons have accessible names and visible tooltips where discovery
  matters.

## Quality gate

A screen is not done until it passes all of these:

- one obvious purpose and one dominant next action;
- visual hierarchy still works in grayscale;
- no decorative card can be mistaken for an interactive object;
- all states exist: loading, empty, partial, error and success;
- keyboard order matches reading order;
- body text and controls meet WCAG 2.2 AA;
- 320px, 768px, 1280px and 1440px layouts are inspected;
- no approved landing section changed unintentionally;
- typecheck, unit tests and production build pass.
