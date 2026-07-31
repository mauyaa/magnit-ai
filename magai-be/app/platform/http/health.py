"""Health endpoints, split by what an orchestrator does with each result.

``/health/live``   — is the process up? Never touches dependencies, so a database
                     blip cannot cause Kubernetes to kill an otherwise fine pod.
``/health/ready``  — can it serve traffic? Checks Postgres and Redis, returns 503
                     when degraded so the pod is pulled from the load balancer.
``/health``        — human-readable aggregate for dashboards and curl.
"""

from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

CHECK_TIMEOUT_SECONDS = 3.0


async def _check_database() -> tuple[bool, str]:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
        return True, "connected"
    except TimeoutError:
        return False, "timeout"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return False, "unavailable"


async def _check_redis(url: str) -> tuple[bool, str]:
    client: aioredis.Redis | None = None
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            client = aioredis.Redis.from_url(url, socket_connect_timeout=2)
            await client.ping()
        return True, "connected"
    except TimeoutError:
        return False, "timeout"
    except Exception as exc:
        logger.warning("Redis health check failed for %s: %s", url, exc)
        return False, "unavailable"
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                # Failing to close a probe connection must never change the health
                # verdict; log at debug so it is discoverable but not noisy.
                logger.debug("Could not close Redis health-check connection", exc_info=True)


async def _gather_checks() -> dict[str, str]:
    if settings.local_builds_enabled:
        _, database_detail = await _check_database()
        return {
            "database": database_detail,
            "redis_events": "in_memory",
            "celery_broker": "in_process",
            "celery_backend": "not_required",
        }

    db_result, events_result, broker_result, backend_result = await asyncio.gather(
        _check_database(),
        _check_redis(settings.redis_url),
        _check_redis(settings.celery_broker_url),
        _check_redis(settings.celery_result_backend),
    )
    return {
        "database": db_result[1],
        "redis_events": events_result[1],
        "celery_broker": broker_result[1],
        "celery_backend": backend_result[1],
    }


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Process-level liveness only — deliberately dependency-free."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict[str, object]:
    checks = await _gather_checks()
    # Redis for events is required to serve; the Celery result backend being down
    # degrades builds but not reads, so it is reported without failing readiness.
    critical = (
        ("database",)
        if settings.local_builds_enabled
        else (
            "database",
            "redis_events",
            "celery_broker",
        )
    )
    ready = all(checks[name] == "connected" for name in critical)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "degraded", "checks": checks}


@router.get("/health")
async def health() -> dict[str, object]:
    checks = await _gather_checks()
    healthy_values = {"connected", "in_memory", "in_process", "not_required"}
    all_ok = all(value in healthy_values for value in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "environment": settings.environment,
        "checks": checks,
    }
