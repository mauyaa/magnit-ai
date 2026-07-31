"""Widget persistence and ownership rules.

Every read and mutation here is scoped by ``user_id``. A widget belonging to
another account is reported as missing rather than forbidden, so the API never
confirms the existence of a resource the caller cannot see.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import jwt
from google.antigravity.types import AntigravityExecutionError
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.entitlements import resolve_entitlements
from app.features.leads.models import Lead
from app.features.leads.notify import post_signed_webhook
from app.features.widgets.models import (
    Widget,
    WidgetDeployment,
    WidgetHealEvent,
    WidgetInteraction,
)
from app.features.widgets.schemas import (
    AnalyticsDay,
    AnalyticsExperience,
    AnalyticsSource,
    FunnelResponse,
    LaunchSetupRequest,
    PortfolioAnalyticsResponse,
    TrackInteractionRequest,
)
from app.platform.clients.deployment import deploy_directory, promote_deployment
from app.platform.config.settings import settings
from app.platform.db.session import rows_affected
from app.platform.observability.metrics import generation_provider_total
from app.platform.pipeline.engine import analyze as pipeline_analyze
from app.platform.pipeline.evidence import collect_site_evidence
from app.platform.pipeline.fallback import grounded_blueprints
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    BlueprintList,
    CreationBrief,
    DecisionSpec,
    SiteEvidence,
    WidgetType,
)
from app.platform.security.url_guard import validate_target_url

logger = logging.getLogger(__name__)


class WidgetNotFound(Exception):
    """The widget does not exist, or is not visible to this caller."""


class WidgetBuildMissing(Exception):
    """No built artifacts on disk for this widget, so it cannot be deployed."""


class InvalidGuestConceptSession(Exception):
    """The signed first-look session is missing, expired, or has been altered."""


def widget_can_build(widget: Widget, subscription_access: bool = False) -> bool:
    """Whether this widget may spend generation and deployment budget.

    ``require_payment_to_build`` is the master switch, and it is what keeps
    development and CI usable: with it off nothing is metered against a plan, so
    a test can build as often as it needs to. Production sets it, and every
    commercial limit below comes into force together.
    """
    return (
        not settings.require_payment_to_build
        or subscription_access
        or widget.entitlement_status in {"paid", "complimentary"}
    )


async def account_can_build(db: AsyncSession, widget: Widget) -> bool:
    """Whether this account may build this widget right now.

    Three independent reasons it may not, checked in the order a customer would
    hit them: no plan at all, this month's builds are spent, or the plan's live
    tools are all in use and this would be one more.
    """
    if widget_can_build(widget):
        return True

    entitlements = await resolve_entitlements(db, widget.user_id)
    if not entitlements.subscribed:
        return False
    if not entitlements.can_build():
        return False
    return entitlements.can_publish(widget)


async def require_widget_entitlement(db: AsyncSession, widget: Widget) -> None:
    """Raise the specific reason a build is not allowed, not a generic refusal.

    The three cases produce different screens — subscribe, wait or upgrade, free
    up a slot — so the caller needs to know which one it is.
    """
    if widget_can_build(widget):
        return

    entitlements = await resolve_entitlements(db, widget.user_id)
    if not entitlements.subscribed:
        raise PermissionError("payment_required")
    entitlements.require_build()
    entitlements.require_publish(widget)


def widget_logic_from_architect(architect: ArchitectOutput) -> dict:
    """The canonical ``widget_logic`` payload.

    One function so the claim path and the build path cannot write two different
    shapes into the same column, which is exactly what they did.
    """
    return {
        "calculation": architect.logic.model_dump(mode="json"),
        "decision": (architect.decision.model_dump(mode="json") if architect.decision else None),
        "claims": [claim.model_dump(mode="json") for claim in architect.claims],
    }


def architect_from_widget(widget: Widget) -> ArchitectOutput:
    """Rebuild the approved design from the columns that store it.

    The widget's own rows are the canonical record of what the customer signed
    off — brand, visual language, calculation, decision, claims and copy. This
    is the one place that reassembles them, so resuming a build and retrying a
    failed one cannot disagree about what was approved.

    Raises ``ValidationError`` or ``ValueError`` if the stored shape cannot make
    a valid design; callers decide what to tell the customer.
    """
    logic = widget.widget_logic or {}
    return ArchitectOutput.model_validate(
        {
            "widget_type": WidgetType(widget.widget_type),
            "brand": widget.brand_tokens,
            "visual_language": widget.visual_language,
            "logic": logic.get("calculation"),
            "copywriting": widget.copywriting,
            "decision": logic.get("decision"),
            "claims": logic.get("claims") or [],
        }
    )


async def persist_architect(db: AsyncSession, widget: Widget, architect: ArchitectOutput) -> None:
    """Save the design a build is about to run with, before it runs.

    Fine-tuning used to live only in one browser tab's session storage, which was
    cleared the moment the build was enqueued and written to the database only
    if the whole build then succeeded. A build that failed — a provider outage,
    a bad generation, a deploy that timed out — therefore threw away every edit
    the customer had made, and the resume screen quietly rebuilt the version
    from before they touched it.

    Writing it here makes the database the record of what was approved, so a
    failure costs a retry rather than the work.
    """
    widget.brand_tokens = architect.brand.model_dump(mode="json")
    widget.visual_language = architect.visual_language.model_dump(mode="json")
    widget.widget_logic = widget_logic_from_architect(architect)
    widget.copywriting = architect.copywriting
    await db.flush()


def decision_spec_of(widget: Widget) -> DecisionSpec | None:
    """The widget's question flow, or ``None`` if it has no valid one.

    Invalid stored specs resolve to ``None`` rather than raising: the column is
    written by a model, and one malformed generation must not make the tool's
    whole dashboard page un-openable.
    """
    raw = (widget.widget_logic or {}).get("decision")
    if not isinstance(raw, dict):
        return None
    try:
        return DecisionSpec.model_validate(raw)
    except ValidationError:
        logger.warning("Widget %s has an unreadable decision spec", widget.id)
        return None


async def put_decision_spec(db: AsyncSession, widget: Widget, decision: DecisionSpec) -> Widget:
    """Replace the question flow, preserving everything else in ``widget_logic``.

    The spec is already validated by its own model — unique question ids, no
    overlapping result ranges, no calculation term pointing at a question that
    does not exist — so an edit that would produce an unscoreable tool is
    rejected before it can reach a visitor.
    """
    logic = dict(widget.widget_logic or {})
    logic["decision"] = decision.model_dump(mode="json")
    # Reassigned rather than mutated in place: SQLAlchemy does not track changes
    # inside a JSON column, so an in-place edit is silently never persisted.
    widget.widget_logic = logic
    await db.flush()
    return widget


def build_embed_code(embed_url: str) -> str:
    """The snippet a customer pastes into their site.

    Points at the tool's permanent address, never at a single build, and never
    back at this API — a page we do not control must not stop working because a
    tool was rebuilt, because a repair ran, or because our API is having a bad
    morning.
    """
    safe_url = html.escape(embed_url, quote=True)
    parsed = urlsplit(embed_url)
    origin = json.dumps(f"{parsed.scheme}://{parsed.netloc}")
    return (
        '<div data-magnit-embed style="width:100%">'
        f'<iframe data-magnit-frame src="{safe_url}" width="100%" height="520" '
        'style="display:block;width:100%;min-height:360px;border:0;overflow:hidden" '
        'loading="lazy" title="Interactive decision tool"></iframe>'
        "</div>"
        "<script>(function(){"
        "var s=document.currentScript,c=s&&s.previousElementSibling,"
        "f=c&&c.querySelector('[data-magnit-frame]');if(!f)return;"
        f"var o={origin};"
        # The campaign that brought the visitor to the page is on the page's own
        # URL, and an iframe sees none of it. Without this hand-off every lead a
        # customer's paid traffic produced was attributed to nothing, and their
        # attribution report was a single "direct" row.
        "try{var q=new URLSearchParams(location.search),u=new URL(f.src),n=0;"
        "['utm_source','utm_medium','utm_campaign','utm_content','utm_term','gclid']"
        ".forEach(function(k){var v=q.get(k);"
        "if(v&&!u.searchParams.has(k)){u.searchParams.set(k,v.slice(0,200));n++;}});"
        "if(n)f.src=u.toString();}catch(_){}"
        "window.addEventListener('message',function(e){"
        "if(e.source!==f.contentWindow||e.origin!==o||!e.data||"
        "e.data.type!=='magnit:resize')return;"
        "var h=Number(e.data.height);if(Number.isFinite(h)&&h>=240&&h<=5000)"
        "f.style.height=Math.ceil(h)+'px';"
        "});})();</script>"
    )


def workspace_dir(widget_id: str) -> Path:
    base = Path(settings.widgets_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / widget_id


def _coerce_widget_id(widget_id: str) -> uuid.UUID | None:
    """Parse an id, returning ``None`` for anything that isn't a UUID.

    Route parameters are strings; a non-UUID value can never match a row, and on
    PostgreSQL comparing it would raise a DataError instead of returning empty.
    """
    try:
        return uuid.UUID(str(widget_id))
    except (ValueError, AttributeError, TypeError):
        return None


async def analyze_url(
    db: AsyncSession,
    user_id: uuid.UUID,
    url: str,
    brief: CreationBrief | None = None,
) -> tuple[Widget, BlueprintList]:
    """Analyze a site and persist the proposed blueprints.

    The URL is SSRF-validated before the agent is allowed anywhere near it.
    """
    safe_url = validate_target_url(url)
    evidence = await collect_site_evidence(safe_url)
    blueprints = await _analyze_with_continuity(evidence, brief)

    widget = Widget(
        user_id=user_id,
        target_url=evidence.target_url,
        widget_type="pending",
        title="Pending selection",
        status="analyzed",
        analyzed_at=datetime.now(UTC),
        blueprints=[b.model_dump(mode="json") for b in blueprints.blueprints],
        creation_brief=brief.model_dump(mode="json") if brief else None,
        source_evidence=evidence.model_dump(mode="json"),
        source_content_fingerprint=evidence.content_fingerprint,
        source_brand_fingerprint=evidence.brand_fingerprint,
    )
    db.add(widget)
    await db.flush()

    return widget, blueprints


async def analyze_guest_url(
    url: str,
    brief: CreationBrief | None = None,
) -> tuple[str, BlueprintList, SiteEvidence]:
    """Run the free first analysis without creating an ownerless widget row."""
    safe_url = validate_target_url(url)
    evidence = await collect_site_evidence(safe_url)
    return (
        evidence.target_url,
        await _analyze_with_continuity(evidence, brief),
        evidence,
    )


async def _analyze_with_continuity(
    evidence: SiteEvidence,
    brief: CreationBrief | None,
) -> BlueprintList:
    """Propose directions, falling back to deterministic ones if the model is down.

    The fallback is a real feature — a grounded direction is better than an error
    page — but it is indistinguishable from success at the API boundary, and that
    is dangerous. A stale model id once returned 404 for every request while this
    path quietly served templates and answered 200. Nothing outside the log
    changed, so the product looked healthy while its whole value proposition was
    switched off.

    Hence the counter: `magai_generation_provider_total{outcome="fallback"}` going
    non-zero is the alarm, and `ops/prometheus/alerts.yml` treats a sustained
    fallback rate as an incident rather than routine degradation.
    """
    try:
        output = await pipeline_analyze(evidence.target_url, evidence, brief)
    except (AntigravityExecutionError, TimeoutError):
        logger.warning(
            "Generation provider unavailable for %s; using grounded directions",
            evidence.domain,
            exc_info=True,
        )
        generation_provider_total.labels("analyzer", "fallback").inc()
        return grounded_blueprints(evidence, brief)
    generation_provider_total.labels("analyzer", "model").inc()
    return output


def create_guest_concept_token(
    target_url: str,
    blueprints: list[Blueprint],
    concepts: list[ArchitectOutput],
    evidence: SiteEvidence,
    brief: CreationBrief | None = None,
) -> str:
    """Sign the free result so it can be claimed after account creation.

    The browser keeps the visible result in session storage. The signed copy is
    the server-side trust boundary: URLs and blueprints cannot be swapped before
    a claimed widget is created.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": "guest-concepts",
        "typ": "guest_concepts",
        "jti": str(uuid.uuid4()),
        "iss": "magnitai",
        "iat": int(now.timestamp()),
        "exp": int((now + settings.guest_concept_ttl).timestamp()),
        "target_url": target_url,
        "blueprints": [item.model_dump(mode="json") for item in blueprints],
        "concepts": [item.model_dump(mode="json") for item in concepts],
        "evidence": evidence.model_dump(mode="json"),
        "brief": (brief or CreationBrief()).model_dump(mode="json"),
        # A nonce ensures identical analyses never produce identical bearer tokens.
        "nonce": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def read_guest_concept_token(
    token: str,
) -> tuple[str, list[Blueprint], list[ArchitectOutput], SiteEvidence, CreationBrief]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="magnitai",
            options={"require": ["exp", "sub", "typ", "jti", "iss"]},
        )
        if payload.get("sub") != "guest-concepts" or payload.get("typ") != "guest_concepts":
            raise InvalidGuestConceptSession()
        # The URL was fully SSRF-checked before this server signed the token, and
        # claiming the result performs no network fetch. Resolving DNS again here
        # made a valid, already-generated result impossible to save during a DNS
        # outage. The signed evidence equality check below remains the integrity
        # boundary; later operations that fetch a URL validate it again.
        target_url = str(payload["target_url"])
        blueprints = [Blueprint.model_validate(item) for item in payload["blueprints"]]
        concepts = [ArchitectOutput.model_validate(item) for item in payload["concepts"]]
        evidence = SiteEvidence.model_validate(payload["evidence"])
        brief = CreationBrief.model_validate(payload.get("brief") or {})
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise InvalidGuestConceptSession() from exc

    if len(blueprints) < 2 or len(concepts) != 2:
        raise InvalidGuestConceptSession()
    if evidence.target_url != target_url:
        raise InvalidGuestConceptSession()
    return target_url, blueprints, concepts, evidence, brief


