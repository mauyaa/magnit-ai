"""Development-only hosting for generated widget artifacts.

Production widgets live on their own Vercel origin. A local checkout has no
deployment provider, but it still needs to prove the same iframe, runtime,
tracking, and lead-capture story. This router publishes the exact generated
``dist`` directory from the API origin and is unreachable in production.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse

from app.features.widgets.service import workspace_dir
from app.platform.config.settings import settings

router = APIRouter(tags=["local-widget-hosting"])
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _dist_dir(widget_id: str) -> Path:
    if not settings.local_builds_enabled:
        raise _NOT_FOUND
    try:
        canonical_id = str(uuid.UUID(widget_id))
    except (ValueError, TypeError, AttributeError):
        raise _NOT_FOUND from None

    dist = (workspace_dir(canonical_id) / "dist").resolve()
    if not dist.is_dir():
        raise _NOT_FOUND
    return dist


def _artifact(widget_id: str, asset_path: str) -> FileResponse:
    dist = _dist_dir(widget_id)
    requested = (dist / asset_path).resolve() if asset_path else dist / "index.html"
    try:
        requested.relative_to(dist)
    except ValueError:
        raise _NOT_FOUND from None

    if requested.is_file():
        return FileResponse(requested)

    # Vite applications may use client-side routes. Unknown asset names must
    # remain a real 404 rather than receiving HTML with a JavaScript MIME type.
    if asset_path and Path(asset_path).suffix:
        raise _NOT_FOUND
    index = dist / "index.html"
    if not index.is_file():
        raise _NOT_FOUND
    return FileResponse(index)


@router.get("/local-widgets/{widget_id}", include_in_schema=False)
async def local_widget_redirect(widget_id: str) -> RedirectResponse:
    _dist_dir(widget_id)
    return RedirectResponse(f"/local-widgets/{widget_id}/", status_code=307)


@router.get("/local-widgets/{widget_id}/", include_in_schema=False)
async def local_widget_index(widget_id: str) -> FileResponse:
    return _artifact(widget_id, "")


@router.get("/local-widgets/{widget_id}/{asset_path:path}", include_in_schema=False)
async def local_widget_asset(widget_id: str, asset_path: str) -> FileResponse:
    return _artifact(widget_id, asset_path)
