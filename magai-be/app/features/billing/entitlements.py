"""Resolve one workspace's plan, allowances and remaining headroom.

Every gate in the product — publishing, building, opening the outcome editor,
connecting a CRM, exporting a CSV — asks this module rather than re-deriving the
answer from a ``Subscription`` row. That is the whole point: the rules used to be
spread across ``widgets.service.account_can_build``, the payments router and two
frontend components, and they disagreed about what a canceled subscriber could
still do.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.models import UsageRecord
from app.features.billing.plans import Feature, Plan, PlanId, get_plan, next_plan_for
from app.features.payments.models import Subscription
from app.features.widgets.models import Widget
from app.platform.config.settings import settings

# The subscription states that actually entitle a workspace. ``past_due`` is
# deliberately included: a card that failed this morning must not take a
# customer's live tools off their website while the retry schedule runs.
ENTITLING_STATUSES = frozenset({"active", "past_due"})

# Statuses a widget occupies while it holds one of the plan's live-tool slots.
OCCUPYING_STATUSES = ("active", "building")


class QuotaExceeded(Exception):
    """A metered allowance is spent. Carries what was hit, for the 402 body."""

    def __init__(self, limit_name: str, limit: int, upgrade_to: Plan | None = None) -> None:
        super().__init__(limit_name)
        self.limit_name = limit_name
        self.limit = limit
        self.upgrade_to = upgrade_to


class FeatureLocked(Exception):
    """The plan does not include this capability."""

    def __init__(self, feature: Feature, upgrade_to: Plan | None = None) -> None:
        super().__init__(str(feature))
        self.feature = feature
        self.upgrade_to = upgrade_to


def _month_before(moment: datetime) -> datetime:
    """The same calendar day one month earlier, clamped to a valid date.

    Used to reconstruct the start of the current billing cycle from its end.
    Naive subtraction of 30 days drifts a day or two every month, which shows up
    as a quota that resets slightly earlier each cycle.
    """
    year = moment.year - 1 if moment.month == 1 else moment.year
    month = 12 if moment.month == 1 else moment.month - 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def period_start(subscription: Subscription | None, now: datetime | None = None) -> datetime:
    """When the current metering window opened.

    A subscriber's window is anchored to their Stripe cycle, so someone who
    subscribes on the 28th gets a full month of builds rather than three days of
    one. Without a subscription there is no cycle to anchor to, so the window is
    the calendar month in UTC.
    """
    moment = now or datetime.now(UTC)
    if subscription is not None and subscription.current_period_end is not None:
        end = subscription.current_period_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        start = _month_before(end)
        # A period end that has already passed means Stripe has not yet told us
        # about the renewal. Roll forward rather than metering against a window
        # that closed, which would otherwise report a permanently spent quota.
        while start > moment:
            end = start
            start = _month_before(start)
        if start <= moment:
            return start
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Usage:
    """What this workspace has spent in the current window."""

    live_tools: int
    total_tools: int
    builds_this_period: int


@dataclass(frozen=True)
class Entitlements:
    """The complete answer to "what may this workspace do right now"."""

    plan: Plan
    status: str
    usage: Usage
    period_started_at: datetime
    current_period_end: datetime | None
    # Widgets bought outright under the one-off launch price. They hold a live
    # slot of their own and stay live even on the free plan — someone who paid
    # for a tool does not lose it because they never took a subscription.
    granted_widget_ids: frozenset[uuid.UUID]

    @property
    def subscribed(self) -> bool:
        return self.status in ENTITLING_STATUSES

    def has(self, feature: Feature) -> bool:
        # With enforcement off every capability is open, so development, CI and
        # demo environments exercise the real product rather than a permanently
        # free-tier version of it. Checked here, once, instead of at each of the
        # dozen call sites that ask this question.
        if not settings.enforce_plan_limits:
            return True
        return self.plan.has(feature)

    def upgrade_for(self, feature: Feature) -> Plan | None:
        return next_plan_for(feature, self.plan.id)

    def require(self, feature: Feature) -> None:
        if not self.has(feature):
            raise FeatureLocked(feature, self.upgrade_for(feature))

    # --- allowances ---------------------------------------------------------

    @property
    def builds_remaining(self) -> int:
        return max(0, self.plan.monthly_build_limit - self.usage.builds_this_period)

    @property
    def live_tools_remaining(self) -> int:
        return max(0, self.plan.live_tool_limit - self.usage.live_tools)

    def can_build(self) -> bool:
        if not settings.enforce_plan_limits:
            return True
        return self.builds_remaining > 0

    def can_publish(self, widget: Widget | None = None) -> bool:
        """Whether one more tool may go live.

        A widget already occupying a slot may always be republished — otherwise
        redeploying a live tool at the cap would fail, which is precisely when a
        customer most needs to be able to redeploy it.
        """
        if not settings.enforce_plan_limits:
            return True
        if widget is not None:
            if widget.id in self.granted_widget_ids:
                return True
            if widget.status in OCCUPYING_STATUSES:
                return True
        return self.live_tools_remaining > 0

    def require_build(self) -> None:
        if not self.can_build():
            raise QuotaExceeded(
                "monthly_builds",
                self.plan.monthly_build_limit,
                next_plan_for(Feature.OUTCOME_EDITOR, self.plan.id),
            )

    def require_publish(self, widget: Widget | None = None) -> None:
        if not self.can_publish(widget):
            raise QuotaExceeded(
                "live_tools",
                self.plan.live_tool_limit,
                next_plan_for(Feature.LEAD_CAPTURE, self.plan.id),
            )


async def _granted_widget_ids(db: AsyncSession, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
    rows = await db.execute(
        select(Widget.id).where(
            Widget.user_id == user_id,
            Widget.entitlement_status.in_(("paid", "complimentary")),
        )
    )
    return frozenset(rows.scalars().all())


async def resolve_entitlements(
    db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> Entitlements:
    """Read the workspace's plan and current usage in one pass."""
    subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    entitled = subscription is not None and subscription.status in ENTITLING_STATUSES
    plan_id: PlanId = subscription.plan if (subscription and entitled) else "free"
    plan = get_plan(plan_id)
    started = period_start(subscription if entitled else None, now)

    live_tools = int(
        await db.scalar(
            select(func.count(Widget.id)).where(
                Widget.user_id == user_id,
                Widget.status.in_(OCCUPYING_STATUSES),
            )
        )
        or 0
    )
    total_tools = int(
        await db.scalar(select(func.count(Widget.id)).where(Widget.user_id == user_id)) or 0
    )
    builds = int(
        await db.scalar(
            select(func.count(UsageRecord.id)).where(
                UsageRecord.user_id == user_id,
                UsageRecord.kind == "build",
                UsageRecord.occurred_at >= started,
            )
        )
        or 0
    )

    return Entitlements(
        plan=plan,
        status=subscription.status if subscription is not None else "free",
        usage=Usage(live_tools=live_tools, total_tools=total_tools, builds_this_period=builds),
        period_started_at=started,
        current_period_end=subscription.current_period_end if subscription else None,
        granted_widget_ids=await _granted_widget_ids(db, user_id),
    )


async def record_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    plan_id: PlanId,
    widget_id: uuid.UUID | None = None,
    context: dict | None = None,
) -> UsageRecord:
    """Meter one billable event.

    Flushed rather than committed: the caller owns the transaction, so metering
    and the action it meters either both land or neither does. A build that is
    counted but never enqueued is the failure mode worth designing against.
    """
    record = UsageRecord(
        user_id=user_id,
        widget_id=widget_id,
        kind=kind,
        plan=plan_id,
        occurred_at=datetime.now(UTC),
        context=context,
    )
    db.add(record)
    await db.flush()
    return record
