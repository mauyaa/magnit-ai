import asyncio
import logging
import os

import httpx

from app.platform.config.settings import settings
from app.platform.pipeline.schemas import DeploymentResult

logger = logging.getLogger(__name__)


def _vercel_headers() -> dict[str, str]:
    if not settings.vercel_api_token:
        raise RuntimeError(
            "MAGAI_VERCEL_API_TOKEN not set. Configure it in .env to manage deployments."
        )
    return {
        "Authorization": f"Bearer {settings.vercel_api_token}",
        "Content-Type": "application/json",
    }


async def _disable_sso(project_id: str) -> None:
    headers = _vercel_headers()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"https://api.vercel.com/v9/projects/{project_id}",
            headers=headers,
            json={"ssoProtection": None},
        )
        if resp.status_code != 200:
            logger.warning("Failed to disable SSO for project %s: %s", project_id, resp.text)


async def _deploy_vercel(files: list[dict], widget_id: str) -> str:
    headers = _vercel_headers()
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


def _read_dist_files(dist_dir: str) -> list[dict]:
    """Read a built directory into Vercel's file payload format.

    Synchronous by design and called via ``asyncio.to_thread``: a widget build can
    contain dozens of files, and reading them inline would block the event loop for
    the whole walk.
    """
    if not os.path.isdir(dist_dir):
        raise RuntimeError(f"Dist directory not found: {dist_dir}")

    files: list[dict] = []
    for root, _dirs, filenames in os.walk(dist_dir):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, dist_dir).replace(os.sep, "/")
            with open(fpath, encoding="utf-8") as handle:
                files.append({"file": rel_path, "data": handle.read()})

    if not files:
        raise RuntimeError(f"Dist directory is empty: {dist_dir}")
    return files


async def deploy_directory(dist_dir: str, widget_id: str) -> DeploymentResult:
    if not settings.vercel_api_token:
        raise RuntimeError(
            "MAGAI_VERCEL_API_TOKEN not set. Configure it in .env to deploy widgets."
        )

    files = await asyncio.to_thread(_read_dist_files, dist_dir)
    url = await _deploy_vercel(files, widget_id)
    return DeploymentResult(url=url, widget_id=widget_id)


def _project_name(widget_id: str) -> str:
    return f"magai-widget-{widget_id[:8]}"


async def add_project_domain(widget_id: str, hostname: str) -> dict:
    """Assign a hostname to the tool's stable Vercel project."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://api.vercel.com/v10/projects/{_project_name(widget_id)}/domains",
            headers=_vercel_headers(),
            json={"name": hostname},
        )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Vercel domain assignment failed: {response.status_code} {response.text}"
        )
    # httpx types .json() as Any; the payload is a JSON object here, and saying
    # so keeps the declared return type honest rather than laundering Any.
    payload: dict = response.json()
    return payload


async def verify_project_domain(widget_id: str, hostname: str) -> dict:
    """Ask Vercel to re-check the current DNS verification challenge."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            (
                f"https://api.vercel.com/v9/projects/{_project_name(widget_id)}"
                f"/domains/{hostname}/verify"
            ),
            headers=_vercel_headers(),
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Vercel domain verification failed: {response.status_code} {response.text}"
        )
    payload: dict = response.json()
    return payload


async def remove_project_domain(widget_id: str, hostname: str) -> None:
    """Detach a hostname from its tool before the local record is removed."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(
            (f"https://api.vercel.com/v9/projects/{_project_name(widget_id)}/domains/{hostname}"),
            headers=_vercel_headers(),
        )
    if response.status_code not in (200, 204, 404):
        raise RuntimeError(f"Vercel domain removal failed: {response.status_code} {response.text}")
