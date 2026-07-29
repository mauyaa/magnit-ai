import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.features.widgets.outcomes import OutcomeConfig
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    CreationBrief,
    DecisionSpec,
    WidgetType,
)


class AnalyzeRequest(BaseModel):
    # Length is bounded here as well as in the SSRF guard so an oversized body is
    # rejected by validation before any resolution work happens.
    url: str = Field(min_length=4, max_length=2048)
    brief: CreationBrief | None = None


class AnalyzeResponse(BaseModel):
    widget_id: str
    blueprints: list[Blueprint]


class CuratedConcept(BaseModel):
    """One of the two complete directions shown during the free first look."""

    blueprint: Blueprint
    architect: ArchitectOutput


class SiteReadResponse(BaseModel):
    """What the crawler found, answered before any model is asked.

    Exists purely to give the visitor something true to look at early. Reading
    the site takes about five seconds; proposing directions takes another fifty,
    and a minute of blank screen is where a first-time visitor leaves. Splitting
    the two lets the interface name the business, show the real brand colours and
    quote actual headings while the slow half runs.

    Every field is observed, never predicted — the point is to prove the site was
    genuinely read, so a progress bar with invented milestones would defeat it.
    """

    target_url: str
    domain: str
    business_name: str = ""
    summary: str = ""
    pages_read: int = 0
    signals_found: int = 0
    colors: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    # A few verbatim quotes, so the read is legible rather than a count.
    highlights: list[str] = Field(default_factory=list, max_length=4)


class GuestConceptsResponse(BaseModel):
    target_url: str
    session_token: str
    concepts: list[CuratedConcept] = Field(min_length=2, max_length=2)
    brief: CreationBrief = Field(default_factory=CreationBrief)


class ClaimGuestConceptRequest(BaseModel):
    session_token: str = Field(min_length=40, max_length=200_000)
    selected_index: int = Field(ge=0, le=1)


class ClaimGuestConceptResponse(AnalyzeResponse):
    selected_index: int
    selected_concept: ArchitectOutput
    entitlement_status: str
    can_build: bool


class ToolTypeResponse(BaseModel):
    """One entry in the catalogue of things a customer can ask us to build."""

    kind: WidgetType
    label: str
    visitor_does: str
    best_for: str
    # True when the analyzer proposed this type for this particular site. The UI
    # leads with those, but every type stays selectable.
    suggested: bool = False


class ToolTypeListResponse(BaseModel):
    tool_types: list[ToolTypeResponse]


class _TypeOrIndex(BaseModel):
    """Either pick one of the analyzer's proposals, or name a type outright.

    `widget_type` wins when both are present, so a client that always sends the
    index it last used cannot silently override an explicit choice.
    """

    blueprint_index: int = Field(default=0, ge=0, le=32)
    widget_type: WidgetType | None = None

    @model_validator(mode="after")
    def _index_ignored_when_type_given(self) -> "_TypeOrIndex":
        if self.widget_type is not None:
            self.blueprint_index = 0
        return self


class ArchitectPreviewRequest(_TypeOrIndex):
    pass


class BuildRequest(_TypeOrIndex):
    widget_id: str
    skip_deploy: bool = False
    # Present when the user reviewed (and possibly edited) the brand match in the
    # confirm step; skips re-extraction so their edits survive into the build.
    architect_override: ArchitectOutput | None = None


class BuildResponse(BaseModel):
    widget_id: str
    iframe_url: str
    status: str
    embed_code: str


class WidgetStatusResponse(BaseModel):
    id: str
    title: str
    widget_type: str
    status: str
    target_url: str
    deployment_url: str | None = None
    embed_code: str | None = None
    leads_count: int
    impressions_count: int
    starts_count: int
    completions_count: int
    cta_clicks_count: int
    # Percentage, rounded to one decimal. None until the widget has been viewed,
    # rather than a misleading 0% for a widget nobody has seen yet.
    conversion_rate: float | None = None
    plan_tier: str
    lead_cap: int
    entitlement_status: str
    can_build: bool
    launch_settings: dict | None = None
    delivery_webhook_url: str | None = None
    consent_text: str | None = None
    creation_brief: dict | None = None
    brand_tokens: dict | None = None
    visual_language: dict | None = None
    widget_logic: dict | None = None
    copywriting: dict | None = None
    design_tokens: dict | None = None
    build_stage: str | None = None
    build_progress: float | None = None
    build_error: str | None = None
    created_at: str
    deployed_at: str | None = None
    last_heal_check_at: str | None = None
    last_brand_check_at: str | None = None


