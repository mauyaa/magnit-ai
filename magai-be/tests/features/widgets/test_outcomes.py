"""The owner-editable result screen, and the overlay that delivers it live."""

import pytest
from pydantic import ValidationError

from app.features.widgets.models import Widget
from app.features.widgets.outcomes import (
    OutcomeConfig,
    ScoreBand,
    derive_outcome_config,
    effective_outcome_config,
)
from app.platform.pipeline.schemas import (
    DecisionCalculation,
    DecisionQuestion,
    DecisionResult,
    DecisionSpec,
)


def _decision(**overrides) -> DecisionSpec:
    defaults = dict(
        mechanism="diagnose",
        buyer_question="How ready are you to scale?",
        value_before_gate="A score and what to do about it",
        qualification_goal="Find teams ready to buy",
        questions=[
            DecisionQuestion(
                id="team_size",
                label="How big is your team?",
                input_type="number",
                minimum=1,
                maximum=500,
                weight=1.0,
            ),
            DecisionQuestion(
                id="has_process",
                label="Do you have a documented process?",
                input_type="boolean",
                weight=2.0,
            ),
        ],
        results=[
            DecisionResult(
                key="high",
                title="High fit",
                summary="You have the right foundations for growth.",
                recommendation="Book a strategy call.",
                minimum_score=80,
                maximum_score=100,
            ),
            DecisionResult(
                key="medium",
                title="Moderate fit",
                summary="Some groundwork is still needed here.",
                recommendation="Read the scaling guide.",
                minimum_score=50,
                maximum_score=79,
            ),
            DecisionResult(
                key="low",
                title="Low fit",
                summary="Start with the fundamentals first.",
                recommendation="Take the free audit.",
                minimum_score=0,
                maximum_score=49,
            ),
        ],
        calculation=DecisionCalculation(kind="weighted_score"),
        primary_cta="Book a call",
    )
    defaults.update(overrides)
    return DecisionSpec(**defaults)


class TestDerivation:
    def test_derives_a_band_per_generated_result(self):
        config = derive_outcome_config(_decision())
        assert [band.label for band in config.bands] == ["High fit", "Moderate fit", "Low fit"]
        assert config.bands[0].importance == "high"

    def test_carries_the_recommendation_across_as_advice(self):
        config = derive_outcome_config(_decision())
        texts = {block.text for block in config.advice}
        assert "Book a strategy call." in texts
        assert all(block.band_key for block in config.advice)

    def test_bands_cover_every_score_without_gaps(self):
        config = derive_outcome_config(_decision())
        for score in range(0, 101):
            assert config.band_for(score) is not None

    def test_repairs_a_generated_range_that_leaves_scores_homeless(self):
        # The model is only loosely constrained and can emit 0-40 and 60-100,
        # leaving the fifties with no result to show.
        decision = _decision(
            results=[
                DecisionResult(
                    key="top",
                    title="Top",
                    summary="The upper band here.",
                    recommendation="Go ahead now.",
                    minimum_score=60,
                    maximum_score=100,
                ),
                DecisionResult(
                    key="bottom",
                    title="Bottom",
                    summary="The lower band here.",
                    recommendation="Wait a while.",
                    minimum_score=0,
                    maximum_score=40,
                ),
            ]
        )
        config = derive_outcome_config(decision)
        assert config.band_for(50) is not None
        assert config.bands[0].maximum_score == 100

    def test_a_widget_with_no_decision_still_gets_a_usable_screen(self):
        config = derive_outcome_config(None, {"cta": "Talk to us"})
        assert len(config.bands) == 1
        assert config.cta.label == "Talk to us"


