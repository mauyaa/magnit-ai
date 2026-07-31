"""Tell the owner when one of their tools captures a lead.

Why this exists: a lead sitting unseen in a dashboard nobody opens is worth
about as much as no lead at all. This is the notification that gives the product
a reason to be checked, and the reply that follows is the whole point of the
tool the customer built.

Two rules govern everything here:

1. **A visitor's submission must never fail because of email.** The submit
   endpoint is public and anonymous — someone filling in a calculator on a
   customer's site. If SMTP is down, the lead is still saved and the visitor
   still sees a thank-you. Every failure below is caught and logged.

2. **It opens its own session.** This runs as a background task, after the
   response is sent and after the request-scoped session has been committed and
   closed. Reusing that session would fail; opening a fresh one also means the
   lead is only ever read once its transaction actually committed, so we cannot
   send mail about a row that got rolled back.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.features.leads.models import Lead
from app.features.users.models import User
from app.features.widgets.models import Widget
from app.platform.db.session import async_session_factory
from app.platform.email.sender import send_email
from app.platform.email.templates import new_lead_email
from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url

logger = logging.getLogger(__name__)


async def post_signed_webhook(
    url: str,
    secret: str,
    event: str,
    payload: dict,
) -> tuple[bool, int | None]:
    """POST one canonical, signed event without following redirects."""
    safe_url = validate_target_url(url)
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.post(
            safe_url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Magnit-Signature": f"sha256={signature}",
                "X-Magnit-Event": event,
            },
        )
    return not response.is_redirect and response.status_code < 300, response.status_code


async def _deliver_webhook(
    db: AsyncSession, lead_id: uuid.UUID, delivery_id: uuid.UUID | None
) -> bool:
    row = (
        await db.execute(
            select(Lead, Widget).join(Widget, Lead.widget_id == Widget.id).where(Lead.id == lead_id)
        )
    ).first()
    if row is None:
        return False
    lead, widget = row
    if not widget.delivery_webhook_url or not widget.delivery_webhook_secret:
        return False

    payload = {
        "event": "lead.created",
        # The outbox row's id. A receiver that saw this delivery before can
        # recognise a retry after an ambiguous timeout instead of filing the
        # same person twice.
        "delivery_id": str(delivery_id) if delivery_id else None,
        "lead": {
            "id": str(lead.id),
            "widget_id": str(widget.id),
            "email": lead.email,
            "name": lead.name,
            "score": lead.score,
            "answers": lead.answers,
            "metadata": lead.extra_meta,
            "created_at": lead.created_at.isoformat(),
        },
    }
    delivered, status_code = await post_signed_webhook(
        widget.delivery_webhook_url,
        widget.delivery_webhook_secret,
        "lead.created",
        payload,
    )
    if not delivered:
        logger.warning("Lead webhook returned %s for widget %s", status_code, widget.id)
        return False
    lead.forwarded = True
    lead.forwarded_at = datetime.now(UTC)
    return True


async def deliver_lead_webhook(
    lead_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    db: AsyncSession | None = None,
    delivery_id: uuid.UUID | None = None,
) -> bool:
    """Deliver a signed lead payload to the customer's configured endpoint.

    ``db`` is supplied by the outbox, which owns the transaction and records the
    attempt alongside this result. Without it the function opens and commits its
    own session, which is how the direct callers and the tests use it.
    """
    try:
        if db is not None:
            return await _deliver_webhook(db, lead_id, delivery_id)
        factory = session_factory or async_session_factory
        async with factory() as own:
            delivered = await _deliver_webhook(own, lead_id, delivery_id)
            if delivered:
                await own.commit()
            return delivered
    except UnsafeTargetURL:
        logger.warning("Blocked unsafe lead webhook for lead %s", lead_id)
        return False
    except Exception:
        logger.exception("Could not deliver webhook for lead %s", lead_id)
        return False


class NotificationNotWanted(Exception):
    """The owner asked not to be emailed, or cannot be. Not a delivery failure."""


async def _lead_notification(db: AsyncSession, lead_id: uuid.UUID) -> tuple[str, str, str, str]:
    row = (
        await db.execute(
            select(Lead, Widget, User)
            .join(Widget, Lead.widget_id == Widget.id)
            .join(User, Widget.user_id == User.id)
            .where(Lead.id == lead_id)
        )
    ).first()

    if row is None:
        logger.warning("Lead %s vanished before its notification could be sent", lead_id)
        raise NotificationNotWanted()

    lead, widget, owner = row

    if not owner.notify_on_lead or not owner.is_active:
        raise NotificationNotWanted()
    if not owner.email_verified:
        # Mailing an unconfirmed address risks sending a stranger's contact
        # details to whoever actually owns that inbox.
        logger.info("Skipping lead notification: owner %s is unverified", owner.id)
        raise NotificationNotWanted()

    subject, text, body = new_lead_email(
        lead_email=lead.email,
        lead_name=lead.name,
        widget_title=widget.title,
        widget_id=str(widget.id),
        lead_id=str(lead.id),
        score=lead.score,
    )
    return owner.email, subject, text, body


async def attempt_owner_notification(db: AsyncSession, lead_id: uuid.UUID) -> str:
    """The outbox's view of this channel: ``delivered``, ``skipped`` or ``failed``.

    ``skipped`` is a real outcome and not a softer word for failure. An owner who
    turned notifications off, or whose address is unconfirmed, is owed nothing —
    retrying that on a backoff schedule for the rest of the day would be a bug
    dressed up as diligence.
    """
    try:
        recipient, subject, text, body = await _lead_notification(db, lead_id)
    except NotificationNotWanted:
        return "skipped"
    await send_email(recipient, subject, text, body)
    return "delivered"


async def notify_owner_of_lead(
    lead_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    db: AsyncSession | None = None,
) -> bool:
    """Email the widget's owner about one captured lead.

    Returns True if a message was handed to the transport. Never raises: the
    caller is serving an anonymous visitor who must not see our mail problems.

    ``session_factory`` exists so tests can point this at their own database;
    ``db`` is passed by the outbox, which owns the transaction.
    """
    try:
        if db is not None:
            recipient, subject, text, body = await _lead_notification(db, lead_id)
        else:
            factory = session_factory or async_session_factory
            async with factory() as own:
                recipient, subject, text, body = await _lead_notification(own, lead_id)

        await send_email(recipient, subject, text, body)
        return True

    except NotificationNotWanted:
        return False
    except Exception:
        # Deliberately broad. Nothing that happens in here is worth a 500 on a
        # customer's own website.
        logger.exception("Could not notify the owner about lead %s", lead_id)
        return False
