"""Payment service internals: the paths where money and entitlement disagree.

The route and signature tests in ``test_payments.py`` cover getting a verified
event into the service. These cover what it does once it is there — the amount
not matching, the session not actually being paid, a refund arriving, a
subscription changing state — because each one either grants access that was not
bought or withholds access that was.

Stripe is stubbed throughout. The service deliberately re-reads the session from
Stripe rather than trusting the webhook body, so the stub is the authority the
code consults, which is exactly the seam worth testing.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import stripe

from app.features.payments.models import Payment, Subscription
from app.features.payments.service import (
    PaymentProviderError,
    handle_checkout_completed,
    handle_checkout_expired,
    handle_payment_refunded,
    handle_subscription_changed,
    handle_subscription_checkout_completed,
    plan_terms,
    subscription_summary,
)
from app.features.widgets.models import Widget
from app.platform.config.settings import settings


class StripeSession:
    """A Stripe object as the SDK presents it: attributes plus ``.get``."""

    def __init__(self, **fields):
        self._fields = fields
        for key, value in fields.items():
            setattr(self, key, value)

    def get(self, key, default=None):
        return self._fields.get(key, default)


async def _widget(db, owner, **overrides) -> Widget:
    fields = {
        "user_id": owner.id,
        "target_url": "https://example.com",
        "widget_type": "roi_calculator",
        "title": "Calc",
        "status": "active",
    }
    fields.update(overrides)
    widget = Widget(**fields)
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def _payment(db, owner, **overrides) -> Payment:
    fields = {
        "user_id": owner.id,
        "stripe_session_id": "cs_test",
        "amount": settings.widget_launch_price_cents,
        "currency": settings.widget_launch_currency,
        "status": "pending",
    }
    fields.update(overrides)
    payment = Payment(**fields)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


class TestCheckoutCompleted:
    async def test_amount_mismatch_is_refused_and_marked_failed(self, db, user, monkeypatch):
        """Never grant on an amount we did not record — that is a price-tampering path."""
        widget = await _widget(db, user, entitlement_status="checkout_pending")
        payment = await _payment(db, user, widget_id=widget.id, stripe_session_id="cs_cheap")

        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(
                payment_status="paid", payment_intent="pi_1", amount_total=1
            ),
        )

        assert await handle_checkout_completed(db, "cs_cheap") is False
        # The service mutates; the webhook route is what commits. Committing here
        # is what proves the decision actually survives the request.
        await db.commit()
        await db.refresh(payment)
        await db.refresh(widget)
        assert payment.status == "failed"
        assert widget.entitlement_status == "checkout_pending"

    async def test_unpaid_session_leaves_the_payment_pending(self, db, user, monkeypatch):
        payment = await _payment(db, user, stripe_session_id="cs_unpaid")

        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(
                payment_status="unpaid",
                payment_intent="pi_1",
                amount_total=settings.widget_launch_price_cents,
            ),
        )

        assert await handle_checkout_completed(db, "cs_unpaid") is False
        await db.refresh(payment)
        assert payment.status == "pending"

    async def test_an_expanded_payment_intent_is_stored_as_its_id(self, db, user, monkeypatch):
        """Storing the object's repr here would break every later refund lookup."""
        payment = await _payment(db, user, stripe_session_id="cs_expanded")

        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(
                payment_status="paid",
                payment_intent=StripeSession(id="pi_expanded"),
                amount_total=settings.widget_launch_price_cents,
            ),
        )

        assert await handle_checkout_completed(db, "cs_expanded") is True
        await db.commit()
        await db.refresh(payment)
        assert payment.stripe_payment_intent == "pi_expanded"
        assert payment.confirmed_at is not None

    async def test_a_session_stripe_cannot_return_raises(self, db, user, monkeypatch):
        await _payment(db, user, stripe_session_id="cs_broken")

        def boom(*args, **kwargs):
            raise stripe.StripeError("api down")

        monkeypatch.setattr(stripe.checkout.Session, "retrieve", boom)

        with pytest.raises(PaymentProviderError):
            await handle_checkout_completed(db, "cs_broken")

    async def test_missing_amount_total_is_accepted(self, db, user, monkeypatch):
        """Some session modes omit it; absence is not a mismatch."""
        payment = await _payment(db, user, stripe_session_id="cs_no_total")

        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(payment_status="paid", payment_intent="pi_1"),
        )

        assert await handle_checkout_completed(db, "cs_no_total") is True
        await db.commit()
        await db.refresh(payment)
        assert payment.status == "confirmed"


