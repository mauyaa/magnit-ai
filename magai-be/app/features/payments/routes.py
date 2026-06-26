import hashlib

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.payments.schemas import (
    CreateCheckoutRequest,
    CreateCheckoutResponse,
    WebhookResponse,
)
from app.features.payments.service import (
    create_checkout_session,
    handle_checkout_completed,
)
from app.platform.config.settings import settings
from app.platform.db.session import get_async_session

router = APIRouter(prefix="/api/payments", tags=["payments"])

stripe.api_key = settings.stripe_secret_key


@router.post("/create-checkout", response_model=CreateCheckoutResponse)
async def create_checkout(
    payload: CreateCheckoutRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user_id = "anonymous"
    url, session_id = await create_checkout_session(
        db,
        user_id=user_id,
        widget_id=payload.widget_id,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
    )
    return CreateCheckoutResponse(checkout_url=url, session_id=session_id)


@router.post("/stripe/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_async_session),
):
    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="missing_signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=f"invalid_signature: {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await handle_checkout_completed(db, session["id"])

    return WebhookResponse(received=True)
