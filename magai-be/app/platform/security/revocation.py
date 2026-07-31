"""Token revocation denylist backed by Redis.

Logout adds a token's ``jti`` to the denylist with a TTL matching the token's own
remaining lifetime, so entries expire on their own and the set stays small.

Availability note: if Redis is unreachable we log loudly and treat the token as
*not* revoked. Failing closed would turn a Redis blip into a total auth outage.
The exposure is bounded by the access-token TTL (30 min by default), and refresh
tokens are additionally checked against ``users.is_active`` in the database on
every use, so a disabled account cannot be resurrected by a cache outage.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import redis.asyncio as aioredis

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "revoked_jti:"
_RETRY_COOLDOWN_SECONDS = 5.0

_pool: aioredis.ConnectionPool | None = None
_redis_retry_after = 0.0


def _redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        # Explicit short timeouts matter more than they look. This check runs on
        # every authenticated request, and without them an unreachable Redis
        # blocks for the OS-level connect timeout — measured at ~4s per request.
        # "Fails open" is only useful if it fails open *quickly*.
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            socket_connect_timeout=settings.redis_timeout_seconds,
            socket_timeout=settings.redis_timeout_seconds,
        )
    return aioredis.Redis(connection_pool=_pool)


async def revoke(jti: str, expires_at: datetime) -> None:
    global _redis_retry_after
    ttl = int((expires_at - datetime.now(UTC)).total_seconds())
    if ttl <= 0:
        return  # Already expired; nothing to deny.
    if time.monotonic() < _redis_retry_after:
        return
    try:
        await _redis().setex(f"{_KEY_PREFIX}{jti}", ttl, "1")
    except Exception as exc:
        _redis_retry_after = time.monotonic() + _RETRY_COOLDOWN_SECONDS
        logger.warning(
            "Redis revocation store unavailable; token remains valid until expiry (%s)",
            type(exc).__name__,
        )


async def is_revoked(jti: str) -> bool:
    global _redis_retry_after
    if time.monotonic() < _redis_retry_after:
        return False
    try:
        found = await _redis().exists(f"{_KEY_PREFIX}{jti}")
        _redis_retry_after = 0.0
        return int(found) > 0
    except Exception as exc:
        _redis_retry_after = time.monotonic() + _RETRY_COOLDOWN_SECONDS
        logger.warning(
            "Redis revocation checks unavailable; relying on access-token expiry (%s)",
            type(exc).__name__,
        )
        return False
