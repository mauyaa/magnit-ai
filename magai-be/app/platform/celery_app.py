from celery import Celery

from app.platform.config.settings import settings

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
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=720,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=3,
)

import app.features.widgets.models  # noqa: E402,F401
import app.features.leads.models  # noqa: E402,F401
import app.platform.pipeline.tasks  # noqa: E402,F401 — register tasks with worker
