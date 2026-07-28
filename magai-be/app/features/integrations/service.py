"""Connect, test, and fan a captured lead out to every connection that wants it."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.features.integrations.models import Integration, IntegrationDelivery
from app.features.integrations.providers import (
    CATALOG_BY_ID,
    DeliveryResult,
    LeadPayload,
    Provider,
    ProviderError,
    deliver,
    get_provider,
)
from app.features.leads.models import Lead
from app.features.widgets.models import Widget
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory
from app.platform.security.secrets import (
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)
from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url

logger = logging.getLogger(__name__)


class IntegrationNotFound(Exception):
    """No such connection, or it belongs to another workspace."""


def _split_fields(
    provider: Provider,
    values: dict[str, str],
) -> tuple[str | None, dict, str | None]:
    """Sort submitted values into credential, config and endpoint.

    One dictionary arrives from the client; the three destinations have different
    security properties, so the split happens once, here, rather than at each
    call site guessing which key is a secret.
    """
    credential: str | None = None
    endpoint_url: str | None = None
    config: dict[str, str] = {}

    for spec in provider.fields:
        raw = str(values.get(spec.name, "") or "").strip()
        if not raw:
            if spec.required:
                raise ProviderError(f"missing_field:{spec.name}")
            continue
        if spec.kind == "secret":
            credential = raw
        elif spec.name == "endpoint_url":
            endpoint_url = raw
        else:
            config[spec.name] = raw

    if provider.auth == "endpoint" and not endpoint_url:
        raise ProviderError("missing_field:endpoint_url")
    if (
        provider.auth == "api_key"
        and not credential
        and any(spec.kind == "secret" for spec in provider.fields)
    ):
        raise ProviderError("missing_field:credential")
    return credential, config, endpoint_url


async def list_integrations(db: AsyncSession, user_id: uuid.UUID) -> list[Integration]:
    result = await db.execute(
        select(Integration)
        .where(Integration.user_id == user_id)
        .order_by(Integration.created_at.asc())
    )
    return list(result.scalars().all())


async def get_owned_integration(
    db: AsyncSession, integration_id: str, user_id: uuid.UUID
) -> Integration:
    try:
        parsed = uuid.UUID(str(integration_id))
    except (ValueError, AttributeError, TypeError):
        raise IntegrationNotFound(integration_id) from None
    integration = await db.scalar(
        select(Integration).where(Integration.id == parsed, Integration.user_id == user_id)
    )
    if integration is None:
        raise IntegrationNotFound(integration_id)
    return integration


async def upsert_integration(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider_id: str,
    values: dict[str, str],
    widget_ids: list[str] | None,
) -> Integration:
    """Create or re-credential one connection.

    Upsert rather than insert because the unique constraint on (user, provider)
    makes reconnecting a broken integration the same action as connecting it, and
    a customer pasting a rotated key should not first have to find and delete the
    old connection.
    """
    provider = get_provider(provider_id)
    credential, config, endpoint_url = _split_fields(provider, values)

    # Customer-supplied destinations are validated before they are ever stored,
    # so an internal address cannot sit in the database waiting for the first
    # lead to turn it into an SSRF.
    if endpoint_url:
        endpoint_url = validate_target_url(endpoint_url)
    if provider.id == "activecampaign" and config.get("api_url"):
        validate_target_url(config["api_url"])

    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == provider.id
        )
    )
    if integration is None:
        integration = Integration(user_id=user_id, provider=provider.id)
        db.add(integration)

    integration.status = "connected"
    integration.config = config or None
    integration.endpoint_url = endpoint_url
    integration.widget_ids = widget_ids
    integration.last_error = None
    if credential:
        integration.credential_encrypted = encrypt_secret(credential)
        integration.credential_hint = mask_secret(credential)
    await db.flush()
    return integration


async def set_integration_scope(
    db: AsyncSession, integration: Integration, widget_ids: list[str] | None
) -> Integration:
    integration.widget_ids = widget_ids
    await db.flush()
    return integration


async def set_integration_enabled(
    db: AsyncSession, integration: Integration, enabled: bool
) -> Integration:
    """Pause or resume without discarding the credential.

    Disabling has to be non-destructive: an owner turning a connection off for a
    week should not have to go back to HubSpot for a new token to turn it on
    again.
    """
    integration.status = "connected" if enabled else "disabled"
    await db.flush()
    return integration


async def delete_integration(db: AsyncSession, integration: Integration) -> None:
    await db.delete(integration)
    await db.flush()


def _credential_for(integration: Integration) -> str | None:
    if not integration.credential_encrypted:
        return None
    try:
        return decrypt_secret(integration.credential_encrypted)
    except SecretDecryptionError:
        # The signing key changed under us. Say so precisely: this is the one
        # failure a customer can fix, by pasting the credential again.
        raise ProviderError("credential_unreadable_reconnect_required") from None


def _sample_payload(widget_title: str) -> LeadPayload:
    return LeadPayload(
        email="test.lead@magnitai.example",
        name="Test Lead",
        score=82,
        answers={"company_size": "11-50 employees"},
        result_title="Strong fit",
        widget_title=widget_title or "Magnit test",
        widget_id="00000000-0000-0000-0000-000000000000",
        lead_id="00000000-0000-0000-0000-000000000000",
        created_at=datetime.now(UTC).isoformat(),
        is_test=True,
    )


async def test_integration(db: AsyncSession, integration: Integration) -> DeliveryResult:
    """Send a real, clearly-marked test event through the live delivery path.

    Not a connectivity ping: it exercises the same code, credential and payload
    shape a captured lead will, so a green result means the next real lead lands.
    """
    provider = get_provider(integration.provider)
    try:
        credential = _credential_for(integration)
    except ProviderError as exc:
        result = DeliveryResult(False, None, str(exc))
    else:
        result = await deliver(
            provider,
            _sample_payload("Connection test"),
            credential=credential,
            config=integration.config,
            endpoint_url=integration.endpoint_url,
            signing_secret=_signing_secret(integration),
        )

    integration.last_test_at = datetime.now(UTC)
    integration.last_status_code = result.status_code
    integration.last_error = None if result.ok else (result.error or "delivery failed")[:500]
    if not result.ok and integration.status == "connected":
        integration.status = "error"
    elif result.ok and integration.status == "error":
        integration.status = "connected"

    db.add(
        IntegrationDelivery(
            integration_id=integration.id,
            lead_id=None,
            status="delivered" if result.ok else "failed",
            status_code=result.status_code,
            error=integration.last_error,
            is_test=True,
        )
    )
    await db.flush()
    return result


def _signing_secret(integration: Integration) -> str:
    """A per-connection HMAC secret, derived deterministically from its id.

    Deterministic rather than stored so there is no second secret to leak, and no
    migration needed to add one. The id is a v4 UUID, so it is unguessable, and
    it is combined with the application secret before use.
    """
    return hashlib.sha256(f"{settings.secret_key}:{integration.id}".encode()).hexdigest()


def integration_covers(integration: Integration, widget_id: uuid.UUID) -> bool:
    """Whether this connection should receive leads from this tool.

    ``None`` means every tool including ones built later; an empty list means
    none, which is how a connection is paused per-tool rather than globally.
    """
    if integration.widget_ids is None:
        return True
    return str(widget_id) in {str(item) for item in integration.widget_ids}


async def fan_out_lead(
    lead_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Deliver one captured lead to every connection that covers its tool.

    Runs as a background task after the visitor's response has been sent, and
    opens its own session for the same reason the email notifier does: the
    request-scoped session is closed by then, and reading the lead in a fresh
    transaction guarantees we never deliver a row that was rolled back.

    Never raises. A visitor filling in a calculator on someone's website must not
    see an error because a CRM is down; the failure is recorded and surfaced on
    the connection instead.
    """
    factory = session_factory or async_session_factory
    delivered = 0
    try:
        async with factory() as db:
            row = (
                await db.execute(
                    select(Lead, Widget)
                    .join(Widget, Lead.widget_id == Widget.id)
                    .where(Lead.id == lead_id)
                )
            ).first()
            if row is None:
                return 0
            lead, widget = row

            integrations = list(
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
            targets = [i for i in integrations if integration_covers(i, widget.id)]
            if not targets:
                return 0

            payload = LeadPayload(
                email=lead.email,
                name=lead.name,
                score=lead.score,
                answers=lead.answers or {},
                result_title=(
                    str((lead.extra_meta or {}).get("result_key"))
                    if (lead.extra_meta or {}).get("result_key")
                    else None
                ),
                widget_title=widget.title,
                widget_id=str(widget.id),
                lead_id=str(lead.id),
                created_at=lead.created_at.isoformat(),
            )

            for integration in targets:
                provider = CATALOG_BY_ID.get(integration.provider)
                if provider is None:
                    continue
                try:
                    credential = _credential_for(integration)
                    result = await deliver(
                        provider,
                        payload,
                        credential=credential,
                        config=integration.config,
                        endpoint_url=integration.endpoint_url,
                        signing_secret=_signing_secret(integration),
                    )
                except (ProviderError, UnsafeTargetURL) as exc:
                    result = DeliveryResult(False, None, str(exc))

                if result.ok:
                    delivered += 1
                    integration.delivered_count += 1
                    integration.last_error = None
                    if integration.status == "error":
                        integration.status = "connected"
                else:
                    integration.failed_count += 1
                    integration.last_error = (result.error or "delivery failed")[:500]
                    integration.status = "error"
                integration.last_status_code = result.status_code

                db.add(
                    IntegrationDelivery(
                        integration_id=integration.id,
                        lead_id=lead.id,
                        status="delivered" if result.ok else "failed",
                        status_code=result.status_code,
                        error=None if result.ok else integration.last_error,
                    )
                )

            if delivered:
                lead.forwarded = True
                lead.forwarded_at = datetime.now(UTC)
            await db.commit()
    except Exception:
        logger.exception("Could not fan out lead %s to integrations", lead_id)
        return delivered
    return delivered


async def deliveries_for_lead(db: AsyncSession, lead_id: uuid.UUID) -> list[IntegrationDelivery]:
    result = await db.execute(
        select(IntegrationDelivery)
        .options(selectinload(IntegrationDelivery.integration))
        .where(IntegrationDelivery.lead_id == lead_id)
        .order_by(IntegrationDelivery.created_at.asc())
    )
    return list(result.scalars().all())
