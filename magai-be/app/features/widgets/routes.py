from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.widgets.models import Widget
from app.features.widgets.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BuildRequest,
    BuildResponse,
    WidgetStatusResponse,
)
from app.features.widgets.service import analyze_url, build_widget
from app.platform.db.session import get_async_session

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    payload: AnalyzeRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user_id = "anonymous"
    blueprints = await analyze_url(db, user_id, payload.url)
    return AnalyzeResponse(blueprints=blueprints.blueprints)


@router.post("/build", response_model=BuildResponse)
async def build_endpoint(
    payload: BuildRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user_id = "anonymous"
    widget = await build_widget(db, user_id, payload.url, payload.blueprint)
    return BuildResponse(
        widget_id=str(widget.id),
        iframe_url=widget.deployment_url or "",
        status=widget.status,
    )


@router.get("/{widget_id}", response_model=WidgetStatusResponse)
async def get_widget_status(
    widget_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    stmt = select(Widget).where(Widget.id == widget_id)
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    if not widget:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="widget_not_found")

    return WidgetStatusResponse(
        widget_id=str(widget.id),
        status=widget.status,
        iframe_url=widget.deployment_url,
        embed_code=widget.embed_code,
    )
