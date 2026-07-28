"""The customer picks the tool, not the model.

The analyzer proposes three blueprints drawn from five types. Before this, those
three were the only buildable options: if the model returned three calculators,
there was no way to ask for a quiz short of re-analyzing and hoping. These tests
pin the escape hatch — any of the five is reachable by name — and pin the two
places it could silently go wrong: a named type must beat a stale index, and
naming a type the analyzer *did* propose must reuse that proposal rather than
throwing away its site-specific title and rationale.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.features.widgets.models import Widget
from app.platform.pipeline.catalog import BY_KIND, CATALOG, blueprint_for
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    BrandExtraction,
    MathLogic,
    WidgetType,
)

PREVIEW_TARGET = "app.features.widgets.routes.run_architect_stage"


def _architect_output(kind: WidgetType) -> ArchitectOutput:
    return ArchitectOutput(
        widget_type=kind,
        brand=BrandExtraction(
            primary_color="#123456",
            secondary_color="#654321",
            background_color="#ffffff",
            accent_color="#ff0000",
            font_headings="Inter",
            font_body="Inter",
            tone="minimal-clean",
        ),
        logic=MathLogic(formula="a*b", variables=[], example_calculation="1*2=2"),
        copywriting={"headline": "h"},
    )


async def _analyzed_widget(db, owner, blueprint_types: list[str]) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type=blueprint_types[0],
        title="Draft",
        status="analyzed",
        blueprints=[
            {
                "type": kind,
                "title": f"The model's {kind}",
                "description": "d",
                "rationale": "r",
            }
            for kind in blueprint_types
        ],
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestCatalog:
    def test_every_nameable_type_is_offered(self):
        # A type in the enum but missing from the catalogue would be buildable
        # by the pipeline yet invisible and unselectable in the product.
        #
        # CUSTOM is the one deliberate exception, and it is exactly that shape:
        # buildable, never offered. It is not a category an owner picks off a
        # list — it is what the analyzer returns when someone describes a tool
        # none of the named shapes fit, so the catalogue must not advertise it
        # and the picker must never show it.
        assert {t.kind for t in CATALOG} == set(WidgetType) - {WidgetType.CUSTOM}

    def test_custom_is_never_offered_as_a_choice(self):
        assert WidgetType.CUSTOM not in {t.kind for t in CATALOG}

    def test_a_custom_blueprint_is_built_from_the_owners_own_words(self):
        # There is no catalogue entry to fall back on, so the sentence the
        # customer wrote is the description. Substituting our own wording would
        # quietly discard the only specification the tool has.
        stated = "A mortgage affordability estimator for first-time buyers"
        bp = blueprint_for(WidgetType.CUSTOM, "https://example.com", intent=stated)
        assert bp.type is WidgetType.CUSTOM
        assert bp.description == stated

    def test_a_custom_blueprint_refuses_to_be_empty(self):
        # Building a "custom" tool with nothing said about it would produce an
        # app from no specification at all; failing loudly beats guessing.
        with pytest.raises(ValueError):
            blueprint_for(WidgetType.CUSTOM, "https://example.com")

    def test_a_stated_intent_sharpens_a_named_type(self):
        stated = "Focus it on multi-site dental practices"
        bp = blueprint_for(WidgetType.ROI_CALCULATOR, "https://example.com", intent=stated)
        assert bp.type is WidgetType.ROI_CALCULATOR
        assert bp.description == stated

    def test_entries_are_described_for_a_non_technical_owner(self):
        for tool in CATALOG:
            assert tool.label and not tool.label.islower()
            assert tool.visitor_does.endswith(".")
            assert tool.best_for.endswith(".")

    def test_synthesised_blueprint_is_valid_and_typed(self):
        bp = blueprint_for(WidgetType.READINESS_QUIZ, "https://example.com")
        assert bp.type is WidgetType.READINESS_QUIZ
        assert BY_KIND[WidgetType.READINESS_QUIZ].label == bp.title


class TestToolTypesEndpoint:
    async def test_lists_every_nameable_type_and_flags_the_suggested_ones(self, as_user, db, user):
        widget = await _analyzed_widget(db, user, ["roi_calculator", "audit_tool"])

        response = await as_user(user).get(f"/api/widgets/{widget.id}/tool-types")

        assert response.status_code == 200
        types = response.json()["tool_types"]
        kinds = {t["kind"] for t in types}
        assert kinds == {w.value for w in WidgetType} - {WidgetType.CUSTOM.value}
        suggested = {t["kind"] for t in types if t["suggested"]}
        assert suggested == {"roi_calculator", "audit_tool"}

    async def test_is_scoped_to_the_owner(self, as_user, db, user, other_user):
        widget = await _analyzed_widget(db, user, ["roi_calculator"])
        response = await as_user(other_user).get(f"/api/widgets/{widget.id}/tool-types")
        assert response.status_code == 404


class TestPreviewByType:
    async def test_can_request_a_type_the_analyzer_never_proposed(self, as_user, db, user):
        # The whole point: three calculators proposed, customer wants a checklist.
        widget = await _analyzed_widget(db, user, ["roi_calculator"])

        with patch(PREVIEW_TARGET, new_callable=AsyncMock) as run:
            run.return_value = _architect_output(WidgetType.INTERACTIVE_CHECKLIST)
            response = await as_user(user).post(
                f"/api/widgets/{widget.id}/architect-preview",
                json={"widget_type": "interactive_checklist"},
            )

        assert response.status_code == 200
        blueprint = run.await_args.args[0]
        assert blueprint.type is WidgetType.INTERACTIVE_CHECKLIST

    async def test_reuses_the_analyzer_proposal_when_the_type_matches(self, as_user, db, user):
        # The model's own proposal carries a title and rationale grounded in the
        # real business; discarding it for a generic stub would be a regression.
        widget = await _analyzed_widget(db, user, ["roi_calculator", "readiness_quiz"])

        with patch(PREVIEW_TARGET, new_callable=AsyncMock) as run:
            run.return_value = _architect_output(WidgetType.READINESS_QUIZ)
            response = await as_user(user).post(
                f"/api/widgets/{widget.id}/architect-preview",
                json={"widget_type": "readiness_quiz"},
            )

        assert response.status_code == 200
        blueprint = run.await_args.args[0]
        assert blueprint.title == "The model's readiness_quiz"

    async def test_named_type_overrides_a_stale_index(self, as_user, db, user):
        # A client that always posts the index it last used must not be able to
        # silently undo an explicit choice.
        widget = await _analyzed_widget(db, user, ["roi_calculator", "audit_tool"])

        with patch(PREVIEW_TARGET, new_callable=AsyncMock) as run:
            run.return_value = _architect_output(WidgetType.AUDIT_TOOL)
            response = await as_user(user).post(
                f"/api/widgets/{widget.id}/architect-preview",
                json={"blueprint_index": 0, "widget_type": "audit_tool"},
            )

        assert response.status_code == 200
        assert run.await_args.args[0].type is WidgetType.AUDIT_TOOL

    async def test_index_still_works_when_no_type_is_named(self, as_user, db, user):
        widget = await _analyzed_widget(db, user, ["roi_calculator", "audit_tool"])

        with patch(PREVIEW_TARGET, new_callable=AsyncMock) as run:
            run.return_value = _architect_output(WidgetType.AUDIT_TOOL)
            response = await as_user(user).post(
                f"/api/widgets/{widget.id}/architect-preview",
                json={"blueprint_index": 1},
            )

        assert response.status_code == 200
        assert run.await_args.args[0].title == "The model's audit_tool"

    @pytest.mark.parametrize("bad", ["", "not_a_type", "ROI_CALCULATOR"])
    async def test_rejects_an_unknown_type(self, as_user, db, user, bad):
        widget = await _analyzed_widget(db, user, ["roi_calculator"])
        response = await as_user(user).post(
            f"/api/widgets/{widget.id}/architect-preview",
            json={"widget_type": bad},
        )
        assert response.status_code == 422
