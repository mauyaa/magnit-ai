import asyncio
import html
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Awaitable, Callable

from app.platform.pipeline.schemas import DesignTokens
from app.platform.pipeline.validation import (
    GeneratedCodeInvalid,
    respects_reduced_motion,
    uses_decision_runtime,
    uses_lead_capture,
    validate_generated_files,
)
from app.platform.pipeline.widget_runtime import (
    LEAD_FORM_CSS,
    RUNTIME_SDK_JS,
    google_fonts_href,
    render_runtime_config,
    render_tokens_css,
)

logger = logging.getLogger(__name__)


PACKAGE_JSON_TEMPLATE = {
    "name": "magai-widget",
    "private": True,
    "version": "1.0.0",
    "type": "module",
    "scripts": {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview",
    },
    "dependencies": {
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
        "lucide-react": "^0.263.1",
    },
    "devDependencies": {
        "@vitejs/plugin-react": "^4.3.4",
        "vite": "^6.0.0",
        "tailwindcss": "^3.4.17",
        "postcss": "^8.4.49",
        "autoprefixer": "^10.4.20",
    },
}

VITE_CONFIG = """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist' },
});
"""

TAILWIND_CONFIG = """/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-soft': 'bounceSoft 1s infinite',
        'spin-slow': 'spin 3s linear infinite',
        'float': 'float 6s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
        bounceSoft: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      boxShadow: {
        'glow': '0 0 20px rgba(59, 130, 246, 0.5)',
        'glow-lg': '0 0 40px rgba(59, 130, 246, 0.6)',
        'inner-glow': 'inset 0 0 20px rgba(255, 255, 255, 0.1)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
};
"""

POSTCSS_CONFIG = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""

INDEX_CSS = """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  * {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  
  *:focus {
    outline: none;
  }
  
  *:focus-visible {
    outline: 2px solid var(--color-primary, #3b82f6);
    outline-offset: 2px;
    border-radius: 4px;
  }
}

@layer components {
  .app-container {
    @apply min-h-screen p-4 md:p-8;
  }
  
  .app-card {
    @apply mx-auto max-w-lg rounded-2xl p-6 md:p-8;
    transition: all 0.3s ease;
  }
  
  .app-input {
    @apply w-full rounded-xl border-2 px-4 py-3 transition-all duration-200;
    background: var(--input-bg, #f8fafc);
    border-color: var(--input-border, #e2e8f0);
    color: var(--color-secondary, #1e293b);
  }
  
  .app-input::placeholder {
    color: var(--input-placeholder, #94a3b8);
  }
  
  .app-input:focus {
    border-color: var(--input-focus-ring, var(--color-primary, #3b82f6));
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    outline: none;
  }
  
  .app-button {
    @apply w-full rounded-xl px-6 py-4 font-semibold transition-all duration-200;
    background: var(
      --button-bg,
      linear-gradient(135deg, var(--color-primary, #3b82f6), var(--color-accent, #8b5cf6))
    );
    color: var(--button-text, #ffffff);
  }
  
  .app-button:hover {
    transform: scale(1.02);
    box-shadow: var(--button-hover-shadow, 0 10px 30px -10px var(--color-primary, #3b82f6));
  }
  
  .app-button:active {
    transform: scale(0.98);
  }
  
  .gradient-text {
    @apply bg-clip-text text-transparent;
    background-image: linear-gradient(
      135deg, var(--color-primary, #3b82f6), var(--color-accent, #8b5cf6)
    );
  }
}
"""


