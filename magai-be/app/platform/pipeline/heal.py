"""Self-heal detection: brand drift and deployment health.

Two checks run against every active widget on a schedule:

*brand drift* — re-extract the source site's brand and compare it with what the
widget was actually built from. A rebrand upstream leaves the widget visibly
stale, and that is the failure mode this product exists to fix.

*deployment health* — confirm the widget's live URL still serves. Vercel
deployments can be deleted, a project can be re-protected, DNS can lapse.

Deliberately *not* checked: host-page DOM or layout changes. Widgets render inside
a sandboxed iframe, so the host page's CSS cannot reach in and break their layout.
Claiming to repair that would be marketing, not engineering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.features.widgets.models import Widget
from app.platform.pipeline.engine import run_architect_stage
from app.platform.pipeline.evidence import collect_site_evidence
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    SiteEvidence,
    WidgetType,
)
from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url

logger = logging.getLogger(__name__)

# Fields whose drift is visible in the rendered widget. Fuzzier descriptors like
# `tone` or `decorative_elements` are free-text and re-word themselves between
# runs, which would produce false-positive rebuilds, so they are excluded.
BRAND_DRIFT_FIELDS = ("primary_color", "secondary_color", "background_color", "font_headings")
VISUAL_DRIFT_FIELDS = ("layout", "card_style")

HEALTH_CHECK_TIMEOUT_SECONDS = 10.0


@dataclass
class DriftResult:
    drifted: bool
    diff: dict[str, dict[str, str]]
    architect_output: ArchitectOutput | None
    evidence: SiteEvidence


def _widget_blueprint(widget: Widget) -> Blueprint:
    """Reconstruct a minimal blueprint for re-running the architect stage."""
    return Blueprint(
        type=WidgetType(widget.widget_type),
        title=widget.title,
        description="",
        rationale="",
    )


def _diff_fields(old: dict, new: dict, fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Compare selected keys, ignoring absent baselines.

    A missing ``old`` value means the widget predates that field being recorded —
    not that it drifted — so it is skipped rather than reported as a change.
    """
    diff: dict[str, dict[str, str]] = {}
    for key in fields:
        old_val, new_val = old.get(key), new.get(key)
        if not old_val or not new_val:
            continue
        if str(old_val).strip().lower() != str(new_val).strip().lower():
            diff[key] = {"old": str(old_val), "new": str(new_val)}
    return diff


async def check_brand_drift(widget: Widget) -> DriftResult:
    """Re-extract the source brand and diff it against the widget's baseline."""
    # Re-validate on every sweep: a domain can change hands or start resolving
    # into private space long after the widget was first created.
    safe_url = validate_target_url(widget.target_url)
    evidence = await collect_site_evidence(safe_url)
    if (
        widget.source_brand_fingerprint
        and widget.source_brand_fingerprint == evidence.brand_fingerprint
    ):
        return DriftResult(
            drifted=False,
            diff={},
            architect_output=None,
            evidence=evidence,
        )

    blueprint = _widget_blueprint(widget)
    fresh = await run_architect_stage(blueprint, evidence.target_url, evidence)

    diff = {
        **_diff_fields(widget.brand_tokens or {}, fresh.brand.model_dump(), BRAND_DRIFT_FIELDS),
        **_diff_fields(
            widget.visual_language or {},
            fresh.visual_language.model_dump(),
            VISUAL_DRIFT_FIELDS,
        ),
    }
    return DriftResult(
        drifted=bool(diff),
        diff=diff,
        architect_output=fresh,
        evidence=evidence,
    )


async def check_deploy_health(widget: Widget) -> bool:
    """True when the widget's live URL serves successfully.

    Redirects are followed manually so each hop can be re-validated: a deployment
    that 302s into private address space would otherwise turn this health check
    into an SSRF primitive.
    """
    if not widget.deployment_url:
        return True

    try:
        url = validate_target_url(widget.deployment_url)
    except UnsafeTargetURL:
        logger.error(
            "Widget %s has a deployment_url that fails validation: %s",
            widget.id,
            widget.deployment_url,
        )
        return False

    try:
        async with httpx.AsyncClient(
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            for _ in range(5):
                response = await client.get(url)
                if not response.is_redirect:
                    return response.status_code < 400

                location = response.headers.get("location")
                if not location:
                    return False
                url = validate_target_url(str(httpx.URL(url).join(location)))

            logger.warning("Widget %s exceeded the redirect limit", widget.id)
            return False
    except UnsafeTargetURL:
        logger.error("Widget %s redirects to a disallowed address", widget.id)
        return False
    except httpx.HTTPError as exc:
        logger.warning("Deploy health check failed for widget %s: %s", widget.id, exc)
        return False
