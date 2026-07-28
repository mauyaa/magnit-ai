import pytest

from app.platform.security.rate_limit import Limit, check_rate_limit, parse_limit


class TestParseLimit:
    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("10/hour", Limit(10, 3600)),
            ("5/minute", Limit(5, 60)),
            ("1/second", Limit(1, 1)),
            ("100/day", Limit(100, 86400)),
            (" 30 / minute ", Limit(30, 60)),
            ("10/HOUR", Limit(10, 3600)),
        ],
    )
    def test_parses_valid_specs(self, spec, expected):
        assert parse_limit(spec) == expected

    @pytest.mark.parametrize("spec", ["10", "hour", "10/fortnight", "", "-5/hour", "10//hour"])
    def test_rejects_invalid_specs(self, spec):
        # A typo in configuration must fail loudly, not silently disable limiting.
        with pytest.raises(ValueError):
            parse_limit(spec)


class FakeRedis:
    """Minimal in-process stand-in for the counter operations used."""

    def __init__(self, fail: bool = False):
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    def pipeline(self):
        return FakePipeline(self)

    async def expire(self, key: str, seconds: int) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.ttls[key] = seconds


class FakePipeline:
    def __init__(self, redis: FakeRedis):
        self.redis = redis
        self.ops: list[tuple[str, str]] = []

    def incr(self, key: str) -> None:
        self.ops.append(("incr", key))

    def ttl(self, key: str) -> None:
        self.ops.append(("ttl", key))

    async def execute(self):
        if self.redis.fail:
            raise ConnectionError("redis down")
        results = []
        for op, key in self.ops:
            if op == "incr":
                self.redis.counters[key] = self.redis.counters.get(key, 0) + 1
                results.append(self.redis.counters[key])
            else:
                results.append(self.redis.ttls.get(key, -2))
        return results


class TestCheckRateLimit:
    async def test_allows_requests_under_the_limit(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.rate_limit._redis", lambda: fake)

        limit = Limit(max_requests=3, window_seconds=60)
        for _ in range(3):
            allowed, _ = await check_rate_limit("analyze", "user:1", limit)
            assert allowed

    async def test_blocks_once_over_the_limit(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.rate_limit._redis", lambda: fake)

        limit = Limit(max_requests=2, window_seconds=60)
        await check_rate_limit("analyze", "user:1", limit)
        await check_rate_limit("analyze", "user:1", limit)

        allowed, retry_after = await check_rate_limit("analyze", "user:1", limit)
        assert not allowed
        assert retry_after > 0

    async def test_identities_have_separate_quotas(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.rate_limit._redis", lambda: fake)

        limit = Limit(max_requests=1, window_seconds=60)
        await check_rate_limit("analyze", "user:1", limit)

        # One tenant exhausting their quota must not affect another.
        allowed, _ = await check_rate_limit("analyze", "user:2", limit)
        assert allowed

    async def test_buckets_are_independent(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("app.platform.security.rate_limit._redis", lambda: fake)

        limit = Limit(max_requests=1, window_seconds=60)
        await check_rate_limit("analyze", "user:1", limit)

        allowed, _ = await check_rate_limit("build", "user:1", limit)
        assert allowed

    async def test_redis_outage_fails_open(self, monkeypatch):
        fake = FakeRedis(fail=True)
        monkeypatch.setattr("app.platform.security.rate_limit._redis", lambda: fake)

        # Documented trade-off: limits protect budget, so a Redis blip must not
        # take the whole API offline.
        allowed, _ = await check_rate_limit("analyze", "user:1", Limit(1, 60))
        assert allowed
