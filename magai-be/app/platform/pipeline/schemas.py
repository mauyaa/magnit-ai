from enum import StrEnum
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class WidgetType(StrEnum):
    """The named shapes a tool can take — a vocabulary, not a menu.

    These five are what the analyzer reaches for first because they are the
    shapes that reliably convert, and they are what the catalogue offers as
    suggestions. But nothing in the pipeline branches on the type: the Architect
    designs against the live site and the real brief, and Codegen builds from the
    resulting logic and decision spec. The type only ever labelled a prompt.

    CUSTOM is the escape hatch, and the reason it exists is a product one: a
    closed list of five silently tells a customer their idea is out of scope
    whenever it does not happen to be one of these. If someone asks for a
    pricing configurator, a symptom checker, or a mortgage affordability tool,
    the honest answer is to build it — not to route them into the nearest of
    five. CUSTOM is never offered as a pick; the analyzer selects it when the
    stated intent does not fit a named shape.
    """

    ROI_CALCULATOR = "roi_calculator"
    READINESS_QUIZ = "readiness_quiz"
    COMPETITIVE_COMPARISON = "competitive_comparison"
    AUDIT_TOOL = "audit_tool"
    INTERACTIVE_CHECKLIST = "interactive_checklist"
    CUSTOM = "custom"


class CreationBrief(BaseModel):
    """Bounded human direction layered on top of grounded website evidence.

    The brief controls product choices, never factual claims. Business-specific
    numbers and proof still need evidence references from the controlled crawl.
    """

    mode: Literal["autopilot", "guided"] = "autopilot"
    # The customer's own words for what they want built.
    #
    # Everything else in this brief is a choice between options we wrote down
    # in advance, which caps the product at what we thought of. This field is
    # the one place someone can describe a tool we never anticipated, and it
    # leads the analyzer rather than merely decorating it. Treated as
    # preference, never as evidence — the same rule the rest of the brief is
    # already under.
    intent: str = Field(default="", max_length=600)
    audience: str = Field(default="", max_length=240)
    goal: Literal[
        "capture_qualified_leads",
        "book_more_calls",
        "educate_buyers",
        "estimate_value",
        "recommend_next_step",
    ] = "capture_qualified_leads"
    offer: str = Field(default="", max_length=280)
    visitor_question: str = Field(default="", max_length=220)
    preferred_type: WidgetType | None = None
    tone: Literal["match_site", "warm", "direct", "premium", "technical", "playful"] = "match_site"
    result_style: Literal["score", "estimate", "recommendation", "comparison", "action_plan"] = (
        "recommendation"
    )
    question_count: int = Field(default=4, ge=2, le=7)
    instructions: str = Field(default="", max_length=800)


class Blueprint(BaseModel):
    type: WidgetType
    title: str
    description: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


class BlueprintList(BaseModel):
    blueprints: list[Blueprint] = Field(min_length=2, max_length=5)

    @field_validator("blueprints")
    @classmethod
    def _unique_types(cls, blueprints: list[Blueprint]) -> list[Blueprint]:
        kinds = [blueprint.type for blueprint in blueprints]
        if len(kinds) != len(set(kinds)):
            raise ValueError("blueprint types must be strategically distinct")
        return blueprints


class EvidenceReference(BaseModel):
    """One bounded, attributable fact extracted from a public source page."""

    id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9_-]+$")
    kind: Literal["heading", "description", "offer", "proof", "price", "cta"]
    text: str = Field(min_length=1, max_length=500)
    source_url: str = Field(min_length=4, max_length=2048)


class SitePageEvidence(BaseModel):
    """The small amount of useful page content the model is allowed to see."""

    url: str = Field(min_length=4, max_length=2048)
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=600)
    headings: list[str] = Field(default_factory=list, max_length=30)
    calls_to_action: list[str] = Field(default_factory=list, max_length=20)
    pricing_signals: list[str] = Field(default_factory=list, max_length=20)


