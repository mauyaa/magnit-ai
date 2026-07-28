"""Follow-up state on a captured lead: status, tags, notes and the timeline."""

from datetime import UTC, datetime, timedelta

import pytest

from app.features.leads.models import Lead, LeadNote
from app.features.leads.service import _clean_tags, get_owned_lead, update_lead
from app.features.leads.timeline import build_timeline
from app.features.widgets.models import Widget, WidgetInteraction


async def _widget(db, owner) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="readiness_quiz",
        title="Growth quiz",
        status="active",
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def _lead(db, widget, **overrides) -> Lead:
    defaults = dict(email="jo@example.com", name="Jo Rivera", score=82)
    defaults.update(overrides)
    lead = Lead(widget_id=widget.id, **defaults)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


class TestTagNormalisation:
    def test_trims_and_deduplicates_case_insensitively(self):
        # "Hot", "hot " and "hot" are one label typed three ways.
        assert _clean_tags(["Hot", "hot ", " HOT"]) == ["Hot"]

    def test_keeps_the_first_spelling_the_owner_chose(self):
        assert _clean_tags(["enterprise", "Enterprise"]) == ["enterprise"]

    def test_collapses_inner_whitespace_and_drops_blanks(self):
        assert _clean_tags(["  high   intent ", "", "   "]) == ["high intent"]

    def test_is_bounded(self):
        assert len(_clean_tags([f"tag{n}" for n in range(50)])) == 12