class TestCheckoutExpired:
    async def test_expiry_releases_the_widget_back_to_preview(self, db, user):
        """Otherwise an abandoned checkout leaves the tool stuck mid-purchase forever."""
        widget = await _widget(db, user, entitlement_status="checkout_pending")
        payment = await _payment(db, user, widget_id=widget.id, stripe_session_id="cs_gone")

        assert await handle_checkout_expired(db, "cs_gone") is True
        await db.refresh(payment)
        await db.refresh(widget)
        assert payment.status == "failed"
        assert widget.entitlement_status == "preview"

    async def test_expiry_of_an_already_paid_session_changes_nothing(self, db, user):
        widget = await _widget(db, user, entitlement_status="paid")
        payment = await _payment(
            db, user, widget_id=widget.id, stripe_session_id="cs_paid", status="confirmed"
        )

        assert await handle_checkout_expired(db, "cs_paid") is True
        await db.refresh(payment)
        await db.refresh(widget)
        assert payment.status == "confirmed"
        assert widget.entitlement_status == "paid"

    async def test_unknown_session_is_unhandled(self, db):
        assert await handle_checkout_expired(db, "cs_never_seen") is False


class TestRefunds:
    async def test_a_full_refund_revokes_the_entitlement(self, db, user):
        widget = await _widget(db, user, entitlement_status="paid")
        payment = await _payment(
            db,
            user,
            widget_id=widget.id,
            status="confirmed",
            stripe_payment_intent="pi_refund",
        )

        assert await handle_payment_refunded(db, "pi_refund", fully_refunded=True) is True
        await db.refresh(payment)
        await db.refresh(widget)
        assert payment.status == "refunded"
        assert widget.entitlement_status == "preview"

    async def test_a_partial_refund_leaves_access_intact(self, db, user):
        """A goodwill partial refund is not a cancellation of the purchase."""
        widget = await _widget(db, user, entitlement_status="paid")
        payment = await _payment(
            db,
            user,
            widget_id=widget.id,
            status="confirmed",
            stripe_payment_intent="pi_partial",
        )

        assert await handle_payment_refunded(db, "pi_partial", fully_refunded=False) is True
        await db.refresh(payment)
        await db.refresh(widget)
        assert payment.status == "confirmed"
        assert widget.entitlement_status == "paid"

    async def test_a_refund_for_an_unknown_intent_is_unhandled(self, db):
        assert await handle_payment_refunded(db, "pi_unknown", fully_refunded=True) is False


