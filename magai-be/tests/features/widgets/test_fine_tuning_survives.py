"""An edit the customer made must outlive the build that failed.

Fine-tuning lived in one browser tab's session storage. The client cleared it as
soon as the build was enqueued, and the database only learned about it if the
whole build then succeeded. So a provider outage, a bad generation or a deploy
that timed out silently discarded every change the customer had made — and the
screen they were sent back to rebuilt the version from before they touched it,
with nothing anywhere saying so.
"""

from __future__ import annotations

import pytest

from app.features.widgets.models import Widget
from app.platform.pipeline.schemas import ArchitectOutput, BrandExtraction, MathLogic, WidgetType

EDITED_HEADLINE = "What is a clearer booking path worth to this practice?"


def _override() -> dict:
    """A design as the review screen would send it, with an edit in it."""
    return ArchitectOutput(
        widget_type=WidgetType.ROI_CALCULATOR,
        brand=BrandExtraction(
            primary_color="#123456",
            secondary_color="#222222",
            background_color="#ffffff",
            accent_color="#b8e430",
            font_headings="Inter",
            font_body="Inter",
            tone="direct",
        ),
        logic=MathLogic(formula="a * b", variables=[], example_calculation="2 * 3 = 6"),
        copywriting={"headline": EDITED_HEADLINE},
    ).model_dump(mode="json")


async def _widget(db, owner, **overrides) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Calc",
        status=overrides.pop("status", "analyzed"),
        blueprints=[
            {
                "type": "roi_calculator",
                "title": "ROI Calculator",
                "description": "d",
                "rationale": "r",
            }
        ],
        copywriting={"headline": "The version the model first proposed"},
        **overrides,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


@pytest.fixture
def quiet_queue(monkeypatch):
    """Enqueue nothing: these tests are about what is saved, not what runs."""
    monkeypatch.setattr("app.features.widgets.routes._enqueue_build", lambda *a, **k: None)


class TestFineTuningIsPersistedBeforeTheBuild:
    async def test_the_edit_is_saved_when_the_build_starts(self, as_user, db, user, quiet_queue):
        widget = await _widget(db, user)

        response = await as_user(user).post(
            "/api/widgets/build",
            json={
                "widget_id": str(widget.id),
                "blueprint_index": 0,
                "architect_override": _override(),
            },
        )

        assert response.status_code == 200
        await db.refresh(widget)
        # Saved now, not on success. This is the whole fix.
        assert widget.copywriting["headline"] == EDITED_HEADLINE
        assert widget.brand_tokens["primary_color"] == "#123456"

    async def test_resuming_a_failed_build_returns_the_edited_version(
        self, as_user, db, user, quiet_queue
    ):
        """The screen the customer lands on after a failure.

        It reconstructs the design from the widget's own columns, so if the edit
        was never written there the customer is handed back the version they
        already rejected.
        """
        widget = await _widget(db, user)

        await as_user(user).post(
            "/api/widgets/build",
            json={
                "widget_id": str(widget.id),
                "blueprint_index": 0,
                "architect_override": _override(),
            },
        )
        widget.status = "failed"
        widget.build_error = "the provider was unavailable"
        await db.commit()

        resumed = await as_user(user).get(f"/api/widgets/{widget.id}/build-resume")

        assert resumed.status_code == 200
        concept = resumed.json()["concept"]
        assert concept["architect"]["copywriting"]["headline"] == EDITED_HEADLINE
        assert concept["architect"]["brand"]["primary_color"] == "#123456"

    async def test_retrying_a_failed_build_replays_the_edit(self, as_user, db, user, monkeypatch):
        """ "Try again" used to mean "try again without my changes"."""
        dispatched: list[dict | None] = []
        monkeypatch.setattr(
            "app.features.widgets.routes._enqueue_build",
            lambda widget, blueprint, skip_deploy, override: dispatched.append(override),
        )

        widget = await _widget(db, user)
        await as_user(user).post(
            "/api/widgets/build",
            json={
                "widget_id": str(widget.id),
                "blueprint_index": 0,
                "architect_override": _override(),
            },
        )
        widget.status = "failed"
        await db.commit()

        response = await as_user(user).post(f"/api/widgets/{widget.id}/retry")

        assert response.status_code == 200
        assert dispatched[-1] is not None
        assert dispatched[-1]["copywriting"]["headline"] == EDITED_HEADLINE

    async def test_a_build_without_an_edit_leaves_the_design_alone(
        self, as_user, db, user, quiet_queue
    ):
        """Nothing to persist is not the same as persisting nothing."""
        widget = await _widget(db, user)
        original = dict(widget.copywriting)

        response = await as_user(user).post(
            "/api/widgets/build",
            json={"widget_id": str(widget.id), "blueprint_index": 0},
        )

        assert response.status_code == 200
        await db.refresh(widget)
        assert widget.copywriting == original
