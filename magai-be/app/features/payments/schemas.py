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


class ReconcileCheckoutRequest(BaseModel):
    """Which checkout the browser is returning from.

    ``kind`` is a hint about where to look the session up, not a claim about its
    outcome — the outcome is always read back from Stripe.
    """

    kind: Literal["one_time", "subscription"] = "one_time"


class ReconcileCheckoutResponse(BaseModel):
    # paid: entitled, go ahead. pending: Stripe is still deciding, or was
    # unreachable. released: nothing was charged and the tool is buildable again.
    outcome: Literal["paid", "pending", "released"]


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
