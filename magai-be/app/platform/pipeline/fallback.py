"""Grounded first-look continuity when the generation provider is unavailable.

The free preview is the product's front door. A provider quota or transient
outage must not discard a visitor's website read or leave them with a dead end.
These fallbacks use only deterministic site evidence and the owner's brief.
They make no invented business claims and never replace paid code generation.
"""

from __future__ import annotations

import re

from app.platform.pipeline.catalog import blueprint_for
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    BlueprintList,
    BrandExtraction,
    CreationBrief,
    DecisionCalculation,
    DecisionQuestion,
    DecisionResult,
    DecisionSpec,
    MathLogic,
    SiteEvidence,
    VisualLanguage,
    WidgetType,
)

_GOAL_PRIORITY: dict[str, tuple[WidgetType, ...]] = {
    "capture_qualified_leads": (
        WidgetType.READINESS_QUIZ,
        WidgetType.AUDIT_TOOL,
        WidgetType.ROI_CALCULATOR,
    ),
    "book_more_calls": (
        WidgetType.AUDIT_TOOL,
        WidgetType.READINESS_QUIZ,
        WidgetType.COMPETITIVE_COMPARISON,
    ),
    "educate_buyers": (
        WidgetType.COMPETITIVE_COMPARISON,
        WidgetType.INTERACTIVE_CHECKLIST,
        WidgetType.READINESS_QUIZ,
    ),
    "estimate_value": (
        WidgetType.ROI_CALCULATOR,
        WidgetType.AUDIT_TOOL,
        WidgetType.READINESS_QUIZ,
    ),
    "recommend_next_step": (
        WidgetType.READINESS_QUIZ,
        WidgetType.INTERACTIVE_CHECKLIST,
        WidgetType.AUDIT_TOOL,
    ),
}

_TITLES: dict[WidgetType, str] = {
    WidgetType.ROI_CALCULATOR: "Value Opportunity Calculator",
    WidgetType.READINESS_QUIZ: "Readiness Check",
    WidgetType.COMPETITIVE_COMPARISON: "Best-Fit Comparison",
    WidgetType.AUDIT_TOOL: "Opportunity Audit",
    WidgetType.INTERACTIVE_CHECKLIST: "Personalised Action Plan",
    WidgetType.CUSTOM: "Your Conversion Tool",
}

_DESCRIPTIONS: dict[WidgetType, str] = {
    WidgetType.ROI_CALCULATOR: (
        "Visitors add their own inputs and receive a clear estimate of where the opportunity lies."
    ),
    WidgetType.READINESS_QUIZ: (
        "Visitors answer a short set of questions and receive a practical readiness result."
    ),
    WidgetType.COMPETITIVE_COMPARISON: (
        "Visitors compare their priorities and receive a best-fit direction "
        "without unsupported claims."
    ),
    WidgetType.AUDIT_TOOL: (
        "Visitors assess their current situation and receive the most useful area to improve first."
    ),
    WidgetType.INTERACTIVE_CHECKLIST: (
        "Visitors work through the important steps and leave with a personalised action plan."
    ),
    WidgetType.CUSTOM: "A focused interactive experience shaped around the owner's stated intent.",
}

_GENERIC_PAGE_TITLES = (
    "one moment",
    "just a moment",
    "attention required",
    "checking your browser",
    "please wait",
    "access denied",
    "home",
    "welcome",
)

_BUSINESS_SUFFIXES = (
    "consulting",
    "construction",
    "software",
    "marketing",
    "financial",
    "dentistry",
    "dental",
    "clinic",
    "health",
    "legal",
    "realty",
    "studio",
    "agency",
    "group",
)


def _domain_name(domain: str) -> str:
    stem = domain.removeprefix("www.").split(".", 1)[0]
    stem = re.sub(r"[-_]+", " ", stem).strip()
    compact = stem.replace(" ", "").lower()
    for suffix in _BUSINESS_SUFFIXES:
        if compact.endswith(suffix) and len(compact) > len(suffix) + 2:
            compact = f"{compact[: -len(suffix)]} {suffix}"
            break
    return compact.title() or "Your Business"


