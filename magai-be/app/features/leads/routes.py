from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.billing.deps import CurrentEntitlements, upgrade_required
from app.features.billing.entitlements import FeatureLocked
from app.features.billing.plans import Feature
from app.features.integrations.service import fan_out_lead
from app.features.leads.models import Lead, LeadNote
from app.features.leads.notify import deliver_lead_webhook, notify_owner_of_lead
from app.features.leads.schemas import (
    CreateLeadNoteRequest,
    LeadDetailResponse,
    LeadNoteResponse,
    LeadResponse,
    SubmitLeadRequest,
    SubmitLeadResponse,
    TimelineEntryResponse,
    UpdateLeadRequest,
)
from app.features.leads.service import (
    LeadCapReached,
    LeadNotFound,
    PayloadTooLarge,
    WidgetNotFound,
    add_lead_note,
    delete_lead_note,
    export_leads_csv,
    get_lead_notes,
    get_owned_lead,
    get_widget_leads,
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
        lead = await submit_lead(
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

    background.add_task(notify_owner_of_lead, lead.id)
    background.add_task(deliver_lead_webhook, lead.id)
    # Connected CRMs and mailing lists, fanned out after the response. Same rule
    # as the other two: a visitor's submission never waits on a third party, and
    # never fails because of one.
    background.add_task(fan_out_lead, lead.id)
    return SubmitLeadResponse(received=True)


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
    return LeadDetailResponse(
        lead=_lead_to_response(lead, len(notes)),
        widget_title=widget.title,
        widget_id=str(widget.id),
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
