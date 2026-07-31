"""Validation of model-generated project files before they are built.

The generated code is untrusted input. It is compiled and served from an isolated
origin, so it cannot reach Magnitai's data — but it can still waste a build slot,
escape the sandbox directory through a crafted path, or ship something that fails
in the visitor's browser rather than at build time.

These checks run before ``pnpm build`` so a bad generation fails fast with an
actionable message instead of a confusing compiler error.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 512_000
MAX_TOTAL_BYTES = 2_000_000
MAX_FILES = 25

# Only source files the Vite scaffold knows how to compile.
ALLOWED_SUFFIXES = (".jsx", ".js", ".css")

# Paths the model must not overwrite: these are the scaffold's own contract with
# the build (entry HTML, config, our hand-written runtime).
PROTECTED_PATHS = frozenset(
    {
        "package.json",
        "pnpm-lock.yaml",
        "vite.config.js",
        "tailwind.config.js",
        "postcss.config.js",
        "index.html",
        "src/main.jsx",
        "src/index.css",
        "src/tokens.css",
        "src/config.js",
        "src/lib/magnitai.js",
    }
)

# Patterns that indicate generated code doing something it never needs to do.
# Each is a defect in the generation, not necessarily an attack.
FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\beval\s*\(", "uses eval()"),
    (r"new\s+Function\s*\(", "constructs functions from strings"),
    (r"\bdocument\.write\s*\(", "uses document.write()"),
    (r"dangerouslySetInnerHTML", "injects raw HTML"),
    (r"<script\b", "embeds a script tag"),
    (r"\bimport\s*\(\s*[\"'`]https?://", "dynamically imports remote code"),
    (r"\brequire\s*\(\s*[\"'](?:fs|child_process|path|os)[\"']\)", "imports Node built-ins"),
    (r"process\.env\.[A-Z_]*(?:SECRET|TOKEN|KEY|PASSWORD)", "reads secrets from the environment"),
    (
        r"localStorage\.(?:setItem|getItem)\s*\(\s*[\"'][^\"']*(?:token|password)",
        "stores credentials",
    ),
)


class GeneratedCodeInvalid(Exception):
    """The model's output cannot be safely built."""


def _normalized_path(raw: str) -> str:
    """Normalize a declared file path, rejecting anything that escapes the project."""
    path = str(raw or "").strip().replace("\\", "/").lstrip("./")

    if not path:
        raise GeneratedCodeInvalid("a generated file has an empty path")
    if path.startswith("/") or ".." in path.split("/"):
        # Path traversal would let generated output overwrite files outside the
        # sandbox, including the template's node_modules.
        raise GeneratedCodeInvalid(f"unsafe file path: {raw!r}")
    if not path.startswith("src/"):
        raise GeneratedCodeInvalid(f"generated files must live under src/: {raw!r}")
    if not path.endswith(ALLOWED_SUFFIXES):
        raise GeneratedCodeInvalid(f"unsupported file type: {raw!r}")
    if path in PROTECTED_PATHS:
        raise GeneratedCodeInvalid(f"{path} is provided by the scaffold and cannot be replaced")

    return path


def validate_generated_files(files: list[dict], entry_point: str = "src/App.jsx") -> list[dict]:
    """Return normalized files, or raise :class:`GeneratedCodeInvalid`.

    Enforces: a present entry point, safe paths, supported types, size caps, and
    the absence of patterns generated UI code has no legitimate need for.
    """
    if not files:
        raise GeneratedCodeInvalid("the model returned no files")
    if len(files) > MAX_FILES:
        raise GeneratedCodeInvalid(f"too many files ({len(files)} > {MAX_FILES})")

    normalized: list[dict] = []
    seen: set[str] = set()
    total_bytes = 0

    for item in files:
        if not isinstance(item, dict) or "path" not in item or "content" not in item:
            raise GeneratedCodeInvalid("each generated file needs a 'path' and 'content'")

        path = _normalized_path(item["path"])
        if path in seen:
            raise GeneratedCodeInvalid(f"duplicate file path: {path}")
        seen.add(path)

        content = item["content"]
        if not isinstance(content, str) or not content.strip():
            raise GeneratedCodeInvalid(f"{path} is empty")

        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise GeneratedCodeInvalid(f"{path} is too large ({size} bytes)")
        total_bytes += size

        for pattern, description in FORBIDDEN_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                raise GeneratedCodeInvalid(f"{path} {description}, which is not allowed")

        normalized.append({"path": path, "content": content})

    if total_bytes > MAX_TOTAL_BYTES:
        raise GeneratedCodeInvalid(f"generated project is too large ({total_bytes} bytes)")

    if not any(f["path"] == entry_point for f in normalized):
        raise GeneratedCodeInvalid(f"the model did not produce the entry point {entry_point}")

    return normalized