class SiteBrandEvidence(BaseModel):
    colors: list[str] = Field(default_factory=list, max_length=20)
    fonts: list[str] = Field(default_factory=list, max_length=12)
    logo_url: str | None = Field(default=None, max_length=2048)


class SiteEvidence(BaseModel):
    """Deterministic crawl result used as the sole business/brand source."""

    target_url: str = Field(min_length=4, max_length=2048)
    domain: str = Field(min_length=1, max_length=255)
    business_name: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=600)
    pages: list[SitePageEvidence] = Field(default_factory=list, min_length=1, max_length=6)
    references: list[EvidenceReference] = Field(default_factory=list, max_length=80)
    brand: SiteBrandEvidence = Field(default_factory=SiteBrandEvidence)
    content_fingerprint: str = Field(min_length=64, max_length=64)
    brand_fingerprint: str = Field(min_length=64, max_length=64)

    def compact_context(self) -> dict[str, Any]:
        """Return the complete but bounded payload sent to generation stages."""
        return self.model_dump(mode="json")


class BrandExtraction(BaseModel):
    primary_color: str
    secondary_color: str
    background_color: str
    accent_color: str
    font_headings: str
    font_body: str
    tone: str
    logo_url: str | None = None


class MathLogic(BaseModel):
    formula: str
    variables: list[dict[str, str]]
    example_calculation: str


class DecisionQuestion(BaseModel):
    """A renderer-safe question. No executable expressions or arbitrary markup."""

    id: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=3, max_length=180)
    help_text: str = Field(default="", max_length=240)
    input_type: Literal["number", "single_choice", "boolean"]
    required: bool = True
    options: list[str] = Field(default_factory=list, max_length=8)
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    default: float | str | bool | None = None
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    option_scores: list[float] = Field(default_factory=list, max_length=8)
    true_score: float = Field(default=100.0, ge=0.0, le=100.0)
    evidence_ref: str | None = Field(default=None, max_length=80)

    @field_validator("true_score", mode="before")
    @classmethod
    def _absent_true_score_is_the_default(cls, value: Any) -> Any:
        """Treat an explicit ``null`` as "not supplied".

        ``true_score`` is only read for boolean questions — see the runtime's
        ``calculateDecision`` — so on a number or choice question it means
        nothing, and a model that writes ``"true_score": null`` there is being
        accurate rather than wrong. Pydantic rejects null for a non-optional
        float, which failed the whole architect stage over a field that would
        never have been read. Observed against gemini-3.6-flash.
        """
        return 100.0 if value is None else value

    @model_validator(mode="after")
    def _validate_input_shape(self) -> "DecisionQuestion":
        if self.input_type == "single_choice" and len(self.options) < 2:
            raise ValueError("single_choice questions require at least two options")
        if self.option_scores and len(self.option_scores) != len(self.options):
            raise ValueError("option_scores must match the number of options")
        if any(score < 0 or score > 100 for score in self.option_scores):
            raise ValueError("option scores must be between 0 and 100")
        if self.input_type != "single_choice" and self.options:
            raise ValueError("only single_choice questions may define options")
        if self.input_type != "single_choice" and self.option_scores:
            raise ValueError("only single_choice questions may define option_scores")
        if self.input_type == "number":
            if self.minimum is not None and self.maximum is not None:
                if self.minimum >= self.maximum:
                    raise ValueError("number question minimum must be below maximum")
            if self.step is not None and self.step <= 0:
                raise ValueError("number question step must be positive")

        # From here down the field is `default`, which is a *preselection* — a
        # convenience, not part of the question's meaning. Nothing computes with
        # it: the runtime scores whatever the visitor actually answers.
        #
        # So an unusable default is dropped or clamped rather than raised.
        # Rejecting it failed the entire architect stage roughly 50 seconds and
        # two model calls into a build, and the visitor saw a bare 500 — for a
        # field whose worst case is that the first option is not pre-ticked.
        # Observed live: gemini-3.6-flash returned a choice default that was not
        # among the options on three questions of one tool.
        #
        # The structural rules above still raise. Those describe what the
        # question *is*, and getting them wrong produces a broken instrument.
        self.default = self._usable_default()
        return self

    def _usable_default(self) -> float | str | bool | None:
        """The supplied default if it can be honoured, otherwise nothing."""
        if self.default is None:
            return None

        if self.input_type == "number":
            if isinstance(self.default, bool) or not isinstance(self.default, (int, float)):
                return None
            value = float(self.default)
            if self.minimum is not None:
                value = max(value, self.minimum)
            if self.maximum is not None:
                value = min(value, self.maximum)
            return value

        if self.input_type == "single_choice":
            return self.default if self.default in self.options else None

        return self.default if isinstance(self.default, bool) else None


