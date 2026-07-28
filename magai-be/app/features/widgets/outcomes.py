"""What the visitor sees once they finish, and who gets to decide it.

The Architect stage designs a result screen: score ranges, a summary and a
recommendation for each. That is a good first draft and a bad final answer,
because the owner is the one who knows that "70-100" should be called "Ready to
scale" rather than "High fit", and which of their three services the person who
scored 84 should actually be pointed at.

So this module models the result screen as configuration. It is *derived* from
the generated decision spec the first time it is read, then owned by the person
who edits it — which is why it lives in its own column and is never overwritten
by a regeneration.
"""

from __future__ import annotations

import re
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.platform.pipeline.schemas import DecisionSpec

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# Fallback band colours, in descending order of score. Chosen so that the top
# band reads as success and the bottom as attention without either being alarming
# — a visitor scoring badly is still a prospect, and a red panel tells them they
# failed a test they did not know they were taking.
_DEFAULT_BAND_COLORS = ("#16A34A", "#D97706", "#DC2626")


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{fallback}_{cleaned}".strip("_")
    return cleaned[:60] or fallback


class ScoreBand(BaseModel):
    """One segment of the score range, and how it is described to the visitor."""

    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=80)
    minimum_score: int = Field(ge=0, le=100)
    maximum_score: int = Field(ge=0, le=100)
    # Drives emphasis on the result screen, and is what the owner is really
    # saying when they mark a band: "this is the one worth a call".
    importance: str = Field(default="medium", pattern=r"^(high|medium|low)$")
    description: str = Field(default="", max_length=600)
    accent_color: str = Field(default="#16A34A", max_length=9)

    @field_validator("accent_color")
    @classmethod
    def _valid_color(cls, value: str) -> str:
        # The value is interpolated into the deployed widget's stylesheet, so a
        # strict shape here is a defence, not a nicety.
        if not _HEX_COLOR.match(value):
            raise ValueError("accent_color must be a hex colour such as #16A34A")
        return value.upper()

    @model_validator(mode="after")
    def _ordered(self) -> ScoreBand:
        if self.minimum_score > self.maximum_score:
            raise ValueError("a band's minimum cannot be above its maximum")
        return self


class AdviceBlock(BaseModel):
    """One line of "recommended for you", optionally scoped to a single band."""

    text: str = Field(min_length=1, max_length=300)
    # None means it is shown to everyone, whatever they scored.
    band_key: str | None = Field(default=None, max_length=60)


class EmailCapture(BaseModel):
    """The gate, which by product rule only ever appears after the result."""

    enabled: bool = True
    heading: str = Field(default="Get your full results", max_length=120)
    subheading: str = Field(
        default="We'll email a detailed breakdown and your action plan.", max_length=240
    )
    button_label: str = Field(default="Send my results", max_length=60)
    placeholder: str = Field(default="Enter your work email", max_length=80)
    require_name: bool = False
    consent_text: str = Field(default="", max_length=300)


class OutcomeCta(BaseModel):
    label: str = Field(default="Book a call", max_length=80)
    url: str = Field(default="", max_length=2048)
    note: str = Field(default="", max_length=160)


class NextStep(BaseModel):
    """One card in the "what to do now" row beneath the result."""

    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=240)
    link_label: str = Field(default="", max_length=60)
    link_url: str = Field(default="", max_length=2048)


class OutcomeConfig(BaseModel):
    """The complete, owner-editable result screen."""

    bands: list[ScoreBand] = Field(min_length=1, max_length=6)
    advice: list[AdviceBlock] = Field(default_factory=list, max_length=12)
    email_capture: EmailCapture = Field(default_factory=EmailCapture)
    cta: OutcomeCta = Field(default_factory=OutcomeCta)
    next_steps: list[NextStep] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _bands_are_a_partition(self) -> OutcomeConfig:
        keys = [band.key for band in self.bands]
        if len(keys) != len(set(keys)):
            raise ValueError("band keys must be unique")

        ordered = sorted(self.bands, key=lambda band: band.minimum_score)
        for lower, upper in pairwise(ordered):
            if lower.maximum_score >= upper.minimum_score:
                raise ValueError(
                    f"bands '{lower.label}' and '{upper.label}' overlap; "
                    "every score must fall in exactly one band"
                )
            # A gap is as broken as an overlap and much harder to notice: a
            # visitor scoring into it sees a result screen with no result.
            if upper.minimum_score - lower.maximum_score > 1:
                raise ValueError(
                    f"scores between {lower.maximum_score} and {upper.minimum_score} "
                    "fall outside every band"
                )

        known = set(keys)
        for block in self.advice:
            if block.band_key is not None and block.band_key not in known:
                raise ValueError(f"advice refers to unknown band '{block.band_key}'")
        return self

    def band_for(self, score: float) -> ScoreBand:
        """The band a score lands in, clamped rather than allowed to miss.

        Validation guarantees the bands cover a contiguous range, but a
        calculation with its own clamp can still produce 104. Returning the
        nearest band beats returning nothing on the one screen the whole tool
        exists to show.
        """
        ordered = sorted(self.bands, key=lambda band: band.minimum_score)
        for band in ordered:
            if band.minimum_score <= score <= band.maximum_score:
                return band
        return ordered[-1] if score > ordered[-1].maximum_score else ordered[0]