class TestValidation:
    def _band(self, key, low, high):
        return ScoreBand(key=key, label=key.title(), minimum_score=low, maximum_score=high)

    def test_overlapping_bands_are_rejected(self):
        with pytest.raises(ValidationError, match="overlap"):
            OutcomeConfig(bands=[self._band("a", 0, 60), self._band("b", 50, 100)])

    def test_a_gap_between_bands_is_rejected(self):
        # A visitor scoring into the gap would see a result screen with no result.
        with pytest.raises(ValidationError, match="fall outside every band"):
            OutcomeConfig(bands=[self._band("a", 0, 40), self._band("b", 60, 100)])

    def test_duplicate_band_keys_are_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            OutcomeConfig(bands=[self._band("a", 0, 50), self._band("a", 51, 100)])

    def test_advice_cannot_point_at_a_band_that_does_not_exist(self):
        with pytest.raises(ValidationError, match="unknown band"):
            OutcomeConfig(
                bands=[self._band("a", 0, 100)],
                advice=[{"text": "Do this", "band_key": "ghost"}],
            )

    def test_a_band_colour_must_be_a_hex_value(self):
        # It is interpolated into the deployed widget's stylesheet.
        with pytest.raises(ValidationError):
            ScoreBand(
                key="a",
                label="A",
                minimum_score=0,
                maximum_score=100,
                accent_color="red; } body { display:none",
            )

    def test_band_for_clamps_a_score_outside_the_range(self):
        config = OutcomeConfig(bands=[self._band("a", 0, 100)])
        assert config.band_for(140).key == "a"
        assert config.band_for(-20).key == "a"


class TestEffectiveConfig:
    def test_prefers_the_owners_saved_version(self):
        saved = OutcomeConfig(
            bands=[ScoreBand(key="mine", label="Mine", minimum_score=0, maximum_score=100)]
        ).model_dump(mode="json")
        config = effective_outcome_config(saved, _decision())
        assert config.bands[0].label == "Mine"

    def test_falls_back_when_the_saved_version_has_gone_stale(self):
        # A regeneration can move the score range under a saved configuration.
        # The visitor-facing screen still has to render something correct.
        config = effective_outcome_config({"bands": []}, _decision())
        assert len(config.bands) == 3