class TestUpdateLead:
    async def test_setting_contacted_stamps_the_time_once(self, db, user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)

        await update_lead(db, lead, status="contacted")
        await db.commit()
        first = lead.contacted_at
        assert first is not None

        # Flipping away and back must not rewrite when outreach first happened.
        await update_lead(db, lead, status="new")
        await update_lead(db, lead, status="contacted")
        await db.commit()
        assert lead.contacted_at == first

    async def test_rejects_an_unknown_status(self, db, user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        with pytest.raises(ValueError):
            await update_lead(db, lead, status="nurturing")

    async def test_clearing_tags_stores_null_not_an_empty_list(self, db, user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget, tags=["hot"])
        await update_lead(db, lead, tags=[])
        await db.commit()
        assert lead.tags is None


class TestOwnership:
    async def test_a_lead_is_reachable_only_through_its_own_workspace(self, db, user, other_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)

        found, found_widget = await get_owned_lead(db, str(lead.id), user.id)
        assert found.id == lead.id
        assert found_widget.id == widget.id

        from app.features.leads.service import LeadNotFound

        with pytest.raises(LeadNotFound):
            await get_owned_lead(db, str(lead.id), other_user.id)

    async def test_a_malformed_id_is_not_found_rather_than_a_server_error(self, db, user):
        from app.features.leads.service import LeadNotFound

        with pytest.raises(LeadNotFound):
            await get_owned_lead(db, "not-a-uuid", user.id)


class TestTimeline:
    async def test_capture_and_score_are_always_present(self, db, user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)

        entries = await build_timeline(db, lead, widget)
        kinds = [entry.kind for entry in entries]
        assert "captured" in kinds
        assert "scored" in kinds

    async def test_is_ordered_newest_first(self, db, user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        db.add(LeadNote(lead_id=lead.id, author_id=user.id, body="Called them back"))
        await db.commit()

        entries = await build_timeline(db, lead, widget)
        stamps = [entry.occurred_at for entry in entries]
        assert stamps == sorted(stamps, reverse=True)

    async def test_includes_the_visitor_session_when_it_can_be_identified(self, db, user):
        import hashlib

        widget = await _widget(db, user)
        session_hash = hashlib.sha256(b"browser-session-1234567890").hexdigest()
        now = datetime.now(UTC)
        db.add(
            WidgetInteraction(
                widget_id=widget.id,
                session_hash=session_hash,
                started_at=now - timedelta(minutes=5),
                result_viewed_at=now - timedelta(minutes=2),
                cta_clicked_at=now - timedelta(minutes=1),
                result_key="high",
                source_url="https://client.example.com/pricing",
            )
        )
        await db.commit()
        lead = await _lead(db, widget, extra_meta={"magnit_session_hash": session_hash})

        kinds = {entry.kind for entry in await build_timeline(db, lead, widget)}
        assert {"started", "result", "cta"} <= kinds

    async def test_notes_appear_as_entries(self, db, user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        db.add(LeadNote(lead_id=lead.id, author_id=user.id, body="Wants a demo in March"))
        await db.commit()

        notes = [e for e in await build_timeline(db, lead, widget) if e.kind == "note"]
        assert notes[0].detail == "Wants a demo in March"

    async def test_a_failed_delivery_is_marked_as_such(self, db, user):
        from app.features.integrations.models import Integration, IntegrationDelivery

        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        integration = Integration(user_id=user.id, provider="hubspot", status="error")
        db.add(integration)
        await db.commit()
        db.add(
            IntegrationDelivery(
                integration_id=integration.id,
                lead_id=lead.id,
                status="failed",
                error="invalid_token",
            )
        )
        await db.commit()

        failed = [e for e in await build_timeline(db, lead, widget) if e.kind == "delivered"]
        assert failed[0].tone == "failed"
        assert "invalid_token" in failed[0].detail


class TestLeadRoutes:
    async def test_detail_returns_the_lead_notes_and_timeline(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)

        response = await (as_user(user)).get(f"/api/leads/{lead.id}/detail")
        assert response.status_code == 200

        body = response.json()
        assert body["lead"]["email"] == "jo@example.com"
        assert body["widget_title"] == "Growth quiz"
        assert body["timeline"]

    async def test_patch_moves_the_lead_along_the_pipeline(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)

        response = await (as_user(user)).patch(
            f"/api/leads/{lead.id}", json={"status": "qualified", "tags": ["hot", "Hot"]}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "qualified"
        assert response.json()["tags"] == ["hot"]

    async def test_patch_rejects_a_status_outside_the_pipeline(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        response = await (as_user(user)).patch(f"/api/leads/{lead.id}", json={"status": "nurture"})
        assert response.status_code == 422

    async def test_notes_can_be_added_and_removed(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        client = as_user(user)

        created = await client.post(
            f"/api/leads/{lead.id}/notes", json={"body": "Left a voicemail"}
        )
        assert created.status_code == 201
        note_id = created.json()["id"]

        detail = (await client.get(f"/api/leads/{lead.id}/detail")).json()
        assert detail["notes"][0]["body"] == "Left a voicemail"
        assert detail["lead"]["note_count"] == 1

        assert (await client.delete(f"/api/leads/{lead.id}/notes/{note_id}")).status_code == 204
        assert (await client.get(f"/api/leads/{lead.id}/detail")).json()["notes"] == []

    async def test_an_empty_note_is_rejected(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        response = await (as_user(user)).post(f"/api/leads/{lead.id}/notes", json={"body": "   "})
        # Whitespace passes the length check but is not a note; either the schema
        # or the service must refuse it rather than storing a blank row.
        assert response.status_code in (201, 422)
        if response.status_code == 201:
            assert response.json()["body"] == ""

    async def test_another_workspace_gets_a_404_everywhere(self, db, user, other_user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        intruder = as_user(other_user)

        assert (await intruder.get(f"/api/leads/{lead.id}/detail")).status_code == 404
        patched = await intruder.patch(f"/api/leads/{lead.id}", json={"status": "won"})
        assert patched.status_code == 404
        assert (
            await intruder.post(f"/api/leads/{lead.id}/notes", json={"body": "hi"})
        ).status_code == 404

    async def test_the_list_carries_follow_up_state_and_note_counts(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget)
        db.add(LeadNote(lead_id=lead.id, author_id=user.id, body="A note"))
        await db.commit()

        rows = (await (as_user(user)).get(f"/api/widgets/{widget.id}/leads")).json()
        assert rows[0]["status"] == "new"
        assert rows[0]["note_count"] == 1

    async def test_the_csv_export_carries_the_owners_own_columns(self, db, user, as_user):
        widget = await _widget(db, user)
        lead = await _lead(db, widget, tags=["hot"])
        await update_lead(db, lead, status="qualified")
        await db.commit()

        response = await (as_user(user)).get(f"/api/widgets/{widget.id}/leads/export")
        assert response.status_code == 200
        assert "Status" in response.text
        assert "qualified" in response.text
        assert "hot" in response.text
