"""One build, all the way through, with nothing faked but the model and the wire.

Every other test in this package isolates a stage. This one refuses to: it runs
the real analyzer, architect, stitcher and codegen functions, the real grounding
validation, the real file validation, the real scaffolder, and the real Vercel
client, and asserts that a scripted set of model replies comes out the far end as
a deployed URL.

That matters because the individual stages can each be correct while the seams
between them are not. The architect's output has to satisfy the codegen prompt's
expectations; the design tokens the stitcher returns have to survive into a
``:root`` block; the files codegen invents have to pass validation *and* land in
a directory layout the Vite scaffold can build; the dist that produces has to be
readable by the deploy client. None of that is exercised by testing a stage
alone, and none of it can be exercised against Gemini and Vercel in CI.

Two things, and only two, are stubbed:

* ``_make_agent`` — returns scripted JSON chosen by which stage is asking.
* ``pnpm`` and ``httpx`` — the build subprocess and the Vercel API.

Everything between them is the production code path. When real API keys do turn
up, the remaining unknown is whether a live model returns output this shape —
not whether the pipeline can carry it.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from app.platform.pipeline import builder, engine
from app.platform.pipeline.schemas import (
    Blueprint,
    EvidenceReference,
    SiteBrandEvidence,
    SiteEvidence,
    SitePageEvidence,
    WidgetType,
)
from app.platform.pipeline.states.analyzer import SYSTEM_PROMPT as ANALYZER_PROMPT
from app.platform.pipeline.states.architect import ARCHITECT_SYSTEM_PROMPT
from app.platform.pipeline.states.codegen import CODEGEN_SYSTEM_PROMPT
from app.platform.pipeline.states.stitcher import STITCHER_SYSTEM_PROMPT

WIDGET_ID = "abcdef1234567890"

# --------------------------------------------------------------------------- #
# What the crawler found. Every id below is cited by the scripted replies, so a
# grounding regression in any stage fails this test rather than passing quietly.
# --------------------------------------------------------------------------- #

EVIDENCE = SiteEvidence(
    target_url="https://northside.example/",
    domain="northside.example",
    business_name="Northside Dental",
    summary="Family dental care in Nairobi.",
    pages=[
        SitePageEvidence(
            url="https://northside.example/",
            title="Northside Dental",
            description="Dental care for families.",
            headings=["Confident dental care"],
            calls_to_action=["Book a visit"],
            pricing_signals=["New patient appointments from $120."],
        )
    ],
    references=[
        EvidenceReference(
            id="heading_1",
            kind="heading",
            text="Confident dental care",
            source_url="https://northside.example/",
        ),
        EvidenceReference(
            id="price_1",
            kind="price",
            text="New patient appointments from $120.",
            source_url="https://northside.example/",
        ),
    ],
    brand=SiteBrandEvidence(colors=["#17324d", "#e8b05c"], fonts=["Inter"], logo_url=None),
    content_fingerprint="c" * 64,
    brand_fingerprint="b" * 64,
)

ANALYZER_REPLY = {
    "blueprints": [
        {
            "type": "roi_calculator",
            "title": "Recovered bookings calculator",
            "description": "Estimates revenue lost to an unclear booking path.",
            "rationale": "The site sells appointments and publishes a starting price.",
            "evidence_refs": ["heading_1", "price_1"],
        },
        {
            "type": "audit_tool",
            "title": "Booking path audit",
            "description": "Scores how easily a new patient can book.",
            "rationale": "The homepage leads with a single booking call to action.",
            "evidence_refs": ["heading_1"],
        },
        {
            "type": "readiness_quiz",
            "title": "New patient readiness",
            "description": "Guides a visitor to the right first appointment.",
            "rationale": "The practice targets families new to the area.",
            "evidence_refs": ["heading_1"],
        },
    ]
}

ARCHITECT_REPLY = {
    "widget_type": "roi_calculator",
    "brand": {
        # Both drawn from evidence; the greys are on the neutral allowlist.
        "primary_color": "#17324d",
        "secondary_color": "#555555",
        "background_color": "#ffffff",
        "accent_color": "#e8b05c",
        "font_headings": "Inter",
        "font_body": "system-ui",
        "tone": "calm-professional",
        "logo_url": None,
    },
    "visual_language": {
        "layout": "centered-single-column",
        "spacing": "comfortable",
        "card_style": "solid-white",
        "border_radius": "rounded",
        "shadow_depth": "subtle",
        "button_style": "filled-solid",
        "decorative_elements": "none",
        "icon_style": "outlined",
        "visual_energy": "calm",
    },
    "logic": {
        "formula": "Monthly new patients times the share lost to an unclear booking path.",
        "variables": [
            {"name": "monthly_patients", "description": "new patients a month", "default": "25"}
        ],
        "example_calculation": "25 patients, 8% recovered, is 2 more a month.",
    },
    "copywriting": {
        "headline": "What is a clearer booking path worth?",
        "subheadline": "An estimate in under a minute.",
        "cta": "See my estimate",
        "result_headline": "Your recoverable bookings",
        "result_subtext": "Based on the numbers you entered.",
    },
    "decision": {
        "mechanism": "estimate",
        "buyer_question": "What is a clearer booking path worth to this practice?",
        "value_before_gate": "A monthly recovered-bookings estimate with its assumptions",
        "qualification_goal": "Practice size and current booking volume",
        "recommended_placement": "New patients page",
        "questions": [
            {
                "id": "monthly_patients",
                "label": "New patients a month",
                "help_text": "Your current average is fine.",
                "input_type": "number",
                "required": True,
                "minimum": 0,
                "maximum": 500,
                "step": 1,
                "default": 25,
                "weight": 1,
                "evidence_ref": "price_1",
            },
            {
                "id": "tracks_online",
                "label": "Do you track online bookings",
                "input_type": "boolean",
                "required": True,
                "weight": 1,
                "true_score": 100,
            },
        ],
        "results": [
            {
                "key": "low",
                "title": "A modest opportunity",
                "summary": "Your booking path is broadly working today.",
                "recommendation": "Review the new-patient page for clarity.",
                "minimum_score": 0,
                "maximum_score": 50,
            },
            {
                "key": "high",
                "title": "A clear opportunity",
                "summary": "There is meaningful revenue in a clearer path.",
                "recommendation": "Book a review of your new-patient journey.",
                "minimum_score": 50,
                "maximum_score": 100,
            },
        ],
        "calculation": {
            "kind": "weighted_score",
            "output_label": "Opportunity score",
            "output_format": "score",
            "clamp_min": 0,
            "clamp_max": 100,
        },
        "qualification_threshold": 60,
        "lead_gate": "after_value",
        "primary_cta": "Discuss this estimate",
        "evidence_refs": ["heading_1", "price_1"],
    },
    "claims": [
        {
            "text": "New patient appointments start at $120.",
            "evidence_ref": "price_1",
            "requires_approval": False,
        }
    ],
}

STITCHER_REPLY = {
    "css_variables": {
        "--color-primary": "#17324d",
        "--color-secondary": "#555555",
        "--color-background": "#ffffff",
        "--color-accent": "#e8b05c",
        "--color-surface": "#ffffff",
        "--color-muted": "#f5f5f5",
        "--font-heading": "Inter",
        "--font-body": "system-ui",
    },
    "component_theme": {
        "button_bg": "var(--color-primary)",
        "button_text": "#ffffff",
        "card_bg": "#ffffff",
        "border_radius": "12px",
        "spacing": "16px",
    },
}

# Deliberately realistic: imports the injected SDK, calls submitLead and
# calculateDecision, animates, and provides the reduced-motion escape. Anything
# less is rejected by validation before the build is attempted.
APP_JSX = """import React, { useState } from 'react';
import { submitLead, calculateDecision, trackResult } from './lib/magnitai.js';

