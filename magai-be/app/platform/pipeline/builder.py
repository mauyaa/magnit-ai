import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

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
    background: var(--button-bg, linear-gradient(135deg, var(--color-primary, #3b82f6), var(--color-accent, #8b5cf6)));
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
    background-image: linear-gradient(135deg, var(--color-primary, #3b82f6), var(--color-accent, #8b5cf6));
  }
}
"""

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Lead Magnet App</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Poppins:wght@300;400;500;600;700;800;900&family=Playfair+Display:wght@400;500;600;700;800;900&family=Montserrat:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
  </head>
  <body class="antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

MAIN_JSX = """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".template-project"
)


def _ensure_template() -> str:
    if os.path.isdir(TEMPLATE_DIR) and os.path.isdir(f"{TEMPLATE_DIR}/node_modules/.pnpm"):
        return TEMPLATE_DIR

    if os.path.isdir(TEMPLATE_DIR):
        shutil.rmtree(TEMPLATE_DIR, ignore_errors=True)

    logger.info("Creating pnpm template project at %s", TEMPLATE_DIR)
    os.makedirs(f"{TEMPLATE_DIR}/src", exist_ok=True)

    for path, content in [
        ("package.json", lambda: json.dumps(PACKAGE_JSON_TEMPLATE, indent=2)),
        ("vite.config.js", lambda: VITE_CONFIG),
        ("tailwind.config.js", lambda: TAILWIND_CONFIG),
        ("postcss.config.js", lambda: POSTCSS_CONFIG),
        ("index.html", lambda: INDEX_HTML),
        ("src/index.css", lambda: INDEX_CSS),
        ("src/main.jsx", lambda: MAIN_JSX),
    ]:
        with open(f"{TEMPLATE_DIR}/{path}", "w") as f:
            f.write(content())

    import subprocess
    result = subprocess.run(
        ["pnpm", "install"],
        cwd=TEMPLATE_DIR,
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        logger.error("pnpm install in template failed:\n%s", result.stderr[:2000])
        raise RuntimeError(f"pnpm install failed for template:\n{result.stderr[:2000]}")
    logger.info("pnpm template ready at %s", TEMPLATE_DIR)

    return TEMPLATE_DIR


def _write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _scaffold_project(project_dir: str, files: list[dict]) -> None:
    template = _ensure_template()
    for item in os.listdir(template):
        src = os.path.join(template, item)
        dst = os.path.join(project_dir, item)
        if item == "node_modules":
            if not os.path.isdir(dst):
                shutil.copytree(src, dst, symlinks=True)
            continue
        elif os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    for f in files:
        _write_file(f"{project_dir}/{f['path']}", f["content"])


async def _run_cmd(cmd: list[str], cwd: str, timeout: int = 120) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "timed out"


async def _run_build(project_dir: str) -> tuple[bool, str]:
    code, out, err = await _run_cmd(["pnpm", "build"], project_dir)
    if code != 0:
        return False, f"pnpm build failed:\n{err[:2000]}"
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
            shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns("node_modules"), dirs_exist_ok=True)
        else:
            shutil.copy2(src_path, dst_path)


async def build_project(
    project_dir: str, files: list[dict], max_retries: int = 2, gen_callback=None
) -> tuple[bool, str]:
    sandbox = tempfile.mkdtemp(prefix="magai-sandbox-")

    try:
        await asyncio.to_thread(_scaffold_project, sandbox, files)

        for attempt in range(max_retries):
            success, output = await _run_build(sandbox)
            if success:
                dist = f"{sandbox}/dist"
                if os.path.exists(f"{dist}/assets"):
                    logger.info("Build succeeded on attempt %d/%d", attempt + 1, max_retries)
                    await asyncio.to_thread(_copy_without_node_modules, sandbox, project_dir)
                    return True, project_dir

                logger.warning("Build succeeded but no dist/assets found")
                await asyncio.to_thread(_copy_without_node_modules, sandbox, project_dir)
                return True, project_dir

            logger.warning("Build failed attempt %d/%d", attempt + 1, max_retries)

            if attempt == max_retries - 1 or not gen_callback:
                logger.warning("Build failed final attempt %d/%d:\n%s", attempt + 1, max_retries, output[:2000])
                return False, output

            files = await gen_callback(output)

            await asyncio.to_thread(_clean_sandbox, sandbox)
            await asyncio.to_thread(_scaffold_project, sandbox, files)

        return False, "Max retries exceeded"
    finally:
        await asyncio.to_thread(shutil.rmtree, sandbox, ignore_errors=True)
