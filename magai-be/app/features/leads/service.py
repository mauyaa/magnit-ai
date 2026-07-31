from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.entitlements import effective_lead_cap, plan_lead_limit
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
# A hard ceiling on one download. Above this the honest answer is a filter, not
# a bigger file — and an unbounded export is how one click reads a table the
# paginated screen exists to avoid reading.
MAX_EXPORT_ROWS = 5_000


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


# How long two submissions from the same person count as one. Long enough to
# cover a retry, a reload and an impatient double-press; short enough that the
# same visitor returning next week is genuinely a new lead.
DUPLICATE_WINDOW = timedelta(minutes=30)


def _session_hash(session_id: object) -> str | None:
    """The stored form of a browser session id: hashed, never the id itself."""
    if not isinstance(session_id, str) or not 16 <= len(session_id) <= 128:
        return None
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


async def _duplicate_of(
    db: AsyncSession,
    widget_id: uuid.UUID,
    email: str,
    session_id: object,
) -> Lead | None:
    """The lead this submission is a repeat of, if there is one.

    Two signals, in order of confidence. A matching browser session is the
    strong one: the same tab, the same person, unambiguously. Email within a
    short window is the fallback for a widget built before sessions existed, and
    is deliberately narrow — the same address a month later is a real second
    enquiry, not a duplicate.
    """
    since = datetime.now(UTC) - DUPLICATE_WINDOW
    session_hash = _session_hash(session_id)

    if session_hash:
        match = await db.scalar(
            select(Lead)
            .where(
                Lead.widget_id == widget_id,
                Lead.email == email,
                Lead.extra_meta["magnit_session_hash"].as_string() == session_hash,
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        if match is not None:
            return match

    recent: Lead | None = await db.scalar(
        select(Lead)
        .where(Lead.widget_id == widget_id, Lead.email == email, Lead.created_at >= since)
        .order_by(Lead.created_at.desc())
        .limit(1)
    )
    return recent


async def submit_lead(
    db: AsyncSession,
    widget_id: str,
    email: str,
    name: str | None = None,
    score: int | None = None,
    answers: dict | None = None,
    metadata: dict | None = None,
) -> tuple[Lead, Widget]:
    """Record a lead captured by a deployed widget.

    Returns the lead and the widget that captured it: the caller needs the
    widget to work out where this lead has to be delivered, and re-reading it a
    second time in the same request would be a query for nothing.

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

    # A resubmission is not a second person.
    #
    # This endpoint is public, called from a page we do not control, and the two
    # most ordinary things a visitor does at this exact moment — pressing the
    # button twice because nothing visibly happened, or reloading after a slow
    # response — both used to file another lead and spend another slot against
    # the tool's cap. The owner then paid attention to the same person three
    # times and reached their limit early.
    existing = await _duplicate_of(db, parsed_id, email, session_id)
    if existing is not None:
        logger.info("Ignoring a repeat submission for widget %s", parsed_id)
        return existing, widget

    # The cap the owner is actually entitled to, not the one written on the row
    # when the tool was created. A workspace that subscribed after publishing was
    # otherwise still held to the one-off launch allowance while its plan, its
    # invoice and its pricing page all said otherwise.
    cap = effective_lead_cap(widget.lead_cap, await plan_lead_limit(db, widget.user_id))

    # Atomic claim of one slot: only succeeds while the widget is under its cap.
    claim = await db.execute(
        update(Widget)
        .where(
            Widget.id == parsed_id,
            Widget.status == "active",
            Widget.leads_count < cap,
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
    session_hash = _session_hash(session_id)
    if session_hash:
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
    return lead, widget


async def get_widget_leads(db: AsyncSession, widget_id: uuid.UUID) -> list[Lead]:
    """Leads for a widget. Callers must have already verified ownership."""
    result = await db.execute(
        select(Lead).where(Lead.widget_id == widget_id).order_by(Lead.created_at.desc())
    )
    return list(result.scalars().all())


async def list_workspace_leads(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    widget_id: uuid.UUID | None = None,
    status: str | None = None,
    query: str | None = None,
    sort: str = "created_at",
    descending: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Lead, str]], int]:
    """One page of the workspace's leads, newest first, with a true total.

    Replaces a fan-out that issued one unpaginated request per tool and threw
    away the ones that failed. At the volumes the plans advertise — 2,000 and
    10,000 leads a tool — that meant a workspace with ten tools asked for
    everything it had ever captured on every visit to the screen, and quietly
    showed a subset if any single request fell over. A page and a count are what
    the screen actually needs, and the count is what makes "showing 50 of 3,214"
    a fact rather than a guess.

    Returns ``(rows, total)`` where each row is a lead and the title of the tool
    that captured it — joined here so the table does not have to look up ten
    widgets to render fifty rows.
    """
    filters = [Widget.user_id == user_id]
    if widget_id is not None:
        filters.append(Lead.widget_id == widget_id)
    if status:
        filters.append(Lead.status == status)
    if query:
        # Email and name only. Answers are visitor-supplied free text and
        # searching them would make this a full scan of a JSON column.
        needle = f"%{query.strip()[:120]}%"
        filters.append(or_(Lead.email.ilike(needle), Lead.name.ilike(needle)))

    total = int(
        await db.scalar(
            select(func.count(Lead.id)).join(Widget, Lead.widget_id == Widget.id).where(*filters)
        )
        or 0
    )

    # Ordering happens here, not in the browser. Sorting one page of fifty and
    # calling it "sorted by score" would be a lie the screen could not detect.
    column = {"score": Lead.score, "email": Lead.email}.get(sort, Lead.created_at)
    ordering = column.desc() if descending else column.asc()

    rows = await db.execute(
        select(Lead, Widget.title)
        .join(Widget, Lead.widget_id == Widget.id)
        .where(*filters)
        # `id` as the tiebreak: without it two leads captured in the same second
        # can swap places between pages, so one is shown twice and one never.
        .order_by(ordering, Lead.id.desc())
        # The route caps what an API caller may ask for; this is the backstop
        # that keeps any caller from reading the whole table in one query.
        .limit(max(1, min(limit, MAX_EXPORT_ROWS)))
        .offset(max(0, offset))
    )
    return [(lead, title) for lead, title in rows.all()], total


async def export_workspace_leads(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    widget_id: uuid.UUID | None = None,
    status: str | None = None,
    query: str | None = None,
) -> str:
    """Every lead matching the current filters, as CSV.

    Deliberately not "every lead on the current page". A download that silently
    exports the fifty rows that happened to be on screen — when the customer
    filtered to three thousand — is worse than no export at all, because they
    will act on it believing it is complete.
    """
    rows, _ = await list_workspace_leads(
        db,
        user_id,
        widget_id=widget_id,
        status=status,
        query=query,
        limit=MAX_EXPORT_ROWS,
        offset=0,
    )
    return export_leads_csv([lead for lead, _ in rows])


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
