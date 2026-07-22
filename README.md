# MagnetAI

Automated lead magnet generator. Enter a URL, get 3 interactive widget ideas (ROI calculator, quiz, audit, etc.), pick one, and deploy a branded React+Tailwind widget — all powered by Google Antigravity + Gemini.

## Architecture

```
                    ┌──────────────┐
                    │  magai-fe    │  Next.js (pnpm)
                    │  Landing +   │
                    │  Dashboard   │
                    └──────┬───────┘
                           │ HTTP
                    ┌──────▼───────┐
                    │  magai-be    │  FastAPI (uv)
                    │              │
                    │  features/   │  ─ widgets, payments, users
                    │  platform/   │
                    │   pipeline/  │  ← 5-state AGY engine
                    └──────┬───────┘
                           │ AGY SDK
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
         │ Gemini │  │ Stitch │  │ Vercel │
         │  1.5   │  │ (MCP)  │  │ (MCP)  │
         └────────┘  └────────┘  └────────┘
```

### Pipeline (5 states)

| State | Agent Tooling | Output |
|---|---|---|
| **Analyzer** | `READ_URL_CONTENT` + Gemini | 3 structured blueprints |
| **Architect** | Gemini (vision + reasoning) | Brand extraction + math logic + copy |
| **Stitcher** | Stitch MCP | Design tokens (CSS vars, theme) |
| **Codegen** | Gemini (code generation) | React+Tailwind `.tsx` component |
| **Deployer** | Vercel MCP | Production iframe URL |

## Getting Started

### Prerequisites

- **Python 3.13+** with [uv](https://docs.astral.sh/uv/)
- **PostgreSQL** running on `localhost:5432`
- **Redis** running on `localhost:6379`
- **pnpm** (for frontend)
- **Node.js 20+** (for frontend)

### Backend

```bash
cd magai-be
cp .env.example .env   # fill in MAGAI_GEMINI_API_KEY, MAGAI_DATABASE_URL, etc.
uv sync
uv run alembic upgrade head

# Terminal 1 — API server (FastAPI)
uv run uvicorn app.platform.http.app:create_app --factory --reload --port 8000

# Terminal 2 — Celery worker (build pipeline)
uv run celery -A app.platform.celery_app worker --loglevel=info
```

### Frontend

```bash
cd magai-fe
cp .env.example .env.local   # set VITE_API_URL=http://localhost:8000
pnpm install
pnpm dev
```

### Environment Variables (`magai-be/.env`)

| Variable | Default | Required |
|---|---|---|
| `MAGAI_DATABASE_URL` | `postgresql+asyncpg://localhost:5432/magai` | Yes |
| `MAGAI_GEMINI_API_KEY` | — | Yes |
| `MAGAI_REDIS_URL` | `redis://localhost:6379/0` | Yes |
| `MAGAI_CELERY_BROKER_URL` | `redis://localhost:6379/1` | Yes |
| `MAGAI_CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Yes |
| `MAGAI_VERCEL_API_TOKEN` | — | For deploy |
| `MAGAI_AGY_MODEL` | `gemini-3.1-pro-preview` | — |
| `MAGAI_SITE_URL` | `http://localhost:8000` | — |
| `MAGAI_DEBUG` | `false` | — |

### Verify It Works

```bash
# Health check (DB + Redis)
curl http://localhost:8000/health

# Analyze a URL
curl -X POST http://localhost:8000/api/widgets/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Build a widget (after analyze returns widget_id + blueprint_index)
curl -X POST http://localhost:8000/api/widgets/build \
  -H "Content-Type: application/json" \
  -d '{"widget_id": "...", "blueprint_index": 0}'

# Stream build events (SSE)
curl -N http://localhost:8000/api/widgets/{widget_id}/events
```

## Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy (async), Alembic, PostgreSQL
- **AI:** Google Antigravity SDK, Gemini 3.1, Stitch MCP
- **Payments:** Stripe Checkout + Webhooks
- **Frontend:** Next.js, TypeScript, Tailwind CSS, pnpm
- **Tooling:** uv, ruff, mypy, pytest
