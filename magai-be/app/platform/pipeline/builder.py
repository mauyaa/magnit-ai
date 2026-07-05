import asyncio
import json
import logging
import os
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
  theme: { extend: {} },
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
"""

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Widget</title>
  </head>
  <body>
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


def _scaffold_project(project_dir: str, files: list[dict]) -> None:
    os.makedirs(f"{project_dir}/src", exist_ok=True)

    with open(f"{project_dir}/package.json", "w") as f:
        json.dump(PACKAGE_JSON_TEMPLATE, f, indent=2)
    with open(f"{project_dir}/vite.config.js", "w") as f:
        f.write(VITE_CONFIG)
    with open(f"{project_dir}/tailwind.config.js", "w") as f:
        f.write(TAILWIND_CONFIG)
    with open(f"{project_dir}/postcss.config.js", "w") as f:
        f.write(POSTCSS_CONFIG)
    with open(f"{project_dir}/index.html", "w") as f:
        f.write(INDEX_HTML)
    with open(f"{project_dir}/src/index.css", "w") as f:
        f.write(INDEX_CSS)
    with open(f"{project_dir}/src/main.jsx", "w") as f:
        f.write(MAIN_JSX)

    for f in files:
        filepath = f"{project_dir}/{f['path']}"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as out:
            out.write(f["content"])


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
    code, out, err = await _run_cmd(["pnpm", "install"], project_dir)
    if code != 0:
        return False, f"pnpm install failed:\n{err[:2000]}"

    code, out, err = await _run_cmd(["pnpm", "build"], project_dir)
    if code != 0:
        return False, f"pnpm build failed:\n{err[:2000]}"

    return True, ""


async def build_project(
    project_dir: str, files: list[dict], max_retries: int = 3, gen_callback=None
) -> tuple[bool, str]:
    _scaffold_project(project_dir, files)

    for attempt in range(max_retries):
        success, output = await _run_build(project_dir)
        if success:
            dist = f"{project_dir}/dist"
            if os.path.exists(f"{dist}/assets"):
                logger.info("Build succeeded on attempt %d/%d", attempt + 1, max_retries)
                return True, project_dir

            logger.warning("Build succeeded but no dist/assets found")
            return True, project_dir

        logger.warning("Build failed attempt %d/%d: %s", attempt + 1, max_retries, output[:200])

        if attempt == max_retries - 1 or not gen_callback:
            return False, output

        files = await gen_callback(output)

        _scaffold_project(project_dir, files)

    return False, "Max retries exceeded"
