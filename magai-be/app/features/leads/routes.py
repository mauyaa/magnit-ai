from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leads.models import Lead
from app.features.leads.schemas import (
    LeadResponse,
    SubmitLeadRequest,
    SubmitLeadResponse,
)
from app.features.leads.service import get_widget_leads, submit_lead
from app.platform.db.session import get_async_session

router = APIRouter(tags=["leads"])


@router.post("/api/leads/{widget_id}", response_model=SubmitLeadResponse)
async def submit_lead_endpoint(
    widget_id: str,
    payload: SubmitLeadRequest,
    db: AsyncSession = Depends(get_async_session),
):
    try:
        await submit_lead(
            db,
            widget_id=widget_id,
            email=payload.email,
            name=payload.name,
            score=payload.score,
            answers=payload.answers,
            metadata=payload.metadata,
        )
        return SubmitLeadResponse(received=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/widgets/{widget_id}/leads", response_model=list[LeadResponse])
async def get_leads(
    widget_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    leads = await get_widget_leads(db, widget_id)
    return [
        LeadResponse(
            id=str(l.id),
            widget_id=str(l.widget_id),
            email=l.email,
            name=l.name,
            score=l.score,
            created_at=l.created_at.isoformat(),
        )
        for l in leads
    ]
