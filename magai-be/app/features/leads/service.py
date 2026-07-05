import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leads.models import Lead
from app.features.widgets.models import Widget

logger = logging.getLogger(__name__)


async def submit_lead(
    db: AsyncSession,
    widget_id: str,
    email: str,
    name: str | None = None,
    score: int | None = None,
    answers: dict | None = None,
    metadata: dict | None = None,
) -> Lead:
    stmt = select(Widget).where(Widget.id == widget_id)
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    if not widget:
        raise ValueError("widget_not_found")

    if widget.leads_count >= widget.lead_cap:
        raise ValueError("lead_cap_reached")

    lead = Lead(
        widget_id=widget_id,
        email=email,
        name=name,
        score=score,
        answers=answers,
        extra_meta=metadata,
    )
    db.add(lead)

    stmt = (
        update(Widget)
        .where(Widget.id == widget_id)
        .values(leads_count=Widget.leads_count + 1)
    )
    await db.execute(stmt)
    await db.flush()

    return lead


async def get_widget_leads(db: AsyncSession, widget_id: str) -> list[Lead]:
    stmt = select(Lead).where(Lead.widget_id == widget_id).order_by(Lead.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
