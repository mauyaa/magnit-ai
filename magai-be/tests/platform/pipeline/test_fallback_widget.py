"""Provider degradation still produces a branded, measurable visitor tool."""

from app.platform.pipeline.fallback_widget import (
    fallback_design_tokens,
    fallback_widget_code,
)
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    BrandExtraction,
    MathLogic,
    WidgetType,
)
from app.platform.pipeline.validation import (
    missing_milestones,
    reads_live_config,
    respects_reduced_motion,
    uses_decision_runtime,
    uses_lead_capture,
    validate_generated_files,
)


def _architect() -> ArchitectOutput:
    return ArchitectOutput(
        widget_type=WidgetType.INTERACTIVE_CHECKLIST,
        brand=BrandExtraction(
            primary_color="#334488",
            secondary_color="#555555",
            background_color="#eeeeee",
            accent_color="#334488",
            font_headings="Inter",
            font_body="Inter",
            tone="calm-professional",
        ),
        logic=MathLogic(formula="x", variables=[], example_calculation="x"),
        copywriting={"headline": "Check your fit"},
    )


def test_confirmed_brand_becomes_the_build_tokens_without_a_model():
    tokens = fallback_design_tokens(_architect())

    assert tokens.css_variables["--color-primary"] == "#334488"
    assert tokens.css_variables["--color-background"] == "#eeeeee"
    assert tokens.css_variables["--font-heading"] == "Inter"


def test_fallback_app_satisfies_the_same_release_contract_as_generated_code():
    code = fallback_widget_code(fallback_design_tokens(_architect()))
    files = [item.model_dump() for item in code.files]

    validate_generated_files(files)
    assert uses_lead_capture(files)
    assert uses_decision_runtime(files)
    assert respects_reduced_motion(files)
    assert reads_live_config(files)
    assert missing_milestones(files) == []


def test_the_fallback_app_does_not_freeze_the_configuration_at_build_time():
    """The failure this file exists to avoid, in the app this file produces.

    It used to bind the questions and the result copy at module scope, from the
    build-time snapshot. An owner could then rewrite a question, be told the
    change was live, and watch the deployed tool keep asking the old one — while
    calculateDecision scored the visitor against the new one. Reading
    MAGNITAI_CONFIG here at all is the shape of that bug.
    """
    source = fallback_widget_code(fallback_design_tokens(_architect())).files[0].content

    assert "MAGNITAI_CONFIG" not in source
    assert "useLiveConfig()" in source
