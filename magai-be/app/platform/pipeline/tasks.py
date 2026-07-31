"""Celery tasks: widget builds and the scheduled self-heal sweep."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.brand import (
    apply_to_extraction,
    design_token_overrides,
    get_brand,
    is_configured,
)
from app.features.widgets.models import Widget, WidgetHealEvent
from app.features.widgets.service import (
    record_deployment,
    widget_logic_from_architect,
    workspace_dir,
)
from app.platform.celery_app import celery_app
from app.platform.clients.deployment import deploy_directory
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory
from app.platform.observability.metrics import (
    heal_checks_total,
    heal_sweep_widgets,
    pipeline_build_duration_seconds,
    pipeline_builds_total,
    product_activation_events_total,
)
from app.platform.pipeline.engine import BuildResult, generate_and_deploy
from app.platform.pipeline.engine import build as pipeline_build
from app.platform.pipeline.events import events as event_manager
from app.platform.pipeline.heal import check_brand_drift, check_deploy_health
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    BrandExtraction,
    CreationBrief,
    SiteEvidence,
    WidgetType,
)
from app.platform.security.locks import LockNotAcquired, distributed_lock, process_lock

logger = logging.getLogger(__name__)

# Error fragments that indicate a deterministic failure: retrying the identical
# job would fail identically, so the widget is marked failed immediately.
_NON_RETRYABLE_MARKERS = (
    "failed to locate a name",
    "No such file or directory",
    "No module named",
    "ImportError",
    "SyntaxError",
    "invalid_blueprint_index",
)


def widget_lock_key(widget_id: str) -> str:
    """The one lock that both building and healing a widget must hold.

    These used to be two keys — ``widget-build:{id}`` and ``widget-heal:{id}`` —
    which excluded two builds and two heals but never a build against a heal.
    That gap was reachable: a heal holds its lock for the minutes
    ``generate_and_deploy`` takes while the widget's status is still "active", so
    nothing stopped an owner pressing Rebuild in that window. Both paths then
    wrote the same ``workspace_dir(widget_id)`` — each one ``rmtree``-ing the
    staging directory the other was mid-copy into — and both recorded a
    deployment, leaving ``deployment_url`` set by whichever committed last.

    One key per widget is what ``locks.py`` already documents as the intent.
    """
    return f"widget:{widget_id}"


_loop: asyncio.AbstractEventLoop | None = None
_local_build_tasks: set[asyncio.Task[None]] = set()


def _get_loop() -> asyncio.AbstractEventLoop:
    """Reuse one event loop per worker process.

    Celery tasks are synchronous entry points into async code; creating a fresh
    loop per task leaks the connection pools bound to the old one.
    """
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _save_to_workspace(widget_id: str, widget: Widget, build_result: BuildResult) -> None:
    """Persist the built project so redeploys and rollbacks need no rebuild."""
    base = workspace_dir(widget_id)
    staging = base.with_name(f"{base.name}.incoming")

    if not build_result.project_dir or not os.path.exists(build_result.project_dir):
        logger.warning("No project directory to save for widget %s", widget_id)
        return

    # Copy to a staging path and swap, so an interrupted copy cannot leave the
    # widget with a half-written build directory.
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(build_result.project_dir, staging, symlinks=True)

    meta = {
        "id": widget_id,
        "target_url": widget.target_url,
        "widget_type": widget.widget_type,
        "title": widget.title,
        "brand_tokens": widget.brand_tokens,
        "visual_language": widget.visual_language,
        "widget_logic": widget.widget_logic,
        "copywriting": widget.copywriting,
        "design_tokens": widget.design_tokens,
        "saved_at": datetime.now(UTC).isoformat(),
    }
    (staging / "meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    staging.rename(base)
    logger.info("Saved build artifacts for widget %s", widget_id)


async def _update_build_progress(widget_id: str, **kwargs: Any) -> None:
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(Widget).where(Widget.id == widget_id))
            widget = result.scalar_one_or_none()
            if widget:
                for key, value in kwargs.items():
                    setattr(widget, key, value)
                await session.commit()
    except Exception:
        logger.warning("Could not persist build progress for %s", widget_id, exc_info=True)


async def _update_widget_after_build(
    widget_id: str,
    build_result: BuildResult,
    *,
    local_publish: bool = False,
) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Widget).where(Widget.id == widget_id))
        widget = result.scalar_one_or_none()
        if widget is None:
            logger.error("Widget %s vanished during its build", widget_id)
            return

        widget.brand_tokens = build_result.architect_output.brand.model_dump(mode="json")
        widget.visual_language = build_result.architect_output.visual_language.model_dump(
            mode="json"
        )
        widget.widget_logic = widget_logic_from_architect(build_result.architect_output)
        widget.copywriting = build_result.architect_output.copywriting
        widget.design_tokens = build_result.design_tokens.model_dump(mode="json")
        widget.build_error = None
        widget.build_stage = None
        widget.build_progress = None
        widget.heal_failure_count = 0

        # Artifacts must exist before database state tells a browser that the
        # tool is live. This ordering matters for local publishing, where the
        # first iframe request can arrive immediately after the status poll.
        _save_to_workspace(widget_id, widget, build_result)

        deployment_url = build_result.deployment.url
        embed_url = build_result.deployment.embed_url
        provider_deployment_id = build_result.deployment.provider_deployment_id
        trigger = "build"
        if local_publish:
            # One address per tool that serves whatever is currently on disk —
            # the same guarantee the production alias gives, locally.
            deployment_url = f"{settings.site_url.rstrip('/')}/local-widgets/{widget_id}/"
            embed_url = deployment_url
            provider_deployment_id = None
            trigger = "local_build"

        if deployment_url:
            await record_deployment(
                session,
                widget,
                deployment_url,
                trigger=trigger,
                embed_url=embed_url,
                provider_deployment_id=provider_deployment_id,
            )
            product_activation_events_total.labels("publish", "succeeded").inc()
        else:
            # A build with publishing explicitly skipped is not live. Keep it
            # retryable and never show an "active" badge without a working URL.
            widget.status = "analyzed"
            widget.deployment_url = None
            widget.embed_code = None

        await session.commit()
        logger.info("Widget %s build complete", widget_id)


async def _run_build_pipeline(
    widget_id: str,
    blueprint_dict: dict,
    url: str,
    skip_deploy: bool,
    architect_override_dict: dict | None = None,
    source_evidence_dict: dict | None = None,
    creation_brief_dict: dict | None = None,
    *,
    local_publish: bool = False,
    use_process_lock: bool = False,
) -> None:
    blueprint = Blueprint(**blueprint_dict)
    architect_override = (
        ArchitectOutput(**architect_override_dict) if architect_override_dict else None
    )
    source_evidence = (
        SiteEvidence.model_validate(source_evidence_dict) if source_evidence_dict else None
    )
    creation_brief = (
        CreationBrief.model_validate(creation_brief_dict) if creation_brief_dict else None
    )

    brand_overrides, token_overrides = await _workspace_brand_overrides(widget_id)

    # One build per widget at a time: concurrent builds share a project directory.
    # The same key the heal sweep takes, so the two cannot overlap either.
    build_lock = (
        process_lock(widget_lock_key(widget_id))
        if use_process_lock
        else distributed_lock(widget_lock_key(widget_id))
    )
    async with build_lock:
        build_result = await pipeline_build(
            blueprint,
            url,
            widget_id,
            skip_deploy=skip_deploy,
            architect_override=architect_override,
            source_evidence=source_evidence,
            creation_brief=creation_brief,
            brand_overrides=brand_overrides,
            token_overrides=token_overrides,
        )
        await _update_widget_after_build(
            widget_id,
            build_result,
            local_publish=local_publish,
        )


async def _workspace_brand_overrides(
    widget_id: str,
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    """Resolve the owner's brand kit into the two plain maps the engine takes.

    Read here rather than passed in as a task argument so a kit edited between
    enqueue and execution is honoured — and so a queued build is never carrying a
    stale copy of someone's colours.

    Best-effort: a workspace with no brand kit is the common case, and a failure
    to read one must degrade to "use the site's own brand" rather than fail a
    build the customer is watching.
    """
    try:
        async with async_session_factory() as session:
            widget = await session.scalar(select(Widget).where(Widget.id == widget_id))
            if widget is None:
                return None, None
            brand = await get_brand(session, widget.user_id)
            if not is_configured(brand):
                return None, None

            # Applied to a throwaway extraction so the diff — only the fields the
            # kit actually sets — is what reaches the engine, rather than a whole
            # brand object that would overwrite the extracted values with blanks.
            neutral = BrandExtraction(
                primary_color="",
                secondary_color="",
                background_color="",
                accent_color="",
                font_headings="",
                font_body="",
                tone="",
            )
            applied = apply_to_extraction(neutral, brand)
            overrides = {
                key: value
                for key, value in applied.model_dump(mode="json").items()
                if isinstance(value, str) and value
            }
            return (overrides or None), (design_token_overrides(brand) or None)
    except Exception:
        logger.warning("Could not read the workspace brand for %s", widget_id, exc_info=True)
        return None, None


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30, acks_late=True)
def build_widget_task(
    # bind=True makes Celery pass the Task instance in as `self`.
    self: Task,
    widget_id: str,
    blueprint_dict: dict,
    url: str,
    skip_deploy: bool = False,
    architect_override_dict: dict | None = None,
    source_evidence_dict: dict | None = None,
    creation_brief_dict: dict | None = None,
) -> dict[str, Any]:
    loop = _get_loop()
    started = time.perf_counter()
    pipeline_builds_total.labels("started").inc()

    try:
        loop.run_until_complete(
            _run_build_pipeline(
                widget_id,
                blueprint_dict,
                url,
                skip_deploy,
                architect_override_dict,
                source_evidence_dict,
                creation_brief_dict,
            )
        )
        pipeline_builds_total.labels("succeeded").inc()
        pipeline_build_duration_seconds.observe(time.perf_counter() - started)
        return {"success": True, "widget_id": widget_id}

    except LockNotAcquired:
        # Another worker is already building this widget; do not double-build.
        logger.warning("Build for widget %s skipped — already in progress", widget_id)
        return {"success": False, "widget_id": widget_id, "error": "build_already_running"}

    except Exception as exc:
        pipeline_builds_total.labels("failed").inc()
        logger.exception(
            "Build failed for widget %s (attempt %d of %d)",
            widget_id,
            self.request.retries + 1,
            self.max_retries + 1,
        )

        error_text = str(exc)[:2000]
        try:
            loop.run_until_complete(
                event_manager.publish_stage(
                    widget_id, "pipeline", "failed", "Build failed", progress=0.0
                )
            )
        except Exception:
            logger.warning("Could not publish failure event for %s", widget_id)

        non_retryable = any(marker in error_text for marker in _NON_RETRYABLE_MARKERS)
        if non_retryable or self.request.retries >= self.max_retries:
            try:
                loop.run_until_complete(
                    _update_build_progress(
                        widget_id,
                        status="failed",
                        build_error=error_text,
                        build_stage=None,
                        build_progress=None,
                    )
                )
            except Exception:
                logger.exception("Could not mark widget %s as failed", widget_id)
            return {"success": False, "widget_id": widget_id, "error": error_text}

        raise self.retry(exc=exc) from exc


async def run_local_widget_build(
    widget_id: str,
    blueprint_dict: dict,
    url: str,
    *,
    publish: bool,
    architect_override_dict: dict | None = None,
    source_evidence_dict: dict | None = None,
    creation_brief_dict: dict | None = None,
) -> None:
    """Run one complete build inside the development API process.

    This is the explicit local counterpart to the Celery entry point, not a
    production fail-open. It uses the same pipeline, durable progress fields,
    artifact store, and error state as the worker path.
    """
    started = time.perf_counter()
    pipeline_builds_total.labels("started").inc()

    try:
        await _run_build_pipeline(
            widget_id,
            blueprint_dict,
            url,
            True,
            architect_override_dict,
            source_evidence_dict,
            creation_brief_dict,
            local_publish=publish,
            use_process_lock=True,
        )
        pipeline_builds_total.labels("succeeded").inc()
        pipeline_build_duration_seconds.observe(time.perf_counter() - started)
    except LockNotAcquired:
        logger.warning("Local build for widget %s skipped — already in progress", widget_id)
    except Exception as exc:
        pipeline_builds_total.labels("failed").inc()
        logger.exception("Local build failed for widget %s", widget_id)
        try:
            await event_manager.publish_stage(
                widget_id, "pipeline", "failed", "Build failed", progress=0.0
            )
        except Exception:
            logger.warning("Could not publish failure event for %s", widget_id)
        await _update_build_progress(
            widget_id,
            status="failed",
            build_error=str(exc)[:2000],
            build_stage=None,
            build_progress=None,
        )


def schedule_local_widget_build(
    widget_id: str,
    blueprint_dict: dict,
    url: str,
    *,
    publish: bool,
    architect_override_dict: dict | None = None,
    source_evidence_dict: dict | None = None,
    creation_brief_dict: dict | None = None,
) -> None:
    """Schedule a dev build and retain it until completion."""
    task = asyncio.create_task(
        run_local_widget_build(
            widget_id,
            blueprint_dict,
            url,
            publish=publish,
            architect_override_dict=architect_override_dict,
            source_evidence_dict=source_evidence_dict,
            creation_brief_dict=creation_brief_dict,
        ),
        name=f"local-widget-build:{widget_id}",
    )
    _local_build_tasks.add(task)
    task.add_done_callback(_local_build_tasks.discard)


async def cancel_local_widget_builds() -> None:
    """Cancel in-process builds during API shutdown."""
    tasks = tuple(_local_build_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# --------------------------------------------------------------------------- #
# Self-heal sweep
# --------------------------------------------------------------------------- #


async def _heal_brand_drift(session: AsyncSession, widget: Widget) -> None:
    brand_cutoff = datetime.now(UTC) - timedelta(minutes=settings.brand_check_interval_minutes)
    if widget.last_brand_check_at and widget.last_brand_check_at >= brand_cutoff:
        return

    try:
        drift = await check_brand_drift(widget)
    except Exception:
        logger.exception("Brand-drift check errored for widget %s", widget.id)
        heal_checks_total.labels("brand_drift", "failed").inc()
        widget.heal_failure_count += 1
        return

    widget.last_brand_check_at = datetime.now(UTC)
    widget.source_evidence = drift.evidence.model_dump(mode="json")
    widget.source_content_fingerprint = drift.evidence.content_fingerprint
    widget.source_brand_fingerprint = drift.evidence.brand_fingerprint

    if not drift.drifted:
        heal_checks_total.labels("brand_drift", "no_drift").inc()
        session.add(
            WidgetHealEvent(
                widget_id=widget.id,
                check_type="brand_drift",
                status="no_drift",
                detected_at=datetime.now(UTC),
            )
        )
        widget.heal_failure_count = 0
        return

    logger.info("Brand drift on widget %s: %s", widget.id, drift.diff)
    event = WidgetHealEvent(
        widget_id=widget.id,
        check_type="brand_drift",
        status="healing",
        diff_summary=drift.diff,
        detected_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()

    try:
        if drift.architect_output is None:
            raise RuntimeError("brand drift detected without a replacement design")
        build_result = await generate_and_deploy(
            str(widget.id),
            drift.architect_output,
            WidgetType(widget.widget_type),
            widget.title,
            skip_deploy=False,
        )
        widget.brand_tokens = build_result.architect_output.brand.model_dump(mode="json")
        widget.visual_language = build_result.architect_output.visual_language.model_dump(
            mode="json"
        )
        widget.design_tokens = build_result.design_tokens.model_dump(mode="json")
        await record_deployment(
            session,
            widget,
            build_result.deployment.url,
            trigger="heal_brand_drift",
            embed_url=build_result.deployment.embed_url,
            provider_deployment_id=build_result.deployment.provider_deployment_id,
        )
        _save_to_workspace(str(widget.id), widget, build_result)

        event.status = "healed"
        event.healed_at = datetime.now(UTC)
        widget.heal_failure_count = 0
        heal_checks_total.labels("brand_drift", "healed").inc()

        await event_manager.publish_stage(
            str(widget.id),
            "heal",
            "complete",
            "Brand drift detected and re-synced",
            data={"diff": drift.diff, "url": build_result.deployment.url},
            progress=100.0,
        )
    except Exception as exc:
        logger.exception("Brand-drift heal failed for widget %s", widget.id)
        event.status = "failed"
        event.diff_summary = {**(event.diff_summary or {}), "error": str(exc)[:500]}
        widget.heal_failure_count += 1
        heal_checks_total.labels("brand_drift", "failed").inc()


async def _heal_deploy_health(session: AsyncSession, widget: Widget) -> None:
    try:
        healthy = await check_deploy_health(widget)
    except Exception:
        logger.exception("Deploy-health check errored for widget %s", widget.id)
        heal_checks_total.labels("deploy_health", "failed").inc()
        return

    if healthy:
        heal_checks_total.labels("deploy_health", "no_drift").inc()
        return

    logger.warning("Widget %s is unreachable at %s", widget.id, widget.deployment_url)
    event = WidgetHealEvent(
        widget_id=widget.id,
        check_type="deploy_health",
        status="healing",
        diff_summary={"unreachable_url": widget.deployment_url or ""},
        detected_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()

    try:
        dist_dir = workspace_dir(str(widget.id)) / "dist"
        if not dist_dir.is_dir():
            raise RuntimeError("no saved build artifacts to redeploy")

        deployment = await deploy_directory(str(dist_dir), str(widget.id))
        await record_deployment(
            session,
            widget,
            deployment.url,
            trigger="heal_deploy_health",
            embed_url=deployment.embed_url,
            provider_deployment_id=deployment.provider_deployment_id,
        )

        event.status = "healed"
        event.healed_at = datetime.now(UTC)
        widget.heal_failure_count = 0
        heal_checks_total.labels("deploy_health", "healed").inc()

        await event_manager.publish_stage(
            str(widget.id),
            "heal",
            "complete",
            "Deployment was unreachable and has been republished",
            data={"url": deployment.url},
            progress=100.0,
        )
    except Exception as exc:
        logger.exception("Deploy-health heal failed for widget %s", widget.id)
        event.status = "failed"
        event.diff_summary = {**(event.diff_summary or {}), "error": str(exc)[:500]}
        widget.heal_failure_count += 1
        heal_checks_total.labels("deploy_health", "failed").inc()


async def _heal_one_widget(widget_id: str) -> None:
    """Run both checks for one widget under an exclusive lock."""
    try:
        async with distributed_lock(widget_lock_key(widget_id)):
            async with async_session_factory() as session:
                result = await session.execute(select(Widget).where(Widget.id == widget_id))
                widget = result.scalar_one_or_none()
                if widget is None or widget.status != "active":
                    return

                # Stamp first: if a check crashes the process, the widget is not
                # re-picked immediately on the next sweep in a tight loop.
                widget.last_heal_check_at = datetime.now(UTC)
                await session.commit()

                await _heal_brand_drift(session, widget)
                await _heal_deploy_health(session, widget)
                await session.commit()

    except LockNotAcquired:
        logger.info("Skipping widget %s — heal or build already running", widget_id)


async def _select_widgets_to_heal() -> list[str]:
    """Pick the widgets most overdue for a check, bounded by the batch size."""
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.self_heal_interval_minutes)
    async with async_session_factory() as session:
        result = await session.execute(
            select(Widget.id)
            .where(
                Widget.status == "active",
                Widget.heal_failure_count < settings.self_heal_max_failures,
                (Widget.last_heal_check_at.is_(None)) | (Widget.last_heal_check_at < cutoff),
            )
            # Nulls-first ordering: never-checked widgets go before stale ones, and
            # oldest-checked before newest, so no widget can be starved.
            .order_by(Widget.last_heal_check_at.asc().nulls_first())
            .limit(settings.self_heal_batch_size)
        )
        return [str(widget_id) for widget_id in result.scalars().all()]


async def _run_self_heal_sweep() -> dict:
    widget_ids = await _select_widgets_to_heal()
    heal_sweep_widgets.set(len(widget_ids))
    logger.info("Self-heal sweep starting for %d widget(s)", len(widget_ids))

    for widget_id in widget_ids:
        try:
            await _heal_one_widget(widget_id)
        except Exception:
            # One widget's failure must never abort the rest of the sweep.
            logger.exception("Self-heal failed for widget %s", widget_id)

    return {"checked": len(widget_ids), "widget_ids": widget_ids}


@celery_app.task(bind=True, acks_late=True)
def run_self_heal_sweep(self: Task) -> dict[str, Any]:
    if not settings.self_heal_enabled:
        logger.info("Self-heal sweep disabled by configuration")
        return {"skipped": True}

    loop = _get_loop()
    try:
        # A single sweep at a time cluster-wide, so overlapping beat ticks or a
        # second worker cannot double-process the same batch.
        return loop.run_until_complete(_sweep_with_lock())
    except LockNotAcquired:
        logger.info("Another self-heal sweep is already running")
        return {"skipped": True, "reason": "sweep_already_running"}


async def _sweep_with_lock() -> dict:
    async with distributed_lock("self-heal-sweep", ttl_seconds=3600):
        return await _run_self_heal_sweep()


@celery_app.task(bind=True, acks_late=True)
def run_lead_delivery_sweep(self: Task) -> dict[str, Any]:
    """Retry every lead delivery whose backoff has elapsed.

    The immediate attempt after capture covers the common case. This covers the
    one that actually loses a business its leads: the CRM that was down for ten
    minutes, the worker that restarted mid-delivery, the endpoint that
    rate-limited a burst. Without it the outbox would record failures nobody
    ever acted on, which is a more honest version of the same problem.
    """
    from app.features.leads.delivery import sweep_due_deliveries

    loop = _get_loop()
    try:

        async def _locked() -> int:
            async with distributed_lock("lead-delivery-sweep", ttl_seconds=600):
                return await sweep_due_deliveries()

        return {"delivered": loop.run_until_complete(_locked())}
    except LockNotAcquired:
        logger.info("Another lead delivery sweep is already running")
        return {"skipped": True, "reason": "sweep_already_running"}
