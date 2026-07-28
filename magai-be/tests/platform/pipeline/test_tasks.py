"""The Celery layer: build orchestration and the scheduled self-heal sweep.

``heal.py`` decides whether a widget has drifted. This module decides which
widgets get asked, what happens to the ones that keep failing, and what a build
does when it goes wrong — all of it running unattended on a schedule, which is
exactly the code nobody is watching when it misbehaves.

The Celery decorators are not exercised through a broker. ``build_widget_task``
is called as a plain function with a stand-in for the bound ``self``, which is
the only part of the Task API it actually touches.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from app.features.users.models import User
from app.features.widgets.models import Widget, WidgetHealEvent
from app.platform.config.settings import settings
from app.platform.pipeline import tasks
from app.platform.security.locks import LockNotAcquired
from app.platform.security.passwords import hash_password


async def make_user(session_factory) -> User:
    async with session_factory() as session:
        account = User(
            email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("correct-horse-battery-99"),
            role="owner",
            email_verified=True,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account


async def make_widget(session_factory, user: User, **overrides) -> Widget:
    fields = {
        "user_id": user.id,
        "target_url": "https://example.com/",
        "widget_type": "roi_calculator",
        "title": "Revenue calculator",
        "status": "active",
        "deployment_url": "https://w.vercel.app",
    }
    fields.update(overrides)
    async with session_factory() as session:
        widget = Widget(**fields)
        session.add(widget)
        await session.commit()
        await session.refresh(widget)
        return widget


@pytest.fixture
def use_test_db(monkeypatch, session_factory):
    """Point the task module's own session factory at the test database."""
    monkeypatch.setattr(tasks, "async_session_factory", session_factory)
    return session_factory


@pytest.fixture
def no_lock(monkeypatch):
    """Grant the distributed lock without Redis."""

    @asynccontextmanager
    async def granted(*args, **kwargs):
        yield True

    monkeypatch.setattr(tasks, "distributed_lock", granted)


@pytest.fixture
def held_lock(monkeypatch):
    """Refuse the distributed lock, as a second worker would."""

    @asynccontextmanager
    async def refused(*args, **kwargs):
        raise LockNotAcquired("held")
        yield  # pragma: no cover

    monkeypatch.setattr(tasks, "distributed_lock", refused)


class TestWidgetLockKey:
    def test_building_and_healing_contend_on_one_key(self):
        """Separate build/heal keys let a rebuild race a heal into the same directory."""
        assert tasks.widget_lock_key("abc") == "widget:abc"


class TestSelectWidgetsToHeal:
    async def test_picks_active_widgets_that_are_due(self, use_test_db, session_factory):
        user = await make_user(session_factory)
        stale = datetime.now(UTC) - timedelta(minutes=settings.self_heal_interval_minutes + 60)
        due = await make_widget(session_factory, user, last_heal_check_at=stale)

        selected = await tasks._select_widgets_to_heal()

        assert selected == [str(due.id)]

    async def test_never_checked_widgets_are_due(self, use_test_db, session_factory):
        user = await make_user(session_factory)
        fresh = await make_widget(session_factory, user, last_heal_check_at=None)

        assert await tasks._select_widgets_to_heal() == [str(fresh.id)]

    async def test_recently_checked_widgets_are_skipped(self, use_test_db, session_factory):
        user = await make_user(session_factory)
        await make_widget(session_factory, user, last_heal_check_at=datetime.now(UTC))

        assert await tasks._select_widgets_to_heal() == []

    async def test_inactive_widgets_are_skipped(self, use_test_db, session_factory):
        user = await make_user(session_factory)
        await make_widget(session_factory, user, status="failed", last_heal_check_at=None)

        assert await tasks._select_widgets_to_heal() == []

    async def test_repeatedly_failing_widgets_are_abandoned(self, use_test_db, session_factory):
        """Otherwise a permanently broken widget burns an AI call every sweep, forever."""
        user = await make_user(session_factory)
        await make_widget(
            session_factory,
            user,
            last_heal_check_at=None,
            heal_failure_count=settings.self_heal_max_failures,
        )

        assert await tasks._select_widgets_to_heal() == []

    async def test_never_checked_widgets_are_served_before_stale_ones(
        self, use_test_db, session_factory
    ):
        """Nulls-first ordering is what stops a new widget being starved by old ones."""
        user = await make_user(session_factory)
        stale = datetime.now(UTC) - timedelta(days=30)
        await make_widget(session_factory, user, title="old", last_heal_check_at=stale)
        never = await make_widget(session_factory, user, title="new", last_heal_check_at=None)

        selected = await tasks._select_widgets_to_heal()

        assert selected[0] == str(never.id)

    async def test_batch_size_bounds_the_sweep(self, use_test_db, session_factory, monkeypatch):
        monkeypatch.setattr(settings, "self_heal_batch_size", 2)
        user = await make_user(session_factory)
        for index in range(4):
            await make_widget(session_factory, user, title=f"w{index}", last_heal_check_at=None)

        assert len(await tasks._select_widgets_to_heal()) == 2