async def claim_guest_concepts(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_url: str,
    blueprints: list[Blueprint],
    concepts: list[ArchitectOutput],
    selected_index: int,
    evidence: SiteEvidence,
    brief: CreationBrief | None = None,
    claim_key: str | None = None,
) -> Widget:
    """Attach a signed free analysis to its new owner without another AI call.

    Idempotent on ``claim_key``. This request is sent from a browser at the
    moment an account is created, which is exactly where retries happen — a
    refresh, an impatient second click, a timeout the client cannot distinguish
    from a failure. Each of those used to produce another tool in the workspace,
    so the customer's first sight of the product was three copies of the thing
    they asked for once.
    """
    if claim_key:
        existing = await db.scalar(
            select(Widget).where(Widget.user_id == user_id, Widget.claim_key == claim_key)
        )
        if existing is not None:
            return existing

    selected_blueprint = blueprints[selected_index]
    selected_concept = concepts[selected_index]
    widget = Widget(
        user_id=user_id,
        target_url=target_url,
        widget_type=selected_blueprint.type.value,
        title=selected_blueprint.title,
        status="analyzed",
        analyzed_at=datetime.now(UTC),
        blueprints=[item.model_dump(mode="json") for item in blueprints],
        creation_brief=brief.model_dump(mode="json") if brief else None,
        brand_tokens=selected_concept.brand.model_dump(mode="json"),
        visual_language=selected_concept.visual_language.model_dump(mode="json"),
        # The same shape a completed build writes. It used to store the bare
        # MathLogic here and the wrapped {calculation, decision, claims} there,
        # so the decision spec the visitor had just reviewed on screen was
        # discarded the moment they claimed it — and the question flow could not
        # be read back until after a build.
        widget_logic=widget_logic_from_architect(selected_concept),
        copywriting=selected_concept.copywriting,
        source_evidence=evidence.model_dump(mode="json"),
        source_content_fingerprint=evidence.content_fingerprint,
        source_brand_fingerprint=evidence.brand_fingerprint,
        claim_key=claim_key,
    )
    db.add(widget)
    await db.flush()
    return widget


