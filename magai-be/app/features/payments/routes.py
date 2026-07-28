from __future__ import annotations

import logging
from urllib.parse import urlsplit

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.payments.schemas import (
    CreateCheckoutRequest,
    CreateCheckoutResponse,
    CreateSubscriptionCheckoutRequest,
    PaymentResponse,
    SubscriptionResponse,
    WebhookResponse,
)
from app.features.payments.service import (
    PaymentProviderError,
    create_checkout_session,
    create_subscription_checkout_session,
    handle_checkout_completed,
    handle_checkout_expired,
    handle_payment_refunded,
    handle_subscription_changed,
    handle_subscription_checkout_completed,
    list_user_payments,
    subscription_summary,
)
from app.features.widgets.service import WidgetNotFound, get_owned_widget
from app.platform.config.settings import settings
from app.platform.db.session import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _assert_same_origin_as_frontend(url: str, field: str) -> None:
    """Reject redirect targets outside the configured frontend origin.

    Otherwise the endpoint is an open redirect: an attacker could send a victim
    through a genuine Stripe checkout that returns to a site they control.
    """
    candidate = urlsplit(str(url))
    allowed_origins = {
        (parts.scheme, parts.netloc)
        for parts in (
            urlsplit(origin) for origin in [settings.frontend_base_url, *settings.cors_origins]
        )
    }
    if (candidate.scheme, candidate.netloc) not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field} must use a configured frontend origin",
        )


@router.post("/create-checkout", response_model=CreateCheckoutResponse)
async def create_checkout(
    payload: CreateCheckoutRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> CreateCheckoutResponse:
    _assert_same_origin_as_frontend(str(payload.success_url), "success_url")
    _assert_same_origin_as_frontend(str(payload.cancel_url), "cancel_url")

    # Ownership check: you can only pay for your own widget.
    try:
        widget = await get_owned_widget(db, payload.widget_id, user.workspace_id)
    except WidgetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget_not_found"
        ) from None

    # Checked before the session is created, not after. Creating a Stripe session
    # is an external side effect that no database rollback can undo, so ordering
    # this the other way left an orphan checkout session in Stripe every time a
    # customer asked to pay for something they already owned.
    if widget.entitlement_status in {"paid", "complimentary"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="widget_already_entitled",
        )

    try:
        url, session_id = await create_checkout_session(
            db,
            user_id=user.workspace_id,
            widget_id=widget.id,
            success_url=str(payload.success_url),
            cancel_url=str(payload.cancel_url),
        )
    except PaymentProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="payment_provider_error"
        ) from None

    widget.entitlement_status = "checkout_pending"
    return CreateCheckoutResponse(checkout_url=url, session_id=session_id)


@router.post(
    "/create-subscription-checkout",
    response_model=CreateCheckoutResponse,
)
async def create_subscription_checkout(
    payload: CreateSubscriptionCheckoutRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> CreateCheckoutResponse:
    _assert_same_origin_as_frontend(str(payload.success_url), "success_url")
    _assert_same_origin_as_frontend(str(payload.cancel_url), "cancel_url")
    try:
        url, session_id = await create_subscription_checkout_session(
            db,
            user_id=user.workspace_id,
            email=user.email,
            plan=payload.plan,
            success_url=str(payload.success_url),
            cancel_url=str(payload.cancel_url),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except PaymentProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="payment_provider_error",
        ) from None
    return CreateCheckoutResponse(checkout_url=url, session_id=session_id)


@router.post("/stripe/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_async_session),
) -> WebhookResponse:
    """Stripe webhook receiver.

    Unauthenticated by necessity, but every request must carry a valid signature
    computed with the shared webhook secret, so only Stripe can drive it.
    """
    if not settings.stripe_webhook_secret:
        logger.error("Stripe webhook received but MAGAI_STRIPE_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="webhook_not_configured"
        )

    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_signature")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        # Do not echo the verification error: it can reveal secret-length details.
        logger.warning("Rejected Stripe webhook with an invalid signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_signature"
        ) from None

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            if session.get("metadata", {}).get("kind") == "workspace_subscription":
                await handle_subscription_checkout_completed(db, session["id"])
            else:
                await handle_checkout_completed(db, session["id"])
        except PaymentProviderError:
            # 502 makes Stripe retry with backoff rather than dropping the event.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="verification_failed"
            ) from None
    elif event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        await handle_checkout_expired(db, session["id"])
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        intent = charge.get("payment_intent")
        if intent:
            await handle_payment_refunded(
                db,
                str(intent),
                fully_refunded=bool(charge.get("refunded")),
            )
    elif event["type"] in {
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        await handle_subscription_changed(db, event["data"]["object"])
    else:
        logger.info("Ignoring unhandled Stripe event type %s", event["type"])

    return WebhookResponse(received=True)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> SubscriptionResponse:
    subscription, active, limit, price = await subscription_summary(db, user.workspace_id)
    if subscription is None:
        return SubscriptionResponse(
            plan="free",
            status="free",
            active_experiences=active,
            experience_limit=0,
            monthly_price=0,
            currency=settings.widget_launch_currency,
        )
    return SubscriptionResponse(
        plan=subscription.plan,
        status=subscription.status,
        active_experiences=active,
        experience_limit=limit,
        monthly_price=price,
        currency=settings.widget_launch_currency,
        current_period_end=(
            subscription.current_period_end.isoformat() if subscription.current_period_end else None
        ),
    )


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> list[PaymentResponse]:
    payments = await list_user_payments(db, user.workspace_id)
    return [
        PaymentResponse(
            id=str(p.id),
            widget_id=str(p.widget_id) if p.widget_id else None,
            amount=p.amount,
            currency=p.currency,
            status=p.status,
            created_at=p.created_at.isoformat(),
            confirmed_at=p.confirmed_at.isoformat() if p.confirmed_at else None,
        )
        for p in payments
    ]
