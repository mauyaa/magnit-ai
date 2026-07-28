"""Scaffolding and the build retry loop.

``build_project`` is the only place model output is given a chance to be wrong
four different ways and still recover: rejected by validation, missing lead
capture, animating without a reduced-motion escape, ignoring the decision
runtime, or simply failing to compile. Each of those has to feed the model
something it can act on, and each has to give up eventually rather than spend
budget forever.

The real ``pnpm build`` is not run here — that is a minute of network per case.
The seam is ``_run_build`` and ``_scaffold_project``, so the loop's decisions are
what gets tested rather than Vite's.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.platform.pipeline import builder
from app.platform.pipeline.schemas import DesignTokens

# Never written to — the copy step out of the sandbox is stubbed — but it is
# still resolved through the platform's temp dir rather than a hardcoded /tmp,
# which does not exist on Windows.
OUT_DIR = os.path.join(tempfile.gettempdir(), "magai-test-out")

TOKENS = DesignTokens(
    css_variables={"--color-primary": "#17324d", "--font-heading": "Inter"},
    component_theme={"button_bg": "var(--color-primary)"},
)

# Passes validation, captures a lead, animates with an escape hatch, and defers
# its arithmetic to the runtime — the shape every other case departs from.
GOOD_APP = {
    "path": "src/App.jsx",
    "content": (
        "import React, { useState } from 'react';\n"
        "import { submitLead, calculateDecision } from './lib/magnitai.js';\n"
        "export default function App() {\n"
        "  const r = calculateDecision({});\n"
        "  const save = () => submitLead({ email: 'a@b.co' });\n"
        "  return <button className='transition-colors motion-reduce:transition-none'"
        " onClick={save}>{r.value}</button>;\n"
        "}\n"
    ),
}


def app_without(*, lead: bool = True, motion: bool = True, decision: bool = True) -> dict:
    """The good app with one requirement deliberately removed."""
    content = GOOD_APP["content"]
    if not lead:
        content = content.replace("submitLead({ email: 'a@b.co' })", "console.log('nope')")
    if not motion:
        content = content.replace(" motion-reduce:transition-none", "")
    if not decision:
        content = content.replace("calculateDecision({})", "({ value: 1 })")
    return {"path": "src/App.jsx", "content": content}


@pytest.fixture
def stub_scaffold(monkeypatch):
    """Replace the filesystem scaffold; record what each attempt was given."""
    scaffolded: list[list[dict]] = []

    def fake_scaffold(project_dir, files, **kwargs):
        scaffolded.append(files)

    monkeypatch.setattr(builder, "_scaffold_project", fake_scaffold)
    monkeypatch.setattr(builder, "_clean_sandbox", lambda sandbox: None)
    monkeypatch.setattr(builder, "_copy_without_node_modules", lambda src, dst: None)
    return scaffolded


async def run_build(files, *, gen_callback=None, decision_spec=None, max_attempts=3, **kwargs):
    return await builder.build_project(
        OUT_DIR,
        files,
        widget_id="w1",
        widget_title="Revenue calculator",
        api_base_url="https://api.example.com",
        design_tokens=TOKENS,
        decision_spec=decision_spec,
        max_attempts=max_attempts,
        gen_callback=gen_callback,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# The entry HTML
# --------------------------------------------------------------------------- #


class TestRenderIndexHtml:
    def test_title_is_the_widgets_own(self):
        """The title is the iframe's accessible name, so it is not decorative."""
        markup = builder.render_index_html("Revenue calculator", None, "https://api.example.com")

        assert "<title>Revenue calculator</title>" in markup

    def test_title_is_escaped(self):
        markup = builder.render_index_html(
            'Bob\'s "tool" <script>alert(1)</script>', None, "https://api.example.com"
        )

        assert "<script>alert(1)</script>" not in markup
        assert "&lt;script&gt;" in markup

    def test_untitled_widget_gets_a_sensible_default(self):
        markup = builder.render_index_html("", None, "https://api.example.com")

        assert "<title>Interactive tool</title>" in markup

    def test_csp_denies_everything_not_needed(self):
        markup = builder.render_index_html("T", None, "https://api.example.com")

        assert "default-src &#x27;none&#x27;" in markup
        assert "object-src &#x27;none&#x27;" in markup
        assert "frame-src &#x27;none&#x27;" in markup
        assert "base-uri &#x27;none&#x27;" in markup

    def test_csp_allows_calling_back_to_this_api(self):
        """Without this the lead submission the whole product exists for is blocked."""
        markup = builder.render_index_html("T", None, "https://api.example.com")

        assert "connect-src &#x27;self&#x27; https://api.example.com" in markup

    def test_no_font_origins_are_allowed_when_no_font_is_requested(self):
        markup = builder.render_index_html("T", None, "https://api.example.com")

        assert "fonts.googleapis.com" not in markup

    def test_requested_fonts_are_linked_and_permitted(self):
        href = "https://fonts.googleapis.com/css2?family=Inter&display=swap"
        markup = builder.render_index_html("T", href, "https://api.example.com")

        assert 'rel="stylesheet"' in markup
        assert "preconnect" in markup
        assert "font-src &#x27;self&#x27; https://fonts.googleapis.com" in markup


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #


