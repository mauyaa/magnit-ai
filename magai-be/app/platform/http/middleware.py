"""HTTP middleware: request correlation, security headers, body size limits."""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)

# Populated per-request and read by the logging filter so every log line emitted
# while handling a request carries its id.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"
_PUBLIC_WIDGET_PATH = re.compile(
    (
        r"^/api/(?:leads/[0-9a-f-]+|widgets/[0-9a-f-]+/"
        r"(?:impression|interactions|runtime-config))$"
    ),
    re.IGNORECASE,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign each request an id, log its outcome, and echo the id back."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        # Never trust an inbound id verbatim — it lands in logs.
        request_id = incoming if _is_safe_request_id(incoming) else str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except ClientDisconnect:
            # A navigation or closed tab can cancel an in-flight request before
            # Starlette has finished reading it. That is a client outcome, not a
            # server crash: record it without a traceback and stop the exception
            # from reaching Uvicorn's error logger.
            response = Response(status_code=499)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "Unhandled error in %s %s after %.1fms",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "request_id": request_id,
            },
        )
        return response


def _is_safe_request_id(value: str) -> bool:
    return bool(value) and len(value) <= 64 and all(c.isalnum() or c in "-_" for c in value)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach hardening headers to every response.

    The API returns JSON, not HTML, so the CSP is maximally restrictive: nothing
    should ever be loaded or framed from an API response. ``frame-ancestors
    'none'`` plus ``X-Frame-Options: DENY`` means the *API* cannot be framed —
    generated widgets are framed from their own Vercel origin, not from here, so
    this does not affect embedding.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        if settings.local_builds_enabled and request.url.path.startswith("/local-widgets/"):
            # Generated local widgets are intentionally iframeable from the
            # configured frontend origins. Their entry HTML carries the same
            # resource CSP as production; this response header adds the framing
            # boundary that cannot be expressed in a meta tag.
            frame_origins = " ".join(settings.cors_origins) or "'self'"
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
            response.headers.setdefault(
                "Content-Security-Policy",
                (
                    "default-src 'none'; script-src 'self'; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "img-src 'self' data:; connect-src 'self'; "
                    f"frame-ancestors 'self' {frame_origins}; "
                    "base-uri 'none'; form-action 'none'; object-src 'none'"
                ),
            )
            response.headers.setdefault(
                "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
            )
            response.headers.setdefault("Cross-Origin-Opener-Policy", "unsafe-none")
            response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
            response.headers.setdefault("Cache-Control", "no-cache")
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        # Tokens and lead data must never be cached by intermediaries.
        response.headers.setdefault("Cache-Control", "no-store")

        # HSTS is only meaningful over TLS, and asserting it on plain HTTP in dev
        # would poison localhost for other projects.
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.hsts_max_age_seconds}; includeSubDomains",
            )

        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before they are buffered.

    Checks ``Content-Length`` up front, and also counts bytes as they stream in so
    a chunked request without a declared length cannot bypass the cap.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    return self._too_large()
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "invalid_content_length"})

        body = await request.body()
        if len(body) > self.max_bytes:
            return self._too_large()

        return await call_next(request)

    def _too_large(self) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={"detail": "request_body_too_large", "max_bytes": self.max_bytes},
        )


class PublicWidgetCorsMiddleware(BaseHTTPMiddleware):
    """Allow deployed widgets to call only their anonymous runtime endpoints.

    Account APIs retain the explicit-origin credentialed CORS policy. These paths
    accept no cookies or bearer token, so a wildcard origin is both safe and
    necessary for widgets embedded on arbitrary customer sites.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        requested_method = (
            request.headers.get("access-control-request-method", "")
            if request.method == "OPTIONS"
            else request.method
        )
        allowed_method = "GET" if request.url.path.lower().endswith("/runtime-config") else "POST"
        if (
            not _PUBLIC_WIDGET_PATH.fullmatch(request.url.path)
            or requested_method.upper() != allowed_method
        ):
            return await call_next(request)

        if request.method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = f"{allowed_method}, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        return response
