from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from google.antigravity.types import AntigravityExecutionError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.auth.service import get_active_user
from app.features.billing.deps import CurrentEntitlements, upgrade_required
from app.features.billing.entitlements import (
    FeatureLocked,
    QuotaExceeded,
    effective_lead_cap,
    plan_lead_limit,
    record_usage,
    resolve_entitlements,
)
from app.features.billing.plans import Feature
from app.features.users.models import User
from app.features.widgets.models import Widget, WidgetDeployment, WidgetHealEvent
from app.features.widgets.outcomes import effective_outcome_config
from app.features.widgets.readiness import assess_readiness
from app.features.widgets.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ArchitectPreviewRequest,
    BuildRequest,
    BuildResponse,
    ClaimGuestConceptRequest,
    ClaimGuestConceptResponse,
    CuratedConcept,
    DecisionResponse,
    DeliveryTestResponse,
    DeploymentResponse,
    FunnelResponse,
    GuestConceptsResponse,
    HealEventResponse,
    ImpressionRequest,
    LaunchSetupRequest,
    LaunchSetupResponse,
    OutcomeConfigResponse,
    PortfolioAnalyticsResponse,
    ReadinessCheckResponse,
    ReadinessResponse,
    ResumeBuildResponse,
    RuntimeConfigResponse,
    SiteReadResponse,
    ToolTypeListResponse,
    ToolTypeResponse,
    TrackInteractionRequest,
    UpdateDecisionRequest,
    UpdateOutcomeConfigRequest,
    WidgetListResponse,
    WidgetStatusResponse,
)
from app.features.widgets.service import (
    InvalidGuestConceptSession,
    RollbackUnavailable,
    WidgetBuildMissing,
    WidgetNotFound,
    account_can_build,
    analyze_guest_url,
    analyze_url,
    architect_from_widget,
    claim_guest_concepts,
    configure_widget_launch,
    create_guest_concept_token,
    decision_spec_of,
    deploy_existing_widget,
    ensure_widget_evidence,
    get_owned_widget,
    list_deployments,
    list_heal_events,
    list_user_widgets,
    persist_architect,
    portfolio_analytics,
    put_decision_spec,
    read_guest_concept_token,
    record_impression,
    record_interaction,
    require_widget_entitlement,
    rollback_widget,
    test_widget_delivery,
    widget_can_build,
    widget_funnel,
)
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory, get_async_session
from app.platform.observability.metrics import (
    first_value_duration_seconds,
    product_activation_events_total,
)
from app.platform.pipeline.catalog import CATALOG, blueprint_for
from app.platform.pipeline.engine import run_architect_stage
from app.platform.pipeline.events import events as pipeline_events
from app.platform.pipeline.evidence import EvidenceCollectionError, collect_site_evidence
from app.platform.pipeline.fallback import grounded_architect
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    CreationBrief,
    SiteEvidence,
    WidgetType,
)
from app.platform.security.rate_limit import rate_limit
from app.platform.security.revocation import is_revoked
from app.platform.security.tokens import TokenError, decode_token
from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/widgets", tags=["widgets"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="widget_not_found")


def _require_verified_email(user: User) -> None:
    """Block spend-incurring actions until the address is confirmed.

    Analysis and builds each cost real Gemini and Vercel budget, so an unverified
    throwaway address must not be able to consume them. Reads stay open, so a new
    user is never stranded with an empty, unexplained dashboard.
    """
    if settings.require_verified_email_to_build and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="email_verification_required"
        )


async def _first_look_architect(
    blueprint: Blueprint,
    target_url: str,
    evidence: SiteEvidence,
    brief: CreationBrief,
) -> ArchitectOutput:
    try:
        return await run_architect_stage(blueprint, target_url, evidence, brief=brief)
    except (AntigravityExecutionError, TimeoutError):
        logger.warning(
            "Generation provider unavailable for %s; using grounded preview",
            target_url,
            exc_info=True,
        )
        return grounded_architect(blueprint, evidence, brief)


def _coerce_widget_id_for_public(widget_id: str) -> uuid.UUID | None:
    """Parse an id from an unauthenticated caller, or return ``None``.

    A non-UUID path segment can never match a row, and on PostgreSQL comparing it
    raises a DataError rather than returning nothing — which would turn a
    malformed public request into a 500.
    """
    try:
        return uuid.UUID(str(widget_id))
    except (ValueError, AttributeError, TypeError):
        return None


