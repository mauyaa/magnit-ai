"""Engine orchestration: what runs, in what order, and what wins.

The four stages are tested individually in ``test_states.py``. What is left here
is the wiring between them, and it carries two decisions that are easy to get
quietly wrong: whether the customer's confirmed design is reused instead of
re-derived, and whether a workspace brand kit actually overrides what the model
chose. Both are promises to a paying customer rather than internal details.

Every agent call is stubbed. The engine constructs real ``Agent`` objects against
Gemini, so the seam is ``_make_agent`` and the stage functions it drives.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.platform.pipeline import engine
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    DeploymentResult,
    DesignTokens,
    ProjectFile,
    WidgetCode,
    WidgetType,
)

BLUEPRINT = Blueprint(
    type=WidgetType.ROI_CALCULATOR,
    title="Revenue calculator",
    description="Estimates recovered revenue.",
    rationale="The site sells appointments.",
    evidence_refs=["heading_1"],
)

STITCHED_TOKENS = DesignTokens(
    css_variables={"--color-primary": "#111111", "--font-heading": "Inter"},
    component_theme={"button_bg": "var(--color-primary)"},
)

WIDGET_CODE = WidgetCode(
    files=[ProjectFile(path="src/App.jsx", content="export default () => null;")],
    design_tokens=STITCHED_TOKENS,
)


def architect_output(**brand_overrides) -> ArchitectOutput:
    brand = {
        "primary_color": "#17324d",
        "secondary_color": "#111111",
        "background_color": "#ffffff",
        "accent_color": "#17324d",
        "font_headings": "Inter",
        "font_body": "system-ui",
        "tone": "calm-professional",
        "logo_url": None,
    }
    brand.update(brand_overrides)
    return ArchitectOutput(
        widget_type=WidgetType.ROI_CALCULATOR,
        brand=brand,
        logic={
            "formula": "volume x rate",
            "variables": [{"name": "volume", "description": "v", "default": "10"}],
            "example_calculation": "10 x 8% = 0.8",
        },
        copywriting={"headline": "What is it worth?"},
    )


class StageRecorder:
    """Collects the progress events the dashboard timeline is built from."""

    def __init__(self) -> None:
        self.stages: list[tuple[str, str]] = []

    async def publish_stage(self, widget_id, stage, status, message, **kwargs):
        self.stages.append((stage, status))


@pytest.fixture
def engine_harness(monkeypatch):
    """Stub every outbound call, and report what the engine asked for."""
    recorder = StageRecorder()
    calls: dict = {"deployed": [], "codegen": [], "architect": []}

    @asynccontextmanager
    async def fake_agent(*args, **kwargs):
        yield object()

    async def fake_stitcher(agent, output):
        return STITCHED_TOKENS

    async def fake_codegen(widget_id, output, tokens, widget_type, widget_title, **kwargs):
        calls["codegen"].append(tokens)
        return WIDGET_CODE, f"/builds/{widget_id}"

    async def fake_deploy(dist_dir, widget_id):
        calls["deployed"].append(dist_dir)
        return DeploymentResult(url="https://w.vercel.app", widget_id=widget_id)

    async def fake_architect_stage(blueprint, url, evidence, widget_id=None, brief=None):
        calls["architect"].append(blueprint)
        return architect_output()

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(engine, "_make_agent", fake_agent)
    monkeypatch.setattr(engine, "run_stitcher", fake_stitcher)
    monkeypatch.setattr(engine, "_codegen_with_retry", fake_codegen)
    monkeypatch.setattr(engine, "deploy_directory", fake_deploy)
    monkeypatch.setattr(engine, "run_architect_stage", fake_architect_stage)
    monkeypatch.setattr(engine, "_update_build_progress", noop)
    monkeypatch.setattr(engine, "record_generation_usage", noop)
    monkeypatch.setattr(engine, "event_manager", recorder)
    calls["stages"] = recorder.stages
    return calls


class TestBuild:
    async def test_a_grounded_build_needs_evidence(self):
        """Without evidence there is nothing to ground the design in, so it must not proceed."""
        with pytest.raises(RuntimeError, match="source evidence is required"):
            await engine.build(BLUEPRINT, "https://example.com/", "w1")

    async def test_a_confirmed_design_is_reused_rather_than_re_derived(self, engine_harness):
        """The customer approved this design; re-running the architect could change it."""
        approved = architect_output(primary_color="#abcdef")

        result = await engine.build(
            BLUEPRINT,
            "https://example.com/",
            "w1",
            architect_override=approved,
            skip_deploy=True,
        )

        assert engine_harness["architect"] == []
        assert result.architect_output.brand.primary_color == "#abcdef"
        assert ("architect", "complete") in engine_harness["stages"]

    async def test_without_a_confirmation_the_architect_stage_runs(self, engine_harness):
        evidence = _evidence()

        await engine.build(
            BLUEPRINT,
            "https://example.com/",
            "w1",
            source_evidence=evidence,
            skip_deploy=True,
        )

        assert engine_harness["architect"] == [BLUEPRINT]

    async def test_a_workspace_brand_kit_overrides_the_extracted_brand(self, engine_harness):
        """The owner set a house style; the site's own colours must not win over it."""
        result = await engine.build(
            BLUEPRINT,
            "https://example.com/",
            "w1",
            architect_override=architect_output(),
            brand_overrides={"primary_color": "#ff6600", "font_headings": "Sora"},
            skip_deploy=True,
        )

        assert result.architect_output.brand.primary_color == "#ff6600"
        assert result.architect_output.brand.font_headings == "Sora"
        # Untouched fields survive the merge rather than being blanked.
        assert result.architect_output.brand.background_color == "#ffffff"


