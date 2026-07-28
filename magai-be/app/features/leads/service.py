from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leads.models import LEAD_STATUSES, Lead, LeadNote
from app.features.widgets.models import Widget, WidgetInteraction
from app.platform.db.session import rows_affected

logger = logging.getLogger(__name__)

# Caps on the free-form JSON a public caller can attach to a lead, so an embedded
# widget cannot be used to stuff arbitrarily large blobs into the database.
MAX_JSON_BYTES = 16_384
MAX_JSON_KEYS = 100
# Owner-authored limits. Generous enough never to be hit in normal use, small
# enough that a scripted client cannot turn a lead row into a document store.
MAX_TAGS = 12
MAX_NOTE_CHARS = 4_000


class WidgetNotFound(Exception):
    pass


class LeadNotFound(Exception):
    """No such lead, or it belongs to another workspace."""


class LeadCapReached(Exception):
    pass


class PayloadTooLarge(Exception):
    pass


def _validate_json_blob(blob: dict | None, field: str) -> dict | None:
    if blob is None:
        return None
    if len(blob) > MAX_JSON_KEYS:
        raise PayloadTooLarge(f"{field} has too many keys (max {MAX_JSON_KEYS})")
    try:
        encoded = json.dumps(blob)
    except (TypeError, ValueError) as exc:
        raise PayloadTooLarge(f"{field} is not JSON-serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise PayloadTooLarge(f"{field} is too large (max {MAX_JSON_BYTES} bytes)")
    return blob


async def submit_lead(
    db: AsyncSession,
    widget_id: str,
    email: str,
    name: str | None = None,
    score: int | None = None,
    answers: dict | None = None,
    metadata: dict | None = None,
) -> Lead:
    """Record a lead captured by a deployed widget.

    Called by anonymous visitors on a customer's site, so it validates sizes and
    enforces the widget's lead cap. The cap is applied with a conditional UPDATE
    so concurrent submissions cannot both slip past the limit.
    """
    try:
        parsed_id = uuid.UUID(str(widget_id))
    except (ValueError, AttributeError, TypeError):
        raise WidgetNotFound(widget_id) from None

    answers = _validate_json_blob(answers, "answers")
    metadata = _validate_json_blob(metadata, "metadata")
    session_id = None
    if metadata:
        metadata = dict(metadata)
        session_id = metadata.pop("magnit_session_id", None)

    result = await db.execute(select(Widget).where(Widget.id == parsed_id))
    widget = result.scalar_one_or_none()
    if widget is None or widget.status != "active":
        raise WidgetNotFound(widget_id)

    # Atomic claim of one slot: only succeeds while the widget is under its cap.
    claim = await db.execute(
        update(Widget)
        .where(
            Widget.id == parsed_id,
            Widget.status == "active",
            Widget.leads_count < Widget.lead_cap,
        )
        .values(leads_count=Widget.leads_count + 1)
    )
    if rows_affected(claim) == 0:
        raise LeadCapReached(widget_id)

    lead = Lead(
        widget_id=parsed_id,
        email=email,
        name=name,
        score=score,
        answers=answers,
        extra_meta=metadata,
    )
    db.add(lead)
    if isinstance(session_id, str) and 16 <= len(session_id) <= 128:
        session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        # Kept on the lead as well as used for the lookup below, so the lead's
        # timeline can find its own visitor session exactly rather than guessing
        # at the most recent one. The hash, never the id: the id is a browser
        # session token and storing it would make the lead row linkable.
        lead.extra_meta = {**(metadata or {}), "magnit_session_hash": session_hash}
        interaction_result = await db.execute(
            select(WidgetInteraction).where(
                WidgetInteraction.widget_id == parsed_id,
                WidgetInteraction.session_hash == session_hash,
            )
        )
        interaction = interaction_result.scalar_one_or_none()
        if interaction is not None and interaction.lead_submitted_at is None:
            interaction.lead_submitted_at = datetime.now(UTC)
    await db.flush()
    return lead


async def get_widget_leads(db: AsyncSession, widget_id: uuid.UUID) -> list[Lead]:
    """Leads for a widget. Callers must have already verified ownership."""
    result = await db.execute(
        select(Lead).where(Lead.widget_id == widget_id).order_by(Lead.created_at.desc())
    )
    return list(result.scalars().all())


async def get_owned_lead(db: AsyncSession, lead_id: str, user_id: uuid.UUID) -> tuple[Lead, Widget]:
    """One lead, joined to its widget, scoped to the caller's own workspace.

    The join is the authorisation: a lead has no owner of its own, so the only
    way to know whether it may be read is through the widget that captured it.
    """
    try:
        parsed = uuid.UUID(str(lead_id))
    except (ValueError, AttributeError, TypeError):
        raise LeadNotFound(lead_id) from None

    row = (
        await db.execute(
            select(Lead, Widget)
            .join(Widget, Lead.widget_id == Widget.id)
            .where(Lead.id == parsed, Widget.user_id == user_id)
        )
    ).first()
    if row is None:
        raise LeadNotFound(lead_id)
    return row[0], row[1]


def _clean_tags(tags: list[str]) -> list[str]:
    """Trim, de-duplicate case-insensitively, and bound the list.

    Tags are typed by hand into a free-text field, so "Hot", "hot " and "hot"
    arrive as three labels for one idea unless they are normalised on the way in.
    The first spelling wins, because that is the one the owner chose.
    """
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in tags:
        label = " ".join(str(tag).split())[:40]
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        cleaned.append(label)
        if len(cleaned) == MAX_TAGS:
            break
    return cleaned


async def update_lead(
    db: AsyncSession,
    lead: Lead,
    status: str | None = None,
    tags: list[str] | None = None,
) -> Lead:
    if status is not None:
        if status not in LEAD_STATUSES:
            raise ValueError("invalid_lead_status")
        lead.status = status
        # Stamped the first time only. "Contacted on" means the first outreach,
        # and re-stamping it every time someone flips the status back and forth
        # would quietly rewrite history.
        if status == "contacted" and lead.contacted_at is None:
            lead.contacted_at = datetime.now(UTC)
    if tags is not None:
        lead.tags = _clean_tags(tags) or None
    await db.flush()
    return lead


async def add_lead_note(db: AsyncSession, lead: Lead, author_id: uuid.UUID, body: str) -> LeadNote:
    note = LeadNote(lead_id=lead.id, author_id=author_id, body=body.strip()[:MAX_NOTE_CHARS])
    db.add(note)
    await db.flush()
    return note


async def delete_lead_note(db: AsyncSession, lead: Lead, note_id: str) -> None:
    try:
        parsed = uuid.UUID(str(note_id))
    except (ValueError, AttributeError, TypeError):
        raise LeadNotFound(note_id) from None
    note = await db.scalar(
        select(LeadNote).where(LeadNote.id == parsed, LeadNote.lead_id == lead.id)
    )
    if note is None:
        raise LeadNotFound(note_id)
    await db.delete(note)
    await db.flush()


async def get_lead_notes(db: AsyncSession, lead_id: uuid.UUID) -> list[LeadNote]:
    result = await db.execute(
        select(LeadNote).where(LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc())
    )
    return list(result.scalars().all())


def export_leads_csv(leads: list[Lead]) -> str:
    """Generate CSV text from a list of Lead model instances.

    Carries the owner's own columns — status, tags — as well as the captured
    ones, because the export's job is to move this list somewhere else to work
    on, and leaving the follow-up state behind makes it a worse copy than the
    screen it came from.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Email",
            "Name",
            "Score",
            "Status",
            "Tags",
            "Created At",
            "Contacted At",
            "Forwarded",
            "Answers",
        ]
    )
    for lead in leads:
        writer.writerow(
            [
                str(lead.id),
                lead.email,
                lead.name or "",
                lead.score if lead.score is not None else "",
                lead.status,
                ", ".join(lead.tags or []),
                lead.created_at.isoformat() if lead.created_at else "",
                lead.contacted_at.isoformat() if lead.contacted_at else "",
                "Yes" if lead.forwarded else "No",
                json.dumps(lead.answers) if lead.answers else "",
            ]
        )
    return output.getvalue()
