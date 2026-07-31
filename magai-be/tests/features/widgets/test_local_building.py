"""The development path proves the same build-to-embed story without cloud infra."""

from __future__ import annotations

import json
import uuid
from unittest.mock import Mock

import pytest

from app.features.widgets import routes
from app.platform.config.settings import settings
from app.platform.pipeline import tasks
from app.platform.pipeline.events import RedisEventManager
from app.platform.security.locks import LockNotAcquired, process_lock


def test_dispatch_uses_the_local_runner_when_no_deployer_is_configured(monkeypatch):
    widget = type(
        "WidgetStub",
        (),
        {
            "id": uuid.uuid4(),
            "target_url": "https://example.com",
            "source_evidence": {"target_url": "https://example.com"},
            "creation_brief": {"mode": "autopilot"},
        },
    )()
    schedule = Mock()
    monkeypatch.setattr(settings, "vercel_api_token", "")
    monkeypatch.setattr(tasks, "schedule_local_widget_build", schedule)

    routes._dispatch_build(
        widget,
        {"type": "audit_tool"},
        skip_deploy=False,
        architect_override={"brand": {"primary_color": "#112233"}},
    )

    schedule.assert_called_once_with(
        str(widget.id),
        {"type": "audit_tool"},
        "https://example.com",
        publish=True,
        architect_override_dict={"brand": {"primary_color": "#112233"}},
        source_evidence_dict={"target_url": "https://example.com"},
        creation_brief_dict={"mode": "autopilot"},
    )


async def test_local_runner_reuses_the_pipeline_and_publishes_locally(monkeypatch):
    called: dict = {}

    async def capture(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(tasks, "_run_build_pipeline", capture)

    await tasks.run_local_widget_build(
        "widget-1",
        {"type": "audit_tool"},
        "https://example.com",
        publish=True,
    )

    assert called["args"][3] is True  # Vercel deploy is skipped.
    assert called["kwargs"]["local_publish"] is True
    assert called["kwargs"]["use_process_lock"] is True


async def test_process_lock_rejects_a_duplicate_local_build():
    async with process_lock("widget:test"):
        with pytest.raises(LockNotAcquired):
            async with process_lock("widget:test"):
                pass


async def test_local_progress_stream_needs_no_redis(monkeypatch):
    monkeypatch.setattr(settings, "vercel_api_token", "")
    manager = RedisEventManager()

    await manager.publish_stage(
        "widget-1",
        "codegen",
        "active",
        "Building the interface",
        progress=55.0,
    )
    stream = manager.event_stream("widget-1")
    event = await anext(stream)
    await stream.aclose()

    payload = json.loads(event.removeprefix("data: "))
    assert payload["stage"] == "codegen"
    assert payload["progress"] == 55.0


async def test_local_artifacts_are_real_iframeable_responses(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vercel_api_token", "")
    monkeypatch.setattr(settings, "widgets_dir", str(tmp_path))
    widget_id = str(uuid.uuid4())
    dist = tmp_path / widget_id / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Working tool</title>")
    (dist / "app.js").write_text("document.body.dataset.ready = 'true'")

    index = await client.get(f"/local-widgets/{widget_id}/")
    asset = await client.get(f"/local-widgets/{widget_id}/app.js")

    assert index.status_code == 200
    assert "Working tool" in index.text
    assert "x-frame-options" not in index.headers
    assert "frame-ancestors" in index.headers["content-security-policy"]
    assert asset.status_code == 200
    assert "javascript" in asset.headers["content-type"]


async def test_local_hosting_refuses_path_traversal(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vercel_api_token", "")
    monkeypatch.setattr(settings, "widgets_dir", str(tmp_path))
    widget_id = str(uuid.uuid4())
    dist = tmp_path / widget_id / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>")
    (tmp_path / "secret.txt").write_text("not public")

    response = await client.get(f"/local-widgets/{widget_id}/%2E%2E/%2E%2E/secret.txt")

    assert response.status_code == 404
