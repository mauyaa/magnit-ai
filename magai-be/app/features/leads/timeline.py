"""One lead's history, assembled from what actually happened.

Not an event log. There is no `lead_events` table and there should not be: every
moment worth showing is already recorded somewhere that had to record it anyway —
the interaction row the widget wrote, the delivery attempt the integration made,
the note the owner left. Writing a parallel event stream alongside those would
create a second source of truth that drifts from the first the moment one write
succeeds and the other does not.

So the timeline is derived. It is always consistent with the data, and there is
nothing to backfill.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.integrations.models import IntegrationDelivery
from app.features.leads.models import Lead, LeadNote
from app.features.widgets.models import Widget, WidgetInteraction


@dataclass(frozen=True)
class TimelineEntry:
    kind: str
    title: str
    detail: str
    occurred_at: datetime
    # "ok" | "pending" | "failed", so the interface can mark a failed delivery
    # without parsing the copy.
    tone: str = "ok"


def _session_hash_of(lead: Lead) -> str | None:
    meta = lead.extra_meta or {}
    value = meta.get("magnit_session_hash")
    return str(value) if value else None


async def build_timeline(db: AsyncSession, lead: Lead, widget: Widget) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = [
        TimelineEntry(
            kind="captured",
            title="Lead captured",
            detail=f'Completed "{widget.title}" and left their details.',
            occurred_at=lead.created_at,
        )
    ]

    if lead.score is not None:
        entries.append(
            TimelineEntry(
                kind="scored",
                title="Score calculated",
                detail=f"Scored {lead.score} out of 100.",
                occurred_at=lead.created_at,
            )
        )

    # The visitor's own session, when the widget managed to associate one. This
    # is where "they viewed their result and then clicked the CTA" comes from.
    interaction = await _interaction_for(db, lead, widget.id)
    if interaction is not None:
        if interaction.started_at:
            entries.append(
                TimelineEntry(
                    kind="started",
                    title="Started the tool",
                    detail=_source_line(interaction),
                    occurred_at=interaction.started_at,
                )
            )
        if interaction.result_viewed_at:
            entries.append(
                TimelineEntry(
                    kind="result",
                    title="Viewed their result",
                    detail=(
                        f"Result: {interaction.result_key}"
                        if interaction.result_key
                        else "Reached the result screen."
                    ),
                    occurred_at=interaction.result_viewed_at,
                )
            )
        if interaction.cta_clicked_at:
            entries.append(
                TimelineEntry(
                    kind="cta",
                    title="Clicked the call to action",
                    detail="Followed the result screen's main action.",
                    occurred_at=interaction.cta_clicked_at,
                )
            )

    deliveries = (
        (
            await db.execute(
                select(IntegrationDelivery)
                .where(IntegrationDelivery.lead_id == lead.id)
                .order_by(IntegrationDelivery.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    for delivery in deliveries:
        succeeded = delivery.status == "delivered"
        entries.append(
            TimelineEntry(
                kind="delivered",
                title=("Sent to your tools" if succeeded else "Delivery failed"),
                detail=(
                    "Delivered successfully."
                    if succeeded
                    else (delivery.error or "The destination refused the lead.")
                ),
                occurred_at=delivery.attempted_at,
                tone="ok" if succeeded else "failed",
            )
        )

    if lead.forwarded and lead.forwarded_at and not deliveries:
        entries.append(
            TimelineEntry(
                kind="delivered",
                title="Sent to your webhook",
                detail="Delivered to the configured endpoint.",
                occurred_at=lead.forwarded_at,
            )
        )

    if lead.contacted_at:
        entries.append(
            TimelineEntry(
                kind="contacted",
                title="Marked as contacted",
                detail="You recorded reaching out to this person.",
                occurred_at=lead.contacted_at,
            )
        )

    notes = (
        (
            await db.execute(
                select(LeadNote)
                .where(LeadNote.lead_id == lead.id)
                .order_by(LeadNote.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    entries.extend(
        TimelineEntry(
            kind="note",
            title="Note added",
            detail=note.body,
            occurred_at=note.created_at,
        )
        for note in notes
    )

    # Newest first: the question this screen answers is "what happened last".
    return sorted(entries, key=lambda entry: entry.occurred_at, reverse=True)


def _source_line(interaction: WidgetInteraction) -> str:
    attribution = interaction.attribution or {}
    campaign = attribution.get("utm_campaign") or attribution.get("utm_source")
    if campaign:
        return f"Arrived from {campaign}."
    if interaction.source_url:
        return f"Arrived from {interaction.source_url}"
    return "Opened the tool."


async def _interaction_for(
    db: AsyncSession, lead: Lead, widget_id: uuid.UUID
) -> WidgetInteraction | None:
    """The visitor session this lead came from, if it can be identified.

    The submission path stores only a hash of the browser session id, never the
    id itself, so this is a lookup by hash rather than anything that could
    identify a person across sites.
    """
    session_hash = _session_hash_of(lead)
    if session_hash:
        found = await db.execute(
            select(WidgetInteraction).where(
                WidgetInteraction.widget_id == widget_id,
                WidgetInteraction.session_hash == session_hash,
            )
        )
        return found.scalar_one_or_none()

    # Older leads predate the hash being stored on the lead itself. Falling back
    # to the session the submit endpoint stamped is better than showing nothing,
    # and it is scoped to this widget so it cannot cross tenants.
    fallback = await db.execute(
        select(WidgetInteraction)
        .where(
            WidgetInteraction.widget_id == widget_id,
            WidgetInteraction.lead_submitted_at.is_not(None),
        )
        .order_by(WidgetInteraction.lead_submitted_at.desc())
        .limit(1)
    )
    return fallback.scalar_one_or_none()
