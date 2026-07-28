"""Lead notifications, and the promises they must not break.

A captured lead is only worth something if the owner finds out while the reply
is still timely, so this is the notification that gives the product a daily
reason to exist. But it hangs off a public, anonymous endpoint embedded on a
customer's own website, which constrains it hard:

* a mail outage must never turn into a 500 on a stranger's site
* the owner must be able to turn it off
* it must never mail an address nobody has confirmed
"""

import uuid
from unittest.mock import AsyncMock, patch

from app.features.leads.models import Lead
from app.features.leads.notify import notify_owner_of_lead
from app.features.widgets.models import Widget
from app.platform.email.sender import EmailDeliveryError
from app.platform.email.templates import new_lead_email

SEND = "app.features.leads.notify.send_email"


async def _widget(db, owner) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Savings calculator",
        status="active",
        deployment_url="https://magai-widget-abc.vercel.app",
        lead_cap=100,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestTemplate:
    def test_puts_the_lead_address_in_the_subject(self):
        # The owner should be able to triage from the notification list alone.
        subject, text, body = new_lead_email(
            lead_email="jo@buyer.com",
            lead_name="Jo",
            widget_title="Savings calculator",
            widget_id=str(uuid.uuid4()),
            score=None,
        )
        assert "jo@buyer.com" in subject
        assert "Jo <jo@buyer.com>" in text
        assert "mailto:jo@buyer.com" in body

    def test_mentions_the_score_only_when_there_is_one(self):
        _, with_score, _ = new_lead_email(
            lead_email="a@b.com",
            lead_name=None,
            widget_title="Quiz",
            widget_id="w",
            score=72,
        )
        _, without, _ = new_lead_email(
            lead_email="a@b.com",
            lead_name=None,
            widget_title="Quiz",
            widget_id="w",
            score=None,
        )
        assert "scored 72" in with_score
        assert "scored" not in without

    def test_escapes_html_in_the_lead_name(self):
        # The name is attacker-controlled: it arrives from a public endpoint.
        _, _, body = new_lead_email(
            lead_email="a@b.com",
            lead_name="<script>alert(1)</script>",
            widget_title="Quiz",
            widget_id="w",
            score=None,
        )
        assert "<script>" not in body
        assert "&lt;script&gt;" in body


class TestNotifier:
    async def test_emails_the_owner(self, db, user, session_factory):
        user.email_verified = True
        widget = await _widget(db, user)
        lead = Lead(widget_id=widget.id, email="buyer@example.com", name="Buyer")
        db.add(lead)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            assert await notify_owner_of_lead(lead.id, session_factory) is True

        assert send.await_args.args[0] == user.email

    async def test_respects_the_opt_out(self, db, user, session_factory):
        user.email_verified = True
        user.notify_on_lead = False
        widget = await _widget(db, user)
        lead = Lead(widget_id=widget.id, email="buyer@example.com")
        db.add(lead)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            assert await notify_owner_of_lead(lead.id, session_factory) is False
        send.assert_not_awaited()

    async def test_never_mails_an_unverified_address(self, db, user, session_factory):
        # Otherwise a stranger's contact details go to whoever really owns the
        # inbox someone typed at signup.
        user.email_verified = False
        widget = await _widget(db, user)
        lead = Lead(widget_id=widget.id, email="buyer@example.com")
        db.add(lead)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock) as send:
            assert await notify_owner_of_lead(lead.id, session_factory) is False
        send.assert_not_awaited()

    async def test_swallows_a_mail_outage(self, db, user, session_factory):
        user.email_verified = True
        widget = await _widget(db, user)
        lead = Lead(widget_id=widget.id, email="buyer@example.com")
        db.add(lead)
        await db.commit()

        with patch(SEND, new_callable=AsyncMock, side_effect=EmailDeliveryError("smtp down")):
            # Returns False rather than raising: the caller is mid-response to a
            # visitor on someone else's website.
            assert await notify_owner_of_lead(lead.id, session_factory) is False

    async def test_tolerates_a_missing_lead(self, session_factory):
        assert await notify_owner_of_lead(uuid.uuid4(), session_factory) is False


class TestSubmitEndpointStaysUp:
    """The guarantee that matters: this endpoint runs on a customer's website.

    The notifier's session factory is pointed at the test database so the
    background task genuinely executes — otherwise these would pass simply
    because it looked in an empty database and found nothing to do.
    """

    async def test_visitor_still_succeeds_when_mail_is_down(
        self, client, db, user, session_factory
    ):
        user.email_verified = True
        widget = await _widget(db, user)

        with (
            patch("app.features.leads.notify.async_session_factory", session_factory),
            patch(SEND, new_callable=AsyncMock, side_effect=EmailDeliveryError("smtp down")),
        ):
            response = await client.post(
                f"/api/leads/{widget.id}",
                json={"email": "buyer@example.com", "name": "Buyer"},
            )

        assert response.status_code == 200
        assert response.json()["received"] is True

    async def test_notifies_the_owner_on_a_real_submission(self, client, db, user, session_factory):
        user.email_verified = True
        widget = await _widget(db, user)

        with (
            patch("app.features.leads.notify.async_session_factory", session_factory),
            patch(SEND, new_callable=AsyncMock) as send,
        ):
            await client.post(f"/api/leads/{widget.id}", json={"email": "buyer@example.com"})

        send.assert_awaited_once()
        assert send.await_args.args[0] == user.email

    async def test_lead_is_committed_before_the_notification_runs(
        self, client, db, user, session_factory
    ):
        """The lead must be durable by the time anything else touches it.

        The notifier runs after the response, in its own session. If it can read
        the lead back, the row was genuinely committed — which is the property
        worth pinning, because a notification about a rolled-back lead would be
        worse than no notification at all.
        """
        user.email_verified = True
        widget = await _widget(db, user)

        real_send = AsyncMock(side_effect=EmailDeliveryError("smtp down"))

        with (
            patch("app.features.leads.notify.async_session_factory", session_factory),
            patch(SEND, real_send),
        ):
            response = await client.post(
                f"/api/leads/{widget.id}", json={"email": "buyer@example.com"}
            )

        assert response.status_code == 200
        # The send was attempted at all, which it can only be after the notifier
        # independently loaded the committed lead, widget, and owner.
        real_send.assert_awaited_once()
        assert "buyer@example.com" in real_send.await_args.args[1]


class TestNotificationSetting:
    async def test_owner_can_turn_notifications_off_and_on(self, as_user, user):
        off = await as_user(user).patch(
            "/api/users/me/notifications", json={"notify_on_lead": False}
        )
        assert off.status_code == 200
        assert off.json()["notify_on_lead"] is False

        on = await as_user(user).patch("/api/users/me/notifications", json={"notify_on_lead": True})
        assert on.json()["notify_on_lead"] is True

    async def test_defaults_to_on(self, as_user, user):
        response = await as_user(user).get("/api/users/me")
        assert response.json()["notify_on_lead"] is True

    async def test_requires_authentication(self, client):
        response = await client.patch("/api/users/me/notifications", json={"notify_on_lead": False})
        assert response.status_code == 401
