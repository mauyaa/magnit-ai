"""The logout denylist, and its deliberate decision to fail open.

The module documents the trade-off: an unreachable Redis treats every token as
valid rather than rejecting everything, because failing closed turns a cache blip
into a total auth outage. That is a security-relevant choice, so it is pinned
here — if someone later "fixes" it into failing closed, that should be a decision
with a failing test in front of it, not a silent change.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.platform.security import revocation


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    async def setex(self, key: str, ttl: int, value: str) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.store[key] = value
        self.ttls[key] = ttl

    async def exists(self, key: str) -> int:
        if self.fail:
            raise ConnectionError("redis down")
        return 1 if key in self.store else 0


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(revocation, "_redis", lambda: fake)
    return fake


@pytest.fixture
def broken_redis(monkeypatch):
    fake = FakeRedis(fail=True)
    monkeypatch.setattr(revocation, "_redis", lambda: fake)
    return fake


class TestRevoke:
    async def test_a_revoked_token_is_denied(self, fake_redis):
        expires = datetime.now(UTC) + timedelta(minutes=30)

        await revocation.revoke("jti-1", expires)

        assert await revocation.is_revoked("jti-1") is True

    async def test_an_unknown_token_is_not_denied(self, fake_redis):
        assert await revocation.is_revoked("never-seen") is False

    async def test_the_entry_expires_with_the_token_it_denies(self, fake_redis):
        """A TTL longer than the token would grow the set forever for no benefit."""
        expires = datetime.now(UTC) + timedelta(minutes=30)

        await revocation.revoke("jti-2", expires)

        ttl = fake_redis.ttls["revoked_jti:jti-2"]
        assert 1750 <= ttl <= 1800

    async def test_an_already_expired_token_is_not_written(self, fake_redis):
        """It cannot be used anyway; writing it would be pure storage cost."""
        await revocation.revoke("jti-3", datetime.now(UTC) - timedelta(seconds=1))

        assert fake_redis.store == {}

    async def test_keys_are_namespaced(self, fake_redis):
        await revocation.revoke("jti-4", datetime.now(UTC) + timedelta(minutes=5))

        assert "revoked_jti:jti-4" in fake_redis.store


class TestFailsOpen:
    async def test_an_unreachable_redis_does_not_reject_every_request(self, broken_redis):
        """Failing closed here would turn a cache blip into a full auth outage.

        The exposure is bounded: access tokens live 30 minutes, and refresh
        tokens are re-checked against the user row on every use, so a disabled
        account cannot be resurrected by a cache outage.
        """
        assert await revocation.is_revoked("jti-5") is False

    async def test_a_failed_revoke_is_swallowed_so_logout_still_succeeds(self, broken_redis):
        # No exception: the user is signed out client-side either way, and the
        # token expires on its own.
        await revocation.revoke("jti-6", datetime.now(UTC) + timedelta(minutes=30))