def _business_name(evidence: SiteEvidence) -> str:
    candidate = evidence.business_name.strip()
    lowered = candidate.lower()
    if (
        not candidate
        or any(marker in lowered for marker in _GENERIC_PAGE_TITLES)
        or len(candidate) > 80
    ):
        return _domain_name(evidence.domain)
    return candidate


def _ordered_kinds(brief: CreationBrief) -> list[WidgetType]:
    kinds: list[WidgetType] = []
    if brief.preferred_type is not None and (
        brief.preferred_type is not WidgetType.CUSTOM or brief.intent.strip()
    ):
        kinds.append(brief.preferred_type)
    for kind in _GOAL_PRIORITY[brief.goal]:
        if kind not in kinds:
            kinds.append(kind)
    for kind in (
        WidgetType.ROI_CALCULATOR,
        WidgetType.READINESS_QUIZ,
        WidgetType.AUDIT_TOOL,
        WidgetType.COMPETITIVE_COMPARISON,
        WidgetType.INTERACTIVE_CHECKLIST,
    ):
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def grounded_blueprints(
    evidence: SiteEvidence,
    brief: CreationBrief | None = None,
) -> BlueprintList:
    """Create three distinct directions using only the crawl and owner brief."""
    chosen_brief = brief or CreationBrief()
    business = _business_name(evidence)
    reference_ids = [reference.id for reference in evidence.references[:4]]
    directions: list[Blueprint] = []

    for kind in _ordered_kinds(chosen_brief)[:3]:
        stated_intent = chosen_brief.intent if kind is chosen_brief.preferred_type else ""
        base = blueprint_for(kind, business, intent=stated_intent)
        directions.append(
            base.model_copy(
                update={
                    "title": (
                        chosen_brief.intent.strip()[:120]
                        if kind is WidgetType.CUSTOM and chosen_brief.intent.strip()
                        else f"{business} {_TITLES[kind]}"
                    ),
                    "description": stated_intent or _DESCRIPTIONS[kind],
                    "rationale": (
                        f"Uses {business}'s own website evidence to give visitors a useful "
                        "answer before asking for contact details."
                    ),
                    "evidence_refs": reference_ids,
                }
            )
        )

    return BlueprintList(blueprints=directions)


def _questions(count: int) -> list[DecisionQuestion]:
    pool = [
        DecisionQuestion(
            id="current_stage",
            label="Where are you in the decision today?",
            help_text="Choose the closest description.",
            input_type="single_choice",
            options=["Just exploring", "Comparing options", "Ready to act"],
            option_scores=[25, 65, 95],
            default="Just exploring",
        ),
        DecisionQuestion(
            id="primary_priority",
            label="What matters most in the outcome?",
            input_type="single_choice",
            options=["Save time", "Improve quality", "Make a confident decision"],
            option_scores=[55, 75, 90],
            default="Make a confident decision",
        ),
        DecisionQuestion(
            id="timeline",
            label="When do you want to make progress?",
            input_type="single_choice",
            options=["This quarter", "This month", "As soon as possible"],
            option_scores=[45, 75, 100],
            default="This month",
        ),
        DecisionQuestion(
            id="clear_baseline",
            label="Do you have a clear picture of your current position?",
            input_type="boolean",
            default=False,
            true_score=90,
        ),
        DecisionQuestion(
            id="team_alignment",
            label="Are the people involved aligned on the goal?",
            input_type="boolean",
            default=False,
            true_score=95,
        ),
        DecisionQuestion(
            id="success_measure",
            label="Can you measure whether the change worked?",
            input_type="boolean",
            default=False,
            true_score=85,
        ),
        DecisionQuestion(
            id="next_step",
            label="Are you ready to commit to one practical next step?",
            input_type="boolean",
            default=True,
            true_score=100,
        ),
    ]
    return pool[:count]


