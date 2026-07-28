# Architecture

How MagnetAI is put together, and why. For setup see [README.md](README.md); for
security specifics see [SECURITY.md](SECURITY.md); for running it see
[OPERATIONS.md](OPERATIONS.md).

---

## Module layout

The backend separates **features** (product capabilities) from **platform**
(infrastructure). A feature may import from platform, and features do not import
each other's internals. Infrastructure — `config`, `db`, `security`, `http`,
`errors`, `logging`, `observability` — imports no feature, so it can be tested
without dragging in product logic.

Two deliberate exceptions, both marked in the code:

- **Composition roots** must know about features by definition: `http/app.py`
  assembles the routers, and `db/models/__init__.py` collects the model graph for
  Alembic and the test-suite `create_all`.
- **`platform/pipeline/`** is the widget generation engine and imports the widgets
  feature's models and persistence helpers. It sits under `platform` because both
  the API and the Celery worker drive it, but it is domain logic, not
  infrastructure. Treat it as a third layer between the two.

```
magai-be/app/
├── main.py                     ASGI entry point
├── features/                   one package per capability
│   ├── auth/                   signup, login, refresh, logout, deps
│   ├── users/                  account management (password, deletion)
│   ├── widgets/                analyze, build, deploy, rollback, heal history
│   ├── leads/                  public submission + owner-scoped reads
│   └── payments/               Stripe checkout and webhooks
└── platform/
    ├── config/                 settings with production validation
    ├── db/                     engine, session, base, portable column types
    ├── security/               passwords, tokens, revocation, rate limit,
    │                           locks, SSRF guard
    ├── http/                   app factory, middleware, health probes
    ├── errors/                 exception handlers
    ├── logging/                structured JSON logging
    ├── observability/          Sentry, Prometheus metrics
    ├── clients/                Vercel deployment, Antigravity agent
    └── pipeline/               the generation engine
        ├── engine.py           stage orchestration
        ├── states/             analyzer, architect, stitcher, codegen
        ├── heal.py             drift and health detection
        ├── builder.py          runs the real Vite build
        ├── events.py           Redis Streams → SSE
        └── tasks.py            Celery tasks
```

Each feature package follows the same four-file shape:

| File | Responsibility |
|---|---|
| `routes.py` | HTTP concerns only: status codes, dependencies, translating domain exceptions |
| `service.py` | Business logic and persistence. Raises domain exceptions, never `HTTPException` |
| `schemas.py` | Pydantic request/response models |
| `models.py` | SQLAlchemy tables |

The split matters most in `service.py`: because it raises domain exceptions rather
than HTTP ones, the same functions are called from Celery tasks — which have no HTTP
context — without duplication.

---

## Data model

```
users
  id, email (unique), password_hash, is_active, role, last_login_at
    │
    ├──< widgets  (ON DELETE CASCADE)
    │      id, user_id, target_url, widget_type, title, status,
    │      blueprints, brand_tokens, visual_language, widget_logic,
    │      copywriting, design_tokens,
    │      deployment_url, embed_code,
    │      leads_count, lead_cap, plan_tier,
    │      build_stage, build_progress, build_error,
    │      analyzed_at, deployed_at,
    │      last_heal_check_at, heal_failure_count
    │        │
    │        ├──< leads                (CASCADE)  email, name, score, answers
    │        ├──< widget_heal_events   (CASCADE)  check_type, status, diff_summary
    │        └──< widget_deployments   (CASCADE)  deployment_url, trigger, is_current
    │
    └──< payments (CASCADE)
           stripe_session_id (unique), amount, currency, status
```

Design notes:

- **`widgets.status`** is constrained to `analyzed | building | active | failed` by
  a CHECK constraint, so an invalid state cannot be written even by a bad migration
  or manual SQL.
- **`widget_deployments`** is an append-only log with exactly one `is_current` row
  per widget. The next-newest row is an unambiguous rollback target, and rollback is
  instant because old Vercel deployments remain immutable and served.
- **`heal_failure_count`** backs off a widget that keeps failing, instead of burning
  a Gemini call on it every sweep. Reset on any successful build or heal.
- **`leads_count`** is denormalized onto `widgets` so the lead cap can be enforced
  with a single conditional `UPDATE ... WHERE leads_count < lead_cap`, which makes
  the check atomic under concurrent submissions.
- **Column types are dialect-portable** (`platform/db/types.py`): `JSONB`/`UUID` on
  PostgreSQL, `JSON`/`CHAR(36)` elsewhere. That is what lets the test suite run the
  real models against in-memory SQLite with no live database.

---

## Request flow

```
Client
  │  Authorization: Bearer <access JWT>
  ▼
RequestContextMiddleware   assign request id, log outcome
MetricsMiddleware          count and time by route template
SecurityHeadersMiddleware  attach hardening headers
BodySizeLimitMiddleware    reject oversized payloads
  ▼
CORS → TrustedHost
  ▼
rate_limit(bucket)         Redis counter, per-user or per-IP
  ▼
get_current_user           decode JWT → revocation check → load active user
  ▼
route handler              translates domain exceptions to status codes
  ▼
service function           ownership-scoped query or mutation
  ▼
PostgreSQL
```

Middleware is registered in reverse order of execution, so the request-context layer
is outermost: its id is available to every log line produced further in, including
those emitted by the exception handlers.

