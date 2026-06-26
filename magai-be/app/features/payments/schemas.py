from pydantic import BaseModel


class CreateCheckoutRequest(BaseModel):
    widget_id: str
    success_url: str
    cancel_url: str


class CreateCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class WebhookResponse(BaseModel):
    received: bool
