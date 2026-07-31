"""Embed-code contract and deployment history / rollback behaviour."""

import pytest
from sqlalchemy import select

from app.features.widgets import service
from app.features.widgets.models import Widget, WidgetDeployment
from app.features.widgets.service import (
    RollbackUnavailable,
    WidgetBuildMissing,
    build_embed_code,
    record_deployment,
    rollback_widget,
)

# The tool's permanent hostname: one project alias resolving to whatever build is
# currently live. Every deploy below reports it, exactly as the provider does.
ALIAS = "https://magai-widget-abc123.vercel.app"


class TestEmbedCode:
    def test_wraps_the_embed_address(self):
        html = build_embed_code(ALIAS)
        assert f'src="{ALIAS}"' in html
        assert "<iframe" in html and "</iframe>" in html
        assert "magnit:resize" in html

    def test_never_points_at_the_backend(self):
        # Regression guard: the snippet used to point at the API's own /embed
        # route serving local disk files, making the Vercel deploy dead weight.
        # It also must not depend on this API being up: the page it lives on
        # belongs to a customer, and our downtime is not their downtime.
        html = build_embed_code(ALIAS)
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
        await record_deployment(
            db, widget, "https://v1.vercel.app", trigger="build", embed_url=ALIAS
        )
        await db.commit()

        assert widget.deployment_url == "https://v1.vercel.app"
        assert widget.embed_url == ALIAS
        assert widget.embed_code and ALIAS in widget.embed_code
        assert widget.deployed_at is not None
        assert widget.status == "active"

    async def test_the_embed_address_survives_a_rebuild(self, db, user):
        """The property the customer's own website depends on.

        They pasted a snippet into a page we cannot edit. If the address inside
        it changed when the tool was rebuilt, that page would keep serving one
        frozen build, and nothing on our side would ever notice.
        """
        widget = await _widget(db, user)
        await record_deployment(
            db, widget, "https://v1.vercel.app", trigger="build", embed_url=ALIAS
        )
        first_snippet = widget.embed_code

        await record_deployment(
            db, widget, "https://v2.vercel.app", trigger="build", embed_url=ALIAS
        )
        await db.commit()

        assert widget.deployment_url == "https://v2.vercel.app"
        assert widget.embed_code == first_snippet

    async def test_a_repair_cannot_move_the_embed_address(self, db, user):
        """Self-healing runs unattended. It must never require a re-paste."""
        widget = await _widget(db, user)
        await record_deployment(
            db, widget, "https://v1.vercel.app", trigger="build", embed_url=ALIAS
        )
        first_snippet = widget.embed_code

        # A provider reporting a different alias — a renamed project, a changed
        # suffix — must not be able to rewrite an address already out in the
        # world on someone else's website.
        await record_deployment(
            db,
            widget,
            "https://v2.vercel.app",
            trigger="heal_deploy_health",
            embed_url="https://something-else.vercel.app",
        )
        await db.commit()

        assert widget.embed_url == ALIAS
        assert widget.embed_code == first_snippet

    async def test_only_the_newest_deployment_is_current(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://v1.vercel.app", trigger="build")
        await record_deployment(db, widget, "https://v2.vercel.app", trigger="heal_brand_drift")
        await db.commit()

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
    async def test_rollback_moves_the_live_build_not_just_our_records(self, db, user, monkeypatch):
        promoted: list[tuple[str, str]] = []

        async def fake_promote(deployment_id: str, widget_id: str) -> None:
            promoted.append((deployment_id, widget_id))

        monkeypatch.setattr(service, "promote_deployment", fake_promote)

        widget = await _widget(db, user)
        await record_deployment(
            db,
            widget,
            "https://v1.vercel.app",
            trigger="build",
            embed_url=ALIAS,
            provider_deployment_id="dpl_1",
        )
        snippet = widget.embed_code
        await record_deployment(
            db,
            widget,
            "https://v2.vercel.app",
            trigger="heal_brand_drift",
            embed_url=ALIAS,
            provider_deployment_id="dpl_2",
        )
        await db.commit()

        await rollback_widget(db, str(widget.id), user.id)
        await db.commit()

        # A bad heal must be undoable without a rebuild — and without the
        # customer touching the page they pasted the snippet into.
        assert widget.deployment_url == "https://v1.vercel.app"
        assert widget.embed_code == snippet
        assert promoted == [("dpl_1", str(widget.id))]

    async def test_a_rollback_the_provider_refuses_is_reported_as_a_failure(
        self, db, user, monkeypatch
    ):
        """Silence here leaves the broken build serving while we claim otherwise."""

        async def refuse(deployment_id: str, widget_id: str) -> None:
            raise RuntimeError("Vercel alias promotion failed: 403")

        monkeypatch.setattr(service, "promote_deployment", refuse)

        widget = await _widget(db, user)
        await record_deployment(
            db,
            widget,
            "https://v1.vercel.app",
            trigger="build",
            embed_url=ALIAS,
            provider_deployment_id="dpl_1",
        )
        await record_deployment(
            db,
            widget,
            "https://v2.vercel.app",
            trigger="build",
            embed_url=ALIAS,
            provider_deployment_id="dpl_2",
        )
        await db.commit()

        with pytest.raises(RollbackUnavailable):
            await rollback_widget(db, str(widget.id), user.id)

    async def test_a_build_with_no_provider_id_cannot_be_rolled_back_silently(self, db, user):
        """Deployed before we recorded provider ids: say so rather than pretend."""
        widget = await _widget(db, user)
        await record_deployment(
            db, widget, "https://v1.vercel.app", trigger="build", embed_url=ALIAS
        )
        await record_deployment(
            db, widget, "https://v2.vercel.app", trigger="build", embed_url=ALIAS
        )
        await db.commit()

        with pytest.raises(RollbackUnavailable):
            await rollback_widget(db, str(widget.id), user.id)

    async def test_a_locally_hosted_tool_rolls_back_without_a_provider(self, db, user):
        """One address serving whatever is on disk: there is nothing to re-point."""
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://local/tool/", trigger="local_build")
        await record_deployment(db, widget, "https://local/tool/", trigger="local_build")
        await db.commit()

        await rollback_widget(db, str(widget.id), user.id)
        await db.commit()

        assert widget.embed_url == "https://local/tool/"

    async def test_rollback_fails_when_there_is_no_history(self, db, user):
        widget = await _widget(db, user)
        await record_deployment(db, widget, "https://only.vercel.app", trigger="build")
        await db.commit()

        with pytest.raises(WidgetBuildMissing):
            await rollback_widget(db, str(widget.id), user.id)

    async def test_rollback_is_recorded_as_its_own_event(self, db, user, monkeypatch):
        async def fake_promote(deployment_id: str, widget_id: str) -> None:
            return None

        monkeypatch.setattr(service, "promote_deployment", fake_promote)

        widget = await _widget(db, user)
        await record_deployment(
            db,
            widget,
            "https://v1.vercel.app",
            trigger="build",
            embed_url=ALIAS,
            provider_deployment_id="dpl_1",
        )
        await record_deployment(
            db,
            widget,
            "https://v2.vercel.app",
            trigger="build",
            embed_url=ALIAS,
            provider_deployment_id="dpl_2",
        )
        await db.commit()

        await rollback_widget(db, str(widget.id), user.id)
        await db.commit()

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
