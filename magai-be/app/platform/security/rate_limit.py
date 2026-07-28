"""Redis-backed fixed-window rate limiting.

Usage as a route dependency::

    @router.post("/analyze", dependencies=[Depends(rate_limit("analyze"))])

Keys are per-user when the caller is authenticated and per-IP otherwise, so one
tenant cannot exhaust another's quota and an anonymous flood is bounded per
source address.

Availability note: if Redis is unreachable the request is allowed through and the
failure is logged. These limits protect budget, not correctness, and a Redis blip
should not take the API down. The counter is incremented before the limit check
so a race cannot let two concurrent requests both pass at the boundary.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.platform.config.settings import settings
from app.platform.security.tokens import TokenError, decode_token

logger = logging.getLogger(__name__)

_PERIOD_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
_LIMIT_PATTERN = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour|day)\s*$", re.IGNORECASE)

_pool: aioredis.ConnectionPool | None = None


def _redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        # Short timeouts so an unreachable Redis costs milliseconds, not seconds.
        # See the note in revocation.py: failing open slowly is its own outage.
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            socket_connect_timeout=settings.redis_timeout_seconds,
            socket_timeout=settings.redis_timeout_seconds,
        )
    return aioredis.Redis(connection_pool=_pool)


@dataclass(frozen=True)
class Limit:
    max_requests: int
    window_seconds: int


def parse_limit(spec: str) -> Limit:
    """Parse a ``"10/hour"``-style spec. Raises ``ValueError`` if malformed."""
    match = _LIMIT_PATTERN.match(spec)
    if not match:
        raise ValueError(f"Invalid rate limit spec: {spec!r} (expected e.g. '10/hour')")
    count, period = match.groups()
    return Limit(max_requests=int(count), window_seconds=_PERIOD_SECONDS[period.lower()])


def _limit_for(name: str) -> Limit:
    spec = getattr(settings, f"rate_limit_{name}", None) or settings.rate_limit_default
    return parse_limit(spec)


def _client_ip(request: Request) -> str:
    """Best-effort client IP.

    ``X-Forwarded-For`` is only trusted when the app is behind a proxy that sets
    it; ``uvicorn --proxy-headers`` already normalizes ``request.client`` in that
    case, so the direct peer is preferred and the header is a fallback only.
    """
    if request.client and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or "unknown"


def _identity(request: Request) -> str:
    """Bucket key for the caller: the account when identifiable, else the IP.

    The token's subject is read directly rather than resolving the full user, for
    two reasons: it keeps this module free of any dependency on the auth *feature*
    (platform code must not import features), and it avoids a database round-trip
    on every rate-limited request. A forged subject is not a concern because
    ``decode_token`` verifies the signature — without the signing key an attacker
    cannot mint a new bucket, and falling back to per-IP is the safe default.
    """
    header = request.headers.get("authorization", "")
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() == "bearer" and credentials:
        try:
            claims = decode_token(credentials.strip(), expected_type="access")
            return f"user:{claims.subject}"
        except TokenError:
            pass  # Expired or invalid: treat as anonymous and limit by IP.
    return f"ip:{_client_ip(request)}"


async def check_rate_limit(bucket: str, identity: str, limit: Limit) -> tuple[bool, int]:
    """Increment the counter and report ``(allowed, retry_after_seconds)``."""
    key = f"ratelimit:{bucket}:{identity}"
    try:
        redis = _redis()
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()

        if ttl is None or ttl < 0:
            # First hit in this window (or a key with no expiry) — start the clock.
            await redis.expire(key, limit.window_seconds)
            ttl = limit.window_seconds

        if int(count) > limit.max_requests:
            return False, int(ttl)
        return True, 0
    except Exception:
        logger.exception("Rate limit check failed for %s — allowing request", key)
        return True, 0


def rate_limit(name: str) -> Any:
    """Build a dependency enforcing the ``rate_limit_<name>`` setting."""

    async def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        allowed, retry_after = await check_rate_limit(name, _identity(request), _limit_for(name))
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limit_exceeded",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

    return Depends(dependency)
