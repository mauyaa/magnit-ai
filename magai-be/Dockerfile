# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# MagnetAI backend image.
#
# Multi-stage: dependencies resolve in a builder layer that is cached on the
# lockfile, so application edits do not re-resolve the environment. The runtime
# stage carries no build toolchain and runs as an unprivileged user.
#
# The generated widgets are built with Node/pnpm inside this container (see
# app/platform/pipeline/builder.py), so the runtime needs Node present.
# ---------------------------------------------------------------------------

FROM ghcr.io/astral-sh/uv:0.5-python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Resolve dependencies first, keyed only on the manifests, so this layer is
# reused whenever application code changes but dependencies do not.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# curl for container healthchecks; Node/pnpm to build generated widget projects.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install --global pnpm@9.11.0 \
 && apt-get purge -y --auto-remove gnupg \
 && rm -rf /var/lib/apt/lists/*

# Non-root: a container escape should not land on a root shell.
RUN groupadd --system --gid 1001 magai \
 && useradd --system --uid 1001 --gid magai --create-home magai

WORKDIR /app

COPY --from=builder --chown=magai:magai /app /app

# Build artifacts for generated widgets live here and must be writable.
RUN mkdir -p /app/workspace && chown -R magai:magai /app/workspace

USER magai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1

# --proxy-headers so the real client IP survives a load balancer, which the rate
# limiter depends on for per-IP quotas.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
