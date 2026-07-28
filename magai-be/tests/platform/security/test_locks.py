"""Distributed lock behaviour.

The lock is what stops two workers from healing or rebuilding the same widget at
once, which would race on the shared build directory.
"""

import pytest

from app.platform.security.locks import LockNotAcquired, distributed_lock


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.store: dict[str, str] = {}
        self.fail = fail

    async def set(self, key, value, nx=False, ex=None):
        if self.fail:
            raise ConnectionError("redis down")
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def eval(self, _script, _numkeys, key, token):
        if self.fail:
            raise ConnectionError("redis down")
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


class TestDistributedLock:
    async def test_lock_is_released_after_the_block(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        async with distributed_lock("widget-heal:abc"):
            assert "lock:widget-heal:abc" in fake.store

        assert "lock:widget-heal:abc" not in fake.store

    async def test_second_holder_is_refused(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        async with distributed_lock("widget-heal:abc"):
            with pytest.raises(LockNotAcquired):
                async with distributed_lock("widget-heal:abc"):
                    pytest.fail("second holder must not acquire the lock")

    async def test_different_names_do_not_collide(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        async with distributed_lock("widget-heal:one"):
            async with distributed_lock("widget-heal:two"):
                assert len(fake.store) == 2

    async def test_lock_released_even_when_body_raises(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        with pytest.raises(RuntimeError):
            async with distributed_lock("widget-heal:abc"):
                raise RuntimeError("build blew up")

        # A failed heal must not leave the widget locked out of future sweeps.
        assert fake.store == {}

    async def test_holder_cannot_delete_another_holders_lock(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        # Simulate the lock having been taken over by someone else mid-flight.
        async with distributed_lock("widget-heal:abc"):
            fake.store["lock:widget-heal:abc"] = "a-different-owners-token"

        # Compare-and-delete means our release was a no-op, not a steal.
        assert fake.store["lock:widget-heal:abc"] == "a-different-owners-token"

    async def test_redis_outage_fails_closed(self, monkeypatch):
        fake = FakeRedis(fail=True)
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        # Opposite trade-off from rate limiting: without a working lock we cannot
        # guarantee exclusivity, and a double rebuild is worse than a skipped one.
        with pytest.raises(LockNotAcquired):
            async with distributed_lock("widget-heal:abc"):
                pytest.fail("must not run without a lock")


class TestWidgetLockKey:
    """Building and healing one widget must contend for the *same* key.

    They were once namespaced separately, which meant an owner pressing Rebuild
    while a scheduled heal was mid-flight got both running at once on the same
    workspace directory. A shared key is the whole mechanism, so it is pinned
    here rather than left to a string literal at two distant call sites.
    """

    async def test_a_build_and_a_heal_exclude_each_other(self, monkeypatch):
        from app.platform.pipeline.tasks import widget_lock_key

        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        async with distributed_lock(widget_lock_key("abc")):
            with pytest.raises(LockNotAcquired):
                async with distributed_lock(widget_lock_key("abc")):
                    pytest.fail("a build must not run while the same widget is healing")

    async def test_different_widgets_still_run_in_parallel(self, monkeypatch):
        from app.platform.pipeline.tasks import widget_lock_key

        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.locks._redis", lambda: fake)

        async with distributed_lock(widget_lock_key("one")):
            async with distributed_lock(widget_lock_key("two")):
                assert len(fake.store) == 2
