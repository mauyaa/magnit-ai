from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.billing.deps import CurrentEntitlements, upgrade_required
from app.features.billing.entitlements import FeatureLocked
from app.features.billing.plans import Feature
from app.features.leads.delivery import (
    deliveries_for,
    enqueue_lead_deliveries,
    retry_delivery,
    run_deliveries,
)
from app.features.leads.models import LEAD_STATUSES, Lead, LeadDelivery, LeadNote
from app.features.leads.schemas import (
    CreateLeadNoteRequest,
    LeadDeliveryResponse,
    LeadDetailResponse,
    LeadNoteResponse,
    LeadPageResponse,
    LeadResponse,
    SubmitLeadRequest,
    SubmitLeadResponse,
    TimelineEntryResponse,
    UpdateLeadRequest,
    WorkspaceLeadResponse,
)
from app.features.leads.service import (
    LeadCapReached,
    LeadNotFound,
    PayloadTooLarge,
    WidgetNotFound,
    add_lead_note,
    delete_lead_note,
    export_leads_csv,
    export_workspace_leads,
    get_lead_notes,
    get_owned_lead,
    get_widget_leads,
    list_workspace_leads,
    submit_lead,
    update_lead,
)
from app.features.leads.timeline import build_timeline
from app.features.widgets.service import WidgetNotFound as OwnedWidgetNotFound
from app.features.widgets.service import get_owned_widget
from app.platform.db.session import get_async_session
from app.platform.security.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["leads"])

_LEAD_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead_not_found")


async def _note_counts(db: AsyncSession, lead_ids: list) -> dict:
    """How many notes each lead carries, in one query rather than N.

    The leads table shows a note indicator per row; asking per row is how a
    hundred-lead page becomes a hundred and one queries.
    """
    if not lead_ids:
        return {}
    rows = await db.execute(
        select(LeadNote.lead_id, func.count(LeadNote.id))
        .where(LeadNote.lead_id.in_(lead_ids))
        .group_by(LeadNote.lead_id)
    )
    return {lead_id: count for lead_id, count in rows.all()}


def _lead_to_response(lead: Lead, note_count: int = 0) -> LeadResponse:
    meta = lead.extra_meta or {}
    return LeadResponse(
        id=str(lead.id),
        widget_id=str(lead.widget_id),
        email=lead.email,
        name=lead.name,
        score=lead.score,
        answers=lead.answers,
        metadata=meta or None,
        qualification_status=(
            str(meta.get("qualification_status")) if meta.get("qualification_status") else None
        ),
        result_key=(str(meta.get("result_key")) if meta.get("result_key") else None),
        forwarded=lead.forwarded,
        forwarded_at=lead.forwarded_at.isoformat() if lead.forwarded_at else None,
        created_at=lead.created_at.isoformat(),
        status=lead.status,
        tags=list(lead.tags or []),
        contacted_at=lead.contacted_at.isoformat() if lead.contacted_at else None,
        note_count=note_count,
    )


@router.post(
    "/api/leads/{widget_id}",
    response_model=SubmitLeadResponse,
    dependencies=[rate_limit("lead_submit")],
)
async def submit_lead_endpoint(
    widget_id: str,
    payload: SubmitLeadRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
) -> SubmitLeadResponse:
    """Public: called by a deployed widget on the customer's own site."""
    try:
        lead, widget = await submit_lead(
            db,
            widget_id=widget_id,
            email=payload.email,
            name=payload.name,
            score=payload.score,
            answers=payload.answers,
            metadata=payload.metadata,
        )
    except WidgetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget_not_found"
        ) from None
    except LeadCapReached:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="lead_cap_reached"
        ) from None
    except PayloadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from None

    # Written down before the response, attempted after it. The outbox row is
    # created in the same transaction as the lead, so a business is never in the
    # position of having a lead in the database with no record that it was owed
    # an email, a webhook and its CRM — which is exactly what a crash between the
    # response and a fire-and-forget task used to produce.
    deliveries = await enqueue_lead_deliveries(db, lead, widget)
    delivery_ids = [row.id for row in deliveries]
    # Same rule as before: a visitor's submission never waits on a third party
    # and never fails because of one. What is new is that failing here schedules
    # a retry rather than losing the delivery.
    background.add_task(run_deliveries, delivery_ids)
    return SubmitLeadResponse(received=True)


