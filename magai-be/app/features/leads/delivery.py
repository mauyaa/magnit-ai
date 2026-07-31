"""The lead outbox: capture is not the same as delivery, and both must be true.

Before this module, a captured lead was handed to three fire-and-forget
background tasks. Each got exactly one attempt, none of them wrote down what
happened, and a process restart between the response and the task simply lost
the delivery. For the one thing this product exists to do — put a lead in front
of a business — that is not a reliability gap, it is the product not working.

The shape here is a transactional outbox:

* Rows are written in the same transaction as the lead. If the lead exists, so
  does a record of every destination it still owes.
* Attempts are recorded, not assumed. A failure sets a next attempt time with
  backoff; a permanent failure is visible to the owner and can be retried by
  hand.
* Each row's id is the idempotency key. A retry after an ambiguous timeout is
  the same delivery, not a second copy of the lead.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.features.integrations.models import Integration
from app.features.integrations.service import integration_covers
from app.features.leads.models import (
    MAX_DELIVERY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    Lead,
    LeadDelivery,
)
from app.features.widgets.models import Widget
from app.platform.db.session import async_session_factory

logger = logging.getLogger(__name__)

# How long a written-but-never-attempted row is left to the request's own
# background task before the sweep treats it as orphaned. Long enough not to
# race that task and deliver the same lead twice; short enough that a lead lost
# to a restart is delivered a minute late rather than never.
UNATTEMPTED_GRACE = timedelta(seconds=45)


async def enqueue_lead_deliveries(
    db: AsyncSession, lead: Lead, widget: Widget
) -> list[LeadDelivery]:
    """Write down where this lead has to go, in the lead's own transaction.

    Called before the response is sent and inside the same unit of work, so the
    outbox can never disagree with the lead table about what was captured.
    Nothing is attempted here — that happens after the visitor has their
    confirmation, and never on their request's critical path.

    Idempotent per lead. Capture already treats a repeat submission as the same
    person, but that only deduplicated the lead row: a second submission still
    enqueued a second full set of destinations, so the owner was emailed twice
    and the CRM received the same person twice. Deduplicating the lead and not
    its deliveries fixes the half nobody sees.
    """
    already = await db.scalar(
        select(LeadDelivery.id).where(LeadDelivery.lead_id == lead.id).limit(1)
    )
    if already is not None:
        return []

    rows: list[LeadDelivery] = [
        LeadDelivery(lead_id=lead.id, channel="owner_email"),
    ]
    if widget.delivery_webhook_url and widget.delivery_webhook_secret:
        rows.append(LeadDelivery(lead_id=lead.id, channel="webhook"))

    # Connections in an error state are included on purpose. Excluding them was
    # how one failed delivery silently stopped a CRM from ever receiving another
    # lead: the connection was marked broken, and every subsequent lead skipped
    # it without a row, without an error, and without anyone being told.
    integrations = (
        (
            await db.execute(
                select(Integration).where(
                    Integration.user_id == widget.user_id,
                    Integration.status.in_(("connected", "error")),
                )
            )
        )
        .scalars()
        .all()
    )
    for integration in integrations:
        if integration_covers(integration, widget.id):
            rows.append(
                LeadDelivery(
                    lead_id=lead.id,
                    channel="integration",
                    integration_id=integration.id,
                )
            )

    for row in rows:
        db.add(row)
    await db.flush()
    return rows


def _schedule_retry(delivery: LeadDelivery, error: str) -> None:
    """Record a failed attempt and decide whether there will be another."""
    delivery.attempts += 1
    delivery.last_error = error[:500]
    if delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
        # Out of automatic attempts, not out of options: the owner can still
        # retry by hand once they have fixed whatever is on the other end.
        delivery.status = "failed"
        delivery.next_attempt_at = None
        return
    delivery.status = "pending"
    delivery.next_attempt_at = datetime.now(UTC) + timedelta(
        seconds=RETRY_BACKOFF_SECONDS[delivery.attempts - 1]
    )


def _mark_delivered(delivery: LeadDelivery) -> None:
    delivery.attempts += 1
    delivery.status = "delivered"
    delivery.delivered_at = datetime.now(UTC)
    delivery.next_attempt_at = None
    delivery.last_error = None


async def _attempt(db: AsyncSession, delivery: LeadDelivery) -> tuple[str, str | None]:
    """Try one delivery. Returns ``(outcome, error)``.

    Each channel owns its own attempt, so this stays a router rather than a
    second implementation of three protocols. The imports are lazy: notify and
    the integration dispatcher both reach back into this package, and importing
    them at module scope makes the cycle a startup failure rather than a runtime
    detail.
    """
    from app.features.integrations.service import deliver_lead_to_integration
    from app.features.leads.notify import attempt_owner_notification, deliver_lead_webhook

    if delivery.channel == "owner_email":
        return await attempt_owner_notification(db, delivery.lead_id), None

    if delivery.channel == "webhook":
        ok = await deliver_lead_webhook(delivery.lead_id, db=db, delivery_id=delivery.id)
        return ("delivered", None) if ok else ("failed", "the endpoint refused the delivery")

    if delivery.channel == "integration" and delivery.integration_id:
        ok, error = await deliver_lead_to_integration(
            db,
            lead_id=delivery.lead_id,
            integration_id=delivery.integration_id,
            delivery_id=delivery.id,
        )
        return ("delivered", None) if ok else ("failed", error)

    return "skipped", None


async def run_deliveries(
    delivery_ids: list[uuid.UUID],
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Attempt specific outbox rows. Never raises.

    Runs after the visitor already has their confirmation, so nothing in here
    can affect what they see. A row that fails keeps its place in the outbox and
    is picked up again by the sweep.
    """
    if not delivery_ids:
        return 0

    factory = session_factory or async_session_factory
    delivered = 0
    try:
        async with factory() as db:
            rows = (
                (
                    await db.execute(
                        select(LeadDelivery).where(
                            LeadDelivery.id.in_(delivery_ids),
                            LeadDelivery.status == "pending",
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                # Asked to deliver something and found nothing. Almost always
                # the request's transaction had not committed yet, which is
                # harmless — the sweep collects the row shortly after — but it
                # is worth one line, because silence here is what hid a lead
                # being captured and never delivered.
                logger.info("Nothing to deliver for %d outbox row(s) yet", len(delivery_ids))
            for row in rows:
                try:
                    outcome, error = await _attempt(db, row)
                except Exception as exc:  # one bad destination must not stop the rest
                    logger.exception("Lead delivery %s raised", row.id)
                    _schedule_retry(row, str(exc))
                    continue
                if outcome == "delivered":
                    _mark_delivered(row)
                    delivered += 1
                elif outcome == "skipped":
                    row.status = "skipped"
                    row.next_attempt_at = None
                else:
                    _schedule_retry(row, error or "delivery was refused")
            await db.commit()
    except Exception:
        logger.exception("Lead delivery batch failed")
    return delivered


async def sweep_due_deliveries(
    limit: int = 200,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Deliver everything still owed: retries, and anything never tried at all.

    This — not the request's background task — is what makes the outbox worth
    having. It has to cover two kinds of row:

    * a failed attempt whose backoff has elapsed;
    * a row that was written and then never attempted, because the immediate
      task read the database before the request's transaction had committed, or
      because the process went away between the two.

    The second one is the case that actually loses a lead. The in-request
    attempt runs in its own session, so there is a window in which the row it
    was asked to deliver is not yet visible to it — it finds nothing, exits
    without complaint, and the lead sits pending forever if only overdue rows
    are ever swept. Treating an untried row as owed after a short grace period
    closes that hole and stops delivery depending on the exact ordering of a
    commit and a background task.
    """
    factory = session_factory or async_session_factory
    now = datetime.now(UTC)
    orphaned_before = now - UNATTEMPTED_GRACE
    try:
        async with factory() as db:
            due = (
                (
                    await db.execute(
                        select(LeadDelivery.id)
                        .where(
                            LeadDelivery.status == "pending",
                            or_(
                                LeadDelivery.next_attempt_at <= now,
                                and_(
                                    LeadDelivery.next_attempt_at.is_(None),
                                    # The grace period is what keeps this from
                                    # racing the request's own attempt and
                                    # delivering the same lead twice.
                                    LeadDelivery.created_at <= orphaned_before,
                                ),
                            ),
                        )
                        .order_by(LeadDelivery.created_at.asc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
    except Exception:
        logger.exception("Could not read the lead delivery outbox")
        return 0

    if not due:
        return 0
    return await run_deliveries(list(due), session_factory=factory)


async def retry_delivery(db: AsyncSession, delivery: LeadDelivery) -> None:
    """Put an exhausted delivery back in the queue, at the owner's request."""
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.next_attempt_at = None
    delivery.last_error = None
    await db.flush()


async def deliveries_for(db: AsyncSession, lead_id: uuid.UUID) -> list[LeadDelivery]:
    result = await db.execute(
        select(LeadDelivery)
        .where(LeadDelivery.lead_id == lead_id)
        .order_by(LeadDelivery.created_at.asc())
    )
    return list(result.scalars().all())