def _config_version(widget: Widget) -> str:
    """A short fingerprint of everything the runtime overlay contains.

    Lets a deployed widget skip a re-render when nothing it draws has changed,
    and gives support a value to compare when a customer says an edit "did not go
    through".
    """
    material = json.dumps(
        [widget.widget_logic, widget.outcome_config, widget.launch_settings, widget.consent_text],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(material.encode()).hexdigest()[:16]


async def _require_build_allowance(db: AsyncSession, widget: Widget) -> None:
    """Refuse a build with the specific reason, so the client can act on it.

    ``require_widget_entitlement`` raises three different exceptions for three
    different customer situations; collapsing them into one "payment_required"
    string — which is what the endpoints used to do — meant a customer who had
    simply used this month's builds was told to buy a plan they already had.
    """
    try:
        await require_widget_entitlement(db, widget)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="payment_required"
        ) from None
    except (FeatureLocked, QuotaExceeded) as exc:
        raise upgrade_required(exc) from None


async def _meter_build(db: AsyncSession, widget: Widget, reason: str) -> None:
    """Record one build against the workspace's monthly allowance.

    Written after the task is enqueued and inside the same transaction, so the
    two land together: metering a build that was never queued would charge a
    customer for nothing, and queueing one that was never metered is how a quota
    is escaped.
    """
    entitlements = await resolve_entitlements(db, widget.user_id)
    await record_usage(
        db,
        widget.user_id,
        "build",
        entitlements.plan.id,
        widget_id=widget.id,
        context={"reason": reason},
    )


def _conversion_rate(w: Widget) -> float | None:
    """Leads as a percentage of views, or ``None`` when there is no denominator."""
    if not w.impressions_count:
        return None
    return round(w.leads_count / w.impressions_count * 100, 1)


def _widget_to_response(
    w: Widget, *, can_build: bool | None = None, plan_leads: int = 0
) -> WidgetStatusResponse:
    """One tool, as the owner's workspace sees it.

    ``plan_leads`` is the subscription's per-tool lead allowance, resolved once
    per request by the caller. It is passed in rather than read here so a list of
    twenty tools does not become twenty subscription lookups — and so the number
    the dashboard shows is the same one lead capture actually enforces.
    """
    return WidgetStatusResponse(
        id=str(w.id),
        title=w.title,
        widget_type=w.widget_type,
        status=w.status,
        target_url=w.target_url,
        deployment_url=w.deployment_url,
        embed_url=w.embed_url,
        embed_code=w.embed_code,
        leads_count=w.leads_count,
        impressions_count=w.impressions_count,
        starts_count=w.starts_count,
        completions_count=w.completions_count,
        cta_clicks_count=w.cta_clicks_count,
        conversion_rate=_conversion_rate(w),
        plan_tier=w.plan_tier,
        lead_cap=effective_lead_cap(w.lead_cap, plan_leads),
        entitlement_status=w.entitlement_status,
        can_build=widget_can_build(w) if can_build is None else can_build,
        launch_settings=w.launch_settings,
        delivery_webhook_url=w.delivery_webhook_url,
        consent_text=w.consent_text,
        creation_brief=w.creation_brief,
        brand_tokens=w.brand_tokens,
        visual_language=w.visual_language,
        widget_logic=w.widget_logic,
        copywriting=w.copywriting,
        design_tokens=w.design_tokens,
        build_stage=w.build_stage,
        build_progress=w.build_progress,
        build_error=w.build_error,
        created_at=w.created_at.isoformat(),
        deployed_at=w.deployed_at.isoformat() if w.deployed_at else None,
        last_heal_check_at=(w.last_heal_check_at.isoformat() if w.last_heal_check_at else None),
        last_brand_check_at=(w.last_brand_check_at.isoformat() if w.last_brand_check_at else None),
    )


def _heal_event_to_response(e: WidgetHealEvent) -> HealEventResponse:
    return HealEventResponse(
        id=str(e.id),
        check_type=e.check_type,
        status=e.status,
        diff_summary=e.diff_summary,
        detected_at=e.detected_at.isoformat(),
        healed_at=e.healed_at.isoformat() if e.healed_at else None,
    )


def _deployment_to_response(d: WidgetDeployment) -> DeploymentResponse:
    return DeploymentResponse(
        id=str(d.id),
        deployment_url=d.deployment_url,
        trigger=d.trigger,
        is_current=d.is_current,
        created_at=d.created_at.isoformat(),
    )


def _stored_blueprints(widget: Widget) -> list[Blueprint]:
    """The directions we produced for this site, skipping any we can no longer read.

    Lenient on purpose: this is used to put a customer back where they were, and
    one unparseable entry should cost them that entry, not the whole draft and
    the site read that produced it.
    """
    parsed: list[Blueprint] = []
    for data in widget.blueprints or []:
        try:
            parsed.append(Blueprint(**data))
        except (ValidationError, TypeError):
            logger.warning("Widget %s has an unreadable blueprint", widget.id)
    return parsed