def derive_outcome_config(
    decision: DecisionSpec | None, copywriting: dict[str, Any] | None = None
) -> OutcomeConfig:
    """Seed a configuration from what the model designed.

    This is what an owner opens the outcomes editor to, so it has to be a
    genuinely usable result screen rather than an empty form: every band already
    carries the summary and recommendation the Architect wrote for it.
    """
    copy = copywriting or {}

    if decision is None or not decision.results:
        return OutcomeConfig(
            bands=[
                ScoreBand(
                    key="your_result",
                    label="Your result",
                    minimum_score=0,
                    maximum_score=100,
                    importance="high",
                    description=str(copy.get("subheadline") or ""),
                    accent_color=_DEFAULT_BAND_COLORS[0],
                )
            ],
            cta=OutcomeCta(label=str(copy.get("cta") or "Book a call")),
        )

    # Highest band first, so the default colour ramp reads success → attention
    # in the order an owner sees them listed.
    results = sorted(
        decision.results,
        key=lambda result: result.minimum_score if result.minimum_score is not None else 0,
        reverse=True,
    )

    bands: list[ScoreBand] = []
    for index, result in enumerate(results):
        minimum = int(result.minimum_score) if result.minimum_score is not None else 0
        maximum = int(result.maximum_score) if result.maximum_score is not None else 100
        bands.append(
            ScoreBand(
                key=_slug(result.key, f"band_{index + 1}"),
                label=result.title[:80],
                minimum_score=max(0, min(100, minimum)),
                maximum_score=max(0, min(100, maximum)),
                importance="high" if index == 0 else "medium" if index == 1 else "low",
                description=result.summary[:600],
                accent_color=_DEFAULT_BAND_COLORS[min(index, len(_DEFAULT_BAND_COLORS) - 1)],
            )
        )

    bands = _repair_coverage(bands)

    advice = [
        AdviceBlock(text=result.recommendation[:300], band_key=band.key)
        for band, result in zip(bands, results, strict=False)
        if result.recommendation
    ]

    return OutcomeConfig(
        bands=bands,
        advice=advice,
        email_capture=EmailCapture(
            heading=str(copy.get("lead_capture_heading") or "Get your full results"),
            subheading=str(
                copy.get("lead_capture_subheading")
                or "We'll email a detailed breakdown and your action plan."
            ),
        ),
        cta=OutcomeCta(label=decision.primary_cta[:80]),
    )


def _repair_coverage(bands: list[ScoreBand]) -> list[ScoreBand]:
    """Close gaps and overlaps so a derived configuration always validates.

    The model's result ranges are only loosely constrained — it can emit 0-49 and
    60-100 and leave the fifties homeless. Rather than reject its output and show
    the owner an error they cannot act on, the ranges are snapped into a
    partition: each band starts one above the previous band's top, and the
    highest reaches 100.
    """
    if not bands:
        return bands

    ordered = sorted(bands, key=lambda band: band.minimum_score)
    repaired: list[ScoreBand] = []
    cursor = 0
    for index, band in enumerate(ordered):
        is_last = index == len(ordered) - 1
        maximum = 100 if is_last else max(cursor, min(100, band.maximum_score))
        repaired.append(band.model_copy(update={"minimum_score": cursor, "maximum_score": maximum}))
        cursor = min(100, maximum + 1)

    # Restore the caller's ordering (highest first) so colours stay put.
    by_key = {band.key: band for band in repaired}
    return [by_key[band.key] for band in bands]


def effective_outcome_config(
    stored: dict[str, Any] | None,
    decision: DecisionSpec | None,
    copywriting: dict[str, Any] | None = None,
) -> OutcomeConfig:
    """What is actually in force: the owner's version if valid, else the derived one.

    A stored configuration that no longer validates — because a regeneration
    changed the score range under it, say — falls back rather than failing. The
    visitor-facing screen must render something correct even when the saved
    version has gone stale.
    """
    if stored:
        try:
            return OutcomeConfig.model_validate(stored)
        except ValueError:
            pass
    return derive_outcome_config(decision, copywriting)