class TestHealOneWidget:
    async def test_widget_that_went_inactive_is_left_alone(
        self, use_test_db, session_factory, no_lock, monkeypatch
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user, status="failed")
        called = {"brand": False}

        async def spy(session, w):
            called["brand"] = True

        monkeypatch.setattr(tasks, "_heal_brand_drift", spy)
        monkeypatch.setattr(tasks, "_heal_deploy_health", spy)

        await tasks._heal_one_widget(str(widget.id))

        assert called["brand"] is False

    async def test_check_time_is_stamped_before_the_checks_run(
        self, use_test_db, session_factory, no_lock, monkeypatch
    ):
        """A check that crashes the worker must not be retried in a tight loop."""
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user, last_heal_check_at=None)
        stamps: list[datetime | None] = []

        async def record(session, w):
            stamps.append(w.last_heal_check_at)

        monkeypatch.setattr(tasks, "_heal_brand_drift", record)
        monkeypatch.setattr(tasks, "_heal_deploy_health", record)

        await tasks._heal_one_widget(str(widget.id))

        assert stamps[0] is not None

    async def test_a_widget_already_being_built_is_skipped(
        self, use_test_db, session_factory, held_lock, monkeypatch
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)
        called = {"brand": False}

        async def spy(session, w):
            called["brand"] = True

        monkeypatch.setattr(tasks, "_heal_brand_drift", spy)

        # Swallowed, not raised: a busy widget is normal, not an incident.
        await tasks._heal_one_widget(str(widget.id))

        assert called["brand"] is False


class TestHealDeployHealth:
    async def test_reachable_deployment_records_nothing(
        self, use_test_db, session_factory, monkeypatch
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)
        monkeypatch.setattr(tasks, "check_deploy_health", _async_return(True))

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_deploy_health(session, live)
            await session.commit()

        assert await _heal_events(session_factory, widget.id) == []

    async def test_unreachable_deployment_without_artifacts_is_recorded_as_failed(
        self, use_test_db, session_factory, monkeypatch
    ):
        """Nothing to republish is a real outcome, and the owner should see it."""
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)
        monkeypatch.setattr(tasks, "check_deploy_health", _async_return(False))

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_deploy_health(session, live)
            await session.commit()

        events = await _heal_events(session_factory, widget.id)
        assert [(e.check_type, e.status) for e in events] == [("deploy_health", "failed")]
        assert "no saved build artifacts" in events[0].diff_summary["error"]

    async def test_a_failing_check_increments_the_backoff_counter(
        self, use_test_db, session_factory, monkeypatch
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)
        monkeypatch.setattr(tasks, "check_deploy_health", _async_return(False))

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_deploy_health(session, live)
            await session.commit()

        async with session_factory() as session:
            refreshed = await session.get(Widget, widget.id)
            assert refreshed.heal_failure_count == 1

    async def test_an_erroring_check_does_not_raise_out_of_the_sweep(
        self, use_test_db, session_factory, monkeypatch
    ):
        async def boom(widget):
            raise RuntimeError("network gone")

        monkeypatch.setattr(tasks, "check_deploy_health", boom)
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_deploy_health(session, live)

        assert await _heal_events(session_factory, widget.id) == []


