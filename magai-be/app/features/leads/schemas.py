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


class WorkspaceLeadResponse(LeadResponse):
    """A lead as the workspace-wide list shows it: with the tool that caught it."""

    widget_title: str


class LeadPageResponse(BaseModel):
    """One page, and enough to know what is not on it.

    ``total`` is the honest count for the current filters. Without it the screen
    can only say "here are some leads", which is exactly the ambiguity that let
    a silently-dropped request look like an empty inbox.
    """

    items: list[WorkspaceLeadResponse]
    total: int
    limit: int
    offset: int


class LeadDeliveryResponse(BaseModel):
    """Where this lead has reached, and where it has not.

    Shown because "we captured it" and "your CRM has it" are different claims,
    and a business relying on the second one deserves to see which is true.
    """

    id: str
    channel: Literal["owner_email", "webhook", "integration"]
    # The connection's provider, for the integration channel. None otherwise.
    provider: str | None = None
    status: Literal["pending", "delivered", "failed", "skipped"]
    attempts: int
    last_error: str | None = None
    next_attempt_at: str | None = None
    delivered_at: str | None = None
    # Whether the owner may ask for another attempt right now.
    retryable: bool = False


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
    deliveries: list[LeadDeliveryResponse]


class UpdateLeadRequest(BaseModel):
    status: Literal["new", "contacted", "qualified", "won", "lost"] | None = None
    tags: list[str] | None = Field(default=None, max_length=12)


class CreateLeadNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)
