from pydantic import BaseModel


class SubmitLeadRequest(BaseModel):
    email: str
    name: str | None = None
    score: int | None = None
    answers: dict | None = None
    metadata: dict | None = None


class SubmitLeadResponse(BaseModel):
    received: bool
    message: str = ""


class LeadResponse(BaseModel):
    id: str
    widget_id: str
    email: str
    name: str | None
    score: int | None
    created_at: str
