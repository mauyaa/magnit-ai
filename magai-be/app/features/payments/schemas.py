from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class CreateCheckoutRequest(BaseModel):
    widget_id: str
    # HttpUrl so a caller cannot hand Stripe a javascript: or data: redirect.
    # The host is additionally pinned to the configured frontend in the route.
    success_url: HttpUrl
    cancel_url: HttpUrl


class CreateCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class CreateSubscriptionCheckoutRequest(BaseModel):
    plan: Literal["studio", "scale"]
    success_url: HttpUrl
    cancel_url: HttpUrl


class SubscriptionResponse(BaseModel):
    plan: Literal["free", "studio", "scale"]
    status: Literal["free", "checkout_pending", "active", "past_due", "canceled"]
    active_experiences: int
    experience_limit: int
    monthly_price: int
    currency: str
    current_period_end: str | None = None


class WebhookResponse(BaseModel):
    received: bool


class PaymentResponse(BaseModel):
    id: str
    widget_id: str | None
    amount: int
    currency: str = Field(max_length=3)
    status: str
    created_at: str
    confirmed_at: str | None = None
