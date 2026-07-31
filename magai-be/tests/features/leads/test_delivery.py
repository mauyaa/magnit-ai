"""The lead outbox: capture and delivery are separate promises.

Every test here is a way a business used to lose a lead without anyone finding
out — the mail server that was down for a minute, the process that restarted
between the response and its background task, the CRM that rate-limited a burst.
The point of the outbox is that none of those end with a lead in our database
and nothing on the other side.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.features.leads.delivery import (
    enqueue_lead_deliveries,
    retry_delivery,
    run_deliveries,
    sweep_due_deliveries,
)
from app.features.leads.models import MAX_DELIVERY_ATTEMPTS, Lead, LeadDelivery
from app.features.widgets.models import Widget

SEND = "app.features.leads.notify.send_email"


async def _lead(db, user, **widget_fields) -> tuple[Lead, Widget]:
    widget = Widget(
        user_id=user.id,
        target_url="https://example.com",
        widget_type="readiness_quiz",
        title="Quiz",
        status="active",
        **widget_fields,
    )
    db.add(widget)
    await db.commit()
    lead = Lead(widget_id=widget.id, email="jo@example.com", name="Jo", score=77)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead, widget


class TestEnqueue:
    async def test_the_obligation_is_written_with_the_lead(self, db, user):
        """If the lead exists, so does the record of where it still has to go."""
        lead, widget = await _lead(db, user)

        rows = await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()

        assert [row.channel for row in rows] == ["owner_email"]
        assert rows[0].status == "pending"
        assert rows[0].attempts == 0

    async def test_a_configured_webhook_gets_its_own_row(self, db, user):
        lead, widget = await _lead(
            db,
            user,
            delivery_webhook_url="https://hooks.example.com/in",
            delivery_webhook_secret="s" * 32,
        )

        rows = await enqueue_lead_deliveries(db, lead, widget)

        # Two destinations, two separate answers to "did it arrive?".
        assert sorted(row.channel for row in rows) == ["owner_email", "webhook"]


class TestAttempts:
    async def test_a_delivered_row_is_settled_and_stops_being_retried(
        self, db, user, session_factory
    ):
        user.email_verified = True
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()

        with (
            patch("app.features.leads.delivery.async_session_factory", session_factory),
            patch(SEND, new_callable=AsyncMock),
        ):
            assert await run_deliveries([rows[0].id], session_factory=session_factory) == 1

        settled = await db.get(LeadDelivery, rows[0].id)
        await db.refresh(settled)
        assert settled.status == "delivered"
        assert settled.delivered_at is not None
        assert settled.next_attempt_at is None

    async def test_a_failure_schedules_another_attempt_instead_of_losing_the_lead(
        self, db, user, session_factory
    ):
        user.email_verified = True
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock, side_effect=RuntimeError("smtp down")):
            assert await run_deliveries([rows[0].id], session_factory=session_factory) == 0

        row = await db.get(LeadDelivery, rows[0].id)
        await db.refresh(row)
        assert row.status == "pending"
        assert row.attempts == 1
        assert row.last_error and "smtp down" in row.last_error
        # SQLite hands back a naive datetime; Postgres an aware one. The claim
        # under test is the same either way: there is a next attempt, and it is
        # in the future rather than immediately.
        assert row.next_attempt_at is not None
        scheduled = row.next_attempt_at
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=UTC)
        assert scheduled > datetime.now(UTC)

    async def test_an_owner_who_turned_notifications_off_is_not_retried_forever(
        self, db, user, session_factory
    ):
        """Skipped is a real outcome. Nothing is owed, so nothing is queued."""
        user.email_verified = True
        user.notify_on_lead = False
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            await run_deliveries([rows[0].id], session_factory=session_factory)

        row = await db.get(LeadDelivery, rows[0].id)
        await db.refresh(row)
        assert row.status == "skipped"
        assert row.next_attempt_at is None
        send.assert_not_awaited()

    async def test_automatic_attempts_are_bounded(self, db, user, session_factory):
        """A permanently broken endpoint must stop consuming workers."""
        user.email_verified = True
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()
        row_id = rows[0].id

        with patch(SEND, new_callable=AsyncMock, side_effect=RuntimeError("still down")):
            for _ in range(MAX_DELIVERY_ATTEMPTS):
                async with session_factory() as prep:
                    due = await prep.get(LeadDelivery, row_id)
                    due.next_attempt_at = None
                    await prep.commit()
                await run_deliveries([row_id], session_factory=session_factory)

        row = await db.get(LeadDelivery, row_id)
        await db.refresh(row)
        assert row.status == "failed"
        assert row.attempts == MAX_DELIVERY_ATTEMPTS
        assert row.next_attempt_at is None


class TestSweep:
    async def test_only_deliveries_whose_backoff_has_elapsed_are_retried(
        self, db, user, session_factory
    ):
        user.email_verified = True
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        rows[0].next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            assert await sweep_due_deliveries(session_factory=session_factory) == 0
        send.assert_not_awaited()

        rows[0].next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock):
            assert await sweep_due_deliveries(session_factory=session_factory) == 1

    async def test_a_brand_new_delivery_is_left_to_the_request_that_made_it(
        self, db, user, session_factory
    ):
        """Within the grace period the request's own task owns it.

        Sweeping immediately would double-deliver every lead: once from the
        background task and once from the sweep a moment later.
        """
        user.email_verified = True
        lead, widget = await _lead(db, user)
        await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            assert await sweep_due_deliveries(session_factory=session_factory) == 0
        send.assert_not_awaited()

    async def test_a_delivery_nobody_ever_attempted_is_rescued(self, db, user, session_factory):
        """The case that actually loses a lead, and the reason for the sweep.

        The in-request attempt runs in its own session, so there is a window in
        which the row it was asked to deliver is not yet visible to it: it finds
        nothing, exits without complaint, and the lead sits pending. If the
        sweep only ever looked at rows with a due time — which a never-attempted
        row does not have — that lead would never be delivered and nothing
        anywhere would say so.
        """
        user.email_verified = True
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        # Older than the grace period: whoever was going to try has not.
        rows[0].created_at = datetime.now(UTC) - timedelta(minutes=5)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            assert await sweep_due_deliveries(session_factory=session_factory) == 1
        send.assert_awaited_once()

        row = await db.get(LeadDelivery, rows[0].id)
        await db.refresh(row)
        assert row.status == "delivered"


class TestManualRetry:
    async def test_an_exhausted_delivery_can_be_put_back_in_the_queue(
        self, db, user, session_factory
    ):
        """The case automatic retries deliberately cannot cover.

        The attempts are bounded so a dead endpoint does not run forever, which
        leaves one situation the product owes an answer for: the customer has
        fixed their end and wants the lead they already have.
        """
        user.email_verified = True
        lead, widget = await _lead(db, user)
        rows = await enqueue_lead_deliveries(db, lead, widget)
        rows[0].status = "failed"
        rows[0].attempts = MAX_DELIVERY_ATTEMPTS
        rows[0].last_error = "connection refused"
        await db.commit()

        await retry_delivery(db, rows[0])
        await db.commit()

        assert rows[0].status == "pending"
        assert rows[0].attempts == 0
        assert rows[0].last_error is None

        with patch(SEND, new_callable=AsyncMock):
            assert await run_deliveries([rows[0].id], session_factory=session_factory) == 1


class TestSubmitEndpoint:
    async def test_a_submission_records_every_destination_it_owes(
        self, client, db, user, session_factory
    ):
        user.email_verified = True
        widget = Widget(
            user_id=user.id,
            target_url="https://example.com",
            widget_type="readiness_quiz",
            title="Quiz",
            status="active",
            delivery_webhook_url="https://hooks.example.com/in",
            delivery_webhook_secret="s" * 32,
        )
        db.add(widget)
        await db.commit()

        with (
            patch("app.features.leads.delivery.async_session_factory", session_factory),
            patch(SEND, new_callable=AsyncMock),
            patch(
                "app.features.leads.notify.post_signed_webhook",
                new=AsyncMock(return_value=(True, 200)),
            ),
        ):
            response = await client.post(
                f"/api/leads/{widget.id}", json={"email": "buyer@example.com"}
            )

        assert response.status_code == 200
        rows = (await db.execute(select(LeadDelivery))).scalars().all()
        assert sorted(row.channel for row in rows) == ["owner_email", "webhook"]


class TestReplayedSubmissions:
    """The same visitor, twice, is one lead.

    This endpoint is public and lives on a page we do not control. The two most
    ordinary things a person does here — pressing the button again because
    nothing visibly happened, and reloading after a slow response — each used to
    file another lead and spend another slot against the tool's cap.
    """

    async def test_a_double_submit_from_one_session_is_one_lead(self, client, db, user):
        user.email_verified = True
        lead, widget = await _lead(db, user)
        await db.delete(lead)
        await db.commit()

        body = {
            "email": "buyer@example.com",
            "metadata": {"magnit_session_id": "s" * 32},
        }
        first = await client.post(f"/api/leads/{widget.id}", json=body)
        second = await client.post(f"/api/leads/{widget.id}", json=body)

        assert (first.status_code, second.status_code) == (200, 200)
        rows = (await db.execute(select(Lead).where(Lead.widget_id == widget.id))).scalars().all()
        assert len(rows) == 1

        await db.refresh(widget)
        # The cap is what the owner paid for. A retry must not spend one.
        assert widget.leads_count == 1

    async def test_a_different_person_in_the_same_window_is_a_real_lead(self, client, db, user):
        user.email_verified = True
        lead, widget = await _lead(db, user)
        await db.delete(lead)
        await db.commit()

        await client.post(
            f"/api/leads/{widget.id}",
            json={"email": "one@example.com", "metadata": {"magnit_session_id": "a" * 32}},
        )
        await client.post(
            f"/api/leads/{widget.id}",
            json={"email": "two@example.com", "metadata": {"magnit_session_id": "b" * 32}},
        )

        rows = (await db.execute(select(Lead).where(Lead.widget_id == widget.id))).scalars().all()
        assert len(rows) == 2

    async def test_a_repeat_does_not_queue_a_second_round_of_deliveries(self, client, db, user):
        """Otherwise the owner is emailed twice about one person.

        Deduplicating the lead row is only half of it: the first version of this
        still enqueued a full second set of destinations on the replay, so one
        person arrived twice in the inbox and twice in the CRM. Driven through
        the endpoint, because the enqueue lives in the route and a service-level
        test cannot see it.
        """
        user.email_verified = True
        lead, widget = await _lead(db, user)
        await db.delete(lead)
        await db.commit()

        body = {
            "email": "buyer@example.com",
            "metadata": {"magnit_session_id": "s" * 32},
        }
        await client.post(f"/api/leads/{widget.id}", json=body)
        await client.post(f"/api/leads/{widget.id}", json=body)

        leads = (await db.execute(select(Lead).where(Lead.widget_id == widget.id))).scalars().all()
        deliveries = (await db.execute(select(LeadDelivery))).scalars().all()
        assert len(leads) == 1
        assert len(deliveries) == 1
