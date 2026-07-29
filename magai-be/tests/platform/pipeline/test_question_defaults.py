"""A question's preselection is a convenience, and is treated like one.

`default` is the only field on a question that nothing computes with — the
runtime scores the visitor's actual answer, never the preselection. Rejecting an
unusable one cost an entire architect stage: two model calls, ~50 seconds, and a
bare 500 in front of the visitor, because a dropdown would not have opened
pre-ticked.

Everything that describes what the question *is* still raises. Those produce a
broken instrument, and a broken instrument is worse than no answer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.pipeline.schemas import DecisionQuestion


def number(**overrides):
    payload = {"id": "volume", "label": "Monthly volume", "input_type": "number"}
    payload.update(overrides)
    return DecisionQuestion(**payload)


def choice(**overrides):
    payload = {
        "id": "segment",
        "label": "Which best describes you",
        "input_type": "single_choice",
        "options": ["Startup", "Scale-up", "Enterprise"],
    }
    payload.update(overrides)
    return DecisionQuestion(**payload)


class TestChoiceDefaults:
    def test_a_default_outside_the_options_is_dropped(self):
        """Exactly what a live model returned on three questions of one tool."""
        assert choice(default="Mid-market").default is None

    def test_a_valid_default_is_kept(self):
        assert choice(default="Scale-up").default == "Scale-up"

    def test_no_default_stays_absent(self):
        assert choice().default is None


class TestNumberDefaults:
    def test_a_default_below_the_minimum_is_clamped_up(self):
        assert number(minimum=10, maximum=100, default=2).default == 10

    def test_a_default_above_the_maximum_is_clamped_down(self):
        assert number(minimum=0, maximum=50, default=999).default == 50

    def test_a_default_inside_the_range_is_untouched(self):
        assert number(minimum=0, maximum=100, default=25).default == 25

    @pytest.mark.parametrize("bad", ["twenty", True])
    def test_a_non_numeric_default_is_dropped(self, bad):
        assert number(default=bad).default is None


class TestBooleanDefaults:
    def test_a_non_boolean_default_is_dropped(self):
        assert (
            DecisionQuestion(
                id="tracked", label="Do you track this", input_type="boolean", default="yes"
            ).default
            is None
        )

    def test_a_boolean_default_is_kept(self):
        assert (
            DecisionQuestion(
                id="tracked", label="Do you track this", input_type="boolean", default=False
            ).default
            is False
        )


class TestStructureStillFails:
    """The relaxation is scoped to the preselection. Shape is still shape."""

    def test_a_choice_with_one_option_is_rejected(self):
        with pytest.raises(ValidationError):
            DecisionQuestion(
                id="segment", label="Pick one", input_type="single_choice", options=["Only"]
            )

    def test_mismatched_option_scores_are_rejected(self):
        """Scores drive the result, so a wrong count is a broken instrument."""
        with pytest.raises(ValidationError):
            choice(option_scores=[10, 20])

    def test_an_inverted_number_range_is_rejected(self):
        with pytest.raises(ValidationError):
            number(minimum=100, maximum=10)

    def test_a_non_positive_step_is_rejected(self):
        with pytest.raises(ValidationError):
            number(step=0)

    def test_options_on_a_number_question_are_rejected(self):
        with pytest.raises(ValidationError):
            number(options=["a", "b"])
