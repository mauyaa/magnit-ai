from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.payments.models import Payment, Subscription
from app.features.widgets.models import Widget
from app.platform.config.settings import settings

logger = logging.getLogger(__name__)


class PaymentProviderError(Exception):
    pass


def plan_terms(plan: str) -> tuple[int, int]:
    if plan == "studio":
        return (
            settings.studio_monthly_price_cents,
            settings.studio_active_experience_limit,
        )
    if plan == "scale":
        return (
            settings.scale_monthly_price_cents,
            settings.scale_active_experience_limit,
        )
    return (0, 0)


def configure_stripe() -> None:
    """Set the Stripe key at startup rather than at import time."""
    stripe.api_key = settings.stripe_secret_key


async def _mark_widget_paid(db: AsyncSession, payment: Payment) -> None:
    if not payment.widget_id:
        return
    widget_result = await db.execute(
        select(Widget).where(
            Widget.id == payment.widget_id,
            Widget.user_id == payment.user_id,
        )
    )
    widget = widget_result.scalar_one_or_none()
    if widget is not None:
        widget.entitlement_status = "paid"


async def create_checkout_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    widget_id: uuid.UUID,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    configure_stripe()
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": settings.widget_launch_currency,
                        "product_data": {
                            "name": "MagnetAI decision tool launch",
                            "description": (
                                "One grounded, branded, working decision tool with deployment"
                            ),
                        },
                        "unit_amount": settings.widget_launch_price_cents,
                    },
                    "quantity": 1,
                }
            ],
            metadata={"user_id": str(user_id), "widget_id": str(widget_id)},
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.StripeError:
        logger.exception("Stripe checkout creation failed for user %s", user_id)
        raise PaymentProviderError() from None

    # Stripe types `url` as optional (it is absent for some session modes). Guard
    # it rather than returning None, which the frontend would happily navigate to.
    if not session.url:
        logger.error("Stripe session %s was created without a checkout URL", session.id)
        raise PaymentProviderError()

    payment = Payment(
        user_id=user_id,
        widget_id=widget_id,
        stripe_session_id=session.id,
        amount=settings.widget_launch_price_cents,
        currency=settings.widget_launch_currency,
        status="pending",
    )
    db.add(payment)
    await db.flush()

    return session.url, session.id