def _blueprint_at(widget: Widget, index: int) -> tuple[dict, Blueprint]:
    blueprints = widget.blueprints or []
    if index >= len(blueprints):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_blueprint_index"
        )
    data = blueprints[index]
    return data, Blueprint(**data)


def _chosen_blueprint(
    widget: Widget, index: int, widget_type: WidgetType | None
) -> tuple[dict, Blueprint]:
    """Resolve the customer's choice into a blueprint.

    Naming a type takes precedence over the index. If the analyzer happened to
    propose that type for this site we reuse its proposal — it has a real title
    and rationale grounded in the actual business — and otherwise synthesise a
    plain one for the Architect to flesh out.
    """
    if widget_type is None:
        return _blueprint_at(widget, index)

    for data in widget.blueprints or []:
        if data.get("type") == widget_type.value:
            return data, Blueprint(**data)

    # The customer's own description of what they wanted, captured at analyze
    # time. It is the whole brief for a CUSTOM tool and a sharper description
    # than the catalogue's generic line for a named one.
    stated_intent = (widget.creation_brief or {}).get("intent")
    blueprint = blueprint_for(
        widget_type,
        widget.target_url,
        intent=stated_intent if isinstance(stated_intent, str) else None,
    )
    return blueprint.model_dump(mode="json"), blueprint


def _enqueue_build(
    widget: Widget, blueprint_data: dict, skip_deploy: bool, architect_override: dict | None
) -> None:
    """Hand the build to Celery, translating a broker outage into a clear 503."""
    from app.platform.pipeline.tasks import build_widget_task

    try:
        # Build progress and completion are read from durable database state; the
        # API never consumes this task's AsyncResult. Publishing without a result
        # keeps a dead result backend from holding the request open through its
        # retry loop. This request is also the retry boundary, so a dead broker
        # becomes an immediate 503 rather than a minute-long loading state.
        build_widget_task.apply_async(
            kwargs={
                "widget_id": str(widget.id),
                "blueprint_dict": blueprint_data,
                "url": widget.target_url,
                "skip_deploy": skip_deploy,
                "architect_override_dict": architect_override,
                "source_evidence_dict": widget.source_evidence,
                "creation_brief_dict": widget.creation_brief,
            },
            ignore_result=True,
            retry=False,
        )
    except Exception:
        logger.exception("Failed to enqueue build for widget %s", widget.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="build_queue_unavailable",
        ) from None


def _dispatch_build(
    widget: Widget,
    blueprint_data: dict,
    skip_deploy: bool,
    architect_override: dict | None,
) -> None:
    """Use the local runner in development and Celery everywhere else."""
    if not settings.local_builds_enabled:
        _enqueue_build(widget, blueprint_data, skip_deploy, architect_override)
        return

    from app.platform.pipeline.tasks import schedule_local_widget_build

    schedule_local_widget_build(
        str(widget.id),
        blueprint_data,
        widget.target_url,
        publish=not skip_deploy,
        architect_override_dict=architect_override,
        source_evidence_dict=widget.source_evidence,
        creation_brief_dict=widget.creation_brief,
    )