@router.get("/api/leads", response_model=LeadPageResponse)
async def list_leads(
    user: CurrentUser,
    widget_id: str | None = Query(default=None),
    lead_status: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, max_length=120),
    sort: str = Query(default="created_at", pattern="^(created_at|score|email)$"),
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
) -> LeadPageResponse:
    """Every lead in the workspace, one page at a time.

    The screen used to build this itself: one unpaginated request per tool,
    fired in parallel, with the failures discarded. That is fine with three
    leads and wrong at the volumes the plans sell — and its failure mode was the
    worst available one, because a dropped request looked exactly like an empty
    inbox. Filtering and counting belong on the side that has the index.
    """
    if lead_status is not None and lead_status not in LEAD_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_lead_status"
        )

    parsed_widget: uuid.UUID | None = None
    if widget_id:
        try:
            parsed_widget = uuid.UUID(widget_id)
        except (ValueError, AttributeError, TypeError):
            # A malformed id filters to nothing rather than 500ing on Postgres.
            return LeadPageResponse(items=[], total=0, limit=limit, offset=offset)

    rows, total = await list_workspace_leads(
        db,
        user.workspace_id,
        widget_id=parsed_widget,
        status=lead_status,
        query=query,
        sort=sort,
        descending=direction == "desc",
        limit=limit,
        offset=offset,
    )
    counts = await _note_counts(db, [lead.id for lead, _ in rows])
    return LeadPageResponse(
        items=[
            WorkspaceLeadResponse(
                **_lead_to_response(lead, counts.get(lead.id, 0)).model_dump(),
                widget_title=title,
            )
            for lead, title in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/api/leads/export.csv", response_class=Response)
async def export_workspace_leads_endpoint(
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    widget_id: str | None = Query(default=None),
    lead_status: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    """Download every lead matching the current filters.

    The filters are the ones on screen, and the download honours all of them.
    The screen used to build this file from whatever rows the browser happened
    to be holding, which with pagination means fifty — a customer filtering to
    three thousand leads and downloading fifty of them would have no way to tell.
    """
    try:
        entitlements.require(Feature.CSV_EXPORT)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    parsed_widget: uuid.UUID | None = None
    if widget_id:
        try:
            parsed_widget = uuid.UUID(widget_id)
        except (ValueError, AttributeError, TypeError):
            parsed_widget = None

    csv_text = await export_workspace_leads(
        db,
        user.workspace_id,
        widget_id=parsed_widget,
        status=lead_status if lead_status in LEAD_STATUSES else None,
        query=query,
    )
    stamp = datetime.now(UTC).date().isoformat()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="magnitai-leads-{stamp}.csv"'},
    )


@router.get("/api/widgets/{widget_id}/leads", response_model=list[LeadResponse])
async def get_leads(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> list[LeadResponse]:
    """Leads for one of the caller's own widgets."""
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except OwnedWidgetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget_not_found"
        ) from None

    leads = await get_widget_leads(db, widget.id)
    counts = await _note_counts(db, [lead.id for lead in leads])
    return [_lead_to_response(lead, counts.get(lead.id, 0)) for lead in leads]


@router.get("/api/leads/{lead_id}/detail", response_model=LeadDetailResponse)
async def get_lead_detail(
    lead_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> LeadDetailResponse:
    """One lead, with its notes and a timeline assembled from real events."""
    try:
        lead, widget = await get_owned_lead(db, lead_id, user.workspace_id)
    except LeadNotFound:
        raise _LEAD_NOT_FOUND from None

    notes = await get_lead_notes(db, lead.id)
    timeline = await build_timeline(db, lead, widget)
    deliveries = await deliveries_for(db, lead.id)
    return LeadDetailResponse(
        lead=_lead_to_response(lead, len(notes)),
        widget_title=widget.title,
        widget_id=str(widget.id),
        deliveries=[_delivery_to_response(row) for row in deliveries],
        notes=[
            LeadNoteResponse(
                id=str(note.id), body=note.body, created_at=note.created_at.isoformat()
            )
            for note in notes
        ],
        timeline=[
            TimelineEntryResponse(
                kind=entry.kind,
                title=entry.title,
                detail=entry.detail,
                occurred_at=entry.occurred_at.isoformat(),
                tone=entry.tone,
            )
            for entry in timeline
        ],
    )


def _delivery_to_response(row: LeadDelivery) -> LeadDeliveryResponse:
    return LeadDeliveryResponse(
        id=str(row.id),
        channel=row.channel,
        provider=None,
        status=row.status,
        attempts=row.attempts,
        last_error=row.last_error,
        next_attempt_at=row.next_attempt_at.isoformat() if row.next_attempt_at else None,
        delivered_at=row.delivered_at.isoformat() if row.delivered_at else None,
        # Only a delivery that has run out of automatic attempts needs a person.
        # Offering "retry" on one that is already queued would invite someone to
        # press it repeatedly and conclude the product is broken.
        retryable=row.status == "failed",
    )


@router.post(
    "/api/leads/{lead_id}/deliveries/{delivery_id}/retry",
    response_model=LeadDeliveryResponse,
)
async def retry_lead_delivery(
    lead_id: str,
    delivery_id: str,
    user: CurrentUser,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
) -> LeadDeliveryResponse:
    """Send a lead to a destination that has stopped trying on its own.

    The automatic attempts are bounded on purpose, so a permanently broken
    endpoint does not consume workers forever. That leaves one case the product
    has to answer for: the customer has fixed their end and wants the lead they
    already have delivered. This is that button.
    """
    try:
        lead, _ = await get_owned_lead(db, lead_id, user.workspace_id)
    except LeadNotFound:
        raise _LEAD_NOT_FOUND from None

    rows = await deliveries_for(db, lead.id)
    row = next((item for item in rows if str(item.id) == delivery_id), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery_not_found")

    await retry_delivery(db, row)
    background.add_task(run_deliveries, [row.id])
    return _delivery_to_response(row)


@router.patch("/api/leads/{lead_id}", response_model=LeadResponse)
async def update_lead_endpoint(
    lead_id: str,
    payload: UpdateLeadRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> LeadResponse:
    """Move a lead along the pipeline, or re-tag it."""
    try:
        lead, _ = await get_owned_lead(db, lead_id, user.workspace_id)
    except LeadNotFound:
        raise _LEAD_NOT_FOUND from None
    try:
        entitlements.require(Feature.LEAD_PIPELINE)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    try:
        await update_lead(db, lead, status=payload.status, tags=payload.tags)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    notes = await get_lead_notes(db, lead.id)
    return _lead_to_response(lead, len(notes))


@router.post(
    "/api/leads/{lead_id}/notes",
    response_model=LeadNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_note(
    lead_id: str,
    payload: CreateLeadNoteRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> LeadNoteResponse:
    try:
        lead, _ = await get_owned_lead(db, lead_id, user.workspace_id)
    except LeadNotFound:
        raise _LEAD_NOT_FOUND from None
    try:
        entitlements.require(Feature.LEAD_PIPELINE)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    note = await add_lead_note(db, lead, user.id, payload.body)
    return LeadNoteResponse(id=str(note.id), body=note.body, created_at=note.created_at.isoformat())


@router.delete("/api/leads/{lead_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead_note_endpoint(
    lead_id: str,
    note_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    try:
        lead, _ = await get_owned_lead(db, lead_id, user.workspace_id)
        await delete_lead_note(db, lead, note_id)
    except LeadNotFound:
        raise _LEAD_NOT_FOUND from None


@router.get("/api/widgets/{widget_id}/leads/export")
async def export_leads(
    widget_id: str,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    """Export leads for one of the caller's own widgets as a CSV file."""
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except OwnedWidgetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget_not_found"
        ) from None
    try:
        entitlements.require(Feature.CSV_EXPORT)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    leads = await get_widget_leads(db, widget.id)
    csv_data = export_leads_csv(leads)
    filename = f"leads_{widget.id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