async def create_subscription_checkout_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    price, _ = plan_terms(plan)
    if not price:
        raise ValueError("invalid_subscription_plan")

    existing = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    if existing is not None and existing.status == "active":
        raise ValueError("subscription_already_active")

    configure_stripe()
    customer_id = (
        existing.stripe_customer_id
        if (existing is not None and existing.stripe_customer_id)
        else None
    )
    customer_email = email if not customer_id else None
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,  # type: ignore[arg-type]
            customer_email=customer_email,  # type: ignore[arg-type]
            line_items=[
                {
                    "price_data": {
                        "currency": settings.widget_launch_currency,
                        "product_data": {
                            "name": f"Magnit {plan.title()} workspace",
                            "description": (
                                "Build, publish, measure, and improve interactive lead experiences."
                            ),
                        },
                        "unit_amount": price,
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "kind": "workspace_subscription",
                "user_id": str(user_id),
                "plan": plan,
            },
            subscription_data={
                "metadata": {
                    "kind": "workspace_subscription",
                    "user_id": str(user_id),
                    "plan": plan,
                }
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.StripeError:
        logger.exception("Stripe subscription checkout failed for user %s", user_id)
        raise PaymentProviderError() from None

    if not session.url:
        raise PaymentProviderError()

    subscription = existing or Subscription(user_id=user_id, plan=plan)
    subscription.plan = plan
    subscription.status = "checkout_pending"
    subscription.stripe_session_id = session.id
    db.add(subscription)
    await db.flush()
    return session.url, session.id


def _period_end(value: object) -> datetime | None:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=UTC)
        if isinstance(value, str):
            return datetime.fromtimestamp(int(value), tz=UTC)
        return None
    except (TypeError, ValueError, OSError):
        return None


def _subscription_status(value: object) -> str:
    status = str(value or "").lower()
    if status in {"active", "trialing"}:
        return "active"
    if status in {"past_due", "unpaid"}:
        return "past_due"
    return "canceled"


async def handle_subscription_checkout_completed(db: AsyncSession, session_id: str) -> bool:
    subscription = await db.scalar(
        select(Subscription).where(Subscription.stripe_session_id == session_id)
    )
    if subscription is None:
        return False

    configure_stripe()
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    except stripe.StripeError:
        raise PaymentProviderError() from None

    stripe_subscription = session.subscription
    subscription_id = (
        stripe_subscription
        if isinstance(stripe_subscription, str)
        else getattr(stripe_subscription, "id", None)
    )
    if not subscription_id:
        raise PaymentProviderError()

    if isinstance(stripe_subscription, str):
        try:
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription)
        except stripe.StripeError:
            raise PaymentProviderError() from None

    subscription.stripe_subscription_id = str(subscription_id)
    customer = session.customer
    subscription.stripe_customer_id = (
        customer if isinstance(customer, str) else getattr(customer, "id", None)
    )
    subscription.status = _subscription_status(getattr(stripe_subscription, "status", "active"))
    subscription.current_period_end = _period_end(
        getattr(stripe_subscription, "current_period_end", None)
    )
    return subscription.status == "active"


async def handle_subscription_changed(db: AsyncSession, payload: object) -> bool:
    subscription_id = str(
        payload.get("id") if isinstance(payload, dict) else getattr(payload, "id", "")
    )
    subscription = await db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    if subscription is None:
        return False
    raw_status = (
        payload.get("status") if isinstance(payload, dict) else getattr(payload, "status", None)
    )
    raw_period_end = (
        payload.get("current_period_end")
        if isinstance(payload, dict)
        else getattr(payload, "current_period_end", None)
    )
    subscription.status = _subscription_status(raw_status)
    subscription.current_period_end = _period_end(raw_period_end)
    return True


async def subscription_summary(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[Subscription | None, int, int, int]:
    subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    active_experiences = int(
        await db.scalar(
            select(func.count(Widget.id)).where(
                Widget.user_id == user_id,
                Widget.status.in_(("active", "building")),
            )
        )
        or 0
    )
    if subscription is None:
        return None, active_experiences, 0, 0
    price, limit = plan_terms(subscription.plan)
    return subscription, active_experiences, limit, price


async def handle_checkout_completed(db: AsyncSession, session_id: str) -> bool:
    """Confirm a payment from a verified ``checkout.session.completed`` event.

    Idempotent: Stripe retries webhooks, so an already-confirmed payment is a
    no-op rather than a double write. The amount is re-read from Stripe instead of
    trusted from the event body.
    """
    configure_stripe()

    result = await db.execute(select(Payment).where(Payment.stripe_session_id == session_id))
    payment = result.scalar_one_or_none()
    if payment is None:
        logger.warning("Webhook for unknown Stripe session %s", session_id)
        return False

    if payment.status == "confirmed":
        await _mark_widget_paid(db, payment)
        logger.info("Ignoring duplicate webhook for already-confirmed session %s", session_id)
        return True

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError:
        logger.exception("Could not verify Stripe session %s", session_id)
        raise PaymentProviderError() from None

    if session.payment_status != "paid":
        logger.warning(
            "Session %s reported status %s; leaving payment pending",
            session_id,
            session.payment_status,
        )
        return False

    amount_paid = session.get("amount_total")
    if amount_paid is not None and int(amount_paid) != payment.amount:
        # Never silently accept a different amount than we recorded.
        logger.error(
            "Amount mismatch for session %s: expected %d, Stripe reported %s",
            session_id,
            payment.amount,
            amount_paid,
        )
        payment.status = "failed"
        return False

    payment.status = "confirmed"
    # payment_intent is an id string when unexpanded, but a PaymentIntent object
    # when the caller expanded it. Store the id either way, never a repr.
    intent = session.payment_intent
    payment.stripe_payment_intent = (
        intent if isinstance(intent, str) else getattr(intent, "id", None)
    )
    payment.confirmed_at = datetime.now(UTC)
    await _mark_widget_paid(db, payment)
    logger.info("Confirmed payment %s for user %s", payment.id, payment.user_id)
    return True


async def handle_checkout_expired(db: AsyncSession, session_id: str) -> bool:
    result = await db.execute(select(Payment).where(Payment.stripe_session_id == session_id))
    payment = result.scalar_one_or_none()
    if payment is None or payment.status != "pending":
        return payment is not None
    payment.status = "failed"
    if payment.widget_id:
        widget = await db.scalar(select(Widget).where(Widget.id == payment.widget_id))
        if widget is not None and widget.entitlement_status == "checkout_pending":
            widget.entitlement_status = "preview"
    return True


async def handle_payment_refunded(
    db: AsyncSession,
    payment_intent: str,
    *,
    fully_refunded: bool,
) -> bool:
    """Revoke future spend after a verified full refund."""
    if not fully_refunded:
        return True
    payment = await db.scalar(
        select(Payment).where(Payment.stripe_payment_intent == payment_intent)
    )
    if payment is None:
        return False
    payment.status = "refunded"
    if payment.widget_id:
        widget = await db.scalar(select(Widget).where(Widget.id == payment.widget_id))
        if widget is not None and widget.entitlement_status == "paid":
            widget.entitlement_status = "preview"
    return True


async def list_user_payments(db: AsyncSession, user_id: uuid.UUID) -> list[Payment]:
    result = await db.execute(
        select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())