async def get_owned_widget(db: AsyncSession, widget_id: str, user_id: uuid.UUID) -> Widget:
    """Fetch a widget the caller owns, or raise :class:`WidgetNotFound`."""
    parsed = _coerce_widget_id(widget_id)
    if parsed is None:
        raise WidgetNotFound(widget_id)

    result = await db.execute(select(Widget).where(Widget.id == parsed, Widget.user_id == user_id))
    widget = result.scalar_one_or_none()
    if widget is None:
        raise WidgetNotFound(widget_id)
    return widget


async def get_widget_unscoped(db: AsyncSession, widget_id: str) -> Widget | None:
    """Fetch a widget without an ownership filter.

    Only for genuinely public paths (anonymous lead submission from an embedded
    widget) and background jobs. Never call this from an authenticated read.
    """
    parsed = _coerce_widget_id(widget_id)
    if parsed is None:
        return None
    result = await db.execute(select(Widget).where(Widget.id == parsed))
    return result.scalar_one_or_none()


async def ensure_widget_evidence(db: AsyncSession, widget: Widget) -> SiteEvidence:
    """Return persisted evidence, backfilling rows created before grounding existed."""
    if widget.source_evidence:
        return SiteEvidence.model_validate(widget.source_evidence)
    evidence = await collect_site_evidence(widget.target_url)
    widget.target_url = evidence.target_url
    widget.source_evidence = evidence.model_dump(mode="json")
    widget.source_content_fingerprint = evidence.content_fingerprint
    widget.source_brand_fingerprint = evidence.brand_fingerprint
    await db.flush()
    return evidence


