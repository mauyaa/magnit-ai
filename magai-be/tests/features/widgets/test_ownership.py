"""Tenant-isolation tests.

Before authorization existed, every widget was owned by the literal string
"anonymous" and any caller could read or mutate any widget. These tests pin the
fix: a second account must be unable to see or touch the first account's data,
and must not even be able to confirm it exists.
"""

import uuid

import pytest

from app.features.leads.models import Lead
from app.features.widgets.models import Widget, WidgetHealEvent


async def _make_widget(db, owner, **overrides) -> Widget:
    # Defaults are popped from overrides so a caller can override any of them
    # without colliding with the explicit keyword arguments below.
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Owner's calculator",
        status=overrides.pop("status", "active"),
        deployment_url=overrides.pop("deployment_url", "https://magai-widget-abc123.vercel.app"),
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


class TestReadIsolation:
    async def test_owner_can_read_their_widget(self, as_user, db, user):
        widget = await _make_widget(db, user)
        response = await as_user(user).get(f"/api/widgets/{widget.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(widget.id)

    async def test_other_user_gets_404_not_403(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user)
        response = await as_user(other_user).get(f"/api/widgets/{widget.id}")
        # 404 rather than 403: a 403 would confirm the widget exists.
        assert response.status_code == 404

    async def test_listing_only_returns_own_widgets(self, as_user, db, user, other_user):
        await _make_widget(db, user)
        response = await as_user(other_user).get("/api/widgets")
        assert response.status_code == 200
        assert response.json()["widgets"] == []

    async def test_leads_are_not_readable_by_another_user(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user)
        db.add(Lead(widget_id=widget.id, email="lead@example.com", name="A Lead"))
        await db.commit()

        assert (await as_user(user).get(f"/api/widgets/{widget.id}/leads")).status_code == 200
        # Lead data is the customer's most sensitive asset in this product.
        intruder = await as_user(other_user).get(f"/api/widgets/{widget.id}/leads")
        assert intruder.status_code == 404

    async def test_heal_events_are_not_readable_by_another_user(
        self, as_user, db, user, other_user
    ):
        widget = await _make_widget(db, user)
        db.add(WidgetHealEvent(widget_id=widget.id, check_type="brand_drift", status="healed"))
        await db.commit()

        assert (await as_user(user).get(f"/api/widgets/{widget.id}/heal-events")).status_code == 200
        assert (
            await as_user(other_user).get(f"/api/widgets/{widget.id}/heal-events")
        ).status_code == 404


class TestMutationIsolation:
    async def test_other_user_cannot_deploy(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user)
        response = await as_user(other_user).post(f"/api/widgets/{widget.id}/deploy")
        assert response.status_code == 404

    async def test_other_user_cannot_rollback(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user)
        response = await as_user(other_user).post(f"/api/widgets/{widget.id}/rollback")
        assert response.status_code == 404

    async def test_other_user_cannot_retry(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user, status="failed")
        response = await as_user(other_user).post(f"/api/widgets/{widget.id}/retry")
        assert response.status_code == 404

    async def test_other_user_cannot_build(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user, status="analyzed", deployment_url=None)
        response = await as_user(other_user).post(
            "/api/widgets/build", json={"widget_id": str(widget.id), "blueprint_index": 0}
        )
        assert response.status_code == 404

    async def test_other_user_cannot_preview(self, as_user, db, user, other_user):
        widget = await _make_widget(db, user)
        response = await as_user(other_user).post(
            f"/api/widgets/{widget.id}/architect-preview", json={"blueprint_index": 0}
        )
        assert response.status_code == 404


class TestUnauthenticatedAccess:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/widgets"),
            ("post", "/api/widgets/analyze"),
            ("post", "/api/widgets/build"),
            ("get", "/api/payments"),
        ],
    )
    async def test_endpoints_require_authentication(self, client, method, path):
        # client.request rather than client.get: httpx's .get() takes no json body.
        response = await client.request(method, path, json={})
        assert response.status_code == 401


class TestMalformedIdentifiers:
    async def test_non_uuid_widget_id_is_404_not_500(self, as_user, user):
        # A non-UUID path parameter must not reach the database and error out.
        response = await as_user(user).get("/api/widgets/not-a-uuid")
        assert response.status_code == 404

    async def test_unknown_uuid_is_404(self, as_user, user):
        response = await as_user(user).get(f"/api/widgets/{uuid.uuid4()}")
        assert response.status_code == 404
