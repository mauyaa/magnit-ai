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
from app.platform.db.session import get_async_session
from app.platform.pipeline.schemas import Blueprint

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


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

    if widget_obj.status != "analyzed":
        raise HTTPException(status_code=400, detail="widget_not_ready")

    if not widget_obj.blueprints or payload.blueprint_index >= len(widget_obj.blueprints):
        raise HTTPException(status_code=400, detail="invalid_blueprint_index")

    blueprint_data = widget_obj.blueprints[payload.blueprint_index]
    blueprint = Blueprint(**blueprint_data)

    widget = await build_widget(db, user_id, payload.widget_id, blueprint, skip_deploy=payload.skip_deploy)

    return BuildResponse(
        widget_id=str(widget.id),
        iframe_url=widget.deployment_url or "",
        status=widget.status,
        embed_code=widget.embed_code or "",
    )


@router.get("", response_model=WidgetListResponse)
async def list_widgets(
    db: AsyncSession = Depends(get_async_session),
):
    widgets = await list_user_widgets(db, "anonymous")
    return WidgetListResponse(
        widgets=[
            WidgetStatusResponse(
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
                widget_logic=w.widget_logic,
                copywriting=w.copywriting,
                design_tokens=w.design_tokens,
                created_at=w.created_at.isoformat(),
                deployed_at=w.deployed_at.isoformat() if w.deployed_at else None,
            )
            for w in widgets
        ]
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


@router.get("/{widget_id}", response_model=WidgetStatusResponse)
async def get_widget_status(
    widget_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    widget = await get_widget(db, widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail="widget_not_found")

    return WidgetStatusResponse(
        id=str(widget.id),
        title=widget.title,
        widget_type=widget.widget_type,
        status=widget.status,
        target_url=widget.target_url,
        deployment_url=widget.deployment_url,
        embed_code=widget.embed_code,
        leads_count=widget.leads_count,
        plan_tier=widget.plan_tier,
        lead_cap=widget.lead_cap,
        brand_tokens=widget.brand_tokens,
        widget_logic=widget.widget_logic,
        copywriting=widget.copywriting,
        design_tokens=widget.design_tokens,
        created_at=widget.created_at.isoformat(),
        deployed_at=widget.deployed_at.isoformat() if widget.deployed_at else None,
    )