async def list_user_widgets(db: AsyncSession, user_id: uuid.UUID) -> list[Widget]:
    result = await db.execute(
        select(Widget).where(Widget.user_id == user_id).order_by(Widget.created_at.desc())
    )
    return list(result.scalars().all())


async def record_deployment(
    db: AsyncSession,
    widget: Widget,
    deployment_url: str,
    trigger: str,
    *,
    embed_url: str | None = None,
    provider_deployment_id: str | None = None,
) -> WidgetDeployment:
    """Point the widget at a new deployment and log it for rollback.

    Previous rows are demoted to ``is_current=False`` so exactly one row is
    current and the next-newest is an unambiguous rollback target.

    The embed address is deliberately write-once. Once a customer has pasted the
    snippet onto their website we cannot edit that page, so the address in it has
    to outlive every rebuild, repair and rollback. Only the first publish may set
    it; later deploys change what it serves, never where it points.
    """
    await db.execute(
        update(WidgetDeployment)
        .where(WidgetDeployment.widget_id == widget.id, WidgetDeployment.is_current.is_(True))
        .values(is_current=False)
    )

    record = WidgetDeployment(
        widget_id=widget.id,
        deployment_url=deployment_url,
        provider_deployment_id=provider_deployment_id,
        trigger=trigger,
        is_current=True,
    )
    db.add(record)

    widget.status = "active"
    widget.deployment_url = deployment_url
    # `or deployment_url` covers the local-hosting path, where the build already
    # lives at a stable per-tool URL and there is no separate alias to assign.
    widget.embed_url = widget.embed_url or embed_url or deployment_url
    widget.embed_code = build_embed_code(widget.embed_url)
    widget.deployed_at = datetime.now(UTC)
    await db.flush()
    return record


