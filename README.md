# MagnetAI

Turn a business website into an interactive lead-capture widget. Enter a URL, pick
one of three AI-proposed widget ideas, review and adjust the extracted brand, and
get an embeddable calculator, quiz, or audit tool deployed to its own URL.

The differentiator is what happens afterwards: MagnetAI re-checks each live widget
on a schedule and repairs it automatically when the source site rebrands or the
deployment goes unreachable.

---

## Contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Self-healing](#self-healing)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Testing](#testing)
- [Further reading](#further-reading)

---

## Quick start

The fastest path is Docker Compose, which brings up Postgres, Redis, the API, the
Celery worker, the scheduler, and the frontend together.

```bash
cp magai-be/.env.example magai-be/.env
```

Fill in at minimum `MAGAI_GEMINI_API_KEY` and `MAGAI_VERCEL_API_TOKEN` (without
them, analysis and deployment cannot run), then:

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs (non-production only): http://localhost:8000/docs

Migrations run automatically before the API and workers start. Create an account
at http://localhost:3000/login and build your first widget.

---

## How it works

```
                        ┌──────────────┐
                        │   magai-fe   │  TanStack Start (React 19, pnpm)
                        │  Marketing + │
                        │   Dashboard  │
                        └──────┬───────┘
                               │ HTTPS + Bearer JWT
                        ┌──────▼───────┐
                        │   magai-be   │  FastAPI (Python 3.13, uv)
                        │              │
                        │  features/   │  auth, users, widgets, leads,
                        │              │  billing, payments, integrations
                        │  platform/   │  db, security, http, observability
                        │   pipeline/  │  ← 4-stage generation engine
                        └──┬────────┬──┘
                           │        │
              ┌────────────┘        └──────────────┐
      ┌───────▼────────┐                  ┌────────▼────────┐
      │  Postgres      │                  │  Redis          │
      │  tenant data   │                  │  queue, events, │
      │                │                  │  locks, limits  │
      └────────────────┘                  └────────┬────────┘
                                                   │
                                        ┌──────────▼──────────┐
                                        │  Celery worker      │  builds
                                        │  Celery beat        │  heal sweep
                                        └──────────┬──────────┘
                                                   │
                                 ┌─────────────────┴─────────────────┐
                            ┌────▼─────┐                      ┌──────▼─────┐
                            │  Gemini  │                      │   Vercel   │
                            │  (AGY)   │                      │  (deploy)  │
                            └──────────┘                      └────────────┘
```

### The generation pipeline

| Stage | What it does | Output |
|---|---|---|
| **Analyzer** | Reads the URL and infers the business, audience, and offer | 3 widget blueprints |
| **Architect** | Extracts brand (colors, type, visual language) and designs the widget's logic and copy | Brand + logic + copywriting |
| **Stitcher** | Turns the brand into concrete design tokens | CSS variables, component theme |
| **Codegen** | Generates a React + Tailwind project and builds it, retrying against real build errors | Built `dist/` |
| **Deployer** | Publishes the build to its own Vercel project | Public URL + embed snippet |

The user reviews the Architect stage's output before Codegen runs, and can edit the
palette or regenerate the concept. Edits are passed back in as an override, so what
they confirmed is what gets built.

### Deployment model

Each widget becomes its own static Vercel project, served from Vercel's edge
network. The customer embeds a plain iframe pointing at that URL — never at this
API. Deploy history is recorded, so a bad deployment can be rolled back instantly
without a rebuild.

### Editing a live tool

Generation produces a first draft, not a final answer. The owner can rewrite the
question flow (`PUT /api/widgets/{id}/decision`) and the result screen —
score bands, the advice under each one, the email capture, the closing call to
action and the suggested next steps (`PUT /api/widgets/{id}/outcomes`).

Those edits reach a live tool **without a rebuild**. The deployed bundle still
bakes in a complete configuration so it renders correctly with no network at all,
and on boot it fetches `GET /api/widgets/{id}/runtime-config` and overlays
whatever the owner has since changed. Renaming a score band is a seconds-long
change rather than a five-minute regeneration.

The result screen is *derived* from what the Architect designed the first time it
is read, then owned by whoever edits it — which is why it lives in its own column
and survives a regeneration that replaces everything else.

---

## Plans and entitlements

`app/features/billing/plans.py` is the single definition of what each tier
includes: price, live-tool cap, monthly build allowance, lead cap, analytics
window and feature set. The API serves it at `GET /api/billing/plans`, and both
the marketing pricing page and the in-product billing screen render from that —
so they cannot drift from what the server actually enforces.

`GET /api/billing/entitlements` answers the only question a screen needs to ask:
what may this workspace do right now, and how much of each allowance is left.
Builds are metered into `usage_records` as they are enqueued, so a build that
consumes a generation run and then fails still counts.

A locked capability returns **402** with the feature that was blocked and the
cheapest plan that unlocks it, which is what lets the client render a real
upgrade prompt instead of a dead end.

`MAGAI_REQUIRE_PAYMENT_TO_BUILD` is the master switch for all of this. With it
off — the default in development and CI — every feature and quota is open, so the
whole product is exercisable without a Stripe account. Production validation
refuses to start without it.

---

## Where leads go

Every captured lead is stored, emailed to the owner, and — after the visitor's
response has already been sent — fanned out to whatever the workspace has
connected: HubSpot, Salesforce (Web-to-Lead), ActiveCampaign, Mailchimp, Google
Sheets, Slack, Zapier, Make, n8n, or a signed webhook to an endpoint of their
own.

Credentials are encrypted at rest with Fernet rather than stored in a column
(see `app/platform/security/secrets.py`); only the last four characters are ever
returned. Customer-supplied destinations go through the same SSRF guard the site
analyzer uses, at connect time and again on every delivery.

Nothing here is a decorative toggle. "Send test lead" performs the same request a
real lead will, and every attempt is recorded in `integration_deliveries`, which
is what the lead's activity timeline reads to show delivery beside capture.

---

## Self-healing

Two scheduled checks run per widget (default every 6 hours, one batch at a time):

**Brand drift.** The Architect stage re-runs against the source site and the
extracted brand is diffed against what the widget was built from. If the site's
colors, heading font, or layout changed, the widget is regenerated and redeployed
automatically. Fuzzy free-text fields are excluded from the diff so a model
re-wording its own description never triggers a needless rebuild.

**Deployment health.** The live URL is fetched and, if unreachable, the last
known-good build is republished. Redirects are re-validated at every hop, so this
check cannot be turned into an SSRF probe.

Every check writes a `widget_heal_events` row, surfaced as a real timeline on the
widget's dashboard page. A widget that fails to heal repeatedly backs off after
`MAGAI_SELF_HEAL_MAX_FAILURES` attempts rather than burning an AI call every sweep.

**What self-healing deliberately does not cover:** host-page DOM or layout changes.
Widgets render inside a sandboxed iframe, so the host page's CSS cannot reach in
and break their layout — there is nothing to repair there, and claiming otherwise
would be marketing rather than engineering.

---

## Local development

Without Docker you need **Python 3.13** with [uv](https://docs.astral.sh/uv/),
**Node 22** with **pnpm**, and running **PostgreSQL** and **Redis**.

### Backend

```bash
cd magai-be
cp .env.example .env
uv sync --extra dev
uv run alembic upgrade head
```

Three processes, in separate terminals:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

```bash
uv run celery -A app.platform.celery_app worker --loglevel=info
```

```bash
uv run celery -A app.platform.celery_app beat --loglevel=info
```

The worker runs builds; beat schedules the self-heal sweep. The API serves traffic
without either, but no widget will build.

### Frontend

```bash
cd magai-fe
pnpm install
pnpm dev
```

Set `VITE_API_URL` if the API is not on `http://localhost:8000`. Vite inlines it at
build time, so it must be present when building, not just when serving.

To enable Google sign-in and sign-up, create a Google OAuth 2.0 Web client and add
your frontend origin, such as `http://localhost:5173`, to its authorized JavaScript
origins. Set the same client ID in both applications:

```env
# magai-fe/.env
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com

# magai-be/.env
MAGAI_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

### Verify

```bash
curl http://localhost:8000/health/ready
```

Then sign up and analyze a site:

```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"correct-horse-battery-99"}'
```

```bash
curl -X POST http://localhost:8000/api/widgets/analyze \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access_token from signup>' \
  -d '{"url":"https://example.com"}'
```

---

## Configuration

Every setting is an environment variable prefixed `MAGAI_`, documented inline in
[`magai-be/.env.example`](magai-be/.env.example) and defined in
`app/platform/config/settings.py`.

The ones that matter most:

| Variable | Purpose |
|---|---|
| `MAGAI_SECRET_KEY` | JWT signing key. **Must** be set to a random 32+ char value in production. |
| `MAGAI_CORS_ALLOW_ORIGINS` | Comma-separated exact origins. Never `*`. |
| `MAGAI_GEMINI_API_KEY` | Required for analysis and generation. |
| `MAGAI_VERCEL_API_TOKEN` | Required to deploy widgets. |
| `MAGAI_GOOGLE_CLIENT_ID` | Verifies Google Identity Services credentials. Must match `VITE_GOOGLE_CLIENT_ID`. |
| `MAGAI_ENVIRONMENT` | `production` enables strict config validation and disables API docs. |
| `MAGAI_SELF_HEAL_INTERVAL_MINUTES` | How often each widget is re-checked (default 360). |

Setting `MAGAI_ENVIRONMENT=production` makes the app **refuse to start** with a
placeholder secret, a wildcard CORS origin, debug mode on, or the SSRF bypass
enabled. That is intentional: these are the misconfigurations most likely to reach
production unnoticed.

---

## Testing

```bash
cd magai-be && uv run pytest
```

```bash
cd magai-fe && pnpm test
```

509 backend tests and 145 frontend tests. The backend suite runs against
in-memory SQLite (models use dialect-portable column types) and stubs Redis, so
it needs no running services. Lint and types:

```bash
cd magai-be && uv run ruff check . && uv run mypy app
```

```bash
cd magai-fe && pnpm lint && pnpm typecheck
```

CI runs all of the above plus a migration up/down/up cycle against real Postgres,
Docker image builds, dependency audits, and CodeQL.

---

## Further reading

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Module layout, data model, request and build flows, design decisions |
| [SECURITY.md](SECURITY.md) | Threat model, controls, known trade-offs, reporting a vulnerability |
| [OPERATIONS.md](OPERATIONS.md) | Deploy, migrate, monitor, back up, and the incident runbook |
| [magai-fe/PRODUCT.md](magai-fe/PRODUCT.md) | Product positioning and voice |
| [magai-fe/DESIGN.md](magai-fe/DESIGN.md) | Design system and visual language |

## Stack

**Backend** — Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL,
Redis, Celery, Argon2id, PyJWT, Prometheus
**AI** — Google Antigravity SDK, Gemini
**Frontend** — React 19, TanStack Start + Router + Query, Tailwind 4, Radix, Vite
**Tooling** — uv, ruff, mypy, pytest, pnpm, ESLint, Vitest, Docker, GitHub Actions