export default function App() {
  const [answers, setAnswers] = useState({ monthly_patients: 25, tracks_online: false });
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle');
  const outcome = calculateDecision(answers);

  async function handleSubmit(event) {
    event.preventDefault();
    setStatus('sending');
    const result = await submitLead({ email, score: outcome.value, answers });
    setStatus(result.ok ? 'done' : 'error');
  }

  return (
    <main className="min-h-screen p-8 transition-colors motion-reduce:transition-none">
      <h1 className="text-4xl font-bold">What is a clearer booking path worth?</h1>
      <div aria-live="polite" onLoad={() => trackResult(outcome.result)}>{outcome.value}</div>
      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Work email</label>
        <input id="email" type="email" value={email}
               onChange={(e) => setEmail(e.target.value)} />
        <button type="submit" disabled={status === 'sending'}>See my estimate</button>
      </form>
    </main>
  );
}
"""

CODEGEN_REPLY = {
    "files": [{"path": "src/App.jsx", "content": APP_JSX}],
    "entry_point": "src/App.jsx",
    "design_tokens": STITCHER_REPLY,
}

BLUEPRINT = Blueprint(**ANALYZER_REPLY["blueprints"][0])


# --------------------------------------------------------------------------- #
# The scripted model
# --------------------------------------------------------------------------- #


def _emit_dist(project_dir: str) -> None:
    """Write the files a successful Vite build would leave in ``dist/``.

    Asserts the generated component actually arrived first: a scaffold that
    silently dropped it would still "build" here and hide the regression.
    """
    sandbox = Path(project_dir)
    assert (sandbox / "src" / "App.jsx").is_file(), "codegen output never reached the sandbox"

    assets = sandbox / "dist" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (sandbox / "dist" / "index.html").write_text(
        "<!doctype html><div id=root></div>", encoding="utf-8"
    )
    (assets / "app.js").write_text("console.log('built')", encoding="utf-8")


class ScriptedResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def structured_output(self) -> dict:
        return self._payload

    async def text(self) -> str:  # pragma: no cover - structured path always wins
        return json.dumps(self._payload)


class ScriptedAgent:
    """Answers as whichever stage is asking, and records that it was asked."""

    def __init__(self, payload: dict, log: list[str], stage: str) -> None:
        self._payload = payload
        self._log = log
        self._stage = stage

    async def chat(self, prompt: str) -> ScriptedResponse:
        self._log.append(self._stage)
        return ScriptedResponse(self._payload)


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    """Wire the whole engine up with a scripted model and no network."""
    stages: list[str] = []
    deploy_payloads: list[dict] = []

    replies = {
        ANALYZER_PROMPT: ("analyzer", ANALYZER_REPLY),
        ARCHITECT_SYSTEM_PROMPT: ("architect", ARCHITECT_REPLY),
        STITCHER_SYSTEM_PROMPT: ("stitcher", STITCHER_REPLY),
        CODEGEN_SYSTEM_PROMPT: ("codegen", CODEGEN_REPLY),
    }

    @asynccontextmanager
    async def fake_agent(system_instructions, *args, **kwargs):
        stage, payload = replies[system_instructions]
        yield ScriptedAgent(payload, stages, stage)

    # A minimal stand-in for the pre-installed pnpm template. The real one only
    # differs by having node_modules, which nothing here reads.
    template = tmp_path / "template"
    (template / "src").mkdir(parents=True)
    (template / "package.json").write_text('{"name":"magai-widget"}', encoding="utf-8")
    (template / "vite.config.js").write_text("export default {};", encoding="utf-8")

    async def fake_pnpm_build(project_dir: str) -> tuple[bool, str]:
        """Stand in for Vite: emit the artifact a real build would leave behind.

        The filesystem work is delegated to a thread for the same reason the real
        builder does it — blocking I/O does not belong on the event loop — which
        also keeps this fake honest about the shape of what it replaces.
        """
        await asyncio.to_thread(_emit_dist, project_dir)
        return True, ""

    async def fake_post(self, url, **kwargs):
        deploy_payloads.append(kwargs.get("json") or {})
        return httpx.Response(
            200,
            json={"url": f"magai-widget-{WIDGET_ID[:8]}.vercel.app", "projectId": "prj_1"},
            request=httpx.Request("POST", url),
        )

    async def fake_patch(self, url, **kwargs):
        return httpx.Response(200, json={}, request=httpx.Request("PATCH", url))

    async def noop(*args, **kwargs):
        return None

    class Recorder:
        def __init__(self) -> None:
            self.published: list[tuple[str, str]] = []

        async def publish_stage(self, widget_id, stage, status, message, **kwargs):
            self.published.append((stage, status))

    recorder = Recorder()

    monkeypatch.setattr(engine, "_make_agent", fake_agent)
    monkeypatch.setattr(engine, "record_generation_usage", noop)
    monkeypatch.setattr(engine, "_update_build_progress", noop)
    monkeypatch.setattr(engine, "event_manager", recorder)
    monkeypatch.setattr(engine.settings, "widgets_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr(engine.settings, "site_url", "https://api.magnit.test")
    monkeypatch.setattr(builder, "_ensure_template", lambda: str(template))
    monkeypatch.setattr(builder, "_run_build", fake_pnpm_build)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(httpx.AsyncClient, "patch", fake_patch)

    return {
        "stages": stages,
        "deploys": deploy_payloads,
        "events": recorder.published,
        "workspace": tmp_path / "workspace",
    }


# --------------------------------------------------------------------------- #
# The build, end to end
# --------------------------------------------------------------------------- #


async def test_a_site_becomes_a_deployed_widget(pipeline):
    """analyze -> architect -> stitcher -> codegen -> validate -> build -> deploy."""
    proposals = await engine.analyze("https://northside.example/", EVIDENCE)
    assert [b.type.value for b in proposals.blueprints] == [
        "roi_calculator",
        "audit_tool",
        "readiness_quiz",
    ]

    result = await engine.build(
        BLUEPRINT,
        "https://northside.example/",
        WIDGET_ID,
        source_evidence=EVIDENCE,
    )

    # Every stage ran, in order, exactly once.
    assert pipeline["stages"] == ["analyzer", "architect", "stitcher", "codegen"]
    assert result.deployment.url == f"https://magai-widget-{WIDGET_ID[:8]}.vercel.app"
    assert result.architect_output.widget_type is WidgetType.ROI_CALCULATOR
    assert result.design_tokens.css_variables["--color-primary"] == "#17324d"


async def test_the_scaffolded_project_is_complete_and_coherent(pipeline):
    """The generated app plus every injected runtime file, in one buildable tree."""
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    project = pipeline["workspace"] / f"build_{WIDGET_ID}"
    for expected in (
        "index.html",
        "src/App.jsx",
        "src/main.jsx",
        "src/index.css",
        "src/tokens.css",
        "src/config.js",
        "src/lib/magnitai.js",
        "package.json",
    ):
        assert (project / expected).is_file(), f"{expected} missing from the scaffold"

    # node_modules is deliberately not carried out of the sandbox.
    assert not (project / "node_modules").exists()


async def test_the_brand_survives_all_the_way_into_the_stylesheet(pipeline):
    """A token the stitcher chose has to reach a :root block, or every var() is dead."""
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    tokens_css = (pipeline["workspace"] / f"build_{WIDGET_ID}" / "src" / "tokens.css").read_text(
        encoding="utf-8"
    )

    assert "--color-primary" in tokens_css
    assert "#17324d" in tokens_css


async def test_the_widget_knows_where_to_send_its_leads(pipeline):
    """The runtime config is baked in; without the right API base, no lead arrives."""
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    config = (pipeline["workspace"] / f"build_{WIDGET_ID}" / "src" / "config.js").read_text(
        encoding="utf-8"
    )

    assert "https://api.magnit.test" in config
    assert WIDGET_ID in config


async def test_the_decision_spec_is_baked_in_for_offline_rendering(pipeline):
    """The result screen has to render with no network, from the approved questions."""
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    config = (pipeline["workspace"] / f"build_{WIDGET_ID}" / "src" / "config.js").read_text(
        encoding="utf-8"
    )

    assert "monthly_patients" in config
    assert "tracks_online" in config


async def test_the_entry_html_carries_the_title_and_its_csp(pipeline):
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    markup = (pipeline["workspace"] / f"build_{WIDGET_ID}" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "<title>Recovered bookings calculator</title>" in markup
    assert "connect-src &#x27;self&#x27; https://api.magnit.test" in markup
    # Inter came from the evidence, so the font link is requested and permitted.
    assert "fonts.googleapis.com" in markup


async def test_the_built_artifact_is_what_gets_uploaded(pipeline):
    """Vercel must receive the dist, keyed by URL path — not the source tree."""
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    uploaded = {entry["file"] for entry in pipeline["deploys"][0]["files"]}

    assert uploaded == {"index.html", "assets/app.js"}
    assert pipeline["deploys"][0]["name"] == f"magai-widget-{WIDGET_ID[:8]}"
    assert pipeline["deploys"][0]["target"] == "production"


async def test_a_preview_build_produces_artifacts_but_publishes_nothing(pipeline):
    result = await engine.build(
        BLUEPRINT,
        "https://northside.example/",
        WIDGET_ID,
        source_evidence=EVIDENCE,
        skip_deploy=True,
    )

    assert result.deployment.url == ""
    assert pipeline["deploys"] == []
    assert (pipeline["workspace"] / f"build_{WIDGET_ID}" / "dist" / "index.html").is_file()


async def test_a_workspace_brand_kit_beats_the_sites_own_colours(pipeline):
    """End to end, an owner's house style has to win — this is a paid feature."""
    result = await engine.build(
        BLUEPRINT,
        "https://northside.example/",
        WIDGET_ID,
        source_evidence=EVIDENCE,
        brand_overrides={"primary_color": "#ff6600"},
        token_overrides={"--color-primary": "#ff6600"},
    )

    assert result.architect_output.brand.primary_color == "#ff6600"
    tokens_css = (pipeline["workspace"] / f"build_{WIDGET_ID}" / "src" / "tokens.css").read_text(
        encoding="utf-8"
    )
    assert "#ff6600" in tokens_css


async def test_the_owner_sees_every_stage_reported(pipeline):
    """The build story on the dashboard is assembled from exactly these events."""
    await engine.build(BLUEPRINT, "https://northside.example/", WIDGET_ID, source_evidence=EVIDENCE)

    assert pipeline["events"] == [
        ("architect", "active"),
        ("architect", "complete"),
        ("stitcher", "active"),
        ("stitcher", "complete"),
        ("codegen", "active"),
        ("codegen", "active"),
        ("codegen", "complete"),
        ("deploy", "active"),
        ("deploy", "complete"),
    ]
