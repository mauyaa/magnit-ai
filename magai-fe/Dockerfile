# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# MagnetAI frontend image (TanStack Start / Nitro server build).
#
# Vite inlines VITE_* variables at build time, so VITE_API_URL is a build
# argument rather than a runtime environment variable.
# ---------------------------------------------------------------------------

FROM node:22-bookworm-slim AS builder

RUN npm install --global pnpm@9.11.0

WORKDIR /app

# Install against the lockfile only, so this layer caches across source edits.
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN pnpm build


FROM node:22-bookworm-slim AS runtime

ENV NODE_ENV=production \
    PORT=3000

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The Nitro build output is self-contained; no node_modules copy required.
COPY --from=builder --chown=node:node /app/.output ./.output

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:3000/ || exit 1

CMD ["node", ".output/server/index.mjs"]
