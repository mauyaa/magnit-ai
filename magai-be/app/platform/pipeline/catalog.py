"""The catalogue of tool types a customer can ask for.

The analyzer proposes three blueprints per site, chosen from five possible
types. Until now those three were the only things a customer could build: if
the model happened to suggest three calculators, there was no way to say "make
it a quiz instead" short of re-analyzing and hoping for a different draw.

This module makes all five reachable. Asking for a type the analyzer did not
propose synthesises a blueprint for it, which the Architect then designs against
the real site exactly as it would a proposed one — the blueprint only ever
carried the type and a working title anyway.
"""

from app.platform.pipeline.schemas import Blueprint, WidgetType


class ToolType:
    """Presentation metadata for one widget type."""

    __slots__ = ("best_for", "kind", "label", "visitor_does")

    def __init__(self, kind: WidgetType, label: str, visitor_does: str, best_for: str) -> None:
        self.kind = kind
        self.label = label
        self.visitor_does = visitor_does
        self.best_for = best_for


CATALOG: tuple[ToolType, ...] = (
    ToolType(
        WidgetType.ROI_CALCULATOR,
        "ROI calculator",
        "Moves a few sliders describing their own situation, and gets a number back.",
        "Anyone whose price is easier to justify than to explain.",
    ),
    ToolType(
        WidgetType.READINESS_QUIZ,
        "Readiness quiz",
        "Answers a handful of questions and gets a score with a recommendation.",
        "Long sales cycles, where the first job is showing someone they have a problem.",
    ),
    ToolType(
        WidgetType.AUDIT_TOOL,
        "Audit tool",
        "Enters their own details and gets a graded breakdown back.",
        "Services where you'd normally do this assessment free on a call.",
    ),
    ToolType(
        WidgetType.COMPETITIVE_COMPARISON,
        "Comparison tool",
        "Picks what they use today and sees an honest side-by-side.",
        "Crowded categories where buyers are already comparing you anyway.",
    ),
    ToolType(
        WidgetType.INTERACTIVE_CHECKLIST,
        "Interactive checklist",
        "Ticks off what they've handled and gets a personalised list of what's left.",
        "Anything with a process — moving, compliance, onboarding, launches.",
    ),
)

BY_KIND: dict[WidgetType, ToolType] = {t.kind: t for t in CATALOG}


def blueprint_for(
    kind: WidgetType,
    business_hint: str | None = None,
    intent: str | None = None,
) -> Blueprint:
    """A blueprint for a type the analyzer did not propose.

    Deliberately plain: the Architect re-reads the live site and writes the real
    title, copy, and logic. Inventing a specific-sounding title here would only
    give the customer a promise the next stage has no obligation to keep.

    ``kind`` may be CUSTOM, which is not in the catalogue — it is what the
    analyzer returns when a customer describes something none of the five named
    shapes fit. In that case the customer's own words are the description,
    because there is no catalogue entry to fall back on and their sentence is a
    better brief than anything we could substitute for it.
    """
    subject = business_hint.strip() if business_hint and business_hint.strip() else "this business"
    stated = (intent or "").strip()

    if kind is WidgetType.CUSTOM:
        if not stated:
            raise ValueError("a custom tool needs the customer's description of it")
        return Blueprint(
            type=kind,
            title="Your tool",
            description=stated,
            rationale=f"Described directly by the owner of {subject}.",
        )

    tool = BY_KIND[kind]
    return Blueprint(
        type=kind,
        title=tool.label,
        # A stated intent is more specific than the catalogue's generic line, so
        # it wins when both are present.
        description=stated or tool.visitor_does,
        rationale=f"Requested directly by the owner of {subject}.",
    )