class TestHealBrandDrift:
    async def test_brand_check_respects_its_own_slower_cadence(self, monkeypatch):
        """Re-extracting a brand costs an AI call, so it runs less often than the sweep.

        Deliberately not round-tripped through the database: SQLite hands back
        naive datetimes where Postgres returns aware ones, so a persisted
        timestamp would fail this comparison for a reason that does not exist in
        production. The gate itself is what is under test.
        """
        called = {"checked": False}

        async def spy(w):
            called["checked"] = True
            raise AssertionError("should not be reached")

        monkeypatch.setattr(tasks, "check_brand_drift", spy)
        widget = _StubWidget()
        widget.last_brand_check_at = datetime.now(UTC)

        await tasks._heal_brand_drift(_NullSession(), widget)

        assert called["checked"] is False

    async def test_stable_brand_records_a_no_drift_event_and_clears_failures(
        self, use_test_db, session_factory, monkeypatch
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user, heal_failure_count=2)
        monkeypatch.setattr(tasks, "check_brand_drift", _async_return(_drift(drifted=False)))

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_brand_drift(session, live)
            await session.commit()

        events = await _heal_events(session_factory, widget.id)
        assert [(e.check_type, e.status) for e in events] == [("brand_drift", "no_drift")]
        async with session_factory() as session:
            assert (await session.get(Widget, widget.id)).heal_failure_count == 0

    async def test_fresh_evidence_is_stored_even_when_nothing_drifted(
        self, use_test_db, session_factory, monkeypatch
    ):
        """The fingerprint is the short-circuit for the next sweep; it has to move."""
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)
        monkeypatch.setattr(tasks, "check_brand_drift", _async_return(_drift(drifted=False)))

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_brand_drift(session, live)
            await session.commit()

        async with session_factory() as session:
            refreshed = await session.get(Widget, widget.id)
            assert refreshed.source_brand_fingerprint == "b" * 64
            assert refreshed.last_brand_check_at is not None

    async def test_drift_without_a_replacement_design_is_recorded_as_failed(
        self, use_test_db, session_factory, monkeypatch
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)
        monkeypatch.setattr(
            tasks,
            "check_brand_drift",
            _async_return(_drift(drifted=True, architect_output=None)),
        )

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_brand_drift(session, live)
            await session.commit()

        events = await _heal_events(session_factory, widget.id)
        assert events[0].status == "failed"
        async with session_factory() as session:
            assert (await session.get(Widget, widget.id)).heal_failure_count == 1

    async def test_an_erroring_check_counts_as_a_failure_without_raising(
        self, use_test_db, session_factory, monkeypatch
    ):
        async def boom(widget):
            raise RuntimeError("site unreachable")

        monkeypatch.setattr(tasks, "check_brand_drift", boom)
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)

        async with session_factory() as session:
            live = await session.get(Widget, widget.id)
            await tasks._heal_brand_drift(session, live)
            await session.commit()

        async with session_factory() as session:
            assert (await session.get(Widget, widget.id)).heal_failure_count == 1


class TestSweep:
    async def test_one_widget_failing_does_not_abort_the_rest(
        self, use_test_db, session_factory, monkeypatch
    ):
        user = await make_user(session_factory)
        first = await make_widget(session_factory, user, title="a", last_heal_check_at=None)
        second = await make_widget(session_factory, user, title="b", last_heal_check_at=None)
        seen: list[str] = []

        async def flaky(widget_id: str):
            seen.append(widget_id)
            if widget_id == str(first.id):
                raise RuntimeError("boom")

        monkeypatch.setattr(tasks, "_heal_one_widget", flaky)

        result = await tasks._run_self_heal_sweep()

        assert result["checked"] == 2
        assert str(second.id) in seen

    def test_disabled_configuration_short_circuits_the_task(self, monkeypatch):
        monkeypatch.setattr(settings, "self_heal_enabled", False)

        assert tasks.run_self_heal_sweep() == {"skipped": True}

    def test_a_second_concurrent_sweep_stands_down(self, monkeypatch):
        monkeypatch.setattr(settings, "self_heal_enabled", True)

        async def refuse():
            raise LockNotAcquired("held")

        monkeypatch.setattr(tasks, "_sweep_with_lock", refuse)

        assert tasks.run_self_heal_sweep() == {
            "skipped": True,
            "reason": "sweep_already_running",
        }


