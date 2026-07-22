import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.widgets.models import Widget
from app.features.widgets.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BuildRequest,
    BuildResponse,
    WidgetListResponse,
    WidgetStatusResponse,
)
from app.features.widgets.service import (
    analyze_url,
    build_widget,
    deploy_existing_widget,
    get_widget,
    list_user_widgets,
)
from app.platform.config.settings import settings
from app.platform.db.session import get_async_session
from app.platform.pipeline.schemas import Blueprint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


def _widget_to_response(w: Widget) -> WidgetStatusResponse:
    return WidgetStatusResponse(
        id=str(w.id),
        title=w.title,
        widget_type=w.widget_type,
        status=w.status,
        target_url=w.target_url,
        deployment_url=w.deployment_url,
        embed_code=w.embed_code,
        leads_count=w.leads_count,
        plan_tier=w.plan_tier,
        lead_cap=w.lead_cap,
        brand_tokens=w.brand_tokens,
        visual_language=w.visual_language,
        widget_logic=w.widget_logic,
        copywriting=w.copywriting,
        design_tokens=w.design_tokens,
        build_stage=w.build_stage,
        build_progress=w.build_progress,
        build_error=w.build_error,
        created_at=w.created_at.isoformat(),
        deployed_at=w.deployed_at.isoformat() if w.deployed_at else None,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    payload: AnalyzeRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user_id = "anonymous"
    widget, blueprints = await analyze_url(db, user_id, payload.url)
    return AnalyzeResponse(
        widget_id=str(widget.id),
        blueprints=blueprints.blueprints,
    )


@router.post("/build", response_model=BuildResponse)
async def build_endpoint(
    payload: BuildRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user_id = "anonymous"

    stmt = select(Widget).where(Widget.id == payload.widget_id)
    result = await db.execute(stmt)
    widget_obj = result.scalar_one_or_none()
    if not widget_obj:
        raise HTTPException(status_code=404, detail="widget_not_found")

    if widget_obj.status not in ("analyzed", "failed"):
        logger.warning(
            "Widget %s has status=%s (expected 'analyzed' or 'failed'), url=%s",
            payload.widget_id, widget_obj.status, widget_obj.target_url,
        )
        raise HTTPException(status_code=400, detail="widget_not_ready")

    if not widget_obj.blueprints or payload.blueprint_index >= len(widget_obj.blueprints):
        raise HTTPException(status_code=400, detail="invalid_blueprint_index")

    blueprint_data = widget_obj.blueprints[payload.blueprint_index]
    blueprint = Blueprint(**blueprint_data)

    from app.platform.pipeline.tasks import build_widget_task

    try:
        build_widget_task.delay(
            widget_id=str(widget_obj.id),
            blueprint_dict=blueprint_data,
            url=widget_obj.target_url,
            skip_deploy=payload.skip_deploy,
        )
    except Exception:
        logger.exception("Failed to enqueue build task for %s (Redis down?)", payload.widget_id)
        raise HTTPException(
            status_code=503,
            detail=f"Build queue unavailable \u2014 check that Redis is running on {settings.celery_broker_url}",
        )

    widget_obj.status = "building"
    widget_obj.widget_type = blueprint.type.value
    widget_obj.title = blueprint.title
    widget_obj.build_stage = "queued"
    widget_obj.build_progress = 0.0
    widget_obj.build_error = None
    await db.commit()

    return BuildResponse(
        widget_id=str(widget_obj.id),
        iframe_url="",
        status="building",
        embed_code="",
    )


@router.get("", response_model=WidgetListResponse)
async def list_widgets(
    db: AsyncSession = Depends(get_async_session),
):
    widgets = await list_user_widgets(db, "anonymous")
    return WidgetListResponse(
        widgets=[_widget_to_response(w) for w in widgets],
    )


@router.post("/{widget_id}/deploy", response_model=BuildResponse)
async def deploy_endpoint(
    widget_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    try:
        widget = await deploy_existing_widget(db, widget_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return BuildResponse(
        widget_id=str(widget.id),
        iframe_url=widget.deployment_url or "",
        status=widget.status,
        embed_code=widget.embed_code or "",
    )


@router.post("/{widget_id}/retry", response_model=BuildResponse)
async def retry_build_endpoint(
    widget_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    stmt = select(Widget).where(Widget.id == widget_id)
    result = await db.execute(stmt)
    widget_obj = result.scalar_one_or_none()
    if not widget_obj:
        raise HTTPException(status_code=404, detail="widget_not_found")

    if widget_obj.status not in ("failed",):
        raise HTTPException(status_code=400, detail="widget_not_failed")

    if not widget_obj.blueprints:
        raise HTTPException(status_code=400, detail="no_blueprints")

    blueprint_data = widget_obj.blueprints[0]

    from app.platform.pipeline.tasks import build_widget_task

    try:
        build_widget_task.delay(
            widget_id=str(widget_obj.id),
            blueprint_dict=blueprint_data,
            url=widget_obj.target_url,
            skip_deploy=False,
        )
    except Exception:
        logger.exception("Failed to enqueue retry build for %s (Redis down?)", widget_id)
        raise HTTPException(
            status_code=503,
            detail=f"Build queue unavailable \u2014 check that Redis is running on {settings.celery_broker_url}",
        )

    widget_obj.status = "building"
    widget_obj.build_stage = "queued"
    widget_obj.build_progress = 0.0
    widget_obj.build_error = None
    await db.commit()

    return BuildResponse(
        widget_id=str(widget_obj.id),
        iframe_url="",
        status="building",
        embed_code="",
    )


@router.get("/{widget_id}", response_model=WidgetStatusResponse)
async def get_widget_status(
    widget_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    widget = await get_widget(db, widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail="widget_not_found")

    return _widget_to_response(widget)