class TrackInteractionRequest(BaseModel):
    """A privacy-light, idempotent event from one embedded visitor session."""

    event: Literal["started", "progressed", "completed", "result_viewed", "cta_clicked"]
    session_id: str = Field(min_length=16, max_length=128)
    step: str | None = Field(default=None, max_length=100)
    result_key: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=2048)
    attribution: dict | None = None

    @field_validator("attribution")
    @classmethod
    def _bounded_attribution(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        if len(value) > 20 or len(json.dumps(value, default=str).encode()) > 4_096:
            raise ValueError("attribution is too large")
        if any(isinstance(item, (dict, list)) for item in value.values()):
            raise ValueError("attribution values must be scalar")
        return value


class FunnelResponse(BaseModel):
    views: int
    starts: int
    completions: int
    results_viewed: int
    cta_clicks: int
    leads: int
    start_rate: float | None
    completion_rate: float | None
    lead_rate: float | None
    cta_rate: float | None
    dropoff_by_step: dict[str, int]


class AnalyticsDay(BaseModel):
    date: str
    starts: int
    completions: int
    leads: int
    cta_clicks: int


class AnalyticsSource(BaseModel):
    source: str
    engaged_visitors: int
    leads: int


class AnalyticsExperience(BaseModel):
    id: str
    title: str
    status: str
    views: int
    starts: int
    completions: int
    leads: int
    conversion_rate: float | None


class PortfolioAnalyticsResponse(BaseModel):
    period_days: int
    experiences: list[AnalyticsExperience]
    daily: list[AnalyticsDay]
    sources: list[AnalyticsSource]
    totals: dict[str, int]
    rates: dict[str, float | None]
    dropoff_by_step: dict[str, int]


def _default_lead_fields() -> list[Literal["email", "name", "company", "phone"]]:
    return ["email", "name"]


class LaunchSetupRequest(BaseModel):
    target_page_url: str | None = Field(default=None, max_length=2048)
    cta_url: str | None = Field(default=None, max_length=2048)
    cta_label: str | None = Field(default=None, max_length=80)
    lead_fields: list[Literal["email", "name", "company", "phone"]] = Field(
        default_factory=_default_lead_fields, max_length=4
    )
    delivery_webhook_url: str | None = Field(default=None, max_length=2048)
    delivery_mode: Literal["custom", "zapier", "make", "n8n"] = "custom"
    consent_text: str | None = Field(default=None, max_length=500)


class LaunchSetupResponse(BaseModel):
    launch_settings: dict
    delivery_webhook_url: str | None
    webhook_signing_secret: str | None
    consent_text: str | None


class DeliveryTestResponse(BaseModel):
    connected: bool
    status_code: int | None
    checked_at: str
    message: str


class OutcomeConfigResponse(BaseModel):
    """The result screen in force, and whether a person has edited it.

    ``customised`` is what lets the editor say "this is what the AI proposed"
    rather than presenting a derived draft as though the owner had written it.
    """

    config: OutcomeConfig
    customised: bool


class UpdateOutcomeConfigRequest(BaseModel):
    config: OutcomeConfig


class DecisionResponse(BaseModel):
    """The question flow, plus whether it can still be changed."""

    decision: DecisionSpec | None
    # False while a build is running: editing questions mid-build would produce a
    # deployed tool that disagrees with what the editor is showing.
    editable: bool


class UpdateDecisionRequest(BaseModel):
    decision: DecisionSpec


class ReadinessCheckResponse(BaseModel):
    id: str
    label: str
    detail: str
    done: bool
    action: str
    blocking: bool


class ReadinessResponse(BaseModel):
    ready: bool
    completed: int
    total: int
    checks: list[ReadinessCheckResponse]


class RuntimeConfigResponse(BaseModel):
    """What a deployed widget fetches at boot to stay current.

    The decision spec and outcome copy are baked into the bundle at build time so
    the widget works even if this endpoint is unreachable. This is the overlay on
    top: it is how an owner's edit to a score band or a call to action reaches a
    live tool in seconds instead of requiring a rebuild and redeploy.
    """

    widget_id: str
    version: str
    decision: DecisionSpec | None
    outcomes: OutcomeConfig
    consent_text: str | None
    cta_url: str | None
    # False when the tool has been unpublished or is over its lead cap, so the
    # deployed widget can stop asking visitors for details it cannot store.
    accepting_leads: bool


class WidgetListResponse(BaseModel):
    widgets: list[WidgetStatusResponse]


class HealEventResponse(BaseModel):
    id: str
    check_type: str
    status: str
    diff_summary: dict | None = None
    detected_at: str
    healed_at: str | None = None


class DeploymentResponse(BaseModel):
    id: str
    deployment_url: str
    trigger: str
    is_current: bool
    created_at: str