class TestGenerateAndDeploy:
    async def test_a_build_is_published_from_its_dist_directory(self, engine_harness):
        result = await engine.generate_and_deploy(
            "w1", architect_output(), WidgetType.ROI_CALCULATOR, "Calc"
        )

        assert engine_harness["deployed"] == ["/builds/w1/dist"]
        assert result.deployment.url == "https://w.vercel.app"
        assert ("deploy", "complete") in engine_harness["stages"]

    async def test_skipping_deploy_produces_artifacts_without_a_url(self, engine_harness):
        """A preview build has to be distinguishable from a published one."""
        result = await engine.generate_and_deploy(
            "w1", architect_output(), WidgetType.ROI_CALCULATOR, "Calc", skip_deploy=True
        )

        assert engine_harness["deployed"] == []
        assert result.deployment.url == ""
        assert result.project_dir == "/builds/w1"

    async def test_token_overrides_beat_the_stitchers_choices(self, engine_harness):
        """A hard override has to be a guarantee, not a request the model may ignore."""
        result = await engine.generate_and_deploy(
            "w1",
            architect_output(),
            WidgetType.ROI_CALCULATOR,
            "Calc",
            skip_deploy=True,
            token_overrides={"--color-primary": "#ff6600"},
        )

        assert result.design_tokens.css_variables["--color-primary"] == "#ff6600"
        # Variables the kit says nothing about keep the Stitcher's values.
        assert result.design_tokens.css_variables["--font-heading"] == "Inter"

    async def test_the_overridden_tokens_are_what_codegen_receives(self, engine_harness):
        """Overriding after codegen would style the shell but not the generated app."""
        await engine.generate_and_deploy(
            "w1",
            architect_output(),
            WidgetType.ROI_CALCULATOR,
            "Calc",
            skip_deploy=True,
            token_overrides={"--color-primary": "#ff6600"},
        )

        assert engine_harness["codegen"][0].css_variables["--color-primary"] == "#ff6600"

    async def test_stage_progress_is_reported_in_order(self, engine_harness):
        await engine.generate_and_deploy(
            "w1", architect_output(), WidgetType.ROI_CALCULATOR, "Calc"
        )

        assert engine_harness["stages"] == [
            ("stitcher", "active"),
            ("stitcher", "complete"),
            ("deploy", "active"),
            ("deploy", "complete"),
        ]


def _evidence():
    from app.platform.pipeline.schemas import (
        EvidenceReference,
        SiteBrandEvidence,
        SiteEvidence,
        SitePageEvidence,
    )

    return SiteEvidence(
        target_url="https://example.com/",
        domain="example.com",
        pages=[SitePageEvidence(url="https://example.com/", title="Home")],
        references=[
            EvidenceReference(
                id="heading_1",
                kind="heading",
                text="Confident dental care",
                source_url="https://example.com/",
            )
        ],
        brand=SiteBrandEvidence(colors=["#17324d"], fonts=["Inter"]),
        content_fingerprint="a" * 64,
        brand_fingerprint="b" * 64,
    )
