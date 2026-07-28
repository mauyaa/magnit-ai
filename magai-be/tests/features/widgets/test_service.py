"""Embed-code contract and deployment history / rollback behaviour."""

import pytest

from app.features.widgets.models import Widget, WidgetDeployment
from app.features.widgets.service import (
    WidgetBuildMissing,
    build_embed_code,
    record_deployment,
    rollback_widget,
)


class TestEmbedCode:
    def test_wraps_the_deployment_url(self):
        html = build_embed_code("https://magai-widget-abc123.vercel.app")
        assert 'src="https://magai-widget-abc123.vercel.app"' in html
        assert "<iframe" in html and "</iframe>" in html
        assert "magnit:resize" in html

    def test_never_points_at_the_backend(self):
        # Regression guard: the snippet used to point at the API's own /embed
        # route serving local disk files, making the Vercel deploy dead weight.
        html = build_embed_code("https://magai-widget-abc123.vercel.app")
        assert "/embed/" not in html

    def test_is_responsive_and_titled_for_accessibility(self):
        html = build_embed_code("https://example.vercel.app")
        assert 'width="100%"' in html
        assert "title=" in html


async def _widget(db, owner) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Calc",
        status="active",
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestDeploymentHistory:
    async def test_recording_a_deployment_updates_the_widget(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://v1.vercel.app", trigger="build")
        await db.commit()

        assert widget.deployment_url == "https://v1.vercel.app"
        assert widget.embed_code and "v1.vercel.app" in widget.embed_code
        assert widget.deployed_at is not None
        assert widget.status == "active"

    async def test_only_the_newest_deployment_is_current(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://v1.vercel.app", trigger="build")
        await record_deployment(db, widget, "https://v2.vercel.app", trigger="heal_brand_drift")
        await db.commit()

        from sqlalchemy import select

        rows = (
            (
                await db.execute(
                    select(WidgetDeployment).where(WidgetDeployment.widget_id == widget.id)
                )
            )
            .scalars()
            .all()
        )

        current = [r for r in rows if r.is_current]
        assert len(current) == 1
        assert current[0].deployment_url == "https://v2.vercel.app"


class TestRollback:
    async def test_rollback_repoints_to_the_previous_deployment(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://v1.vercel.app", trigger="build")
        await record_deployment(db, widget, "https://v2.vercel.app", trigger="heal_brand_drift")
        await db.commit()

        await rollback_widget(db, str(widget.id), user.id)
        await db.commit()

        # A bad heal must be undoable without a rebuild.
        assert widget.deployment_url == "https://v1.vercel.app"
        assert "v1.vercel.app" in (widget.embed_code or "")

    async def test_rollback_fails_when_there_is_no_history(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://only.vercel.app", trigger="build")
        await db.commit()

        with pytest.raises(WidgetBuildMissing):
            await rollback_widget(db, str(widget.id), user.id)

    async def test_rollback_is_recorded_as_its_own_event(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://v1.vercel.app", trigger="build")
        await record_deployment(db, widget, "https://v2.vercel.app", trigger="build")
        await db.commit()

        await rollback_widget(db, str(widget.id), user.id)
        await db.commit()

        from sqlalchemy import select

        triggers = (
            (
                await db.execute(
                    select(WidgetDeployment.trigger).where(WidgetDeployment.widget_id == widget.id)
                )
            )
            .scalars()
            .all()
        )
        assert "rollback" in triggers
