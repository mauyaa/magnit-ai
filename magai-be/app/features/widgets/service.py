import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.widgets.models import Widget
from app.platform.clients.deployment import deploy_directory
from app.platform.config.settings import settings
from app.platform.pipeline.engine import analyze as pipeline_analyze, build as pipeline_build
from app.platform.pipeline.schemas import Blueprint, BlueprintList

logger = logging.getLogger(__name__)


async def analyze_url(db: AsyncSession, user_id: str, url: str) -> tuple[Widget, BlueprintList]:
    blueprints = await pipeline_analyze(url)

    widget = Widget(
        user_id=user_id,
        target_url=url,
        widget_type="pending",
        title="Pending selection",
        status="analyzed",
        analyzed_at=datetime.now(UTC),
        blueprints=[b.model_dump() for b in blueprints.blueprints],
    )
    db.add(widget)
    await db.flush()

    return widget, blueprints


def _workspace_path(widget_id: str) -> str:
    base = Path(settings.widgets_dir)
    base.mkdir(parents=True, exist_ok=True)
    return str(base / widget_id)


def _save_to_workspace(widget_id: str, widget: Widget, build_result) -> None:
    base = _workspace_path(widget_id)
    if os.path.exists(base):
        shutil.rmtree(base)

    if build_result.project_dir and os.path.exists(build_result.project_dir):
        shutil.copytree(build_result.project_dir, base, symlinks=True)

    meta = {
        "id": widget_id,
        "target_url": widget.target_url,
        "widget_type": widget.widget_type,
        "title": widget.title,
        "blueprints": widget.blueprints,
        "brand_tokens": widget.brand_tokens,
        "widget_logic": widget.widget_logic,
        "copywriting": widget.copywriting,
        "design_tokens": widget.design_tokens,
    }
    with open(f"{base}/meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    logger.info("Saved widget %s to workspace/", widget_id)


async def build_widget(
    db: AsyncSession,
    user_id: str,
    widget_id: str,
    blueprint: Blueprint,
    skip_deploy: bool = False,
) -> Widget:
    stmt = select(Widget).where(Widget.id == widget_id, Widget.user_id == user_id)
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    if not widget:
        raise ValueError("widget_not_found")

    widget.status = "building"
    widget.widget_type = blueprint.type.value
    widget.title = blueprint.title

    build_result = await pipeline_build(blueprint, widget.target_url, str(widget.id), skip_deploy=skip_deploy)

    widget.status = "active"
    widget.deployment_url = build_result.deployment.url
    widget.embed_code = f'<iframe src="{settings.site_url}/embed/{widget.id}" width="100%" height="600px"></iframe>'
    widget.deployed_at = datetime.now(UTC)

    widget.brand_tokens = build_result.architect_output.brand.model_dump()
    widget.widget_logic = build_result.architect_output.logic.model_dump()
    widget.copywriting = build_result.architect_output.copywriting
    widget.design_tokens = build_result.design_tokens.model_dump()

    _save_to_workspace(str(widget.id), widget, build_result)

    return widget


async def deploy_existing_widget(db: AsyncSession, widget_id: str) -> Widget:
    stmt = select(Widget).where(Widget.id == widget_id)
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    if not widget:
        raise ValueError("widget_not_found")

    ws_dir = _workspace_path(widget_id)
    dist_dir = os.path.join(ws_dir, "dist")
    if not os.path.isdir(dist_dir):
        raise ValueError("widget_build_not_found")

    deployment = await deploy_directory(dist_dir, widget_id)

    widget.status = "active"
    widget.deployment_url = deployment.url
    widget.embed_code = f'<iframe src="{settings.site_url}/embed/{widget_id}" width="100%" height="600px"></iframe>'
    widget.deployed_at = datetime.now(UTC)

    return widget


async def get_widget(db: AsyncSession, widget_id: str, user_id: str | None = None) -> Widget | None:
    stmt = select(Widget).where(Widget.id == widget_id)
    if user_id:
        stmt = stmt.where(Widget.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_user_widgets(db: AsyncSession, user_id: str) -> list[Widget]:
    stmt = (
        select(Widget)
        .where(Widget.user_id == user_id)
        .order_by(Widget.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