async def deploy_existing_widget(db: AsyncSession, widget_id: str, user_id: uuid.UUID) -> Widget:
    """Re-publish a widget's already-built artifacts to a fresh deployment."""
    widget = await get_owned_widget(db, widget_id, user_id)

    dist_dir = workspace_dir(str(widget.id)) / "dist"
    if not dist_dir.is_dir():
        raise WidgetBuildMissing(widget_id)

    deployment = await deploy_directory(str(dist_dir), str(widget.id))
    await record_deployment(
        db,
        widget,
        deployment.url,
        trigger="redeploy",
        embed_url=deployment.embed_url,
        provider_deployment_id=deployment.provider_deployment_id,
    )
    return widget


class RollbackUnavailable(Exception):
    """The previous build exists but the live address could not be moved to it."""


async def rollback_widget(db: AsyncSession, widget_id: str, user_id: uuid.UUID) -> Widget:
    """Serve the previous build from the tool's permanent address.

    Cheap and instant compared with a rebuild: the old deployment is immutable
    and still hosted, so this only moves which one the embedded address resolves
    to. That move is the whole operation — a rollback that updated our database
    but left the customer's website serving the broken build would be a lie told
    to the one person who came here because something was wrong.
    """
    widget = await get_owned_widget(db, widget_id, user_id)

    result = await db.execute(
        select(WidgetDeployment)
        .where(
            WidgetDeployment.widget_id == widget.id,
            WidgetDeployment.is_current.is_(False),
        )
        .order_by(WidgetDeployment.created_at.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none()
    if previous is None:
        raise WidgetBuildMissing(widget_id)

    # When the embed already points straight at this build's own URL there is no
    # alias to move — that is the local-hosting case, where one address serves
    # whatever is on disk.
    if widget.embed_url and widget.embed_url != previous.deployment_url:
        if not previous.provider_deployment_id:
            # Deployed before we started recording provider ids. Saying so is
            # the only honest option: we cannot move the live address, and
            # pretending otherwise would leave the broken build serving.
            raise RollbackUnavailable(widget_id)
        try:
            await promote_deployment(previous.provider_deployment_id, str(widget.id))
        except Exception as exc:  # provider-shaped failure; re-raised as our own
            logger.exception("Could not roll widget %s back to its previous build", widget.id)
            raise RollbackUnavailable(widget_id) from exc

    await record_deployment(
        db,
        widget,
        previous.deployment_url,
        trigger="rollback",
        provider_deployment_id=previous.provider_deployment_id,
    )
    logger.info("Rolled widget %s back to %s", widget.id, previous.deployment_url)
    return widget


async def list_deployments(
    db: AsyncSession, widget_id: str, user_id: uuid.UUID
) -> list[WidgetDeployment]:
    widget = await get_owned_widget(db, widget_id, user_id)
    result = await db.execute(
        select(WidgetDeployment)
        .where(WidgetDeployment.widget_id == widget.id)
        .order_by(WidgetDeployment.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


def _own_host(host: str) -> bool:
    """Whether a referrer host is one of ours rather than a customer's site."""
    ours = {
        urlsplit(url).netloc.lower()
        for url in (settings.frontend_base_url, settings.site_url)
        if url
    }
    return host.lower() in ours


def embed_host_of(source_url: str | None) -> str | None:
    """The customer's own host from a referrer, or ``None`` if it is not one.

    The owner previewing their tool in our dashboard, and the build screen's own
    live preview, both load the same public URL and both send a referrer — ours.
    Treating those as evidence of installation is how "verify installation"
    could pass for a tool that had never been pasted anywhere, and how a
    workspace's own tab inflated the visitor count it was being judged on.
    """
    if not source_url:
        return None
    host = urlsplit(source_url).netloc
    if not host or _own_host(host):
        return None
    return host[:255]


async def record_impression(
    db: AsyncSession, widget_id: str, source_url: str | None = None
) -> bool:
    """Record one view. Returns whether the widget existed.

    Called by the deployed widget on mount, so it is unauthenticated and must be
    cheap. No per-view row is stored — a counter is all the conversion-rate
    calculation needs, and it keeps an embedded widget from being used to grow
    the database.

    Views from our own screens are not counted at all. They are the owner
    looking at their own work, and counting them means every tool's conversion
    rate is quietly diluted by the person who built it.
    """
    parsed = _coerce_widget_id(widget_id)
    if parsed is None:
        return False

    host = embed_host_of(source_url)
    if source_url and host is None:
        # One of our own screens. Confirm the widget exists so the caller's
        # contract is unchanged, then record nothing.
        return bool(await db.scalar(select(Widget.id).where(Widget.id == parsed)))

    values: dict = {"impressions_count": Widget.impressions_count + 1}
    if host:
        # First sighting on a real page is the moment the tool is installed —
        # no interaction required, because a visitor who scrolls past without
        # touching it has still proved the snippet is on the page.
        values["embed_host"] = host
        values["first_embedded_at"] = func.coalesce(Widget.first_embedded_at, datetime.now(UTC))

    result = await db.execute(
        update(Widget).where(Widget.id == parsed, Widget.status == "active").values(**values)
    )
    return rows_affected(result) > 0


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


async def record_interaction(
    db: AsyncSession,
    widget_id: str,
    payload: TrackInteractionRequest,
) -> bool:
    """Record an idempotent visitor milestone without identity fingerprinting."""
    parsed = _coerce_widget_id(widget_id)
    if parsed is None:
        return False

    widget = await get_widget_unscoped(db, widget_id)
    if widget is None or widget.status != "active":
        return False

    hashed = _session_hash(payload.session_id)
    now = datetime.now(UTC)
    insert_values = {
        "widget_id": parsed,
        "session_hash": hashed,
        "source_url": payload.source_url,
        "attribution": payload.attribution,
        "last_step": payload.step,
        "result_key": payload.result_key,
    }
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        pg_stmt = pg_insert(WidgetInteraction).values(**insert_values)
        await db.execute(
            pg_stmt.on_conflict_do_nothing(index_elements=["widget_id", "session_hash"])
        )
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        sqlite_stmt = sqlite_insert(WidgetInteraction).values(**insert_values)
        await db.execute(
            sqlite_stmt.on_conflict_do_nothing(index_elements=["widget_id", "session_hash"])
        )
    else:
        result = await db.execute(
            select(WidgetInteraction).where(
                WidgetInteraction.widget_id == parsed,
                WidgetInteraction.session_hash == hashed,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(WidgetInteraction(**insert_values))
            await db.flush()

    counter_name: str | None = None
    timestamp_name: str | None = None
    if payload.event == "started":
        counter_name, timestamp_name = "starts_count", "started_at"
    elif payload.event == "completed":
        counter_name, timestamp_name = "completions_count", "completed_at"
    elif payload.event == "result_viewed":
        timestamp_name = "result_viewed_at"
    elif payload.event == "cta_clicked":
        counter_name, timestamp_name = "cta_clicks_count", "cta_clicked_at"

    updates: dict[str, object] = {}
    if payload.step:
        updates["last_step"] = payload.step
    if payload.result_key:
        updates["result_key"] = payload.result_key
    if timestamp_name:
        updates[timestamp_name] = now
        milestone = await db.execute(
            update(WidgetInteraction)
            .where(
                WidgetInteraction.widget_id == parsed,
                WidgetInteraction.session_hash == hashed,
                getattr(WidgetInteraction, timestamp_name).is_(None),
            )
            .values(**updates)
        )
        if counter_name and rows_affected(milestone) > 0:
            await db.execute(
                update(Widget)
                .where(Widget.id == parsed)
                .values(**{counter_name: getattr(Widget, counter_name) + 1})
            )
    elif updates:
        await db.execute(
            update(WidgetInteraction)
            .where(
                WidgetInteraction.widget_id == parsed,
                WidgetInteraction.session_hash == hashed,
            )
            .values(**updates)
        )

    await db.flush()
    return True


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


async def widget_funnel(db: AsyncSession, widget_id: str, user_id: uuid.UUID) -> FunnelResponse:
    widget = await get_owned_widget(db, widget_id, user_id)
    result_views = await db.scalar(
        select(func.count(WidgetInteraction.id)).where(
            WidgetInteraction.widget_id == widget.id,
            WidgetInteraction.result_viewed_at.is_not(None),
        )
    )
    dropoff_rows = await db.execute(
        select(WidgetInteraction.last_step, func.count(WidgetInteraction.id))
        .where(
            WidgetInteraction.widget_id == widget.id,
            WidgetInteraction.started_at.is_not(None),
            WidgetInteraction.completed_at.is_(None),
            WidgetInteraction.last_step.is_not(None),
        )
        .group_by(WidgetInteraction.last_step)
    )
    results_viewed = int(result_views or 0)
    return FunnelResponse(
        views=widget.impressions_count,
        starts=widget.starts_count,
        completions=widget.completions_count,
        results_viewed=results_viewed,
        cta_clicks=widget.cta_clicks_count,
        leads=widget.leads_count,
        start_rate=_rate(widget.starts_count, widget.impressions_count),
        completion_rate=_rate(widget.completions_count, widget.starts_count),
        lead_rate=_rate(widget.leads_count, widget.impressions_count),
        cta_rate=_rate(widget.cta_clicks_count, results_viewed),
        dropoff_by_step={str(step): int(count) for step, count in dropoff_rows.all()},
    )


async def portfolio_analytics(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_days: int = 30,
) -> PortfolioAnalyticsResponse:
    """Return truthful portfolio analytics without invented benchmark data."""
    widgets = await list_user_widgets(db, user_id)
    widget_ids = [widget.id for widget in widgets]
    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=period_days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=UTC)

    interactions: list[WidgetInteraction] = []
    leads: list[Lead] = []
    if widget_ids:
        interaction_rows = await db.execute(
            select(WidgetInteraction).where(
                WidgetInteraction.widget_id.in_(widget_ids),
                WidgetInteraction.created_at >= since,
            )
        )
        interactions = list(interaction_rows.scalars().all())
        lead_rows = await db.execute(
            select(Lead).where(
                Lead.widget_id.in_(widget_ids),
                Lead.created_at >= since,
            )
        )
        leads = list(lead_rows.scalars().all())

    by_day = {
        (first_day + timedelta(days=offset)).isoformat(): {
            "starts": 0,
            "completions": 0,
            "leads": 0,
            "cta_clicks": 0,
        }
        for offset in range(period_days)
    }
    source_counts: dict[str, dict[str, int]] = {}
    dropoff: dict[str, int] = {}
    for interaction in interactions:
        day = interaction.created_at.date().isoformat()
        if day in by_day:
            if interaction.started_at:
                by_day[day]["starts"] += 1
            if interaction.completed_at:
                by_day[day]["completions"] += 1
            if interaction.cta_clicked_at:
                by_day[day]["cta_clicks"] += 1
        attribution = interaction.attribution or {}
        source = str(attribution.get("utm_source") or attribution.get("source") or "").strip()
        if not source and interaction.source_url:
            source = urlsplit(interaction.source_url).hostname or ""
        source = source or "Direct / unknown"
        bucket = source_counts.setdefault(source[:120], {"engaged_visitors": 0, "leads": 0})
        bucket["engaged_visitors"] += 1
        if interaction.lead_submitted_at:
            bucket["leads"] += 1
        if interaction.started_at and not interaction.completed_at and interaction.last_step:
            dropoff[interaction.last_step] = dropoff.get(interaction.last_step, 0) + 1

    for lead in leads:
        day = lead.created_at.date().isoformat()
        if day in by_day:
            by_day[day]["leads"] += 1

    total_views = sum(widget.impressions_count for widget in widgets)
    total_starts = sum(widget.starts_count for widget in widgets)
    total_completions = sum(widget.completions_count for widget in widgets)
    total_leads = sum(widget.leads_count for widget in widgets)
    total_cta = sum(widget.cta_clicks_count for widget in widgets)
    experiences = [
        AnalyticsExperience(
            id=str(widget.id),
            title=widget.title,
            status=widget.status,
            views=widget.impressions_count,
            starts=widget.starts_count,
            completions=widget.completions_count,
            leads=widget.leads_count,
            conversion_rate=_rate(widget.leads_count, widget.impressions_count),
        )
        for widget in sorted(
            widgets,
            key=lambda item: (item.leads_count, item.impressions_count),
            reverse=True,
        )
    ]
    sources = [
        AnalyticsSource(source=source, **counts)
        for source, counts in sorted(
            source_counts.items(),
            key=lambda item: item[1]["engaged_visitors"],
            reverse=True,
        )[:8]
    ]
    return PortfolioAnalyticsResponse(
        period_days=period_days,
        experiences=experiences,
        daily=[AnalyticsDay(date=day, **values) for day, values in by_day.items()],
        sources=sources,
        totals={
            "experiences": len(widgets),
            "live": sum(widget.status == "active" for widget in widgets),
            "visitors": total_views,
            "starts": total_starts,
            "completions": total_completions,
            "leads": total_leads,
            "cta_clicks": total_cta,
        },
        rates={
            "start_rate": _rate(total_starts, total_views),
            "completion_rate": _rate(total_completions, total_starts),
            "lead_rate": _rate(total_leads, total_views),
            "cta_rate": _rate(total_cta, total_completions),
        },
        dropoff_by_step=dict(sorted(dropoff.items(), key=lambda item: item[1], reverse=True)),
    )


async def configure_widget_launch(
    db: AsyncSession,
    widget_id: str,
    user_id: uuid.UUID,
    payload: LaunchSetupRequest,
) -> tuple[Widget, str | None]:
    widget = await get_owned_widget(db, widget_id, user_id)
    launch = {
        "target_page_url": (
            validate_target_url(payload.target_page_url) if payload.target_page_url else None
        ),
        "cta_url": validate_target_url(payload.cta_url) if payload.cta_url else None,
        "cta_label": payload.cta_label or "Continue",
        "lead_fields": list(dict.fromkeys(payload.lead_fields)),
        "delivery_mode": payload.delivery_mode,
    }
    webhook_url = (
        validate_target_url(payload.delivery_webhook_url) if payload.delivery_webhook_url else None
    )
    new_secret: str | None = None
    if webhook_url and (
        webhook_url != widget.delivery_webhook_url or not widget.delivery_webhook_secret
    ):
        new_secret = secrets.token_urlsafe(32)
        widget.delivery_webhook_secret = new_secret
    if not webhook_url:
        widget.delivery_webhook_secret = None

    widget.launch_settings = launch
    widget.delivery_webhook_url = webhook_url
    widget.consent_text = payload.consent_text
    await db.flush()
    return widget, new_secret


async def test_widget_delivery(
    db: AsyncSession,
    widget_id: str,
    user_id: uuid.UUID,
) -> tuple[bool, int | None, datetime]:
    """Prove that the configured destination accepts Magnit's signed payload."""
    widget = await get_owned_widget(db, widget_id, user_id)
    if not widget.delivery_webhook_url or not widget.delivery_webhook_secret:
        raise ValueError("delivery_not_configured")

    checked_at = datetime.now(UTC)
    delivered, status_code = await post_signed_webhook(
        widget.delivery_webhook_url,
        widget.delivery_webhook_secret,
        "connection.test",
        {
            "event": "connection.test",
            "widget": {
                "id": str(widget.id),
                "title": widget.title,
            },
            "sent_at": checked_at.isoformat(),
        },
    )
    launch = dict(widget.launch_settings or {})
    launch.update(
        {
            "delivery_status": "connected" if delivered else "failed",
            "delivery_checked_at": checked_at.isoformat(),
            "delivery_status_code": status_code,
        }
    )
    widget.launch_settings = launch
    await db.flush()
    return delivered, status_code, checked_at


async def list_heal_events(
    db: AsyncSession, widget_id: str, user_id: uuid.UUID
) -> list[WidgetHealEvent]:
    widget = await get_owned_widget(db, widget_id, user_id)
    result = await db.execute(
        select(WidgetHealEvent)
        .where(WidgetHealEvent.widget_id == widget.id)
        .order_by(WidgetHealEvent.detected_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())
