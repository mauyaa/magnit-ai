from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Imported for its side effect: registers every model so SQLAlchemy mappers are
# configured before the first query runs.
import app.platform.db.models  # noqa: F401  (must follow the app imports)
from app.features.auth.routes import router as auth_router
from app.features.billing.routes import router as billing_router
from app.features.integrations.routes import router as integrations_router
from app.features.leads.routes import router as leads_router
from app.features.payments.routes import router as payments_router
from app.features.users.api_access import router as api_access_router
from app.features.users.routes import router as users_router
from app.features.widgets.routes import router as widgets_router
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory, engine, rows_affected
from app.platform.errors.handlers import register_exception_handlers
from app.platform.http.health import router as health_router
from app.platform.http.middleware import (
    BodySizeLimitMiddleware,
    PublicWidgetCorsMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.platform.logging.config import configure_logging
from app.platform.observability.metrics import MetricsMiddleware, render_metrics
from app.platform.observability.sentry import init_sentry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Note: models are imported at module scope (see the import block above), not
    # here. `import app.platform.db.models` inside this function would bind the
    # local name `app` to the module and shadow the FastAPI parameter.
    logger.info(
        "Starting MagnetAI API",
        extra={"environment": settings.environment, "sentry": bool(settings.sentry_dsn)},
    )

    # Widgets left mid-build by a previous process (deploy, crash, OOM) would sit
    # in "building" forever, so they are returned to a retryable state on boot.
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "UPDATE widgets SET status = 'analyzed', build_stage = NULL, "
                    "build_progress = NULL, build_error = NULL WHERE status = 'building'"
                )
            )
            reset_count = rows_affected(result)
            if reset_count:
                logger.warning("Reset %d stale building widgets on startup", reset_count)
            await session.commit()
    except Exception:
        # A database outage must not prevent the process from starting; readiness
        # will report it and the load balancer will hold traffic back.
        logger.exception("Startup reconciliation skipped — database unreachable")

    try:
        yield
    finally:
        # Graceful shutdown: return pooled connections so in-flight queries finish
        # and Postgres does not accumulate abandoned sessions across restarts.
        logger.info("Shutting down MagnetAI API")
        await engine.dispose()


def create_app() -> FastAPI:
    configure_logging()
    init_sentry()

    app = FastAPI(
        title="MagnetAI",
        version="1.0.0",
        lifespan=lifespan,
        # OpenAPI docs are useful internally but enumerate the whole attack
        # surface, so they are disabled in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    # Middleware executes in reverse registration order, so the outermost layer is
    # registered last: request context wraps everything (its id reaches all logs),
    # then metrics, then security headers, then the body-size gate closest to the
    # route so oversized payloads are rejected before any handler work.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestContextMiddleware)

    if settings.trusted_host_list != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

    # Explicit origins only. A wildcard with credentials is rejected by browsers
    # and would allow any site to drive the API with a victim's token.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(PublicWidgetCorsMiddleware)

    register_exception_handlers(app)

    if settings.metrics_enabled:

        @app.get("/metrics", include_in_schema=False)
        async def metrics() -> Response:
            """Prometheus scrape endpoint.

            Exposes no customer data, but should still be restricted to the
            monitoring network at the ingress/firewall layer.
            """
            body, content_type = render_metrics()
            return Response(content=body, media_type=content_type)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(api_access_router)
    app.include_router(widgets_router)
    app.include_router(billing_router)
    app.include_router(payments_router)
    app.include_router(integrations_router)
    app.include_router(leads_router)

    return app
