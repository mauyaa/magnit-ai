"""Redis distributed lock.

Used so two workers (or an overlapping beat tick) can never heal or rebuild the
same widget concurrently — which would race on the shared build directory and
could publish the losing worker's output.

Correctness properties:

* Acquire is a single ``SET NX EX``, so it is atomic.
* Every lock carries a random token and is released with a Lua compare-and-delete,
  so a holder that has already timed out cannot delete a *different* holder's lock.
* Locks always expire, so a worker that dies mid-heal cannot deadlock the widget.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Any, cast

import redis.asyncio as aioredis

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)

# Only delete the key if we still own it.
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_pool: aioredis.ConnectionPool | None = None
_process_locks: dict[str, asyncio.Lock] = {}


def _redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            socket_connect_timeout=settings.redis_timeout_seconds,
            socket_timeout=settings.redis_timeout_seconds,
        )
    return aioredis.Redis(connection_pool=_pool)


class LockNotAcquired(Exception):
    """Another holder owns the lock; the caller should skip this item."""


@asynccontextmanager
async def process_lock(name: str) -> AsyncIterator[None]:
    """Hold a lock inside this API process.

    This is intentionally not a Redis fallback. It is used only by the explicit
    development-local build runner, where all builds live in one process. The
    production worker path always uses :func:`distributed_lock`.
    """
    lock = _process_locks.setdefault(name, asyncio.Lock())
    if lock.locked():
        raise LockNotAcquired(name)

    await lock.acquire()
    try:
        yield
    finally:
        lock.release()
        _process_locks.pop(name, None)


@asynccontextmanager
async def distributed_lock(name: str, ttl_seconds: int | None = None) -> AsyncIterator[None]:
    """Hold a named lock for the duration of the block.

    Raises :class:`LockNotAcquired` if someone else holds it. Redis being
    unavailable is also treated as *not acquired*: without a working lock we
    cannot guarantee exclusivity, and skipping a heal cycle is strictly safer than
    two workers rebuilding the same widget at once.
    """
    key = f"lock:{name}"
    token = str(uuid.uuid4())
    ttl = ttl_seconds or settings.self_heal_lock_ttl_seconds
    redis = _redis()

    try:
        acquired = await redis.set(key, token, nx=True, ex=ttl)
    except Exception:
        logger.exception("Could not reach Redis to acquire lock %s — skipping", key)
        raise LockNotAcquired(name) from None

    if not acquired:
        raise LockNotAcquired(name)

    try:
        yield
    finally:
        try:
            # redis-py types eval() as possibly-sync depending on the client mode;
            # the async client always returns an awaitable.
            await cast("Awaitable[Any]", redis.eval(_RELEASE_SCRIPT, 1, key, token))
        except Exception:
            # The TTL guarantees eventual release even if this fails.
            logger.exception("Failed to release lock %s; it will expire in %ss", key, ttl)