class DecisionResult(BaseModel):
    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=10, max_length=500)
    recommendation: str = Field(min_length=5, max_length=500)
    minimum_score: float | None = None
    maximum_score: float | None = None


class CalculationTerm(BaseModel):
    question_id: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    multiplier: float = Field(ge=-1_000_000, le=1_000_000)


class DecisionCalculation(BaseModel):
    """A small declarative calculation language; never evaluated as code."""

    kind: Literal["weighted_score", "linear_estimate"] = "weighted_score"
    output_label: str = Field(default="Your result", min_length=2, max_length=120)
    output_format: Literal["score", "number", "currency", "percent"] = "score"
    currency: str = Field(default="USD", min_length=3, max_length=3)
    decimals: int = Field(default=0, ge=0, le=2)
    constant: float = Field(default=0.0, ge=-1_000_000_000, le=1_000_000_000)
    terms: list[CalculationTerm] = Field(default_factory=list, max_length=12)
    clamp_min: float | None = Field(default=None, ge=-1_000_000_000, le=1_000_000_000)
    clamp_max: float | None = Field(default=None, ge=-1_000_000_000, le=1_000_000_000)

    @model_validator(mode="after")
    def _validate_range(self) -> "DecisionCalculation":
        if self.clamp_min is not None and self.clamp_max is not None:
            if self.clamp_min >= self.clamp_max:
                raise ValueError("calculation clamp_min must be below clamp_max")
        if self.kind == "linear_estimate" and not self.terms:
            raise ValueError("linear estimates require at least one term")
        return self


