"""Where the decision schema bends, and where it must not.

Both normalisers here exist because of failures observed against a live
gemini-3.6-flash, not because of a hypothetical. The architect stage is the
second AI call in a build, so rejecting its output throws away the analyzer's
work too — which makes "fail on a synonym" an expensive way to be strict about
something nothing reads.

The line drawn: shapes that carry no meaning are normalised; anything genuinely
unrecognised still fails, so a real misunderstanding surfaces instead of being
rounded off into a plausible-looking build.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.pipeline.schemas import DecisionQuestion, DecisionSpec


def question(**overrides):
    payload = {
        "id": "monthly_volume",
        "label": "Monthly volume",
        "input_type": "number",
        "weight": 1,
    }
    payload.update(overrides)
    return payload


def spec(**overrides):
    payload = {
        "mechanism": "estimate",
        "buyer_question": "What is a clearer booking path worth?",
        "value_before_gate": "A monthly estimate with its assumptions",
        "qualification_goal": "Practice size and volume",
        "questions": [
            question(),
            question(id="tracks_online", label="Do you track bookings", input_type="boolean"),
        ],
        "results": [
            {
                "key": "priority",
                "title": "Your clearest opportunity",
                "summary": "A concise interpretation",
                "recommendation": "A concrete next step",
            }
        ],
        "primary_cta": "Discuss this result",
    }
    payload.update(overrides)
    return payload


class TestTrueScore:
    def test_an_explicit_null_falls_back_to_the_default(self):
        """Only boolean questions read it, so null on a number question is honest."""
        parsed = DecisionQuestion(**question(true_score=None))

        assert parsed.true_score == 100.0

    def test_an_omitted_value_still_defaults(self):
        assert DecisionQuestion(**question()).true_score == 100.0

    def test_a_supplied_value_is_kept(self):
        assert DecisionQuestion(**question(input_type="boolean", true_score=60)).true_score == 60

    @pytest.mark.parametrize("bad", [-1, 101])
    def test_an_out_of_range_score_is_still_rejected(self, bad):
        """Tolerating null must not turn into tolerating nonsense."""
        with pytest.raises(ValidationError):
            DecisionQuestion(**question(input_type="boolean", true_score=bad))


class TestMechanism:
    @pytest.mark.parametrize("value", ["estimate", "diagnose", "advise"])
    def test_the_canonical_values_pass_through(self, value):
        assert DecisionSpec(**spec(mechanism=value)).mechanism == value

    @pytest.mark.parametrize(
        ("supplied", "expected"),
        [
            # Both observed from a live model on consecutive runs.
            ("audit", "diagnose"),
            ("recommendation", "advise"),
            # Their inflections, which is why this matches on stems.
            ("recommend", "advise"),
            ("recommends", "advise"),
            ("assessment", "diagnose"),
            ("assess", "diagnose"),
            ("evaluation", "diagnose"),
            ("calculation", "estimate"),
            ("calculator", "estimate"),
            ("forecasting", "estimate"),
            ("comparison", "advise"),
            ("checklist", "advise"),
            ("guidance", "advise"),
        ],
    )
    def test_synonyms_map_onto_the_three_we_accept(self, supplied, expected):
        assert DecisionSpec(**spec(mechanism=supplied)).mechanism == expected

    @pytest.mark.parametrize("value", ["Audit", "  AUDIT  ", "Readiness Quiz", "audit-tool"])
    def test_case_spacing_and_punctuation_do_not_matter(self, value):
        assert DecisionSpec(**spec(mechanism=value)).mechanism == "diagnose"

    @pytest.mark.parametrize("value", ["teleport", "", "vibes"])
    def test_something_genuinely_unrecognised_still_fails(self, value):
        """A word we cannot place means the model misunderstood; that should surface."""
        with pytest.raises(ValidationError):
            DecisionSpec(**spec(mechanism=value))

    def test_a_non_string_is_left_for_pydantic_to_reject(self):
        with pytest.raises(ValidationError):
            DecisionSpec(**spec(mechanism=42))
