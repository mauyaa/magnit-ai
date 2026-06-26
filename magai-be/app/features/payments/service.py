import logging
from datetime import UTC, datetime

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.payments.models import Payment
from app.platform.config.settings import settings

logger = logging.getLogger(__name__)
stripe.api_key = settings.stripe_secret_key


async def create_checkout_session(
    db: AsyncSession,
    user_id: str,
    widget_id: str,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "MagnetAI Widget Deployment",
                            "description": "One-time deployment fee for your interactive lead magnet widget",
                        },
                        "unit_amount": 9900,
                    },
                    "quantity": 1,
                }
            ],
            metadata={"user_id": user_id, "widget_id": widget_id},
            success_url=success_url,
            cancel_url=cancel_url,
        )

        payment = Payment(
            user_id=user_id,
            widget_id=widget_id,
            stripe_session_id=session.id,
            amount=9900,
            currency="usd",
            status="pending",
        )
        db.add(payment)
        await db.flush()

        return session.url, session.id
    except stripe.StripeError as e:
        logger.error("Stripe error: %s", e)
        raise HTTPException(status_code=502, detail="payment_provider_error")


async def handle_checkout_completed(
    db: AsyncSession, session_id: str
) -> bool:
    stmt = select(Payment).where(Payment.stripe_session_id == session_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning("Payment not found for session %s", session_id)
        return False

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            payment.status = "confirmed"
            payment.stripe_payment_intent = session.payment_intent
            payment.confirmed_at = datetime.now(UTC)
    except stripe.StripeError as e:
        logger.error("Stripe verification error: %s", e)

    return True