def uses_lead_capture(files: list[dict]) -> bool:
    """Whether the generated app actually calls the lead-capture SDK.

    A lead magnet that never submits a lead is a failed generation, however good it
    looks. The caller feeds this back to the model as a retry reason.
    """
    return any(re.search(r"\bsubmitLead\s*\(", f["content"]) for f in files)


def uses_decision_runtime(files: list[dict]) -> bool:
    """Whether result logic is delegated to the deterministic runtime contract."""
    return any(re.search(r"\bcalculateDecision\s*\(", f["content"]) for f in files)


def reads_live_config(files: list[dict]) -> bool:
    """Whether the app renders from the owner's current configuration."""
    return any(re.search(r"\buseLiveConfig\s*\(", f["content"]) for f in files)


# The funnel the workspace reports on. Impressions are recorded by the runtime
# itself; these three are the ones only the app knows the moment for, and
# without them the analytics screen shows visitors and leads with nothing in
# between — which reads as "nobody engaged" rather than "we did not measure".
_REQUIRED_MILESTONES = ("trackStart", "trackComplete", "trackResult")


def missing_milestones(files: list[dict]) -> list[str]:
    """Funnel milestones the generated app never reports."""
    return [
        name
        for name in _REQUIRED_MILESTONES
        if not any(re.search(rf"\b{name}\s*\(", f["content"]) for f in files)
    ]


# Short strings are not evidence of anything: "Yes", "Your budget" and "Email"
# will legitimately appear in generated markup no matter where the question list
# came from. A whole sentence appearing verbatim is a different matter.
_COPY_MATCH_MIN_LENGTH = 16


def _editable_copy(decision_spec: dict | None, outcomes: dict | None) -> list[str]:
    """The strings an owner can change after the build, worth checking for.

    Deliberately narrow. These are exactly the fields the question and result
    editors write to — the ones the product tells the owner are live the moment
    they save. Everything else the model writes is its own copy and may be
    hardcoded freely.
    """
    candidates: list[str] = []

    for question in (decision_spec or {}).get("questions") or []:
        if isinstance(question, dict):
            candidates.append(str(question.get("label") or ""))
            candidates.append(str(question.get("help_text") or ""))

    for band in (outcomes or {}).get("bands") or []:
        if isinstance(band, dict):
            candidates.append(str(band.get("label") or ""))
            candidates.append(str(band.get("description") or ""))

    for block in (outcomes or {}).get("advice") or []:
        if isinstance(block, dict):
            candidates.append(str(block.get("text") or ""))

    return [text for text in (c.strip() for c in candidates) if len(text) >= _COPY_MATCH_MIN_LENGTH]


def frozen_copy_in(
    files: list[dict],
    decision_spec: dict | None,
    outcomes: dict | None,
) -> list[str]:
    """Owner-editable copy the model wrote into the source as a literal.

    This is how "your edit is live" quietly became untrue. The runtime hands the
    app the owner's current questions and score bands, but nothing stopped the
    model from also typing them into the JSX. When it did, the deployed tool went
    on asking the questions it was born with while ``calculateDecision`` scored
    the visitor against the owner's new ones — the visible half and the scoring
    half disagreeing, with no error anywhere to say so.

    A literal match is strong evidence: code that maps over ``config.decisionSpec
    .questions`` cannot contain the question's own wording.
    """
    found: list[str] = []
    for text in _editable_copy(decision_spec, outcomes):
        if any(text in item["content"] for item in files):
            found.append(text)
    return found


# Tailwind's motion utilities. A generated app that uses any of these is
# animating, and therefore owes the visitor a way out of it.
_MOTION_PATTERN = re.compile(
    r"\b(?:"
    r"transition(?:-all|-colors|-opacity|-transform|-shadow)?"
    r"|animate-(?!none)[a-z-]+"
    r"|duration-\d+"
    r")\b"
)

# Either Tailwind's variant, or the media query written by hand — both are real
# answers, and a generated counter that reads the media query in JS is the only
# way to skip a tween rather than merely shorten it.
_REDUCED_MOTION_PATTERN = re.compile(r"motion-reduce:|prefers-reduced-motion")


def respects_reduced_motion(files: list[dict]) -> bool:
    """Whether an animating app also honours ``prefers-reduced-motion``.

    The system prompt asks for animated counters and state transitions, which
    means every generated widget animates by default. For a visitor with
    vestibular disorders that setting is not a preference, it is why they turned
    it on — and unlike most accessibility failures this one is mechanically
    checkable, so it is checked rather than hoped for.

    An app that animates nothing at all passes: there is nothing to opt out of.
    """
    animating = [f for f in files if _MOTION_PATTERN.search(f["content"])]
    if not animating:
        return True
    return any(_REDUCED_MOTION_PATTERN.search(f["content"]) for f in files)
