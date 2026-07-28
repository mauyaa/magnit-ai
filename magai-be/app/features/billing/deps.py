"""Plan gates as FastAPI dependencies.

``CurrentEntitlements`` resolves once per request and is what every gated route
depends on::

    async def handler(entitlements: CurrentEntitlements):
        entitlements.require(Feature.CRM_INTEGRATIONS)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.billing.entitlements import (
    Entitlements,
    FeatureLocked,
    QuotaExceeded,
    resolve_entitlements,
)
from app.platform.db.session import get_async_session


async def get_entitlements(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Entitlements:
    return await resolve_entitlements(db, user.workspace_id)


CurrentEntitlements = Annotated[Entitlements, Depends(get_entitlements)]


def upgrade_required(error: FeatureLocked | QuotaExceeded) -> HTTPException:
    """Turn a locked capability into a 402 the interface can act on.

    The body names the plan that would unlock it and its price, so the client can
    render a real upgrade prompt instead of a dead end. 402 rather than 403: this
    is not "you may never", it is "not on this plan".
    """
    upgrade = error.upgrade_to
    detail: dict[str, object] = {
        "error": "upgrade_required",
        "upgrade_to": (
            {
                "plan": upgrade.id,
                "name": upgrade.name,
                "monthly_price": upgrade.monthly_price_cents,
            }
            if upgrade is not None
            else None
        ),
    }
    if isinstance(error, FeatureLocked):
        detail["feature"] = str(error.feature)
    else:
        detail["limit"] = error.limit_name
        detail["limit_value"] = error.limit

    return HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)