def render_index_html(title: str, fonts_href: str | None, api_base_url: str) -> str:
    """Build the entry HTML for a generated widget.

    Two things the previous hardcoded template got wrong: the title was always
    "Lead Magnet App" (visible in the iframe's accessible name), and the font link
    requested four fixed families regardless of the brand's actual fonts.

    The CSP is scoped to what a generated widget legitimately needs: its own
    bundle, inline styles from Tailwind, Google Fonts, and XHR back to this API for
    lead submission. Everything else — remote scripts, frames, objects — is denied,
    which bounds what model-generated code can do in a visitor's browser.
    """
    safe_title = html.escape(title or "Interactive tool", quote=True)
    font_origins = " https://fonts.googleapis.com https://fonts.gstatic.com" if fonts_href else ""

    csp = (
        "default-src 'none'; "
        "script-src 'self'; "
        f"style-src 'self' 'unsafe-inline'{font_origins}; "
        f"font-src 'self'{font_origins}; "
        "img-src 'self' data:; "
        f"connect-src 'self' {api_base_url}; "
        "form-action 'none'; "
        "base-uri 'none'; "
        "frame-src 'none'; "
        "object-src 'none'"
    )

    font_tags = ""
    if fonts_href:
        font_tags = (
            '\n    <link rel="preconnect" href="https://fonts.googleapis.com">'
            '\n    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'\n    <link href="{html.escape(fonts_href, quote=True)}" rel="stylesheet">'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=True)}" />
    <meta name="referrer" content="no-referrer-when-downgrade" />
    <title>{safe_title}</title>{font_tags}
  </head>
  <body class="antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""


# Imports tokens.css before index.css so Tailwind's utilities can reference the
# variables, and records an impression on mount so submissions have a denominator.
MAIN_JSX = """import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { trackImpression } from './lib/magnitai.js';
import './tokens.css';
import './index.css';

function Root() {
  useEffect(() => {
    trackImpression();
  }, []);
  return <App />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
"""

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".template-project")


# Serializes template creation within a worker process. Two builds starting
# concurrently on a cold cache would otherwise both rmtree and re-install into the
# same directory, and the loser would scaffold from a half-installed template.
_template_lock = threading.Lock()


def _template_is_ready() -> bool:
    return os.path.isdir(TEMPLATE_DIR) and os.path.isdir(f"{TEMPLATE_DIR}/node_modules/.pnpm")


