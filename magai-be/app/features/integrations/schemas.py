from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderFieldResponse(BaseModel):
    name: str
    label: str
    help_text: str
    kind: str
    required: bool
    placeholder: str


class ProviderResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    auth: str
    setup_hint: str
    docs_url: str
    fields: list[ProviderFieldResponse]
    # The plan feature this provider needs, so the catalogue can be rendered
    # complete — with the locked ones visibly locked — rather than hiding
    # capabilities a customer is one upgrade away from.
    feature: str
    available: bool


class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderResponse]


class IntegrationResponse(BaseModel):
    id: str
    provider: str
    status: str
    config: dict | None
    # Never the credential itself — only enough of it to be recognised.
    credential_hint: str | None
    endpoint_url: str | None
    widget_ids: list[str] | None
    last_test_at: str | None
    last_status_code: int | None
    last_error: str | None
    delivered_count: int
    failed_count: int
    created_at: str


class IntegrationListResponse(BaseModel):
    integrations: list[IntegrationResponse]


class ConnectIntegrationRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    # Field names are provider-defined, so this is an open map validated against
    # the provider's declared fields in the service rather than by a schema that
    # would have to enumerate every provider's shape.
    values: dict[str, str] = Field(default_factory=dict)
    widget_ids: list[str] | None = None


class UpdateIntegrationRequest(BaseModel):
    enabled: bool | None = None
    widget_ids: list[str] | None = None


class IntegrationTestResponse(BaseModel):
    ok: bool
    status_code: int | None
    message: str
    checked_at: str