class TestBuildWidgetTask:
    """``bind=True`` means Celery supplies ``self``, so the task is called with
    its real arguments and its retry behaviour is driven through the request
    stack rather than by passing a stand-in in the first position."""

    def test_a_widget_already_building_is_not_built_twice(self, monkeypatch):
        async def refuse(*args, **kwargs):
            raise LockNotAcquired("held")

        monkeypatch.setattr(tasks, "_run_build_pipeline", refuse)

        with build_task(monkeypatch):
            result = tasks.build_widget_task(
                "w1", {"type": "roi_calculator"}, "https://example.com/"
            )

        assert result == {
            "success": False,
            "widget_id": "w1",
            "error": "build_already_running",
        }

    def test_success_is_reported_back(self, monkeypatch):
        async def succeed(*args, **kwargs):
            return None

        monkeypatch.setattr(tasks, "_run_build_pipeline", succeed)

        with build_task(monkeypatch):
            result = tasks.build_widget_task(
                "w1", {"type": "roi_calculator"}, "https://example.com/"
            )

        assert result == {"success": True, "widget_id": "w1"}

    @pytest.mark.parametrize(
        "message",
        ["SyntaxError: unexpected token", "invalid_blueprint_index", "No module named 'x'"],
    )
    def test_deterministic_failures_are_not_retried(self, monkeypatch, message):
        """Retrying an identical job that failed deterministically just wastes a slot."""
        marked: dict = {}

        async def fail(*args, **kwargs):
            raise RuntimeError(message)

        async def capture(widget_id, **kwargs):
            marked.update(kwargs)

        monkeypatch.setattr(tasks, "_run_build_pipeline", fail)
        monkeypatch.setattr(tasks, "_update_build_progress", capture)

        with build_task(monkeypatch) as state:
            result = tasks.build_widget_task(
                "w1", {"type": "roi_calculator"}, "https://example.com/"
            )

        assert result["success"] is False
        assert state["retried"] is False
        assert marked["status"] == "failed"

    def test_a_transient_failure_is_retried(self, monkeypatch):
        """A 503 from the model provider is worth one more attempt."""

        async def fail(*args, **kwargs):
            raise RuntimeError("gemini returned 503")

        monkeypatch.setattr(tasks, "_run_build_pipeline", fail)

        with build_task(monkeypatch) as state:
            with pytest.raises(_Retry):
                tasks.build_widget_task("w1", {"type": "roi_calculator"}, "https://example.com/")

        assert state["retried"] is True

    def test_the_last_attempt_marks_the_widget_failed_instead_of_retrying(self, monkeypatch):
        marked: dict = {}

        async def fail(*args, **kwargs):
            raise RuntimeError("gemini returned 503")

        async def capture(widget_id, **kwargs):
            marked.update(kwargs)

        monkeypatch.setattr(tasks, "_run_build_pipeline", fail)
        monkeypatch.setattr(tasks, "_update_build_progress", capture)

        # retries == max_retries: the budget is spent, so the owner is told.
        with build_task(monkeypatch, retries=1) as state:
            result = tasks.build_widget_task(
                "w1", {"type": "roi_calculator"}, "https://example.com/"
            )

        assert result["success"] is False
        assert state["retried"] is False
        assert marked["build_error"] == "gemini returned 503"


