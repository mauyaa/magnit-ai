"""Impression tracking, conversion rate, and the email-verification gate."""

import uuid

from app.features.widgets.models import Widget
from app.features.widgets.service import record_impression


async def _widget(db, owner, **overrides) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Calc",
        status=overrides.pop("status", "active"),
        blueprints=[
            {
                "type": "roi_calculator",
                "title": "ROI Calculator",
                "description": "d",
                "rationale": "r",
            }
        ],
        **overrides,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestRecordImpression:
    async def test_increments_the_counter(self, db, user):
        widget = await _widget(db, user)
        assert await record_impression(db, str(widget.id)) is True
        await db.commit()
        await db.refresh(widget)
        assert widget.impressions_count == 1

    async def test_counts_each_view(self, db, user):
        widget = await _widget(db, user)
        for _ in range(3):
            await record_impression(db, str(widget.id))
        await db.commit()
        await db.refresh(widget)
        assert widget.impressions_count == 3

    async def test_ignores_widgets_that_are_not_live(self, db, user):
        widget = await _widget(db, user, status="analyzed")
        # A widget still building is not embedded anywhere, so a view is spurious.
        assert await record_impression(db, str(widget.id)) is False
        await db.commit()
        await db.refresh(widget)
        assert widget.impressions_count == 0

    async def test_unknown_widget_reports_false(self, db):
        assert await record_impression(db, str(uuid.uuid4())) is False

    async def test_non_uuid_is_handled(self, db):
        assert await record_impression(db, "garbage") is False


class TestImpressionEndpoint:
    async def test_needs_no_authentication(self, client, db, user):
        widget = await _widget(db, user)
        response = await client.post(f"/api/widgets/{widget.id}/impression")
        assert response.status_code == 204

    async def test_unknown_widget_still_returns_204(self, client):
        # A 404 here would let anyone probe which widget ids exist.
        response = await client.post(f"/api/widgets/{uuid.uuid4()}/impression")
        assert response.status_code == 204

    async def test_deployed_widgets_receive_public_noncredentialed_cors(self, client, db, user):
        widget = await _widget(db, user)
        response = await client.options(
            f"/api/widgets/{widget.id}/impression",
            headers={
                "Origin": "https://customer-widget.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 204
        assert response.headers["access-control-allow-origin"] == "*"


class TestConversionRate:
    async def test_is_null_before_any_view(self, as_user, db, user):
        widget = await _widget(db, user)
        body = (await as_user(user).get(f"/api/widgets/{widget.id}")).json()
        # None rather than 0%, which would imply the widget is performing badly
        # when in fact nobody has seen it yet.
        assert body["conversion_rate"] is None
        assert body["impressions_count"] == 0

    async def test_computed_from_leads_over_impressions(self, as_user, db, user):
        widget = await _widget(db, user, impressions_count=200, leads_count=25)
        body = (await as_user(user).get(f"/api/widgets/{widget.id}")).json()
        assert body["conversion_rate"] == 12.5

    async def test_rounded_to_one_decimal(self, as_user, db, user):
        widget = await _widget(db, user, impressions_count=3, leads_count=1)
        body = (await as_user(user).get(f"/api/widgets/{widget.id}")).json()
        assert body["conversion_rate"] == 33.3


class TestEmailVerificationGate:
    async def test_unverified_user_cannot_analyze(self, as_user, unverified_user):
        response = await as_user(unverified_user).post(
            "/api/widgets/analyze", json={"url": "https://example.com"}
        )
        # Analysis spends a real Gemini call, so a throwaway address must not
        # be able to consume it.
        assert response.status_code == 403
        assert response.json()["detail"] == "email_verification_required"

    async def test_unverified_user_cannot_build(self, as_user, db, unverified_user):
        widget = await _widget(db, unverified_user, status="analyzed")
        response = await as_user(unverified_user).post(
            "/api/widgets/build", json={"widget_id": str(widget.id), "blueprint_index": 0}
        )
        assert response.status_code == 403

    async def test_unverified_user_can_still_read_their_dashboard(
        self, as_user, db, unverified_user
    ):
        await _widget(db, unverified_user)
        # Reads stay open, so a new user is not stranded with an empty screen and
        # no explanation.
        response = await as_user(unverified_user).get("/api/widgets")
        assert response.status_code == 200
        assert len(response.json()["widgets"]) == 1

    async def test_verified_user_passes_the_gate(self, as_user, db, user, monkeypatch):
        widget = await _widget(db, user, status="analyzed")
        # Stub the queue: this test is about the gate, not Celery.
        monkeypatch.setattr(
            "app.features.widgets.routes._enqueue_build", lambda *args, **kwargs: None
        )
        response = await as_user(user).post(
            "/api/widgets/build", json={"widget_id": str(widget.id), "blueprint_index": 0}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "building"


class TestPaymentEntitlementGate:
    async def test_preview_cannot_spend_build_budget_when_gate_is_enabled(
        self, as_user, db, user, monkeypatch
    ):
        widget = await _widget(
            db,
            user,
            status="analyzed",
            entitlement_status="preview",
        )
        monkeypatch.setattr(
            "app.features.widgets.routes.settings.require_payment_to_build",
            True,
        )
        response = await as_user(user).post(
            "/api/widgets/build",
            json={"widget_id": str(widget.id), "blueprint_index": 0},
        )
        assert response.status_code == 402
        assert response.json()["detail"] == "payment_required"
