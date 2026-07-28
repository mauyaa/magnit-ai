"""Optional Sentry error reporting.

Guarded on both the DSN setting and the SDK being installed, so the app runs
identically with or without it. Request bodies and headers are not sent, and a
scrubber strips anything sensitive that reaches an event by another route.
"""

from __future__ import annotations

import logging
from typing import Any

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)

_SENSITIVE_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "cookie",
)


def _scrub_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: ("[redacted]" if _is_sensitive(key) else value)
                for key, value in headers.items()
            }

    extra = event.get("extra")
    if isinstance(extra, dict):
        event["extra"] = {
            key: ("[redacted]" if _is_sensitive(key) else value) for key, value in extra.items()
        }

    return event


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_SUBSTRINGS)


def init_sentry() -> bool:
    """Initialize Sentry if configured. Returns whether it was enabled."""
    if not settings.sentry_dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("MAGAI_SENTRY_DSN is set but sentry-sdk is not installed")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Never attach request bodies or PII; leads contain customer contact data.
        send_default_pii=False,
        max_request_body_size="never",
        before_send=_scrub_event,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
    )
    logger.info("Sentry initialized for environment %s", settings.environment)
    return True