@router.post(
    "/read-site",
    response_model=SiteReadResponse,
    dependencies=[rate_limit("guest_concepts")],
)
async def read_site_endpoint(payload: AnalyzeRequest) -> SiteReadResponse:
    """Crawl only — the fast half of the first look, answered on its own.

    Shares the guest rate limit with `/guest-concepts` deliberately: it is the
    same anonymous crawl of a caller-supplied URL, and giving it its own budget
    would just open a cheaper way to spend the same egress.
    """
    try:
        safe_url = validate_target_url(payload.url)
        evidence = await collect_site_evidence(safe_url)
    except (UnsafeTargetURL, EvidenceCollectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    return SiteReadResponse(
        target_url=evidence.target_url,
        domain=evidence.domain,
        business_name=evidence.business_name,
        summary=evidence.summary,
        pages_read=len(evidence.pages),
        signals_found=len(evidence.references),
        colors=evidence.brand.colors[:6],
        fonts=evidence.brand.fonts[:3],
        highlights=_distinct_highlights(evidence),
    )


def _distinct_highlights(evidence: SiteEvidence) -> list[str]:
    """A few different quotes, not the same sentence three times.

    A site's meta description usually repeats its hero heading, so taking the
    first few references verbatim shows the visitor one sentence twice and
    reads like a bug rather than a thorough read.
    """
    seen: set[str] = set()
    quotes: list[str] = []
    for reference in evidence.references:
        text = reference.text.strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        quotes.append(text)
        if len(quotes) == 4:
            break
    return quotes


@router.post(
    "/guest-concepts",
    response_model=GuestConceptsResponse,
    dependencies=[rate_limit("guest_concepts")],
)
async def guest_concepts_endpoint(payload: AnalyzeRequest) -> GuestConceptsResponse:
    """Return the one free, two-direction first look.

    Nothing is persisted before the visitor creates an account. A signed session
    token carries the trusted analysis across that account boundary.
    """
    started = time.perf_counter()
    product_activation_events_total.labels("first_look", "started").inc()
    try:
        brief = payload.brief or CreationBrief()
        target_url, analyzed, evidence = await analyze_guest_url(payload.url, brief)
    except (UnsafeTargetURL, EvidenceCollectionError) as exc:
        product_activation_events_total.labels("first_look", "failed").inc()
        first_value_duration_seconds.observe(time.perf_counter() - started)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    except (AntigravityExecutionError, TimeoutError):
        product_activation_events_total.labels("first_look", "failed").inc()
        first_value_duration_seconds.observe(time.perf_counter() - started)
        logger.warning("First-look analysis provider unavailable", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="generation_unavailable",
        ) from None

    ordered = list(analyzed.blueprints)
    if brief.preferred_type is not None:
        ordered.sort(key=lambda item: item.type is not brief.preferred_type)
    selected = list(ordered[:2])
    used_types = {item.type for item in selected}
    for tool in CATALOG:
        if len(selected) == 2:
            break
        if tool.kind not in used_types:
            selected.append(blueprint_for(tool.kind, target_url))
            used_types.add(tool.kind)

    if len(selected) != 2:
        product_activation_events_total.labels("first_look", "failed").inc()
        first_value_duration_seconds.observe(time.perf_counter() - started)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="concept_generation_incomplete"
        )

    try:
        architects = list(
            await asyncio.gather(
                *(
                    _first_look_architect(blueprint, target_url, evidence, brief)
                    for blueprint in selected
                )
            )
        )
    except (AntigravityExecutionError, TimeoutError):
        product_activation_events_total.labels("first_look", "failed").inc()
        first_value_duration_seconds.observe(time.perf_counter() - started)
        logger.warning("First-look architecture provider unavailable", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="generation_unavailable",
        ) from None
    session_token = create_guest_concept_token(
        target_url,
        selected,
        architects,
        evidence,
        brief,
    )
    response = GuestConceptsResponse(
        target_url=target_url,
        session_token=session_token,
        concepts=[
            CuratedConcept(blueprint=blueprint, architect=architect)
            for blueprint, architect in zip(selected, architects, strict=True)
        ],
        brief=brief,
    )
    product_activation_events_total.labels("first_look", "succeeded").inc()
    first_value_duration_seconds.observe(time.perf_counter() - started)
    return response


