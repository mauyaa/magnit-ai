"""Logging configuration: structured JSON in production, readable text in dev.

JSON lines are what log aggregators (CloudWatch, Loki, Datadog) can index without
regex parsing. Every record carries the active request id so a user-reported id
retrieves the whole request's log trail.
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

from app.platform.config.settings import settings

# Attributes present on every LogRecord; anything else was passed via `extra=`
# and is worth promoting into the structured payload.
_STANDARD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

# Values that must never reach the logs even if a caller passes them in `extra`.
_REDACTED_KEYS = frozenset(
    {
        "password",
        "new_password",
        "current_password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "secret_key",
        "authorization",
        "api_key",
        "gemini_api_key",
        "stripe_secret_key",
        "vercel_api_token",
        "cookie",
        "set-cookie",
    }
)

REDACTION_PLACEHOLDER = "[redacted]"


class RequestIdFilter(logging.Filter):
    """Stamp each record with the current request id (``-`` outside a request)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            from app.platform.http.middleware import request_id_ctx

            record.request_id = request_id_ctx.get()
        return True


def _scrub(key: str, value: Any) -> Any:
    return REDACTION_PLACEHOLDER if key.lower() in _REDACTED_KEYS else value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "environment": settings.environment,
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in payload:
                payload[key] = _scrub(key, value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    formatter: dict[str, Any] = (
        {"()": "app.platform.logging.config.JsonFormatter"}
        if settings.log_format == "json"
        else {
            "format": "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s",
        }
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": "app.platform.logging.config.RequestIdFilter"},
            },
            "formatters": {"default": formatter},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": settings.log_level.upper()},
            "loggers": {
                # Our own request logging already covers access lines.
                "uvicorn.access": {"handlers": ["console"], "level": "WARNING", "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
                # Full SQL echo is opt-in via MAGAI_DEBUG on the engine itself.
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )
