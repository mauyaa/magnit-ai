"""Celery application: build queue and the self-heal beat schedule.

Run the worker and the scheduler separately::

    celery -A app.platform.celery_app worker --loglevel=info
    celery -A app.platform.celery_app beat   --loglevel=info

Exactly one beat process should run per environment. If a second one is started
anyway, the sweep's distributed lock keeps duplicate ticks from double-processing
the same widgets.
"""

from typing import Any

from celery import Celery
from celery.signals import worker_process_init

from app.platform.config.settings import settings
from app.platform.logging.config import configure_logging

celery_app = Celery(
    "magai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # acks_late plus reject-on-worker-lost: a task killed mid-flight is redelivered
    # rather than silently lost. Builds are idempotent per widget (guarded by the
    # per-widget lock), so redelivery is safe.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Builds are long and CPU/network heavy; prefetching would leave jobs queued
    # behind a busy worker instead of going to an idle one.
    worker_prefetch_multiplier=1,
    # Recycle workers periodically so a leak in an SDK cannot grow unbounded.
    worker_max_tasks_per_child=50,
    task_soft_time_limit=900,
    task_time_limit=1080,
    broker_connection_retry_on_startup=True,
    result_expires=86400,
)

if settings.self_heal_enabled:
    celery_app.conf.beat_schedule = {
        "self-heal-sweep": {
            "task": "app.platform.pipeline.tasks.run_self_heal_sweep",
            "schedule": settings.self_heal_interval_minutes * 60,
            # Drop a tick rather than stacking sweeps if beat falls behind.
            "options": {"expires": settings.self_heal_interval_minutes * 60},
        },
    }


@worker_process_init.connect
def _configure_worker_logging(**_kwargs: Any) -> None:
    """Give worker processes the same structured logging as the API."""
    configure_logging()


# Import models so SQLAlchemy mappers are configured, then tasks so the worker
# registers them. Tasks must come last: they import this module.
import app.platform.db.models  # noqa: E402
import app.platform.pipeline.tasks  # noqa: E402,F401