def _ensure_template() -> str:
    """Create (once) a pre-installed template project and return its path.

    Dependencies are installed a single time and the resulting ``node_modules`` is
    reused for every build, which is the difference between a ~90s and a ~5s
    scaffold step.
    """
    if _template_is_ready():
        return TEMPLATE_DIR

    with _template_lock:
        # Re-check: another thread may have finished while we waited.
        if _template_is_ready():
            return TEMPLATE_DIR

        staging = f"{TEMPLATE_DIR}.building"
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(TEMPLATE_DIR, ignore_errors=True)

        logger.info("Creating pnpm template project at %s", TEMPLATE_DIR)
        os.makedirs(f"{staging}/src", exist_ok=True)

        for path, content in [
            ("package.json", json.dumps(PACKAGE_JSON_TEMPLATE, indent=2)),
            ("vite.config.js", VITE_CONFIG),
            ("tailwind.config.js", TAILWIND_CONFIG),
            ("postcss.config.js", POSTCSS_CONFIG),
        ]:
            with open(f"{staging}/{path}", "w", encoding="utf-8") as handle:
                handle.write(content)

        # Fixed argument list, no shell: nothing here is caller-controlled.
        result = subprocess.run(
            ["pnpm", "install", "--prefer-offline"],  # noqa: S607
            cwd=staging,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            logger.error("pnpm install in template failed:\n%s", result.stderr[:2000])
            raise RuntimeError(f"pnpm install failed for template:\n{result.stderr[:2000]}")

        # Atomic-ish publish: the ready-marker directory only appears once the
        # install has fully succeeded.
        os.rename(staging, TEMPLATE_DIR)
        logger.info("pnpm template ready at %s", TEMPLATE_DIR)

    return TEMPLATE_DIR


def _write_file(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _scaffold_project(
    project_dir: str,
    files: list[dict],
    *,
    widget_id: str,
    widget_title: str,
    api_base_url: str,
    design_tokens: DesignTokens,
    decision_spec: dict | None,
    outcomes: dict | None = None,
) -> None:
    """Assemble a buildable project: template, injected runtime, generated UI.

    Write order matters. The scaffold's own files (including our hand-written
    runtime SDK and the design-token stylesheet) are written *after* the template
    copy and *before* the generated files — and ``validate_generated_files`` has
    already rejected any generated path that would collide with them.
    """
    template = _ensure_template()

    for item in os.listdir(template):
        src = os.path.join(template, item)
        dst = os.path.join(project_dir, item)
        if item == "node_modules":
            if not os.path.isdir(dst):
                shutil.copytree(src, dst, symlinks=True)
            continue
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    fonts_href = google_fonts_href(design_tokens.css_variables or {})

    for path, content in [
        ("index.html", render_index_html(widget_title, fonts_href, api_base_url)),
        ("src/main.jsx", MAIN_JSX),
        ("src/index.css", INDEX_CSS + LEAD_FORM_CSS),
        # The brand's tokens as a real :root block — without this every
        # var(--color-*) in the generated markup resolves to nothing.
        ("src/tokens.css", render_tokens_css(design_tokens)),
        (
            "src/config.js",
            render_runtime_config(widget_id, api_base_url, decision_spec, outcomes),
        ),
        ("src/lib/magnitai.js", RUNTIME_SDK_JS),
    ]:
        _write_file(os.path.join(project_dir, path), content)

    # Distinct name from the template-copy loop above, whose `item` is a filename
    # string rather than a generated-file mapping.
    for generated in files:
        _write_file(os.path.join(project_dir, generated["path"]), generated["content"])


async def _run_cmd(cmd: list[str], cwd: str, timeout_seconds: int = 180) -> tuple[int, str, str]:
    """Run a command, returning ``(returncode, stdout, stderr)``.

    The timeout is handled here rather than by the caller because a subprocess must
    be explicitly killed on expiry — an outer ``asyncio.timeout`` would abandon a
    still-running pnpm process and leak it for the life of the worker.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        return (
            proc.returncode or 0,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()  # Reap it, so no zombie is left behind.
        return -1, "", f"build timed out after {timeout_seconds}s"


async def _run_build(project_dir: str) -> tuple[bool, str]:
    code, stdout, stderr = await _run_cmd(["pnpm", "build"], project_dir)
    if code != 0:
        # Vite writes some diagnostics to stdout, so include both streams or the
        # retry feedback can end up empty and useless to the model.
        details = (stderr or stdout or "no output").strip()
        return False, f"pnpm build failed:\n{details[:2000]}"
    return True, ""


def _clean_sandbox(sandbox: str) -> None:
    for item in os.listdir(sandbox):
        if item == "node_modules":
            continue
        path = os.path.join(sandbox, item)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)


def _copy_without_node_modules(src: str, dst: str) -> None:
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        src_path = os.path.join(src, item)
        if item == "node_modules":
            continue
        dst_path = os.path.join(dst, item)
        if os.path.isdir(src_path):
            shutil.copytree(
                src_path,
                dst_path,
                ignore=shutil.ignore_patterns("node_modules"),
                dirs_exist_ok=True,
            )
        else:
            shutil.copy2(src_path, dst_path)


async def build_project(
    project_dir: str,
    files: list[dict],
    *,
    widget_id: str,
    widget_title: str,
    api_base_url: str,
    design_tokens: DesignTokens,
    decision_spec: dict | None = None,
    outcomes: dict | None = None,
    max_attempts: int = 3,
    gen_callback: Callable[[str], Awaitable[list[dict]]] | None = None,
) -> tuple[bool, str]:
    """Validate, scaffold, and build a generated widget in a disposable sandbox.

    Each attempt can fail for three distinct reasons, and all three are fed back to
    the model as concrete feedback rather than being retried blindly:

    1. validation rejected the output (bad path, missing entry point, forbidden API)
    2. no call to ``submitLead`` — a lead magnet that cannot capture a lead
    3. the Vite build itself failed, with the compiler's own errors

    Returns ``(True, project_dir)`` or ``(False, reason)``.
    """
    sandbox = tempfile.mkdtemp(prefix="magai-sandbox-")
    last_error = "build never ran"

    try:
        for attempt in range(1, max_attempts + 1):
            try:
                validated = validate_generated_files(files)
            except GeneratedCodeInvalid as exc:
                last_error = f"Generated code rejected: {exc}"
                logger.warning("Attempt %d/%d — %s", attempt, max_attempts, last_error)
                if attempt == max_attempts or not gen_callback:
                    return False, last_error
                files = await gen_callback(last_error)
                continue

            # Enforced rather than merely requested: the whole product is lead
            # capture, so a widget that never submits one is a failed generation.
            if not uses_lead_capture(validated):
                last_error = (
                    "The app never calls submitLead() from './lib/magnitai.js'. "
                    "Add an email capture step that calls it before showing the result."
                )
                logger.warning("Attempt %d/%d — no lead capture", attempt, max_attempts)
                if attempt == max_attempts or not gen_callback:
                    return False, last_error
                files = await gen_callback(last_error)
                continue

            # Every generated widget animates — the system prompt asks for
            # animated counters and state transitions. That makes a missing
            # reduced-motion fallback a defect shipped to every visitor of every
            # customer site, and it is one of the few accessibility failures a
            # machine can actually detect, so it is enforced rather than asked for.
            if not respects_reduced_motion(validated):
                last_error = (
                    "The app animates but never honours prefers-reduced-motion. "
                    "Add Tailwind's `motion-reduce:` variant to every transition and "
                    "animation (e.g. `transition-transform motion-reduce:transition-none`), "
                    "and for animated counters read "
                    "window.matchMedia('(prefers-reduced-motion: reduce)') and set the "
                    "final value immediately instead of tweening to it."
                )
                logger.warning("Attempt %d/%d - no reduced-motion fallback", attempt, max_attempts)
                if attempt == max_attempts or not gen_callback:
                    return False, last_error
                files = await gen_callback(last_error)
                continue

            if decision_spec is not None and not uses_decision_runtime(validated):
                last_error = (
                    "The app never calls calculateDecision(answers) from "
                    "'./lib/magnitai.js'. Use the runtime result instead of "
                    "implementing or inventing calculation logic."
                )
                logger.warning("Attempt %d/%d - no decision runtime", attempt, max_attempts)
                if attempt == max_attempts or not gen_callback:
                    return False, last_error
                files = await gen_callback(last_error)
                continue

            await asyncio.to_thread(_clean_sandbox, sandbox)
            await asyncio.to_thread(
                _scaffold_project,
                sandbox,
                validated,
                widget_id=widget_id,
                widget_title=widget_title,
                api_base_url=api_base_url,
                design_tokens=design_tokens,
                decision_spec=decision_spec,
                outcomes=outcomes,
            )

            success, output = await _run_build(sandbox)
            if success:
                # A build can exit zero yet emit nothing usable; the served
                # artifact is index.html plus its hashed assets.
                index_exists = await asyncio.to_thread(
                    os.path.isfile, os.path.join(sandbox, "dist", "index.html")
                )
                if not index_exists:
                    last_error = "Build reported success but produced no dist/index.html"
                    logger.warning("Attempt %d/%d — %s", attempt, max_attempts, last_error)
                    if attempt == max_attempts or not gen_callback:
                        return False, last_error
                    files = await gen_callback(last_error)
                    continue

                logger.info("Build succeeded on attempt %d/%d", attempt, max_attempts)
                await asyncio.to_thread(_copy_without_node_modules, sandbox, project_dir)
                return True, project_dir

            last_error = output
            logger.warning("Build failed on attempt %d/%d", attempt, max_attempts)
            if attempt == max_attempts or not gen_callback:
                logger.error("Build failed after %d attempts:\n%s", attempt, output[:2000])
                return False, last_error

            files = await gen_callback(output)

        return False, last_error
    finally:
        await asyncio.to_thread(shutil.rmtree, sandbox, ignore_errors=True)
