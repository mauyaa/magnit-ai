import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.widgets.models import Widget
from app.platform.pipeline.engine import analyze as pipeline_analyze, build as pipeline_build
from app.platform.pipeline.schemas import Blueprint, BlueprintList

logger = logging.getLogger(__name__)


async def analyze_url(db: AsyncSession, user_id: str, url: str) -> BlueprintList:
    blueprints = await pipeline_analyze(url)

    widget = Widget(
        user_id=user_id,
        target_url=url,
        widget_type="pending",
        title="Pending selection",
        status="analyzed",
        analyzed_at=datetime.now(UTC),
    )
    db.add(widget)
    await db.flush()

    return blueprints


async def build_widget(
    db: AsyncSession,
    user_id: str,
    url: str,
    blueprint: Blueprint,
    widget_id: str | None = None,
) -> Widget:
    if widget_id:
        stmt = select(Widget).where(Widget.id == widget_id, Widget.user_id == user_id)
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()
        if not widget:
            raise ValueError("widget_not_found")
    else:
        widget = Widget(
            user_id=user_id,
            target_url=url,
            widget_type=blueprint.type.value,
            title=blueprint.title,
            status="building",
        )
        db.add(widget)
        await db.flush()

    widget.status = "building"
    widget.widget_type = blueprint.type.value
    widget.title = blueprint.title

    deployment = await pipeline_build(blueprint, url, str(widget.id))

    widget.status = "active"
    widget.deployment_url = deployment.url
    widget.embed_code = f'<iframe src="{deployment.url}" width="100%" height="600px"></iframe>'
    widget.deployed_at = datetime.now(UTC)

    return widget