async def _built_widget(db, user) -> Widget:
    widget = Widget(
        user_id=user.id,
        target_url="https://example.com",
        widget_type="readiness_quiz",
        title="Readiness",
        status="active",
        deployment_url="https://magai-widget-abc.vercel.app",
        widget_logic={"decision": _decision().model_dump(mode="json")},
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestOutcomeRoutes:
    async def test_get_returns_the_derived_config_when_untouched(self, db, user, as_user):
        widget = await _built_widget(db, user)
        response = await (as_user(user)).get(f"/api/widgets/{widget.id}/outcomes")
        assert response.status_code == 200
        assert response.json()["customised"] is False
        assert len(response.json()["config"]["bands"]) == 3

    async def test_put_saves_and_marks_it_customised(self, db, user, as_user):
        widget = await _built_widget(db, user)
        config = OutcomeConfig(
            bands=[
                ScoreBand(
                    key="ready",
                    label="Ready to scale",
                    minimum_score=0,
                    maximum_score=100,
                    description="You are set.",
                )
            ]
        ).model_dump(mode="json")

        response = await (as_user(user)).put(
            f"/api/widgets/{widget.id}/outcomes", json={"config": config}
        )
        assert response.status_code == 200
        assert response.json()["customised"] is True
        assert response.json()["config"]["bands"][0]["label"] == "Ready to scale"

    async def test_put_rejects_an_invalid_band_layout(self, db, user, as_user):
        widget = await _built_widget(db, user)
        response = await (as_user(user)).put(
            f"/api/widgets/{widget.id}/outcomes",
            json={
                "config": {
                    "bands": [
                        {"key": "a", "label": "A", "minimum_score": 0, "maximum_score": 60},
                        {"key": "b", "label": "B", "minimum_score": 50, "maximum_score": 100},
                    ]
                }
            },
        )
        assert response.status_code == 422

    async def test_delete_restores_the_generated_version(self, db, user, as_user):
        widget = await _built_widget(db, user)
        widget.outcome_config = OutcomeConfig(
            bands=[ScoreBand(key="mine", label="Mine", minimum_score=0, maximum_score=100)]
        ).model_dump(mode="json")
        await db.commit()

        response = await (as_user(user)).delete(f"/api/widgets/{widget.id}/outcomes")
        assert response.status_code == 200
        assert response.json()["customised"] is False
        assert len(response.json()["config"]["bands"]) == 3

    async def test_another_workspace_cannot_read_or_write(self, db, user, other_user, as_user):
        widget = await _built_widget(db, user)
        client = as_user(other_user)
        assert (await client.get(f"/api/widgets/{widget.id}/outcomes")).status_code == 404
        assert (
            await client.put(f"/api/widgets/{widget.id}/outcomes", json={"config": {"bands": []}})
        ).status_code in (404, 422)


class TestRuntimeConfig:
    async def test_serves_the_live_overlay_without_authentication(self, db, user, client):
        # The caller is an anonymous visitor on someone else's website.
        widget = await _built_widget(db, user)
        response = await client.get(f"/api/widgets/{widget.id}/runtime-config")
        assert response.status_code == 200

        body = response.json()
        assert body["widget_id"] == str(widget.id)
        assert body["decision"]["buyer_question"] == "How ready are you to scale?"
        assert len(body["outcomes"]["bands"]) == 3
        assert body["accepting_leads"] is True
        assert "max-age" in response.headers.get("cache-control", "")

    async def test_deployed_origin_can_fetch_live_owner_edits(self, db, user, client):
        widget = await _built_widget(db, user)
        response = await client.options(
            f"/api/widgets/{widget.id}/runtime-config",
            headers={
                "Origin": "https://customer-widget.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 204
        assert response.headers["access-control-allow-origin"] == "*"
        assert "GET" in response.headers["access-control-allow-methods"]

    async def test_reflects_an_owner_edit_without_a_rebuild(self, db, user, as_user, client):
        widget = await _built_widget(db, user)
        await (as_user(user)).put(
            f"/api/widgets/{widget.id}/outcomes",
            json={
                "config": OutcomeConfig(
                    bands=[
                        ScoreBand(
                            key="renamed",
                            label="Renamed live",
                            minimum_score=0,
                            maximum_score=100,
                        )
                    ]
                ).model_dump(mode="json")
            },
        )

        body = (await client.get(f"/api/widgets/{widget.id}/runtime-config")).json()
        assert body["outcomes"]["bands"][0]["label"] == "Renamed live"

    async def test_version_changes_when_the_configuration_does(self, db, user, as_user, client):
        widget = await _built_widget(db, user)
        before = (await client.get(f"/api/widgets/{widget.id}/runtime-config")).json()["version"]

        await (as_user(user)).put(
            f"/api/widgets/{widget.id}/outcomes",
            json={
                "config": OutcomeConfig(
                    bands=[ScoreBand(key="x", label="X", minimum_score=0, maximum_score=100)]
                ).model_dump(mode="json")
            },
        )
        after = (await client.get(f"/api/widgets/{widget.id}/runtime-config")).json()["version"]
        assert before != after

    async def test_stops_accepting_leads_at_the_cap(self, db, user, client):
        widget = await _built_widget(db, user)
        widget.leads_count = widget.lead_cap
        await db.commit()

        body = (await client.get(f"/api/widgets/{widget.id}/runtime-config")).json()
        assert body["accepting_leads"] is False

    async def test_unbuilt_and_unknown_widgets_are_404(self, db, user, client):
        widget = await _built_widget(db, user)
        widget.status = "analyzed"
        await db.commit()

        assert (await client.get(f"/api/widgets/{widget.id}/runtime-config")).status_code == 404
        assert (await client.get("/api/widgets/not-a-uuid/runtime-config")).status_code == 404


class TestDecisionRoutes:
    async def test_get_returns_the_question_flow(self, db, user, as_user):
        widget = await _built_widget(db, user)
        response = await (as_user(user)).get(f"/api/widgets/{widget.id}/decision")
        assert response.status_code == 200
        assert len(response.json()["decision"]["questions"]) == 2
        assert response.json()["editable"] is True

    async def test_put_replaces_the_flow(self, db, user, as_user):
        widget = await _built_widget(db, user)
        decision = _decision().model_dump(mode="json")
        decision["questions"][0]["label"] = "How many people are on your team?"

        response = await (as_user(user)).put(
            f"/api/widgets/{widget.id}/decision", json={"decision": decision}
        )
        assert response.status_code == 200
        await db.refresh(widget)
        assert (
            widget.widget_logic["decision"]["questions"][0]["label"]
            == "How many people are on your team?"
        )

    async def test_put_preserves_the_rest_of_widget_logic(self, db, user, as_user):
        widget = await _built_widget(db, user)
        widget.widget_logic = {
            **widget.widget_logic,
            "claims": [{"text": "Trusted by 1,200 teams", "requires_approval": False}],
        }
        await db.commit()

        await (as_user(user)).put(
            f"/api/widgets/{widget.id}/decision",
            json={"decision": _decision().model_dump(mode="json")},
        )
        await db.refresh(widget)
        assert widget.widget_logic["claims"][0]["text"] == "Trusted by 1,200 teams"

    async def test_put_rejects_a_calculation_pointing_at_a_missing_question(
        self, db, user, as_user
    ):
        widget = await _built_widget(db, user)
        decision = _decision(
            calculation=DecisionCalculation(
                kind="linear_estimate", terms=[{"question_id": "team_size", "multiplier": 2}]
            )
        ).model_dump(mode="json")
        decision["calculation"]["terms"][0]["question_id"] = "not_a_question"

        response = await (as_user(user)).put(
            f"/api/widgets/{widget.id}/decision", json={"decision": decision}
        )
        assert response.status_code == 422

    async def test_editing_is_refused_mid_build(self, db, user, as_user):
        # The build reads this column; an edit landing mid-run produces a
        # deployed tool that disagrees with what the owner is looking at.
        widget = await _built_widget(db, user)
        widget.status = "building"
        await db.commit()

        response = await (as_user(user)).put(
            f"/api/widgets/{widget.id}/decision",
            json={"decision": _decision().model_dump(mode="json")},
        )
        assert response.status_code == 409


class TestReadiness:
    async def test_reports_a_checklist_answered_from_real_state(self, db, user, as_user):
        widget = await _built_widget(db, user)
        response = await (as_user(user)).get(f"/api/widgets/{widget.id}/readiness")
        assert response.status_code == 200

        body = response.json()
        checks = {check["id"]: check for check in body["checks"]}
        assert checks["built"]["done"] is True
        assert checks["questions"]["done"] is True
        # Nothing has been embedded yet, and that check is deliberately advisory.
        assert checks["embedded"]["done"] is False
        assert checks["embedded"]["blocking"] is False

    async def test_a_separately_paid_tool_explains_why_it_is_covered(self, db, user, as_user):
        # "1 of 0 live tools in use" is arithmetic, not an explanation. A tool
        # bought outright on the free plan has to say so.
        widget = await _built_widget(db, user)
        widget.entitlement_status = "paid"
        await db.commit()

        body = (await (as_user(user)).get(f"/api/widgets/{widget.id}/readiness")).json()
        entitled = next(check for check in body["checks"] if check["id"] == "entitled")
        assert entitled["done"] is True
        assert "on its own" in entitled["detail"]
        assert "of 0" not in entitled["detail"]

    async def test_the_entitlement_line_never_prints_a_nonsense_ratio(self, db, user, as_user):
        widget = await _built_widget(db, user)
        body = (await (as_user(user)).get(f"/api/widgets/{widget.id}/readiness")).json()
        entitled = next(check for check in body["checks"] if check["id"] == "entitled")
        assert "of 0" not in entitled["detail"]

    async def test_an_unbuilt_widget_is_not_ready(self, db, user, as_user):
        widget = await _built_widget(db, user)
        widget.status = "analyzed"
        widget.deployment_url = None
        await db.commit()

        body = (await (as_user(user)).get(f"/api/widgets/{widget.id}/readiness")).json()
        assert body["ready"] is False
