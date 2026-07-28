from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.billing.deps import CurrentEntitlements, upgrade_required
from app.features.billing.entitlements import FeatureLocked
from app.features.integrations.models import Integration
from app.features.integrations.providers import CATALOG, ProviderError, get_provider
from app.features.integrations.schemas import (
    ConnectIntegrationRequest,
    IntegrationListResponse,
    IntegrationResponse,
    IntegrationTestResponse,
    ProviderCatalogResponse,
    ProviderFieldResponse,
    ProviderResponse,
    UpdateIntegrationRequest,
)
from app.features.integrations.service import (
    IntegrationNotFound,
    delete_integration,
    get_owned_integration,
    list_integrations,
    set_integration_enabled,
    set_integration_scope,
    test_integration,
    upsert_integration,
)
from app.platform.db.session import get_async_session
from app.platform.security.url_guard import UnsafeTargetURL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="integration_not_found")


def _to_response(integration: Integration) -> IntegrationResponse:
    return IntegrationResponse(
        id=str(integration.id),
        provider=integration.provider,
        status=integration.status,
        config=integration.config,
        credential_hint=integration.credential_hint,
        endpoint_url=integration.endpoint_url,
        widget_ids=(
            [str(item) for item in integration.widget_ids]
            if integration.widget_ids is not None
            else None
        ),
        last_test_at=(integration.last_test_at.isoformat() if integration.last_test_at else None),
        last_status_code=integration.last_status_code,
        last_error=integration.last_error,
        delivered_count=integration.delivered_count,
        failed_count=integration.failed_count,
        created_at=integration.created_at.isoformat(),
    )


def _provider_error(exc: ProviderError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.get("/catalog", response_model=ProviderCatalogResponse)
async def get_catalog(entitlements: CurrentEntitlements) -> ProviderCatalogResponse:
    """Every provider, with the ones this plan cannot use marked rather than hidden.

    Hiding locked providers is the more common choice and the wrong one here: a
    customer evaluating whether to upgrade needs to see what upgrading buys.
    """
    return ProviderCatalogResponse(
        providers=[
            ProviderResponse(
                id=provider.id,
                name=provider.name,
                category=provider.category,
                description=provider.description,
                auth=provider.auth,
                setup_hint=provider.setup_hint,
                docs_url=provider.docs_url,
                feature=str(provider.feature),
                available=entitlements.has(provider.feature),
                fields=[
                    ProviderFieldResponse(
                        name=spec.name,
                        label=spec.label,
                        help_text=spec.help_text,
                        kind=spec.kind,
                        required=spec.required,
                        placeholder=spec.placeholder,
                    )
                    for spec in provider.fields
                ],
            )
            for provider in CATALOG
        ]
    )


@router.get("", response_model=IntegrationListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> IntegrationListResponse:
    integrations = await list_integrations(db, user.workspace_id)
    return IntegrationListResponse(integrations=[_to_response(i) for i in integrations])


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def connect_endpoint(
    payload: ConnectIntegrationRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> IntegrationResponse:
    try:
        provider = get_provider(payload.provider)
    except ProviderError as exc:
        raise _provider_error(exc) from None

    try:
        entitlements.require(provider.feature)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    try:
        integration = await upsert_integration(
            db, user.workspace_id, provider.id, payload.values, payload.widget_ids
        )
    except ProviderError as exc:
        raise _provider_error(exc) from None
    except UnsafeTargetURL as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    return _to_response(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_endpoint(
    integration_id: str,
    payload: UpdateIntegrationRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> IntegrationResponse:
    try:
        integration = await get_owned_integration(db, integration_id, user.workspace_id)
    except IntegrationNotFound:
        raise _NOT_FOUND from None

    if payload.enabled is not None:
        await set_integration_enabled(db, integration, payload.enabled)
    # Distinguished from "not sent" by the request model default: sending an
    # explicit null scopes the connection back to every tool, which is a real
    # instruction and not the same as leaving the scope alone.
    if "widget_ids" in payload.model_fields_set:
        await set_integration_scope(db, integration, payload.widget_ids)

    return _to_response(integration)


@router.post("/{integration_id}/test", response_model=IntegrationTestResponse)
async def test_endpoint(
    integration_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> IntegrationTestResponse:
    try:
        integration = await get_owned_integration(db, integration_id, user.workspace_id)
    except IntegrationNotFound:
        raise _NOT_FOUND from None

    result = await test_integration(db, integration)
    return IntegrationTestResponse(
        ok=result.ok,
        status_code=result.status_code,
        message=(
            "Test lead accepted"
            if result.ok
            else (result.error or "The destination did not accept the test event")
        ),
        checked_at=(integration.last_test_at or datetime.now(UTC)).isoformat(),
    )


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_endpoint(
    integration_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    try:
        integration = await get_owned_integration(db, integration_id, user.workspace_id)
    except IntegrationNotFound:
        raise _NOT_FOUND from None
    await delete_integration(db, integration)
