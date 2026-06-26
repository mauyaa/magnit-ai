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

### Backend

```bash
cd magai-be
cp .env.example .env   # fill in GEMINI_API_KEY, STRIPE keys, etc.
uv sync
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd magai-fe
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL
pnpm install
pnpm dev
```

### Database

```bash
cd magai-be
uv run alembic upgrade head
```

## Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy (async), Alembic, PostgreSQL
- **AI:** Google Antigravity SDK, Gemini 2.5, Stitch MCP
- **Payments:** Stripe Checkout + Webhooks
- **Frontend:** Next.js, TypeScript, Tailwind CSS, pnpm
- **Tooling:** uv, ruff, mypy, pytest
