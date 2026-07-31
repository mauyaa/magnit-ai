from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.features.widgets import routes


def _widget() -> SimpleNamespace:
    return SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        target_url="https://example.com",
        source_evidence={"target_url": "https://example.com"},
        creation_brief={"mode": "autopilot"},
    )


def test_build_publish_does_not_wait_for_an_unused_result_backend(monkeypatch):
    publish = Mock()
    from app.platform.pipeline import tasks

    monkeypatch.setattr(tasks.build_widget_task, "apply_async", publish)

    routes._enqueue_build(
        _widget(),
        {"type": "audit_tool"},
        skip_deploy=False,
        architect_override=None,
    )

    publish.assert_called_once_with(
        kwargs={
            "widget_id": "11111111-1111-1111-1111-111111111111",
            "blueprint_dict": {"type": "audit_tool"},
            "url": "https://example.com",
            "skip_deploy": False,
            "architect_override_dict": None,
            "source_evidence_dict": {"target_url": "https://example.com"},
            "creation_brief_dict": {"mode": "autopilot"},
        },
        ignore_result=True,
        retry=False,
    )


def test_unavailable_queue_becomes_a_readable_service_error(monkeypatch):
    from app.platform.pipeline import tasks

    monkeypatch.setattr(
        tasks.build_widget_task,
        "apply_async",
        Mock(side_effect=ConnectionError("broker unavailable")),
    )

    with pytest.raises(HTTPException) as caught:
        routes._enqueue_build(
            _widget(),
            {"type": "audit_tool"},
            skip_deploy=False,
            architect_override=None,
        )

    assert caught.value.status_code == 503
    assert caught.value.detail == "build_queue_unavailable"