class TestFilesystemHelpers:
    def test_write_file_creates_missing_parents(self, tmp_path):
        target = tmp_path / "src" / "lib" / "magnitai.js"

        builder._write_file(str(target), "export const x = 1;")

        assert target.read_text(encoding="utf-8") == "export const x = 1;"

    def test_clean_sandbox_keeps_node_modules(self, tmp_path):
        """Deleting it would turn every retry back into a 90-second install."""
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "react").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "index.html").write_text("old", encoding="utf-8")

        builder._clean_sandbox(str(tmp_path))

        assert (tmp_path / "node_modules" / "react").is_dir()
        assert not (tmp_path / "src").exists()
        assert not (tmp_path / "index.html").exists()

    def test_copy_without_node_modules_leaves_dependencies_behind(self, tmp_path):
        src = tmp_path / "sandbox"
        (src / "node_modules" / "react").mkdir(parents=True)
        (src / "dist").mkdir()
        (src / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
        (src / "index.html").write_text("<html></html>", encoding="utf-8")
        dst = tmp_path / "out"

        builder._copy_without_node_modules(str(src), str(dst))

        assert (dst / "dist" / "index.html").is_file()
        assert (dst / "index.html").is_file()
        assert not (dst / "node_modules").exists()


# --------------------------------------------------------------------------- #
# The retry loop
# --------------------------------------------------------------------------- #


class TestBuildProject:
    async def test_successful_build_returns_the_output_directory(self, monkeypatch, stub_scaffold):
        monkeypatch.setattr(builder, "_run_build", _build_result(True))
        monkeypatch.setattr(os.path, "isfile", lambda path: True)

        ok, result = await run_build([GOOD_APP])

        assert ok is True
        assert result == OUT_DIR
        assert len(stub_scaffold) == 1

    async def test_invalid_code_without_a_regenerator_gives_up_immediately(self):
        """No callback means no second chance; spend nothing further."""
        ok, reason = await run_build([{"path": "../escape.jsx", "content": "x"}])

        assert ok is False
        assert "Generated code rejected" in reason

    async def test_invalid_code_is_regenerated_and_can_succeed(self, monkeypatch, stub_scaffold):
        monkeypatch.setattr(builder, "_run_build", _build_result(True))
        monkeypatch.setattr(os.path, "isfile", lambda path: True)
        feedback: list[str] = []

        async def regenerate(reason: str):
            feedback.append(reason)
            return [GOOD_APP]

        ok, _ = await run_build(
            [{"path": "../escape.jsx", "content": "x"}], gen_callback=regenerate
        )

        assert ok is True
        assert "Generated code rejected" in feedback[0]

    async def test_missing_lead_capture_is_fed_back_by_name(self, monkeypatch, stub_scaffold):
        """The retry only helps if the model is told which call is missing."""
        monkeypatch.setattr(builder, "_run_build", _build_result(True))
        monkeypatch.setattr(os.path, "isfile", lambda path: True)
        feedback: list[str] = []

        async def regenerate(reason: str):
            feedback.append(reason)
            return [GOOD_APP]

        ok, _ = await run_build([app_without(lead=False)], gen_callback=regenerate)

        assert ok is True
        assert "submitLead()" in feedback[0]

    async def test_missing_lead_capture_fails_when_it_cannot_be_regenerated(self):
        ok, reason = await run_build([app_without(lead=False)])

        assert ok is False
        assert "never calls submitLead()" in reason

    async def test_animation_without_a_reduced_motion_escape_is_rejected(self):
        ok, reason = await run_build([app_without(motion=False)])

        assert ok is False
        assert "prefers-reduced-motion" in reason
        assert "motion-reduce:" in reason

    async def test_decision_runtime_is_only_required_when_there_is_a_spec(
        self, monkeypatch, stub_scaffold
    ):
        """A widget built before the decision contract existed must still build."""
        monkeypatch.setattr(builder, "_run_build", _build_result(True))
        monkeypatch.setattr(os.path, "isfile", lambda path: True)

        ok, _ = await run_build([app_without(decision=False)], decision_spec=None)

        assert ok is True

    async def test_ignoring_the_decision_runtime_is_rejected_when_a_spec_exists(self):
        ok, reason = await run_build(
            [app_without(decision=False)], decision_spec={"mechanism": "estimate"}
        )

        assert ok is False
        assert "calculateDecision(answers)" in reason

    async def test_compiler_errors_are_the_retry_feedback(self, monkeypatch, stub_scaffold):
        monkeypatch.setattr(os.path, "isfile", lambda path: True)
        attempts = {"n": 0}

        async def flaky_build(project_dir):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return False, "pnpm build failed:\nsrc/App.jsx:3 'useMemo' is not defined"
            return True, ""

        monkeypatch.setattr(builder, "_run_build", flaky_build)
        feedback: list[str] = []

        async def regenerate(reason: str):
            feedback.append(reason)
            return [GOOD_APP]

        ok, _ = await run_build([GOOD_APP], gen_callback=regenerate)

        assert ok is True
        assert "'useMemo' is not defined" in feedback[0]

    async def test_gives_up_after_the_attempt_limit(self, monkeypatch, stub_scaffold):
        monkeypatch.setattr(builder, "_run_build", _build_result(False, "pnpm build failed:\nboom"))
        calls = {"n": 0}

        async def regenerate(reason: str):
            calls["n"] += 1
            return [GOOD_APP]

        ok, reason = await run_build([GOOD_APP], gen_callback=regenerate, max_attempts=3)

        assert ok is False
        assert "boom" in reason
        # Regenerated after the first two failures, then stopped rather than
        # spending a third model call it would never use.
        assert calls["n"] == 2

    async def test_build_that_produces_no_index_html_is_treated_as_a_failure(
        self, monkeypatch, stub_scaffold
    ):
        """Vite can exit zero and emit nothing; deploying that serves a blank page."""
        monkeypatch.setattr(builder, "_run_build", _build_result(True))
        monkeypatch.setattr(os.path, "isfile", lambda path: False)

        ok, reason = await run_build([GOOD_APP])

        assert ok is False
        assert "produced no dist/index.html" in reason

    async def test_sandbox_is_removed_even_when_the_build_fails(self, monkeypatch, stub_scaffold):
        monkeypatch.setattr(builder, "_run_build", _build_result(False, "nope"))
        removed: list[str] = []

        real_rmtree = builder.shutil.rmtree

        def tracking_rmtree(path, **kwargs):
            removed.append(path)
            return real_rmtree(path, **kwargs)

        monkeypatch.setattr(builder.shutil, "rmtree", tracking_rmtree)

        await run_build([GOOD_APP])

        assert any("magai-sandbox-" in path for path in removed)


def _build_result(success: bool, output: str = ""):
    async def _run(project_dir: str):
        return success, output

    return _run
