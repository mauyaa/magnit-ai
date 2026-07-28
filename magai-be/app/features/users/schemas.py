from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


class ChangePasswordResponse(BaseModel):
    changed: bool


class DeleteAccountRequest(BaseModel):
    # Re-authentication for a destructive, irreversible action.
    current_password: str = Field(min_length=1, max_length=1024)


class DeleteAccountResponse(BaseModel):
    deleted: bool


class NotificationSettingsRequest(BaseModel):
    notify_on_lead: bool | None = None
    notify_weekly_summary: bool | None = None
    notify_product_updates: bool | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)


class UpdateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(min_length=1, max_length=80)


class UpdateLabsRequest(BaseModel):
    enabled: bool


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    created_at: str
    email_verified: bool
    mfa_enabled: bool
    notify_on_lead: bool
    display_name: str | None
    workspace_name: str
    workspace_timezone: str
    workspace_id: str
    notify_weekly_summary: bool
    notify_product_updates: bool
    labs_enabled: bool


class TeamMemberResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    role: str
    joined_at: str
    is_current_user: bool


class WorkspaceInviteResponse(BaseModel):
    id: str
    email: str
    role: str
    expires_at: str
    created_at: str


class TeamResponse(BaseModel):
    members: list[TeamMemberResponse]
    invitations: list[WorkspaceInviteResponse]
    can_manage: bool


class CreateWorkspaceInviteRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class AcceptWorkspaceInviteRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: str | None
    expires_at: str | None


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyResponse]


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class CreatedApiKeyResponse(ApiKeyResponse):
    key: str


class CustomDomainResponse(BaseModel):
    id: str
    widget_id: str
    hostname: str
    status: str
    verification: list[dict]
    last_checked_at: str | None
    last_error: str | None
    created_at: str


class CustomDomainListResponse(BaseModel):
    domains: list[CustomDomainResponse]


class CreateCustomDomainRequest(BaseModel):
    widget_id: str
    hostname: str = Field(min_length=4, max_length=253)


_HEX = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class FontPairingResponse(BaseModel):
    id: str
    label: str
    heading: str
    body: str
    note: str


class WorkspaceBrandResponse(BaseModel):
    accent_color: str | None
    background_color: str | None
    font_pairing: str | None
    corner_radius: int | None
    tone: str | None
    logo_url: str | None
    brand_personality: str | None
    # False while every field is still empty, so the screen can say "using each
    # site's own brand" rather than presenting blank inputs as a configuration.
    configured: bool
    font_pairings: list[FontPairingResponse]


class UpdateWorkspaceBrandRequest(BaseModel):
    """Every field optional, and null is meaningful.

    Omitting a key leaves it alone; sending null clears it and hands that
    decision back to the site's own brand. Those are different instructions and
    the API has to be able to tell them apart, which is why nothing here has a
    non-null default.
    """

    accent_color: str | None = Field(default=None, pattern=_HEX)
    background_color: str | None = Field(default=None, pattern=_HEX)
    font_pairing: str | None = Field(default=None, max_length=40)
    corner_radius: int | None = Field(default=None, ge=0, le=32)
    tone: Literal["light", "soft", "deep"] | None = None
    logo_url: str | None = Field(default=None, max_length=2048)
    brand_personality: str | None = Field(default=None, max_length=240)
