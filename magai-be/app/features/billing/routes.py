from __future__ import annotations

from fastapi import APIRouter

from app.features.billing.deps import CurrentEntitlements
from app.features.billing.entitlements import Entitlements
from app.features.billing.plans import Feature, Plan, all_plans, is_purchasable
from app.features.billing.schemas import (
    AllowanceResponse,
    EntitlementsResponse,
    PlanCatalogResponse,
    PlanResponse,
    UsageResponse,
)
from app.platform.config.settings import settings

router = APIRouter(prefix="/api/billing", tags=["billing"])


def plan_to_response(plan: Plan) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        tagline=plan.tagline,
        monthly_price=plan.monthly_price_cents,
        currency=settings.widget_launch_currency,
        live_tool_limit=plan.live_tool_limit,
        monthly_build_limit=plan.monthly_build_limit,
        lead_limit_per_tool=plan.lead_limit_per_tool,
        analytics_window_days=plan.analytics_window_days,
        features=sorted(str(feature) for feature in plan.features),
        highlights=list(plan.highlights),
        purchasable=is_purchasable(plan.id),
    )


def entitlements_to_response(entitlements: Entitlements) -> EntitlementsResponse:
    # The *effective* grant, not the plan's raw feature set. These differ whenever
    # enforcement is off (development, CI, demos), and reporting the raw set there
    # made every screen render an upgrade prompt for a capability the server would
    # have allowed — a UI that disagrees with its own API.
    effective = sorted(str(feature) for feature in Feature if entitlements.has(feature))

    return EntitlementsResponse(
        plan=plan_to_response(entitlements.plan),
        status=entitlements.status,
        usage=UsageResponse(
            live_tools=entitlements.usage.live_tools,
            total_tools=entitlements.usage.total_tools,
            builds_this_period=entitlements.usage.builds_this_period,
        ),
        allowance=AllowanceResponse(
            builds_remaining=entitlements.builds_remaining,
            live_tools_remaining=entitlements.live_tools_remaining,
            can_build=entitlements.can_build(),
            can_publish=entitlements.can_publish(),
        ),
        features=effective,
        period_started_at=entitlements.period_started_at.isoformat(),
        current_period_end=(
            entitlements.current_period_end.isoformat() if entitlements.current_period_end else None
        ),
        granted_widget_ids=[str(widget_id) for widget_id in entitlements.granted_widget_ids],
    )


@router.get("/plans", response_model=PlanCatalogResponse)
async def get_plan_catalog() -> PlanCatalogResponse:
    """The whole catalogue, unauthenticated.

    Public because the pricing page needs it before anyone has an account, and
    because a plan's price and limits are not secrets — they are the offer.
    """
    return PlanCatalogResponse(
        plans=[plan_to_response(plan) for plan in all_plans()],
        currency=settings.widget_launch_currency,
        single_tool_price=settings.widget_launch_price_cents,
    )


@router.get("/entitlements", response_model=EntitlementsResponse)
async def get_entitlements_endpoint(entitlements: CurrentEntitlements) -> EntitlementsResponse:
    """What this workspace may do, and how much of each allowance is left."""
    return entitlements_to_response(entitlements)
