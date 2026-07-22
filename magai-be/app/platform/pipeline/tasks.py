from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.features.widgets.models import Widget
from app.platform.celery_app import celery_app
from app.platform.clients.deployment import deploy_directory
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory
from app.platform.pipeline.engine import build as pipeline_build
from app.platform.pipeline.events import events as event_manager
from app.platform.pipeline.schemas import Blueprint

logger = logging.getLogger(__name__)


_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


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


async def _update_build_progress(widget_id: str, **kwargs) -> None:
    try:
        async with async_session_factory() as session:
            stmt = select(Widget).where(Widget.id == widget_id)
            result = await session.execute(stmt)
            widget = result.scalar_one_or_none()
            if widget:
                for k, v in kwargs.items():
                    setattr(widget, k, v)
                await session.commit()
    except Exception:
        logger.warning("Failed to persist build progress for %s", widget_id, exc_info=True)


async def _update_widget_after_build(widget_id: str, build_result):
    async with async_session_factory() as session:
        stmt = select(Widget).where(Widget.id == widget_id)
        result = await session.execute(stmt)
        widget = result.scalar_one_or_none()
        if not widget:
            logger.error("Widget %s not found after build", widget_id)
            return

        widget.status = "active"
        widget.widget_type = widget.widget_type
        widget.deployment_url = build_result.deployment.url
        widget.embed_code = (
            f'<iframe src="{settings.site_url}/embed/{widget.id}"'
            f' width="100%" height="600px"></iframe>'
        )
        widget.deployed_at = datetime.now(UTC)
        widget.build_error = None
        widget.build_stage = None
        widget.build_progress = None

        widget.brand_tokens = build_result.architect_output.brand.model_dump()
        widget.visual_language = build_result.architect_output.visual_language.model_dump()
        widget.widget_logic = build_result.architect_output.logic.model_dump()
        widget.copywriting = build_result.architect_output.copywriting
        widget.design_tokens = build_result.design_tokens.model_dump()

        _save_to_workspace(widget_id, widget, build_result)

        await session.commit()
        logger.info("Widget %s updated to active", widget_id)


async def _run_build_pipeline(widget_id: str, blueprint_dict: dict, url: str, skip_deploy: bool):
    logger.info("Build pipeline starting for widget %s", widget_id)
    blueprint = Blueprint(**blueprint_dict)

    build_result = await pipeline_build(blueprint, url, widget_id, skip_deploy=skip_deploy)

    await _update_widget_after_build(widget_id, build_result)

    logger.info("Build pipeline complete for widget %s", widget_id)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30, acks_late=True)
def build_widget_task(self, widget_id: str, blueprint_dict: dict, url: str, skip_deploy: bool = False):
    loop = _get_loop()
    try:
        loop.run_until_complete(_run_build_pipeline(widget_id, blueprint_dict, url, skip_deploy))
        return {"success": True, "widget_id": widget_id}
    except Exception as exc:
        logger.exception(
            "build_widget_task failed for %s (attempt %d/%d)",
            widget_id,
            self.request.retries,
            self.max_retries,
        )
        try:
            loop.run_until_complete(
                event_manager.publish_stage(
                    widget_id, "pipeline", "failed",
                    f"Build failed: {exc}",
                    progress=0.0,
                )
            )
        except Exception:
            pass

        exc_str = str(exc)[:2000]
        is_fatal = any(
            kw in exc_str for kw in [
                "failed to locate a name",
                "No such file or directory",
                "No module named",
                "ImportError",
                "SyntaxError",
            ]
        )

        if is_fatal or self.request.retries >= self.max_retries:
            try:
                loop.run_until_complete(
                    _update_build_progress(
                        widget_id, status="failed", build_error=exc_str, build_stage=None, build_progress=None,
                    )
                )
            except Exception:
                pass
            return {"success": False, "widget_id": widget_id, "error": exc_str}

        raise self.retry(exc=exc)