def grounded_architect(
    blueprint: Blueprint,
    evidence: SiteEvidence,
    brief: CreationBrief | None = None,
) -> ArchitectOutput:
    """Turn a grounded direction into a safe, usable interactive preview."""
    chosen_brief = brief or CreationBrief()
    colors = evidence.brand.colors
    fonts = evidence.brand.fonts
    references = [reference.id for reference in evidence.references[:4]]
    business = _business_name(evidence)
    tone = "clear and direct" if chosen_brief.tone == "match_site" else chosen_brief.tone
    mechanism = (
        "estimate"
        if blueprint.type is WidgetType.ROI_CALCULATOR
        else "diagnose"
        if blueprint.type in {WidgetType.AUDIT_TOOL, WidgetType.READINESS_QUIZ}
        else "advise"
    )
    buyer_question = (
        chosen_brief.visitor_question.strip()
        or "What is the strongest next step for your situation?"
    )

    decision = DecisionSpec(
        mechanism=mechanism,
        buyer_question=buyer_question,
        value_before_gate="A useful result and practical next step before contact details.",
        qualification_goal=(
            chosen_brief.audience.strip()
            or "Understand the visitor's priorities, urgency, and readiness."
        ),
        recommended_placement="Primary service or decision page",
        questions=_questions(chosen_brief.question_count),
        results=[
            DecisionResult(
                key="starting_point",
                title="Start with clarity",
                summary="You have an opportunity, but the decision needs a clearer baseline first.",
                recommendation="Define the outcome and agree on one measurable priority.",
                minimum_score=0,
                maximum_score=39,
            ),
            DecisionResult(
                key="clear_path",
                title="Your path is taking shape",
                summary=(
                    "The important pieces are present and one focused step can create momentum."
                ),
                recommendation=(
                    "Choose the highest-priority gap and turn it into a short action plan."
                ),
                minimum_score=40,
                maximum_score=69,
            ),
            DecisionResult(
                key="ready_to_move",
                title="You are ready to move",
                summary=(
                    "Your priorities, timing, and decision readiness point to a clear next move."
                ),
                recommendation="Confirm ownership and begin with the first measurable action.",
                minimum_score=70,
                maximum_score=100,
            ),
        ],
        calculation=DecisionCalculation(
            kind="weighted_score",
            output_label="Readiness score",
            output_format="score",
            clamp_min=0,
            clamp_max=100,
        ),
        qualification_threshold=65,
        primary_cta="Discuss my result",
        evidence_refs=references,
    )

    return ArchitectOutput(
        widget_type=blueprint.type,
        brand=BrandExtraction(
            primary_color=colors[0] if colors else "#10231f",
            secondary_color=colors[1] if len(colors) > 1 else "#41534d",
            background_color="#f7f5ee",
            accent_color=colors[2] if len(colors) > 2 else "#6f8f3d",
            font_headings=fonts[0] if fonts else "Inter",
            font_body=fonts[1] if len(fonts) > 1 else fonts[0] if fonts else "Inter",
            tone=tone,
            logo_url=evidence.brand.logo_url,
        ),
        visual_language=VisualLanguage(
            layout="centered-single-column",
            spacing="comfortable",
            card_style="editorial",
            border_radius="soft",
            shadow_depth="subtle",
            button_style="filled-solid",
            decorative_elements="minimal",
            icon_style="outlined",
            visual_energy="calm",
        ),
        logic=MathLogic(
            formula="Weighted readiness score from the visitor's own answers.",
            variables=[
                {
                    "name": question.id,
                    "description": question.label,
                    "default": str(question.default),
                }
                for question in decision.questions
            ],
            example_calculation="Answers are normalised and combined into a score from 0 to 100.",
        ),
        copywriting={
            "headline": blueprint.title,
            "subheadline": blueprint.description,
            "cta": "See my result",
            "result_headline": f"Your {business} next step",
        },
        decision=decision,
        claims=[],
    )
