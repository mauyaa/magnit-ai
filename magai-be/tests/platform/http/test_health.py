"""Health endpoints, and the distinction an orchestrator acts on.

These three endpoints exist to be read by machines that will restart or
de-register the process based on what they say, so the interesting cases are the
unhappy ones: liveness must never fail for a dependency outage (that turns a
database blip into a restart loop), readiness must fail for one (that is how a
sick pod leaves the load balancer), and the split between the two has to hold.
"""

from __future__ import annotations

import asyncio

import pytest

from app.platform.http import health


def _stub_checks(monkeypatch, **results: str) -> None:
    """Pin the dependency probe results without touching Postgres or Redis."""
    checks = {
        "database": "connected",
        "redis_events": "connected",
        "celery_broker": "connected",
        "celery_backend": "connected",
    }
    checks.update(results)

    async def gather() -> dict[str, str]:
        return checks

    monkeypatch.setattr(health, "_gather_checks", gather)


class TestLiveness:
    async def test_reports_alive_without_touching_dependencies(self, client, monkeypatch):
        """If this ever consulted a dependency, an outage would become a restart loop."""

        async def explode() -> dict[str, str]:
            raise AssertionError("liveness must not probe dependencies")

        monkeypatch.setattr(health, "_gather_checks", explode)

        response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


class TestReadiness:
    async def test_ready_when_everything_answers(self, client, monkeypatch):
        _stub_checks(monkeypatch)

        response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @pytest.mark.parametrize("dependency", ["database", "redis_events", "celery_broker"])
    async def test_a_critical_dependency_pulls_the_pod_from_the_balancer(
        self, client, monkeypatch, dependency
    ):
        _stub_checks(monkeypatch, **{dependency: "unavailable"})

        response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

    async def test_a_dead_result_backend_degrades_builds_but_still_serves_reads(
        self, client, monkeypatch
    ):
        """Reads do not need the Celery result backend, so it must not fail readiness."""
        _stub_checks(monkeypatch, celery_backend="unavailable")

        response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        # Still reported, so an operator can see it.
        assert response.json()["checks"]["celery_backend"] == "unavailable"

    async def test_every_dependency_is_named_in_the_response(self, client, monkeypatch):
        _stub_checks(monkeypatch)

        checks = (await client.get("/health/ready")).json()["checks"]

        assert set(checks) == {"database", "redis_events", "celery_broker", "celery_backend"}


class TestAggregateHealth:
    async def test_ok_when_all_four_answer(self, client, monkeypatch):
        _stub_checks(monkeypatch)

        body = (await client.get("/health")).json()

        assert body["status"] == "ok"
        assert body["environment"] == "development"

    async def test_degraded_when_anything_is_down(self, client, monkeypatch):
        """Unlike readiness, the human-facing view degrades on *any* failure."""
        _stub_checks(monkeypatch, celery_backend="unavailable")

        body = (await client.get("/health")).json()

        assert body["status"] == "degraded"

    async def test_always_answers_200_so_a_dashboard_can_read_it(self, client, monkeypatch):
        _stub_checks(monkeypatch, database="unavailable")

        assert (await client.get("/health")).status_code == 200


class TestProbes:
    async def test_database_timeout_is_distinguished_from_an_error(self, monkeypatch):
        """ "timeout" and "unavailable" send an operator to different places."""

        class SlowSession:
            async def __aenter__(self):
                await asyncio.sleep(10)
                return self

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(health, "async_session_factory", SlowSession)
        monkeypatch.setattr(health, "CHECK_TIMEOUT_SECONDS", 0.01)

        assert await health._check_database() == (False, "timeout")

    async def test_database_error_is_reported_as_unavailable(self, monkeypatch):
        class BrokenSession:
            async def __aenter__(self):
                raise ConnectionRefusedError("no postgres")

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(health, "async_session_factory", BrokenSession)

        assert await health._check_database() == (False, "unavailable")

    async def test_unreachable_redis_is_unavailable(self, monkeypatch):
        class BrokenRedis:
            @staticmethod
            def from_url(url, **kwargs):
                raise ConnectionError("no redis")

        monkeypatch.setattr(health.aioredis, "Redis", BrokenRedis)

        assert await health._check_redis("redis://localhost:6379/0") == (False, "unavailable")

    async def test_a_probe_connection_that_will_not_close_does_not_change_the_verdict(
        self, monkeypatch
    ):
        """Redis answered, so it is up; failing to hang up is not a health problem."""
        closed: list[bool] = []

        class Probe:
            async def ping(self):
                return True

            async def aclose(self):
                closed.append(True)
                raise OSError("connection reset")

        class Factory:
            @staticmethod
            def from_url(url, **kwargs):
                return Probe()

        monkeypatch.setattr(health.aioredis, "Redis", Factory)

        assert await health._check_redis("redis://localhost:6379/0") == (True, "connected")
        assert closed == [True]
