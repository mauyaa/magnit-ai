"""Is this tool actually ready to be in front of customers?

The checklist exists because "built" and "working" are different things, and the
gap between them is where tools quietly fail: deployed but never embedded,
capturing leads that go nowhere, ending on a call to action that points at
nothing. Every check below is answered from real state — a deployment row, an
impression with a referrer, a connected integration — never from a box someone
ticked.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.entitlements import Entitlements
from app.features.integrations.models import Integration
from app.features.integrations.service import integration_covers
from app.features.users.models import User
from app.features.widgets.models import Widget, WidgetInteraction
from app.features.widgets.outcomes import effective_outcome_config
from app.platform.pipeline.schemas import DecisionSpec


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    label: str
    detail: str
    done: bool
    # Where the interface should send someone to fix it. Empty when the check is
    # not something the owner acts on directly (a plan cap, say).
    action: str = ""
    blocking: bool = True


@dataclass(frozen=True)
class Readiness:
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.done for check in self.checks if check.blocking)

    @property
    def completed(self) -> int:
        return sum(1 for check in self.checks if check.done)


def _decision_of(widget: Widget) -> DecisionSpec | None:
    raw = (widget.widget_logic or {}).get("decision")
    if not isinstance(raw, dict):
        return None
    try:
        return DecisionSpec.model_validate(raw)
    except ValueError:
        return None


async def _embed_detected(db: AsyncSession, widget: Widget) -> bool:
    """Whether the tool has been seen on a page that is not one of ours.

    Recorded at the moment of the view, not of an interaction. Requiring an
    interaction made this both wrong ways at once: a correctly pasted embed that
    nobody had touched yet could not be verified, while the owner clicking
    through the preview inside their own dashboard verified it falsely. A view
    with a referrer from the customer's own host is the honest signal — it means
    the snippet is on a real page, whether or not anyone has used it yet.
    """
    if widget.first_embedded_at is not None:
        return True

    # Tools published before views carried a referrer. An interaction from a
    # real page is still proof for them.
    seen = await db.scalar(
        select(func.count(WidgetInteraction.id)).where(
            WidgetInteraction.widget_id == widget.id,
            WidgetInteraction.source_url.is_not(None),
        )
    )
    return bool(seen)


async def _delivery_configured(db: AsyncSession, widget: Widget, owner: User) -> bool:
    if widget.delivery_webhook_url:
        return True
    if owner.notify_on_lead and owner.email_verified:
        return True
    integrations = (
        (
            await db.execute(
                select(Integration).where(
                    Integration.user_id == widget.user_id,
                    Integration.status == "connected",
                )
            )
        )
        .scalars()
        .all()
    )
    return any(integration_covers(item, widget.id) for item in integrations)


def _entitlement_detail(widget: Widget, entitlements: Entitlements, can_publish: bool) -> str:
    """Say *why* this tool is (or is not) covered.

    Three different situations pass this check and they are not interchangeable.
    Printing the plan's cap in all of them produced "1 of 0 live tools in use"
    for a tool bought outright on the free plan — arithmetic that is not wrong so
    much as meaningless.
    """
    if widget.id in entitlements.granted_widget_ids:
        return "Paid for on its own, so it stays live on any plan."
    if not can_publish:
        return (
            f"{entitlements.plan.name} allows "
            f"{entitlements.plan.live_tool_limit} live "
            f"{'tool' if entitlements.plan.live_tool_limit == 1 else 'tools'}."
        )
    if entitlements.plan.live_tool_limit <= 0:
        return f"Covered on {entitlements.plan.name}."
    return (
        f"{entitlements.usage.live_tools} of {entitlements.plan.live_tool_limit} live tools in use."
    )


async def assess_readiness(
    db: AsyncSession,
    widget: Widget,
    owner: User,
    entitlements: Entitlements,
) -> Readiness:
    decision = _decision_of(widget)
    outcomes = effective_outcome_config(widget.outcome_config, decision, widget.copywriting)
    launch = widget.launch_settings or {}

    built = widget.status == "active" and bool(widget.deployment_url)
    question_count = len(decision.questions) if decision is not None else 0
    has_questions = question_count > 0
    destination = str(launch.get("cta_url") or outcomes.cta.url or "").strip()
    # Resolved once. Each of these is a query, and reading them inline in both
    # the `done` flag and the sentence describing it would double the round trips
    # for a panel that renders on every visit to the tool.
    delivery_ready = await _delivery_configured(db, widget, owner)
    embedded = await _embed_detected(db, widget)
    can_publish = entitlements.can_publish(widget)

    checks = (
        ReadinessCheck(
            id="built",
            label="Tool built and deployed",
            detail=(
                "Live at its own address."
                if built
                else "Finish the build to publish this tool to its own address."
            ),
            done=built,
            action="build",
        ),
        ReadinessCheck(
            id="entitled",
            label="Covered by your plan",
            detail=_entitlement_detail(widget, entitlements, can_publish),
            done=can_publish,
            action="billing",
        ),
        ReadinessCheck(
            id="questions",
            label="Questions reviewed",
            detail=(
                f"{question_count} questions, scored and ready."
                if has_questions
                else "This tool has no question flow yet."
            ),
            done=has_questions,
            action="questions",
        ),
        ReadinessCheck(
            id="outcomes",
            label="Results configured",
            detail=(
                f"{len(outcomes.bands)} score "
                f"{'band' if len(outcomes.bands) == 1 else 'bands'} covering every score."
            ),
            done=bool(outcomes.bands),
            action="outcomes",
        ),
        ReadinessCheck(
            id="destination",
            label="Call to action points somewhere",
            detail=(
                f"Visitors are sent to {destination}"
                if destination
                else "Set where the final button sends people."
            ),
            done=bool(destination),
            action="outcomes",
        ),
        ReadinessCheck(
            id="delivery",
            label="Leads reach you",
            detail=(
                "Captured leads are delivered."
                if delivery_ready
                else "Turn on lead emails, add a webhook, or connect an integration."
            ),
            done=delivery_ready,
            action="integrations",
        ),
        ReadinessCheck(
            id="embedded",
            label="Embedded on your site",
            detail=(
                # The host, when we have it. "Seen running on your website" is
                # a claim; "seen running on northsidedental.com" is evidence,
                # and it is also how an owner spots that they pasted it onto
                # their staging site by mistake.
                f"Seen running on {widget.embed_host}."
                if embedded and widget.embed_host
                else "Seen running on your website."
                if embedded
                else "Paste the embed snippet into the page this tool belongs on."
            ),
            done=embedded,
            action="embed",
            # Not blocking: publishing is what produces the snippet, so requiring
            # the snippet before publishing would be a circular gate.
            blocking=False,
        ),
    )

    return Readiness(checks=checks)
