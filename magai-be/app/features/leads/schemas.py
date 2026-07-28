from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SubmitLeadRequest(BaseModel):
    # EmailStr rather than str: this endpoint is public, so a junk address should
    # be rejected at the edge instead of polluting a customer's lead list.
    email: EmailStr
    name: str | None = Field(default=None, max_length=255)
    score: int | None = Field(default=None, ge=-1_000_000, le=1_000_000)
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
    answers: dict | None
    metadata: dict | None
    qualification_status: str | None
    result_key: str | None
    forwarded: bool
    forwarded_at: str | None
    created_at: str
    # Owner-maintained follow-up state, so the leads table can be worked from
    # rather than only read.
    status: str = "new"
    tags: list[str] = Field(default_factory=list)
    contacted_at: str | None = None
    note_count: int = 0


class LeadNoteResponse(BaseModel):
    id: str
    body: str
    created_at: str


class TimelineEntryResponse(BaseModel):
    kind: str
    title: str
    detail: str
    occurred_at: str
    tone: str


class LeadDetailResponse(BaseModel):
    """Everything the lead page shows, in one request.

    Assembled server-side rather than left to the client to stitch from four
    endpoints: the timeline needs interactions and deliveries joined in order,
    and doing that in the browser means four round trips and a sort that can
    disagree with the server's.
    """

    lead: LeadResponse
    widget_title: str
    widget_id: str
    notes: list[LeadNoteResponse]
    timeline: list[TimelineEntryResponse]


class UpdateLeadRequest(BaseModel):
    status: Literal["new", "contacted", "qualified", "won", "lost"] | None = None
    tags: list[str] | None = Field(default=None, max_length=12)


class CreateLeadNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)