---

## Build flow

A build is asynchronous because it takes minutes and involves several AI calls.

```
POST /api/widgets/analyze
  → SSRF-validate URL
  → Analyzer stage (Gemini) → 3 blueprints
  → persist widget (status=analyzed)

POST /api/widgets/{id}/architect-preview        ← "Regenerate" calls this again
  → Architect stage (Gemini) → brand + logic + copy
  → returned, not persisted

POST /api/widgets/build  { architect_override } ← the user's confirmed/edited brand
  → enqueue Celery task, status=building
  │
  └─ worker: build_widget_task
       → acquire per-widget lock
       → Architect (skipped when overridden)
       → Stitcher   → design tokens
       → Codegen    → generate project, run real Vite build,
       │              retry against actual build errors
       → Deploy     → Vercel project → public URL
       → record deployment, save artifacts, status=active
       │
       └─ progress published to Redis Streams throughout
            → GET /api/widgets/{id}/events (SSE) → live build UI
```

Two decisions worth calling out:

**The architect override.** Without it, the confirm step would be theatre: the user
edits a colour, then the build re-extracts the brand and silently discards the edit.
Passing the confirmed output back in is what makes the review step real.

**Codegen validates against a real build.** The generated project is actually
compiled with Vite, and compile errors are fed back to the model as feedback for a
retry. An AI-authored component that merely looks plausible is worthless if it does
not build.

---

## Self-heal flow

```
Celery beat (every MAGAI_SELF_HEAL_INTERVAL_MINUTES)
  → run_self_heal_sweep
      → acquire cluster-wide sweep lock        (one sweep at a time)
      → select active widgets, oldest-checked first, LIMIT batch_size,
        excluding those past the failure threshold
      │
      └─ per widget: acquire per-widget lock
           → stamp last_heal_check_at, commit
           │
           ├─ brand drift:   re-run Architect → diff → regenerate + redeploy
           └─ deploy health: GET live URL → republish saved build if unreachable
           │
           └─ write widget_heal_events row, publish SSE event, update metrics
```

Scalability and safety properties:

- **Bounded batches** with nulls-first, oldest-first ordering: the sweep's cost is
  constant regardless of tenant count, and no widget can be starved.
- **Two lock scopes.** One cluster-wide lock stops overlapping beat ticks; one
  per-widget lock (shared with the build path) stops a heal and a manual rebuild
  from racing on the same build directory.
- **`last_heal_check_at` is stamped before the checks run**, so a crash mid-check
  cannot put the widget into a tight re-check loop.
- **One widget's failure never aborts the sweep** — each is wrapped individually.

---

## Key design decisions

**Celery over background tasks.** Builds take minutes and must survive an API
restart or deploy. FastAPI `BackgroundTasks` would lose in-flight work; a broker
gives durability, retries, and a separate scaling axis for build capacity.

**Redis Streams for progress, not WebSockets.** Progress is a one-way append-only
log with no client→server messaging. Streams give replay-on-reconnect for free (a
client that reconnects mid-build sees everything it missed), and SSE is a simpler
transport with automatic reconnection.

**One Vercel project per widget.** Origin isolation: AI-generated code runs on its
own domain with no access to MagnetAI's cookies, credentials, or database.
Immutable deployments also make rollback trivial.

**Widgets are iframes.** This constrains the product honestly. It means the host
page cannot break the widget's layout — which is exactly why "self-healing" here
means brand drift and uptime, not DOM repair.

**Fail-open rate limits, fail-closed locks.** Opposite choices for opposite reasons:
rate limits protect budget (a Redis blip shouldn't cause an outage), while locks
protect correctness (a double rebuild is worse than a skipped cycle). Both are
documented at their definitions and covered by tests.

**Ownership checks in the service layer, not middleware.** Middleware cannot know
which resource a request is about. Putting `user_id` into the query itself means
there is no code path where the filter can be forgotten — and it is enforced by
tests that assert a second account gets a 404.

---

## Frontend structure

```
magai-fe/src/
├── routes/                 file-based routes (TanStack Router)
├── components/magnitai/    product components
│   ├── AuthForm            login / signup
│   ├── RequireAuth         client-side route gate (UX, not security)
│   ├── CheckoutFlow        URL → blueprint → confirm/edit → build
│   ├── LiveBuildStory      SSE build progress
│   ├── EmbedCodePanel      the actual deliverable
│   └── ErrorBoundary       subtree failure isolation
├── components/ui/          shadcn/Radix primitives
└── lib/
    ├── api-client.ts       fetch wrapper: token, refresh, error normalization
    ├── api.ts              React Query hooks
    ├── auth.tsx            auth context
    └── auth-storage.ts     token persistence
```

The layering matters in `lib/`: **`api-client.ts` owns all transport concerns** —
attaching the token, refreshing once on a 401 and replaying, de-duplicating
concurrent refreshes (critical, because refresh tokens are single-use), and turning
API error codes into readable messages. Hooks in `api.ts` never touch `fetch`
directly, so none of that logic is duplicated per endpoint.

The current user comes from `/api/auth/me` rather than from decoding the JWT
client-side, so a token belonging to a deleted or deactivated account resolves to
"signed out" instead of appearing valid.
