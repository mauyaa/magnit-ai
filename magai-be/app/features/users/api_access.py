"""Workspace API access authenticated by settings-issued keys."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leads.models import Lead
from app.features.users.models import ApiKey
from app.features.widgets.models import Widget
from app.platform.db.session import get_async_session

router = APIRouter(prefix="/api/developer", tags=["developer"])


async def api_workspace(
    x_api_key: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_async_session),
) -> uuid.UUID:
    if not x_api_key or not x_api_key.startswith("magai_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    digest = hashlib.sha256(x_api_key.encode()).hexdigest()
    key = await db.scalar(
        select(ApiKey).where(
            ApiKey.key_hash == digest,
            ApiKey.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    expires_at = key.expires_at if key else None
    if expires_at is not None and expires_at.tzinfo is None:
        # SQLite drops timezone metadata in tests; production Postgres does not.
        expires_at = expires_at.replace(tzinfo=UTC)
    if key is None or (expires_at is not None and expires_at <= now):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    key.last_used_at = now
    return key.owner_id


ApiWorkspace = Annotated[uuid.UUID, Depends(api_workspace)]


@router.get("/tools")
async def list_tools(
    owner_id: ApiWorkspace,
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    tools = list(
        (
            await db.scalars(
                select(Widget).where(Widget.user_id == owner_id).order_by(Widget.created_at.desc())
            )
        ).all()
    )
    return {
        "tools": [
            {
                "id": str(tool.id),
                "title": tool.title,
                "type": tool.widget_type,
                "status": tool.status,
                "source_url": tool.target_url,
                "deployment_url": tool.deployment_url,
                "leads_count": tool.leads_count,
                "created_at": tool.created_at.isoformat(),
            }
            for tool in tools
        ]
    }


@router.get("/leads")
async def list_leads(
    owner_id: ApiWorkspace,
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    rows = (
        await db.execute(
            select(Lead, Widget.title)
            .join(Widget, Widget.id == Lead.widget_id)
            .where(Widget.user_id == owner_id)
            .order_by(Lead.created_at.desc())
        )
    ).all()
    return {
        "leads": [
            {
                "id": str(lead.id),
                "tool_id": str(lead.widget_id),
                "tool_title": title,
                "email": lead.email,
                "name": lead.name,
                "score": lead.score,
                "answers": lead.answers,
                "status": lead.status,
                "tags": lead.tags or [],
                "created_at": lead.created_at.isoformat(),
            }
            for lead, title in rows
        ]
    }