class DecisionSpec(BaseModel):
    """The product contract shared by preview, codegen, analytics and QA."""

    mechanism: Literal["estimate", "diagnose", "advise"]

    @field_validator("mechanism", mode="before")
    @classmethod
    def _normalize_mechanism(cls, value: Any) -> Any:
        """Map the words a model reaches for onto the three we accept.

        The blueprint type leads the prompt, so for an ``audit_tool`` the model
        answers ``"audit"`` — reasonable, and rejected. This is descriptive
        metadata that nothing branches on, so failing a build that already cost
        two model calls over a synonym is the wrong trade.

        Matched on stems rather than whole words, because the variants are
        morphological: one run answered ``"audit"``, the next ``"recommendation"``.
        An exact table turns into a bug report per inflection.

        Still a fixed list, not fuzzy matching — anything outside it fails, because
        an unrecognised mechanism means the model produced something we do not
        understand, and that should surface rather than be rounded off.
        """
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in {"estimate", "diagnose", "advise"}:
            return normalized

        stems = (
            ("estimat", "estimate"),
            ("calculat", "estimate"),
            ("forecast", "estimate"),
            ("project", "estimate"),
            ("quantif", "estimate"),
            ("audit", "diagnose"),
            ("assess", "diagnose"),
            ("diagnos", "diagnose"),
            ("evaluat", "diagnose"),
            ("scor", "diagnose"),
            ("quiz", "diagnose"),
            ("readiness", "diagnose"),
            ("advis", "advise"),
            ("recommend", "advise"),
            ("compar", "advise"),
            ("checklist", "advise"),
            ("guid", "advise"),
            ("plan", "advise"),
        )
        for stem, canonical in stems:
            if normalized.startswith(stem):
                return canonical
        return normalized

    buyer_question: str = Field(min_length=8, max_length=220)
    value_before_gate: str = Field(min_length=8, max_length=260)
    qualification_goal: str = Field(min_length=5, max_length=260)
    recommended_placement: str = Field(default="Primary service page", max_length=180)
    questions: list[DecisionQuestion] = Field(min_length=2, max_length=7)
    results: list[DecisionResult] = Field(min_length=1, max_length=5)
    calculation: DecisionCalculation = Field(default_factory=DecisionCalculation)
    qualification_threshold: int = Field(default=60, ge=0, le=100)
    lead_gate: Literal["after_value"] = "after_value"
    primary_cta: str = Field(min_length=2, max_length=80)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("questions")
    @classmethod
    def _unique_question_ids(cls, questions: list[DecisionQuestion]) -> list[DecisionQuestion]:
        ids = [question.id for question in questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        return questions

    @model_validator(mode="after")
    def _validate_calculation_refs(self) -> "DecisionSpec":
        question_ids = {question.id for question in self.questions}
        unknown = {
            term.question_id
            for term in self.calculation.terms
            if term.question_id not in question_ids
        }
        if unknown:
            raise ValueError(f"calculation references unknown questions: {sorted(unknown)}")
        keys = [result.key for result in self.results]
        if len(keys) != len(set(keys)):
            raise ValueError("result keys must be unique")
        for result in self.results:
            if (
                result.minimum_score is not None
                and result.maximum_score is not None
                and result.minimum_score > result.maximum_score
            ):
                raise ValueError("result minimum_score cannot exceed maximum_score")
        ordered = sorted(
            self.results,
            key=lambda result: (
                float("-inf") if result.minimum_score is None else result.minimum_score
            ),
        )
        for previous, current in pairwise(ordered):
            if (
                previous.maximum_score is not None
                and current.minimum_score is not None
                and previous.maximum_score > current.minimum_score
            ):
                raise ValueError("result score ranges must not overlap")
        if self.calculation.kind == "weighted_score" and not any(
            question.weight > 0 for question in self.questions
        ):
            raise ValueError("weighted scores require at least one positive question weight")
        return self


class GroundedClaim(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    evidence_ref: str | None = Field(default=None, max_length=80)
    requires_approval: bool = False


class VisualLanguage(BaseModel):
    layout: str = "centered-single-column"
    spacing: str = "comfortable"
    card_style: str = "solid-white"
    border_radius: str = "rounded"
    shadow_depth: str = "subtle"
    button_style: str = "filled-solid"
    decorative_elements: str = "none"
    icon_style: str = "outlined"
    visual_energy: str = "balanced"


class ArchitectOutput(BaseModel):
    widget_type: WidgetType
    brand: BrandExtraction
    visual_language: VisualLanguage = VisualLanguage()
    logic: MathLogic
    copywriting: dict[str, Any]
    decision: DecisionSpec | None = None
    claims: list[GroundedClaim] = Field(default_factory=list, max_length=30)


class DesignTokens(BaseModel):
    css_variables: dict[str, str]
    component_theme: dict[str, str]


class DeploymentResult(BaseModel):
    url: str
    widget_id: str


class ProjectFile(BaseModel):
    path: str
    content: str


class WidgetCode(BaseModel):
    files: list[ProjectFile]
    design_tokens: DesignTokens
    entry_point: str = "src/App.jsx"


class PipelineStatus(BaseModel):
    state: str
    progress: float
    error: str | None = None
    blueprints: list[Blueprint] | None = None
    deployment_url: str | None = None
    iframe_html: str | None = None