class TestSaveToWorkspace:
    def test_missing_build_directory_is_a_warning_not_a_crash(self, tmp_path, monkeypatch):
        """The deploy already succeeded; failing here would undo a working build."""
        monkeypatch.setattr(tasks, "workspace_dir", lambda widget_id: tmp_path / widget_id)

        tasks._save_to_workspace("w1", _StubWidget(), _StubBuildResult(project_dir=None))

        assert not (tmp_path / "w1").exists()

    def test_artifacts_and_metadata_are_published_atomically(self, tmp_path, monkeypatch):
        source = tmp_path / "build"
        (source / "dist").mkdir(parents=True)
        (source / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
        monkeypatch.setattr(tasks, "workspace_dir", lambda widget_id: tmp_path / widget_id)

        tasks._save_to_workspace("w1", _StubWidget(), _StubBuildResult(project_dir=str(source)))

        saved = tmp_path / "w1"
        assert (saved / "dist" / "index.html").is_file()
        assert (saved / "meta.json").is_file()
        # The staging directory is renamed into place, never left behind.
        assert not (tmp_path / "w1.incoming").exists()

    def test_a_previous_build_is_replaced(self, tmp_path, monkeypatch):
        saved = tmp_path / "w1"
        (saved / "dist").mkdir(parents=True)
        (saved / "dist" / "stale.html").write_text("old", encoding="utf-8")
        source = tmp_path / "build"
        (source / "dist").mkdir(parents=True)
        (source / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
        monkeypatch.setattr(tasks, "workspace_dir", lambda widget_id: tmp_path / widget_id)

        tasks._save_to_workspace("w1", _StubWidget(), _StubBuildResult(project_dir=str(source)))

        assert not (saved / "dist" / "stale.html").exists()
        assert (saved / "dist" / "index.html").is_file()


class TestWorkspaceBrandOverrides:
    async def test_a_workspace_without_a_brand_kit_overrides_nothing(
        self, use_test_db, session_factory
    ):
        user = await make_user(session_factory)
        widget = await make_widget(session_factory, user)

        assert await tasks._workspace_brand_overrides(str(widget.id)) == (None, None)

    async def test_an_unknown_widget_overrides_nothing(self, use_test_db):
        assert await tasks._workspace_brand_overrides(str(uuid.uuid4())) == (None, None)

    async def test_a_failure_to_read_the_kit_degrades_instead_of_failing_the_build(
        self, monkeypatch
    ):
        """The customer is watching this build; a brand-kit read is not worth losing it."""

        def broken():
            raise RuntimeError("database gone")

        monkeypatch.setattr(tasks, "async_session_factory", broken)

        assert await tasks._workspace_brand_overrides("w1") == (None, None)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


class _Retry(Exception):
    """Stands in for ``celery.exceptions.Retry``.

    Called outside a worker, the real ``Task.retry`` re-raises the original
    exception instead of signalling a retry, which makes "was this retried?"
    indistinguishable from "did this fail?". Substituting it keeps that
    distinction, which is the whole point of these tests.
    """


@contextmanager
def build_task(monkeypatch, *, retries: int = 0):
    """Run ``build_widget_task`` with a known retry count and an observable retry."""
    task = tasks.build_widget_task
    state = {"retried": False}

    def fake_retry(exc=None):
        state["retried"] = True
        return _Retry()

    monkeypatch.setattr(task, "retry", fake_retry)
    task.push_request(retries=retries)
    try:
        yield state
    finally:
        task.pop_request()


class _NullSession:
    """Enough of an AsyncSession for the paths that return before touching it."""

    def add(self, _instance) -> None:  # pragma: no cover - defensive
        raise AssertionError("nothing should be recorded on this path")

    async def flush(self) -> None:  # pragma: no cover - defensive
        raise AssertionError("nothing should be flushed on this path")


class _StubWidget:
    def __init__(self) -> None:
        self.id = "w1"
        self.target_url = "https://example.com/"
        self.widget_type = "roi_calculator"
        self.title = "Revenue calculator"
        self.brand_tokens: dict = {}
        self.visual_language: dict = {}
        self.widget_logic: dict = {}
        self.copywriting: dict = {}
        self.design_tokens: dict = {}
        self.last_brand_check_at = None
        self.heal_failure_count = 0


class _StubBuildResult:
    def __init__(self, project_dir: str | None) -> None:
        self.project_dir = project_dir


def _async_return(value):
    async def _call(*args, **kwargs):
        return value

    return _call


class _StubEvidence:
    content_fingerprint = "a" * 64
    brand_fingerprint = "b" * 64

    def model_dump(self, mode: str = "python") -> dict:
        return {"target_url": "https://example.com/"}


class _StubDrift:
    def __init__(self, drifted: bool, architect_output, diff: dict) -> None:
        self.drifted = drifted
        self.architect_output = architect_output
        self.diff = diff
        self.evidence = _StubEvidence()


def _drift(*, drifted: bool, architect_output=None, diff: dict | None = None) -> _StubDrift:
    return _StubDrift(
        drifted, architect_output, diff or {"primary_color": {"old": "a", "new": "b"}}
    )


async def _heal_events(session_factory, widget_id) -> list[WidgetHealEvent]:
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(WidgetHealEvent).where(WidgetHealEvent.widget_id == widget_id)
        )
        return list(result.scalars().all())