class TestSubscriptionLifecycle:
    async def test_completed_checkout_activates_the_workspace(self, db, user, monkeypatch):
        subscription = Subscription(
            user_id=user.id,
            plan="studio",
            status="checkout_pending",
            stripe_session_id="cs_sub",
        )
        db.add(subscription)
        await db.commit()

        period_end = int(datetime(2026, 12, 1, tzinfo=UTC).timestamp())
        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(
                subscription=StripeSession(
                    id="sub_1", status="active", current_period_end=period_end
                ),
                customer="cus_1",
            ),
        )

        assert await handle_subscription_checkout_completed(db, "cs_sub") is True
        await db.commit()
        await db.refresh(subscription)
        assert subscription.status == "active"
        assert subscription.stripe_subscription_id == "sub_1"
        assert subscription.stripe_customer_id == "cus_1"
        assert subscription.current_period_end.year == 2026

    async def test_an_unexpanded_subscription_id_is_fetched(self, db, user, monkeypatch):
        subscription = Subscription(
            user_id=user.id, plan="studio", status="checkout_pending", stripe_session_id="cs_str"
        )
        db.add(subscription)
        await db.commit()

        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(subscription="sub_str", customer="cus_1"),
        )
        monkeypatch.setattr(
            stripe.Subscription,
            "retrieve",
            lambda *a, **k: StripeSession(id="sub_str", status="trialing"),
        )

        # A trial is active access, so it must not read as unpaid.
        assert await handle_subscription_checkout_completed(db, "cs_str") is True
        await db.commit()
        await db.refresh(subscription)
        assert subscription.status == "active"

    async def test_a_session_without_a_subscription_raises(self, db, user, monkeypatch):
        subscription = Subscription(
            user_id=user.id, plan="studio", status="checkout_pending", stripe_session_id="cs_none"
        )
        db.add(subscription)
        await db.commit()

        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda *a, **k: StripeSession(subscription=None, customer="cus_1"),
        )

        with pytest.raises(PaymentProviderError):
            await handle_subscription_checkout_completed(db, "cs_none")

    async def test_an_unknown_session_is_unhandled(self, db):
        assert await handle_subscription_checkout_completed(db, "cs_never") is False

    @pytest.mark.parametrize(
        ("stripe_status", "expected"),
        [
            ("active", "active"),
            ("trialing", "active"),
            ("past_due", "past_due"),
            ("unpaid", "past_due"),
            ("canceled", "canceled"),
            ("incomplete_expired", "canceled"),
        ],
    )
    async def test_stripe_statuses_map_onto_access(self, db, user, stripe_status, expected):
        """Anything not clearly paid or in grace collapses to no access."""
        subscription = Subscription(
            user_id=user.id, plan="studio", status="active", stripe_subscription_id="sub_map"
        )
        db.add(subscription)
        await db.commit()

        assert (
            await handle_subscription_changed(
                db, {"id": "sub_map", "status": stripe_status, "current_period_end": None}
            )
            is True
        )
        await db.commit()
        await db.refresh(subscription)
        assert subscription.status == expected

    async def test_a_change_for_an_unknown_subscription_is_unhandled(self, db):
        assert await handle_subscription_changed(db, {"id": "sub_unknown"}) is False

    async def test_an_unparseable_period_end_does_not_break_the_update(self, db, user):
        """A bad timestamp must not strand a subscription in its previous state."""
        subscription = Subscription(
            user_id=user.id, plan="studio", status="active", stripe_subscription_id="sub_bad"
        )
        db.add(subscription)
        await db.commit()

        assert (
            await handle_subscription_changed(
                db, {"id": "sub_bad", "status": "active", "current_period_end": "not-a-timestamp"}
            )
            is True
        )
        await db.refresh(subscription)
        assert subscription.current_period_end is None


class TestPlanTerms:
    def test_known_plans_carry_a_price_and_a_limit(self):
        price, limit = plan_terms("studio")
        assert price == settings.studio_monthly_price_cents
        assert limit == settings.studio_active_experience_limit

    def test_an_unknown_plan_is_worth_nothing(self):
        """Free and typo'd plan names must both fall through to no allowance."""
        assert plan_terms("enterprise-gold") == (0, 0)


class TestSubscriptionSummary:
    async def test_a_workspace_without_a_subscription_reports_its_usage(self, db, user):
        await _widget(db, user, status="active")
        await _widget(db, user, status="building")
        await _widget(db, user, status="failed")

        subscription, active, limit, price = await subscription_summary(db, user.id)

        # "building" counts: it is occupying a slot the plan has to allow for.
        assert subscription is None
        assert active == 2
        assert (limit, price) == (0, 0)

    async def test_a_subscribed_workspace_reports_its_plan_terms(self, db, user):
        db.add(Subscription(user_id=user.id, plan="scale", status="active"))
        await _widget(db, user, status="active")
        await db.commit()

        subscription, active, limit, price = await subscription_summary(db, user.id)

        assert subscription is not None
        assert active == 1
        assert limit == settings.scale_active_experience_limit
        assert price == settings.scale_monthly_price_cents

    async def test_another_workspaces_tools_are_not_counted(self, db, user, other_user):
        await _widget(db, user, status="active")
        await _widget(db, other_user, status="active")

        _, active, _, _ = await subscription_summary(db, user.id)

        assert active == 1
