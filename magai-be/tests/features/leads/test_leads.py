"""Lead submission: the one deliberately public write path in the API."""

import uuid

import pytest

from app.features.leads.service import (
    LeadCapReached,
    PayloadTooLarge,
    WidgetNotFound,
    submit_lead,
)
from app.features.widgets.models import Widget


async def _widget(db, owner, **overrides) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Calc",
        status="active",
        **overrides,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestSubmitLeadService:
    async def test_records_lead_and_increments_count(self, db, user):
        widget = await _widget(db, user)
        lead, captured_by = await submit_lead(
            db, widget_id=str(widget.id), email="a@example.com", name="A"
        )
        await db.commit()
        await db.refresh(widget)

        assert lead.email == "a@example.com"
        # The widget comes back with the lead: the caller needs it to work out
        # where this lead has to be delivered, and re-reading it would be a
        # second query for a row already in hand.
        assert captured_by.id == widget.id
        assert widget.leads_count == 1

    async def test_unknown_widget_raises(self, db):
        with pytest.raises(WidgetNotFound):
            await submit_lead(db, widget_id=str(uuid.uuid4()), email="a@example.com")

    async def test_non_uuid_widget_id_raises_not_found(self, db):
        with pytest.raises(WidgetNotFound):
            await submit_lead(db, widget_id="garbage", email="a@example.com")

    async def test_lead_cap_is_enforced(self, db, user):
        widget = await _widget(db, user, lead_cap=1)
        await submit_lead(db, widget_id=str(widget.id), email="first@example.com")
        await db.commit()

        with pytest.raises(LeadCapReached):
            await submit_lead(db, widget_id=str(widget.id), email="second@example.com")

    async def test_cap_of_zero_rejects_immediately(self, db, user):
        widget = await _widget(db, user, lead_cap=0)
        with pytest.raises(LeadCapReached):
            await submit_lead(db, widget_id=str(widget.id), email="a@example.com")

    async def test_oversized_answers_are_rejected(self, db, user):
        widget = await _widget(db, user)
        # A public endpoint must not accept unbounded JSON into the database.
        with pytest.raises(PayloadTooLarge):
            await submit_lead(
                db,
                widget_id=str(widget.id),
                email="a@example.com",
                answers={"blob": "x" * 20_000},
            )

    async def test_too_many_answer_keys_rejected(self, db, user):
        widget = await _widget(db, user)
        with pytest.raises(PayloadTooLarge):
            await submit_lead(
                db,
                widget_id=str(widget.id),
                email="a@example.com",
                answers={f"k{i}": i for i in range(200)},
            )


class TestSubmitLeadEndpoint:
    async def test_submission_needs_no_authentication(self, client, db, user):
        widget = await _widget(db, user)
        response = await client.post(
            f"/api/leads/{widget.id}", json={"email": "visitor@example.com", "name": "Visitor"}
        )
        assert response.status_code == 200
        assert response.json()["received"] is True

    async def test_invalid_email_is_rejected(self, client, db, user):
        widget = await _widget(db, user)
        response = await client.post(f"/api/leads/{widget.id}", json={"email": "nope"})
        assert response.status_code == 422

    async def test_unknown_widget_is_404(self, client):
        response = await client.post(
            f"/api/leads/{uuid.uuid4()}", json={"email": "visitor@example.com"}
        )
        assert response.status_code == 404

    async def test_cap_reached_is_409(self, client, db, user):
        widget = await _widget(db, user, lead_cap=0)
        response = await client.post(f"/api/leads/{widget.id}", json={"email": "v@example.com"})
        assert response.status_code == 409


class TestExportLeadsEndpoint:
    async def test_export_leads_csv(self, client, db, user, auth_headers):
        widget = await _widget(db, user)
        await submit_lead(db, widget_id=str(widget.id), email="lead1@example.com", name="Lead One")
        await db.commit()

        response = await client.get(
            f"/api/widgets/{widget.id}/leads/export", headers=auth_headers(user)
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "lead1@example.com" in response.text
        assert "Lead One" in response.text
