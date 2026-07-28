"""Exception handlers that log detail server-side and reveal nothing to clients.

An unhandled exception previously surfaced as a FastAPI stack trace when
``debug`` was on and an opaque 500 otherwise. Here every unexpected error becomes
a uniform JSON body carrying only the request id, so a user can quote it in a
support ticket and an operator can find the full traceback in the logs.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.platform.security.url_guard import UnsafeTargetURL

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Domain error with an explicit, client-safe message and status."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "request_id": _request_id(request)},
        )

    @app.exception_handler(UnsafeTargetURL)
    async def unsafe_url_handler(request: Request, exc: UnsafeTargetURL) -> JSONResponse:
        # Safety net: routes translate this explicitly, but a guard called deeper
        # in the stack should still produce a clean 422 rather than a 500.
        logger.warning("Blocked unsafe target URL: %s", exc)
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "request_id": _request_id(request)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's raw errors can echo submitted values (including passwords),
        # so only the field location and message are returned.
        safe_errors = [
            {"field": ".".join(str(p) for p in err.get("loc", ())), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "validation_error",
                "errors": safe_errors,
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": _request_id(request)},
            headers=headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Database messages can contain table/column names and fragments of the
        # offending values — never forward them.
        logger.exception("Database error handling %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=503,
            content={"detail": "database_unavailable", "request_id": _request_id(request)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled %s on %s %s",
            type(exc).__name__,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "internal_error", "request_id": _request_id(request)},
        )

    # Keep HTTPException identical to the Starlette variant it subclasses.
    # Starlette types handlers as accepting a bare Exception, which is broader than
    # our narrowed signature; the registration key guarantees the concrete type.
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
