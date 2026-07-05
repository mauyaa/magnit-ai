import logging
import os
import re

import httpx

from app.platform.config.settings import settings
from app.platform.pipeline.schemas import DeploymentResult, WidgetCode

logger = logging.getLogger(__name__)


import re


def _sanitize_code(code: str) -> str:
    lines = code.split("\n")
    cleaned = []
    lucide_imports = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import React") or stripped.startswith("import {") and "lucide-react" in stripped:
            if "lucide-react" in stripped:
                match = re.search(r"\{\s*([^}]+)\}\s*from\s*['\"]lucide-react['\"]", stripped)
                if match:
                    cleaned.append(f"const {{ {match.group(1).strip()} }} = LucideReact;")
                    lucide_imports = True
            continue
        if stripped.startswith("export "):
            continue
        cleaned.append(line)
    if not lucide_imports:
        cleaned.insert(0, "const {} = LucideReact;")
    code = "\n".join(cleaned)
    code = re.sub(r":\s*(React\.\w+|\w+(?:<[^>]*>)?)(\s*[=,;)\]}])", r"\2", code)
    code = re.sub(r":\s*\w+(?:\s*\|\s*\w+)*(\s*[=,;)\]}])", r"\1", code)
    code = re.sub(r"(\w+)(<[^>]*>)(\s*\()", r"\1\3", code)
    code = code.replace("{ maximumFractionDigits }", "{ maximumFractionDigits: 2 }")
    return code


def _component_name(code: str) -> str:
    m = re.search(r"(?:const|function)\s+(\w+)\s*[=(]", code)
    return m.group(1) if m else "Widget"


def build_widget_html(source_code: str) -> str:
    source_code = _sanitize_code(source_code)
    comp = _component_name(source_code)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body>
  <div id="root"></div>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://unpkg.com/lucide-react@0.263.1/dist/umd/lucide-react.js"></script>
  <script type="text/babel" data-presets="react">
    {source_code}
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement({comp}));
  </script>
</body>
</html>"""


async def _disable_sso(project_id: str) -> None:
    headers = {
        "Authorization": f"Bearer {settings.vercel_api_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"https://api.vercel.com/v9/projects/{project_id}",
            headers=headers,
            json={"ssoProtection": None},
        )
        if resp.status_code != 200:
            logger.warning("Failed to disable SSO for project %s: %s", project_id, resp.text)


async def _deploy_vercel(files: list[dict], widget_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {settings.vercel_api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "name": f"magai-widget-{widget_id[:8]}",
        "files": files,
        "target": "production",
        "projectSettings": {
            "framework": None,
            "devCommand": None,
            "installCommand": None,
            "buildCommand": None,
            "outputDirectory": None,
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            params={"skipAutoDetectionConfirmation": "1"},
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Vercel deploy failed: {resp.status_code} {resp.text}")

        data = resp.json()
        url = data.get("url", "")
        if not url:
            raise RuntimeError("Vercel returned no URL")

        project_id = data.get("projectId")
        if project_id:
            await _disable_sso(project_id)

        return f"https://{url}"


async def deploy_widget(widget_code: WidgetCode, widget_id: str) -> DeploymentResult:
    html = build_widget_html(widget_code.source_code if hasattr(widget_code, 'source_code') else "")

    if settings.vercel_api_token:
        url = await _deploy_vercel(
            [{"file": "index.html", "data": html}], widget_id
        )
    else:
        raise RuntimeError(
            "MAGAI_VERCEL_API_TOKEN not set. Configure it in .env to deploy widgets."
        )

    return DeploymentResult(url=url, widget_id=widget_id)


async def deploy_directory(dist_dir: str, widget_id: str) -> DeploymentResult:
    if not os.path.isdir(dist_dir):
        raise RuntimeError(f"Dist directory not found: {dist_dir}")

    files = []
    for root, dirs, filenames in os.walk(dist_dir):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, dist_dir)
            with open(fpath, "r", encoding="utf-8") as f:
                files.append({"file": rel_path, "data": f.read()})

    if settings.vercel_api_token:
        url = await _deploy_vercel(files, widget_id)
    else:
        raise RuntimeError(
            "MAGAI_VERCEL_API_TOKEN not set. Configure it in .env to deploy widgets."
        )

    return DeploymentResult(url=url, widget_id=widget_id)
