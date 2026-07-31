from __future__ import annotations

from pydantic import BaseModel


class PlanResponse(BaseModel):
    """One tier, exactly as the catalogue defines it.

    Served to both the marketing pricing page and the in-product billing screen
    so the two cannot describe the same plan differently, which they did for as
    long as each kept its own hardcoded copy.
    """

    id: str
    name: str
    tagline: str
    monthly_price: int
    currency: str
    live_tool_limit: int
    monthly_build_limit: int
    lead_limit_per_tool: int
    analytics_window_days: int
    features: list[str]
    highlights: list[str]
    purchasable: bool


class PlanCatalogResponse(BaseModel):
    plans: list[PlanResponse]
    currency: str
    single_tool_price: int


class UsageResponse(BaseModel):
    live_tools: int
    total_tools: int
    builds_this_period: int


class AllowanceResponse(BaseModel):
    """Remaining headroom, precomputed so no client re-derives it."""

    builds_remaining: int
    live_tools_remaining: int
    can_build: bool
    can_publish: bool


class EntitlementsResponse(BaseModel):
    plan: PlanResponse
    status: str
    usage: UsageResponse
    allowance: AllowanceResponse
    features: list[str]
    period_started_at: str
    current_period_end: str | None
    granted_widget_ids: list[str]
