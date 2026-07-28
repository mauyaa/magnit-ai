"""The plan catalogue: one definition of what each tier includes.

Before this module the same facts were written down in four places — the Stripe
line item, ``settings.*_active_experience_limit``, the settings page's hardcoded
plan cards, and the marketing pricing page — and they had already drifted. The
catalogue is now the single source, the API serves it, and both the product and
the marketing page render from what the server says.

Limits that operators genuinely need to tune per environment (price, live-tool
cap) still come from settings; everything else is a product decision and lives
here in code, where it can be reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.platform.config.settings import settings

PlanId = str

# Plans, weakest first. Order matters: it is the upgrade path the UI walks, and
# `next_plan_for` below relies on it.
PLAN_ORDER: tuple[PlanId, ...] = ("free", "studio", "scale")

# The tiers Stripe can actually sell. "free" is the absence of a subscription,
# never something a customer checks out.
PURCHASABLE_PLANS: tuple[PlanId, ...] = ("studio", "scale")


class Feature(StrEnum):
    """A capability a plan either grants or withholds.

    Named for what the customer gets, not for the screen that happens to use it,
    so one feature can gate an API route, a nav entry and a button without three
    different names for the same idea.
    """

    LEAD_CAPTURE = "lead_capture"
    LEAD_NOTIFICATIONS = "lead_notifications"
    LEAD_PIPELINE = "lead_pipeline"
    CSV_EXPORT = "csv_export"
    WEBHOOK_DELIVERY = "webhook_delivery"
    CRM_INTEGRATIONS = "crm_integrations"
    BRAND_KIT = "brand_kit"
    OUTCOME_EDITOR = "outcome_editor"
    QUESTION_EDITOR = "question_editor"
    ADVANCED_ANALYTICS = "advanced_analytics"
    SELF_HEALING = "self_healing"
    PRIORITY_SUPPORT = "priority_support"
    CUSTOM_DOMAINS = "custom_domains"
    API_ACCESS = "api_access"


@dataclass(frozen=True)
class Plan:
    """One tier, complete. Everything a screen needs to describe or enforce it."""

    id: PlanId
    name: str
    tagline: str
    monthly_price_cents: int
    # 0 means nothing may be published. It is not "unlimited" — an unlimited cap
    # is expressed as a large number, because a sentinel that reads as zero is
    # exactly the kind of thing that silently disables a paying customer.
    live_tool_limit: int
    monthly_build_limit: int
    lead_limit_per_tool: int
    analytics_window_days: int
    features: frozenset[Feature]
    # Marketing bullets. Kept beside the limits they describe so a copy change
    # cannot quietly contradict the number the server enforces.
    highlights: tuple[str, ...]

    def has(self, feature: Feature) -> bool:
        return feature in self.features


_STUDIO_FEATURES = frozenset(
    {
        Feature.LEAD_CAPTURE,
        Feature.LEAD_NOTIFICATIONS,
        Feature.LEAD_PIPELINE,
        Feature.CSV_EXPORT,
        Feature.WEBHOOK_DELIVERY,
        Feature.BRAND_KIT,
        Feature.OUTCOME_EDITOR,
        Feature.QUESTION_EDITOR,
        Feature.SELF_HEALING,
        Feature.CUSTOM_DOMAINS,
        Feature.API_ACCESS,
    }
)

_SCALE_FEATURES = _STUDIO_FEATURES | {
    Feature.CRM_INTEGRATIONS,
    Feature.ADVANCED_ANALYTICS,
    Feature.PRIORITY_SUPPORT,
}


def _catalog() -> dict[PlanId, Plan]:
    """Build the catalogue from current settings.

    A function rather than a module constant so tests can move a limit through
    settings and see the catalogue follow, instead of having to monkeypatch a
    frozen dict.
    """
    return {
        "free": Plan(
            id="free",
            name="Free preview",
            tagline="Read your site and see two directions. No card, no account needed.",
            monthly_price_cents=0,
            # Free genuinely cannot publish. That is the product: looking is free,
            # going live is what is paid for.
            live_tool_limit=0,
            monthly_build_limit=2,
            lead_limit_per_tool=0,
            analytics_window_days=7,
            features=frozenset(),
            highlights=(
                "Two AI directions for your site",
                "Full interactive preview",
                "No account needed to look",
            ),
        ),
        "studio": Plan(
            id="studio",
            name="Studio",
            tagline="For one business putting real tools in front of real visitors.",
            monthly_price_cents=settings.studio_monthly_price_cents,
            live_tool_limit=settings.studio_active_experience_limit,
            monthly_build_limit=25,
            lead_limit_per_tool=2_000,
            analytics_window_days=30,
            features=_STUDIO_FEATURES,
            # Deliberately not "N live tools": every surface that renders these
            # also renders the capacity, and the pricing card printed the cap
            # twice, one line apart. Highlights say what you can *do*.
            highlights=(
                "Lead capture, alerts and CSV export",
                "Edit questions, results and branding",
                "Automatic brand and uptime repair",
                "Signed webhook delivery",
                "Custom domains and API access",
            ),
        ),
        "scale": Plan(
            id="scale",
            name="Scale",
            tagline="For a portfolio of sites, or one site with a tool per service line.",
            monthly_price_cents=settings.scale_monthly_price_cents,
            live_tool_limit=settings.scale_active_experience_limit,
            monthly_build_limit=100,
            lead_limit_per_tool=10_000,
            analytics_window_days=90,
            features=_SCALE_FEATURES,
            highlights=(
                "Everything in Studio",
                "CRM and marketing integrations",
                "Advanced analytics and attribution",
                "Priority support",
            ),
        ),
    }


def get_plan(plan_id: PlanId | None) -> Plan:
    """Resolve a plan id, falling back to free.

    Unknown ids resolve to free rather than raising: a plan string arrives from a
    database row that a future migration could rename, and the safe failure is to
    withhold features, never to 500 the whole workspace.
    """
    return _catalog().get(str(plan_id or "free"), _catalog()["free"])


def all_plans() -> list[Plan]:
    return [_catalog()[plan_id] for plan_id in PLAN_ORDER]


def is_purchasable(plan_id: PlanId) -> bool:
    return plan_id in PURCHASABLE_PLANS


def next_plan_for(feature: Feature, current: PlanId) -> Plan | None:
    """The cheapest plan above ``current`` that grants ``feature``.

    This is what turns a 402 into a useful screen: the API can say not just "you
    cannot do this" but "Scale can, and it costs this much".
    """
    catalog = _catalog()
    try:
        start = PLAN_ORDER.index(current)
    except ValueError:
        start = 0
    for plan_id in PLAN_ORDER[start + 1 :]:
        if catalog[plan_id].has(feature):
            return catalog[plan_id]
    return None
