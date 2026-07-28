"""Plan resolution, quotas and the enforcement switch."""

from datetime import UTC, datetime, timedelta

import pytest

from app.features.billing.entitlements import (
    FeatureLocked,
    QuotaExceeded,
    period_start,
    record_usage,
    resolve_entitlements,
)
from app.features.billing.plans import Feature, all_plans, get_plan, next_plan_for
from app.features.payments.models import Subscription
from app.features.widgets.models import Widget


async def _subscribe(db, user, plan="studio", status="active", period_end=None):
    subscription = Subscription(
        user_id=user.id,
        plan=plan,
        status=status,
        current_period_end=period_end,
    )
    db.add(subscription)
    await db.commit()
    return subscription


async def _widget(db, user, status="active") -> Widget:
    widget = Widget(
        user_id=user.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Calc",
        status=status,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


@pytest.fixture
def enforced(monkeypatch):
    """Turn on commercial enforcement, which development and CI leave off."""
    monkeypatch.setattr("app.platform.config.settings.settings.require_payment_to_build", True)


class TestPlanCatalog:
    def test_every_plan_is_self_consistent(self):
        for plan in all_plans():
            assert plan.live_tool_limit >= 0
            assert plan.monthly_build_limit > 0
            assert plan.highlights, f"{plan.id} has no highlights to render"

    def test_free_cannot_publish_or_use_paid_features(self):
        free = get_plan("free")
        assert free.live_tool_limit == 0
        assert not free.has(Feature.CRM_INTEGRATIONS)
        assert not free.has(Feature.BRAND_KIT)

    def test_scale_is_a_superset_of_studio(self):
        assert get_plan("studio").features <= get_plan("scale").features

    def test_unknown_plan_falls_back_to_free_rather_than_raising(self):
        # A renamed plan string in the database must withhold features, never
        # take the whole workspace down.
        assert get_plan("enterprise-v2").id == "free"
        assert get_plan(None).id == "free"

    def test_upgrade_path_names_the_cheapest_plan_that_unlocks_a_feature(self):
        assert next_plan_for(Feature.CRM_INTEGRATIONS, "free").id == "scale"
        assert next_plan_for(Feature.BRAND_KIT, "free").id == "studio"
        # Nothing above scale, so there is no upgrade to offer.
        assert next_plan_for(Feature.CRM_INTEGRATIONS, "scale") is None


class TestPeriodStart:
    def test_without_a_subscription_the_window_is_the_calendar_month(self):
        now = datetime(2026, 3, 17, 9, 30, tzinfo=UTC)
        assert period_start(None, now) == datetime(2026, 3, 1, tzinfo=UTC)

    def test_a_subscriber_window_is_anchored_to_their_stripe_cycle(self):
        # Someone who subscribed on the 28th gets a full month of builds, not
        # the three days left in the calendar month.
        now = datetime(2026, 3, 2, tzinfo=UTC)
        subscription = Subscription(
            plan="studio",
            status="active",
            current_period_end=datetime(2026, 3, 28, tzinfo=UTC),
        )
        assert period_start(subscription, now) == datetime(2026, 2, 28, tzinfo=UTC)

    def test_month_arithmetic_clamps_rather_than_drifting(self):
        # 31 March minus one month has no 31 February to land on.
        subscription = Subscription(
            plan="studio",
            status="active",
            current_period_end=datetime(2026, 3, 31, tzinfo=UTC),
        )
        assert period_start(subscription, datetime(2026, 3, 5, tzinfo=UTC)) == datetime(
            2026, 2, 28, tzinfo=UTC
        )

    def test_a_stale_period_end_rolls_back_to_a_window_containing_now(self):
        # Stripe has not told us about the renewal yet. Metering against a window
        # that already closed would report a permanently spent quota.
        subscription = Subscription(
            plan="studio",
            status="active",
            current_period_end=datetime(2026, 1, 10, tzinfo=UTC),
        )
        start = period_start(subscription, datetime(2026, 3, 5, tzinfo=UTC))
        assert start <= datetime(2026, 3, 5, tzinfo=UTC)


class TestResolveEntitlements:
    async def test_no_subscription_resolves_to_free(self, db, user):
        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.plan.id == "free"
        assert entitlements.status == "free"
        assert not entitlements.subscribed

    async def test_active_subscription_grants_its_plan(self, db, user):
        await _subscribe(db, user, plan="scale")
        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.plan.id == "scale"
        assert entitlements.subscribed

    async def test_past_due_still_entitles(self, db, user):
        # A card that failed this morning must not pull a customer's live tools
        # off their website while Stripe retries.
        await _subscribe(db, user, plan="studio", status="past_due")
        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.subscribed
        assert entitlements.plan.id == "studio"

    async def test_canceled_falls_back_to_free(self, db, user):
        await _subscribe(db, user, plan="scale", status="canceled")
        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.plan.id == "free"
        assert not entitlements.subscribed

    async def test_usage_counts_live_tools_and_builds_in_the_window(self, db, user):
        await _widget(db, user, status="active")
        await _widget(db, user, status="building")
        await _widget(db, user, status="analyzed")
        await record_usage(db, user.id, "build", "free")
        await db.commit()

        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.usage.live_tools == 2
        assert entitlements.usage.total_tools == 3
        assert entitlements.usage.builds_this_period == 1

    async def test_usage_outside_the_window_is_not_counted(self, db, user):
        record = await record_usage(db, user.id, "build", "free")
        record.occurred_at = datetime.now(UTC) - timedelta(days=90)
        await db.commit()

        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.usage.builds_this_period == 0

    async def test_paid_widgets_are_reported_as_individual_grants(self, db, user):
        widget = await _widget(db, user)
        widget.entitlement_status = "paid"
        await db.commit()

        entitlements = await resolve_entitlements(db, user.id)
        assert widget.id in entitlements.granted_widget_ids


class TestEnforcement:
    async def test_with_enforcement_off_everything_is_open(self, db, user):
        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.plan.id == "free"
        # Free grants none of these, but development and CI run unenforced so the
        # whole product is exercisable.
        assert entitlements.has(Feature.CRM_INTEGRATIONS)
        assert entitlements.can_build()
        assert entitlements.can_publish()

    async def test_with_enforcement_on_free_is_gated(self, db, user, enforced):
        entitlements = await resolve_entitlements(db, user.id)
        assert not entitlements.has(Feature.CRM_INTEGRATIONS)
        assert not entitlements.can_publish()
        with pytest.raises(FeatureLocked) as caught:
            entitlements.require(Feature.CRM_INTEGRATIONS)
        # The error carries the upgrade, so a 402 can render a real prompt.
        assert caught.value.upgrade_to is not None
        assert caught.value.upgrade_to.id == "scale"

    async def test_build_quota_is_enforced_once_spent(self, db, user, enforced):
        await _subscribe(db, user, plan="studio")
        for _ in range(get_plan("studio").monthly_build_limit):
            await record_usage(db, user.id, "build", "studio")
        await db.commit()

        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.builds_remaining == 0
        with pytest.raises(QuotaExceeded) as caught:
            entitlements.require_build()
        assert caught.value.limit_name == "monthly_builds"

    async def test_live_tool_cap_is_enforced(self, db, user, enforced):
        await _subscribe(db, user, plan="studio")
        for _ in range(get_plan("studio").live_tool_limit):
            await _widget(db, user, status="active")

        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.live_tools_remaining == 0
        with pytest.raises(QuotaExceeded):
            entitlements.require_publish()

    async def test_a_widget_already_live_may_always_be_republished(self, db, user, enforced):
        # Otherwise redeploying at the cap fails — exactly when a customer most
        # needs to be able to redeploy.
        await _subscribe(db, user, plan="studio")
        widgets = [
            await _widget(db, user, status="active")
            for _ in range(get_plan("studio").live_tool_limit)
        ]
        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.can_publish(widgets[0])

    async def test_a_separately_paid_widget_stays_publishable_on_free(self, db, user, enforced):
        widget = await _widget(db, user, status="analyzed")
        widget.entitlement_status = "paid"
        await db.commit()

        entitlements = await resolve_entitlements(db, user.id)
        assert entitlements.plan.id == "free"
        assert entitlements.can_publish(widget)


class TestBillingRoutes:
    async def test_plan_catalog_is_public(self, client):
        response = await client.get("/api/billing/plans")
        assert response.status_code == 200
        plans = response.json()["plans"]
        assert [plan["id"] for plan in plans] == ["free", "studio", "scale"]
        assert plans[0]["purchasable"] is False
        assert plans[1]["purchasable"] is True

    async def test_entitlements_require_authentication(self, client):
        assert (await client.get("/api/billing/entitlements")).status_code == 401

    async def test_reported_features_match_what_the_server_would_allow(self, db, user, as_user):
        # With enforcement off the server allows everything, so the response has
        # to say so. Reporting the free plan's empty feature set here made every
        # screen render an upgrade prompt for something the API would have done.
        body = (await (as_user(user)).get("/api/billing/entitlements")).json()
        assert body["plan"]["id"] == "free"
        assert body["plan"]["features"] == []
        assert "crm_integrations" in body["features"]

    async def test_reported_features_are_the_plan_when_enforced(self, db, user, as_user, enforced):
        body = (await (as_user(user)).get("/api/billing/entitlements")).json()
        assert body["features"] == []

    async def test_entitlements_report_plan_usage_and_allowance(self, db, user, as_user):
        await _widget(db, user, status="active")
        response = await (as_user(user)).get("/api/billing/entitlements")
        assert response.status_code == 200

        body = response.json()
        assert body["plan"]["id"] == "free"
        assert body["usage"]["live_tools"] == 1
        assert "allowance" in body and "builds_remaining" in body["allowance"]