@router.post("/claim-guest", response_model=ClaimGuestConceptResponse)
async def claim_guest_concept_endpoint(
    payload: ClaimGuestConceptRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> ClaimGuestConceptResponse:
    """Save a visitor's chosen free direction to their new account."""
    try:
        target_url, blueprints, concepts, evidence, brief = read_guest_concept_token(
            payload.session_token
        )
    except InvalidGuestConceptSession:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="guest_session_invalid"
        ) from None

    # The signed session plus the direction chosen from it identifies this
    # claim exactly. Replaying the request — a refresh, a second click, a
    # timeout the browser could not tell from a failure — reaches the same
    # tool instead of creating another one.
    claim_key = hashlib.sha256(
        f"{payload.session_token}:{payload.selected_index}".encode()
    ).hexdigest()

    widget = await claim_guest_concepts(
        db,
        user.workspace_id,
        target_url,
        blueprints,
        concepts,
        payload.selected_index,
        evidence,
        brief,
        claim_key=claim_key,
    )
    product_activation_events_total.labels("concept_claim", "succeeded").inc()
    return ClaimGuestConceptResponse(
        widget_id=str(widget.id),
        blueprints=blueprints,
        selected_index=payload.selected_index,
        selected_concept=concepts[payload.selected_index],
        entitlement_status=widget.entitlement_status,
        can_build=await account_can_build(db, widget),
    )


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[rate_limit("analyze")])
async def analyze_endpoint(
    payload: AnalyzeRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> AnalyzeResponse:
    _require_verified_email(user)
    try:
        widget, blueprints = await analyze_url(db, user.workspace_id, payload.url, payload.brief)
    except (UnsafeTargetURL, EvidenceCollectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    return AnalyzeResponse(widget_id=str(widget.id), blueprints=blueprints.blueprints)


@router.get("/portfolio/analytics", response_model=PortfolioAnalyticsResponse)
async def portfolio_analytics_endpoint(
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    period_days: int = Query(default=30, ge=7, le=90),
    db: AsyncSession = Depends(get_async_session),
) -> PortfolioAnalyticsResponse:
    """Portfolio analytics, clipped to the window the plan actually sells.

    Every plan advertises a retention window and none of them enforced it, so
    "90 days of history" was a line on the pricing page rather than a difference
    a customer could feel. Clipped rather than refused: asking for more history
    than the plan carries should return the history the plan carries, with the
    window it used, not an error.
    """
    allowed = entitlements.plan.analytics_window_days
    if settings.enforce_plan_limits and allowed > 0:
        period_days = min(period_days, allowed)
    return await portfolio_analytics(db, user.workspace_id, period_days)


@router.get("/{widget_id}/build-resume", response_model=ResumeBuildResponse)
async def resume_build_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> ResumeBuildResponse:
    """Restore a draft without relying on one tab's session storage.

    Answers for both places a customer stops. If they chose a direction, that
    concept comes back whole. If they only got as far as analysing the site,
    the blueprints come back and ``concept`` is null — which is a resumable
    state, not a broken one. Treating it as broken is what made the dashboard
    promote a draft as the next best action and then hand the customer an empty
    form with their site analysis quietly thrown away.
    """
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None

    try:
        brief = CreationBrief.model_validate(widget.creation_brief or {})
    except (ValidationError, TypeError):
        brief = CreationBrief()

    blueprints = _stored_blueprints(widget)

    concept: CuratedConcept | None = None
    try:
        _, blueprint = _chosen_blueprint(widget, 0, WidgetType(widget.widget_type))
        concept = CuratedConcept(blueprint=blueprint, architect=architect_from_widget(widget))
    except (ValueError, ValidationError, TypeError):
        # No direction chosen yet, or a design we can no longer read. Either way
        # the site read is still good and the customer can choose from it.
        logger.info("Widget %s resumes at the choice, not at a concept", widget.id)

    if concept is None and not blueprints:
        # Nothing survived: no chosen design and no directions to offer. This is
        # the only genuinely unresumable draft, and it is worth saying so rather
        # than pretending the customer never started.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="widget_resume_unavailable",
        )

    return ResumeBuildResponse(
        target_url=widget.target_url,
        concept=concept,
        blueprints=blueprints,
        brief=brief,
    )


@router.get("/{widget_id}/tool-types", response_model=ToolTypeListResponse)
async def tool_types_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> ToolTypeListResponse:
    """Every tool we can build for this site, with the analyzer's picks flagged.

    The customer is not limited to the three the model proposed; this is what
    lets them say "make it a quiz instead" without re-analyzing the site.
    """
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None

    suggested = {b.get("type") for b in (widget.blueprints or [])}
    return ToolTypeListResponse(
        tool_types=[
            ToolTypeResponse(
                kind=tool.kind,
                label=tool.label,
                visitor_does=tool.visitor_does,
                best_for=tool.best_for,
                suggested=tool.kind.value in suggested,
            )
            for tool in CATALOG
        ]
    )


@router.post(
    "/{widget_id}/architect-preview",
    response_model=ArchitectOutput,
    dependencies=[rate_limit("preview")],
)
async def architect_preview_endpoint(
    widget_id: str,
    payload: ArchitectPreviewRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> ArchitectOutput:
    """Extract the brand match for review before committing to a build.

    Calling this again with the same blueprint is the "Regenerate" action — it
    produces a fresh take without persisting anything.
    """
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    await _require_build_allowance(db, widget)

    _, blueprint = _chosen_blueprint(widget, payload.blueprint_index, payload.widget_type)
    try:
        evidence = await ensure_widget_evidence(db, widget)
    except EvidenceCollectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    brief = CreationBrief.model_validate(widget.creation_brief or {})
    try:
        return await run_architect_stage(blueprint, widget.target_url, evidence, brief=brief)
    except (AntigravityExecutionError, TimeoutError):
        logger.warning(
            "Generation provider unavailable for %s; using grounded preview",
            widget.target_url,
            exc_info=True,
        )
        return grounded_architect(blueprint, evidence, brief)


@router.post("/build", response_model=BuildResponse, dependencies=[rate_limit("build")])
async def build_endpoint(
    payload: BuildRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> BuildResponse:
    _require_verified_email(user)
    try:
        widget = await get_owned_widget(db, payload.widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None

    if widget.status not in ("analyzed", "failed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="widget_not_ready")
    await _require_build_allowance(db, widget)

    try:
        await ensure_widget_evidence(db, widget)
    except EvidenceCollectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    blueprint_data, blueprint = _chosen_blueprint(
        widget, payload.blueprint_index, payload.widget_type
    )

    override = payload.architect_override
    if override is not None:
        # Written before the build is enqueued, not after it succeeds. The
        # customer's edits lived in one tab's session storage, which the client
        # cleared as soon as the build started — so a failed build discarded
        # every change they had made and the resume screen rebuilt the version
        # from before they touched it.
        await persist_architect(db, widget, override)

    _dispatch_build(
        widget,
        blueprint_data,
        payload.skip_deploy,
        override.model_dump(mode="json") if override else None,
    )
    await _meter_build(db, widget, "build")

    widget.status = "building"
    widget.widget_type = blueprint.type.value
    widget.title = blueprint.title
    widget.build_stage = "queued"
    widget.build_progress = 0.0
    widget.build_error = None
    product_activation_events_total.labels("build", "started").inc()

    return BuildResponse(widget_id=str(widget.id), iframe_url="", status="building", embed_code="")


@router.post("/{widget_id}/retry", response_model=BuildResponse, dependencies=[rate_limit("build")])
async def retry_build_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> BuildResponse:
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None

    if widget.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="widget_not_failed")
    await _require_build_allowance(db, widget)

    blueprint_data, _ = _blueprint_at(widget, 0)
    # Retry the design that was approved, not the one the model first proposed.
    # Passing None here meant pressing "Try again" on a failed build quietly
    # reverted every edit the customer had made to it.
    try:
        approved = architect_from_widget(widget)
    except (ValueError, ValidationError, TypeError):
        logger.warning("Widget %s has no reusable design; retrying from its blueprint", widget.id)
        approved = None

    _dispatch_build(
        widget,
        blueprint_data,
        skip_deploy=False,
        architect_override=approved.model_dump(mode="json") if approved else None,
    )
    await _meter_build(db, widget, "retry")

    widget.status = "building"
    widget.build_stage = "queued"
    widget.build_progress = 0.0
    widget.build_error = None

    return BuildResponse(widget_id=str(widget.id), iframe_url="", status="building", embed_code="")


@router.get("", response_model=WidgetListResponse)
async def list_widgets(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> WidgetListResponse:
    widgets = await list_user_widgets(db, user.workspace_id)
    plan_leads = await plan_lead_limit(db, user.workspace_id)
    return WidgetListResponse(
        widgets=[
            _widget_to_response(w, can_build=await account_can_build(db, w), plan_leads=plan_leads)
            for w in widgets
        ]
    )


@router.post("/{widget_id}/deploy", response_model=BuildResponse)
async def deploy_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> BuildResponse:
    try:
        candidate = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    await _require_build_allowance(db, candidate)

    try:
        widget = await deploy_existing_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    except WidgetBuildMissing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="widget_build_not_found"
        ) from None

    return BuildResponse(
        widget_id=str(widget.id),
        iframe_url=widget.deployment_url or "",
        status=widget.status,
        embed_code=widget.embed_code or "",
    )


@router.post("/{widget_id}/rollback", response_model=BuildResponse)
async def rollback_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> BuildResponse:
    """Serve the previous build from the tool's permanent address. No rebuild."""
    try:
        widget = await rollback_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    except WidgetBuildMissing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="no_previous_deployment"
        ) from None
    except RollbackUnavailable:
        # The customer came here because something is wrong on their website.
        # Reporting success while that page keeps serving the broken build would
        # be the worst possible moment to be inaccurate.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="rollback_unavailable"
        ) from None

    return BuildResponse(
        widget_id=str(widget.id),
        iframe_url=widget.deployment_url or "",
        status=widget.status,
        embed_code=widget.embed_code or "",
    )


@router.get("/{widget_id}", response_model=WidgetStatusResponse)
async def get_widget_status(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> WidgetStatusResponse:
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    return _widget_to_response(
        widget,
        can_build=await account_can_build(db, widget),
        plan_leads=await plan_lead_limit(db, user.workspace_id),
    )


@router.get("/{widget_id}/heal-events", response_model=list[HealEventResponse])
async def get_heal_events(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> list[HealEventResponse]:
    try:
        events = await list_heal_events(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    return [_heal_event_to_response(e) for e in events]


@router.get("/{widget_id}/deployments", response_model=list[DeploymentResponse])
async def get_deployments(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> list[DeploymentResponse]:
    try:
        deployments = await list_deployments(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    return [_deployment_to_response(d) for d in deployments]


@router.post(
    "/{widget_id}/impression",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
    dependencies=[rate_limit("impression")],
)
async def record_impression_endpoint(
    widget_id: str,
    payload: ImpressionRequest | None = None,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    """Public: a deployed widget reporting that it was viewed.

    Unauthenticated by necessity — the visitor has no account. Returns 204 whether
    or not the widget exists, so this cannot be used to enumerate widget ids, and
    responds with no body because the caller is fire-and-forget.

    The body is optional so a widget built before it existed keeps working; what
    it carries is the host page's address, which is how a passive embed proves
    it is installed and how our own preview screens stay out of the numbers.
    """
    await record_impression(db, widget_id, payload.source_url if payload else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{widget_id}/interactions",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
    dependencies=[rate_limit("interaction")],
)
async def record_interaction_endpoint(
    widget_id: str,
    payload: TrackInteractionRequest,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    await record_interaction(db, widget_id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{widget_id}/funnel", response_model=FunnelResponse)
async def widget_funnel_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> FunnelResponse:
    try:
        return await widget_funnel(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None


@router.get("/{widget_id}/outcomes", response_model=OutcomeConfigResponse)
async def get_outcomes_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> OutcomeConfigResponse:
    """The result screen as it stands: the owner's edit, or the AI's proposal."""
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    return OutcomeConfigResponse(
        config=effective_outcome_config(
            widget.outcome_config, decision_spec_of(widget), widget.copywriting
        ),
        customised=widget.outcome_config is not None,
    )


@router.put("/{widget_id}/outcomes", response_model=OutcomeConfigResponse)
async def put_outcomes_endpoint(
    widget_id: str,
    payload: UpdateOutcomeConfigRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> OutcomeConfigResponse:
    """Replace the result screen.

    Takes effect immediately on the live tool: the deployed widget re-reads the
    runtime overlay rather than needing a rebuild, so editing a score band is a
    seconds-long change rather than a five-minute one.
    """
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    try:
        entitlements.require(Feature.OUTCOME_EDITOR)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    widget.outcome_config = payload.config.model_dump(mode="json")
    return OutcomeConfigResponse(config=payload.config, customised=True)


@router.delete("/{widget_id}/outcomes", response_model=OutcomeConfigResponse)
async def reset_outcomes_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> OutcomeConfigResponse:
    """Discard the owner's edits and fall back to what the AI designed."""
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    widget.outcome_config = None
    return OutcomeConfigResponse(
        config=effective_outcome_config(None, decision_spec_of(widget), widget.copywriting),
        customised=False,
    )


@router.get("/{widget_id}/decision", response_model=DecisionResponse)
async def get_decision_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> DecisionResponse:
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    return DecisionResponse(decision=decision_spec_of(widget), editable=widget.status != "building")


@router.put("/{widget_id}/decision", response_model=DecisionResponse)
async def put_decision_endpoint(
    widget_id: str,
    payload: UpdateDecisionRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> DecisionResponse:
    """Replace the question flow.

    Rejected while a build is in flight, because the build reads this column: an
    edit landing mid-run produces a deployed tool that does not match what the
    owner is looking at, with no way to tell which version won.
    """
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None
    try:
        entitlements.require(Feature.QUESTION_EDITOR)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None
    if widget.status == "building":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="widget_building")

    await put_decision_spec(db, widget, payload.decision)
    return DecisionResponse(decision=payload.decision, editable=True)


@router.get("/{widget_id}/readiness", response_model=ReadinessResponse)
async def get_readiness_endpoint(
    widget_id: str,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> ReadinessResponse:
    """The publish checklist, every item answered from real state."""
    try:
        widget = await get_owned_widget(db, widget_id, user.workspace_id)
    except WidgetNotFound:
        raise _NOT_FOUND from None

    readiness = await assess_readiness(db, widget, user, entitlements)
    return ReadinessResponse(
        ready=readiness.ready,
        completed=readiness.completed,
        total=len(readiness.checks),
        checks=[
            ReadinessCheckResponse(
                id=check.id,
                label=check.label,
                detail=check.detail,
                done=check.done,
                action=check.action,
                blocking=check.blocking,
            )
            for check in readiness.checks
        ],
    )


@router.get(
    "/{widget_id}/runtime-config",
    response_model=RuntimeConfigResponse,
    include_in_schema=False,
)
async def runtime_config_endpoint(
    widget_id: str,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
) -> RuntimeConfigResponse:
    """Public: what a deployed widget reads at boot to pick up owner edits.

    Unauthenticated by necessity — the caller is an anonymous visitor on someone
    else's website. Everything here is already visible to that visitor the moment
    the tool renders, so there is nothing to leak; the widget's own id is the only
    input, and an unknown id is a 404 like any other.

    Cached briefly at the edge: this is fetched once per page view, and a minute
    of staleness on a copy change is a fair trade for not putting a database read
    in front of every impression.
    """
    parsed = _coerce_widget_id_for_public(widget_id)
    widget = await db.scalar(select(Widget).where(Widget.id == parsed)) if parsed else None
    if widget is None or widget.status != "active":
        raise _NOT_FOUND

    decision = decision_spec_of(widget)
    outcomes = effective_outcome_config(widget.outcome_config, decision, widget.copywriting)
    launch = widget.launch_settings or {}

    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return RuntimeConfigResponse(
        widget_id=str(widget.id),
        # Changes whenever anything the widget renders changes, so a client can
        # cheaply tell "same config" from "re-render".
        version=_config_version(widget),
        decision=decision,
        outcomes=outcomes,
        consent_text=widget.consent_text or outcomes.email_capture.consent_text or None,
        cta_url=str(launch.get("cta_url") or outcomes.cta.url or "") or None,
        accepting_leads=widget.leads_count
        < effective_lead_cap(widget.lead_cap, await plan_lead_limit(db, widget.user_id)),
    )


@router.put("/{widget_id}/launch", response_model=LaunchSetupResponse)
async def configure_widget_launch_endpoint(
    widget_id: str,
    payload: LaunchSetupRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> LaunchSetupResponse:
    # Everything else on this screen — placement, CTA, consent, which fields to
    # ask for — belongs to any published tool. Forwarding leads to another system
    # is the part the plans sell, and it was the one thing here nobody checked.
    if payload.delivery_webhook_url:
        try:
            entitlements.require(Feature.WEBHOOK_DELIVERY)
        except FeatureLocked as exc:
            raise upgrade_required(exc) from None

    try:
        widget, new_secret = await configure_widget_launch(
            db, widget_id, user.workspace_id, payload
        )
    except WidgetNotFound:
        raise _NOT_FOUND from None
    except UnsafeTargetURL as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    return LaunchSetupResponse(
        launch_settings=widget.launch_settings or {},
        delivery_webhook_url=widget.delivery_webhook_url,
        webhook_signing_secret=new_secret,
        consent_text=widget.consent_text,
    )


@router.post("/{widget_id}/launch/test", response_model=DeliveryTestResponse)
async def test_widget_delivery_endpoint(
    widget_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> DeliveryTestResponse:
    try:
        connected, status_code, checked_at = await test_widget_delivery(
            db, widget_id, user.workspace_id
        )
    except WidgetNotFound:
        raise _NOT_FOUND from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except UnsafeTargetURL as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    return DeliveryTestResponse(
        connected=connected,
        status_code=status_code,
        checked_at=checked_at.isoformat(),
        message=(
            "Connection confirmed" if connected else "The destination did not accept the test event"
        ),
    )


def _sse_unauthorized() -> Response:
    return Response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content='{"detail":"not_authenticated"}',
        media_type="application/json",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/{widget_id}/events", include_in_schema=False)
async def widget_events(widget_id: str, request: Request) -> Response:
    """Server-sent build progress for one widget.

    Authenticated via an ``access_token`` query parameter rather than a header,
    because ``EventSource`` cannot set headers. The token is fully verified and
    widget ownership is checked before any event is streamed.

    A dedicated session is opened rather than using the request-scoped dependency:
    the stream outlives the handler, and holding a pooled connection open for the
    duration of a build would exhaust the pool.
    """
    token = request.query_params.get("access_token", "")
    if not token:
        return _sse_unauthorized()

    try:
        claims = decode_token(token, expected_type="access")
    except TokenError:
        return _sse_unauthorized()

    if await is_revoked(claims.jti):
        return _sse_unauthorized()

    async with async_session_factory() as session:
        user = await get_active_user(session, claims.subject)
        if user is None:
            return _sse_unauthorized()
        try:
            await get_owned_widget(session, widget_id, user.workspace_id)
        except WidgetNotFound:
            return Response(
                status_code=status.HTTP_404_NOT_FOUND,
                content='{"detail":"widget_not_found"}',
                media_type="application/json",
            )

    return StreamingResponse(
        pipeline_events.event_stream(widget_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Stops nginx from buffering the stream into uselessness.
            "X-Accel-Buffering": "no",
        },
    )
