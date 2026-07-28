from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    # Supplied on the second attempt when the first returns mfa_required.
    mfa_code: str | None = Field(default=None, max_length=32)


class GoogleCredentialRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=20_000)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access-token lifetime in seconds.


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


class LogoutResponse(BaseModel):
    revoked: bool


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=1024)


class AcknowledgedResponse(BaseModel):
    """Deliberately contentless.

    Used by the endpoints that must not reveal whether an address is registered.
    """

    ok: bool = True


class MfaEnrollResponse(BaseModel):
    secret: str
    # otpauth:// URI for the client to render as a QR code.
    provisioning_uri: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class MfaConfirmResponse(BaseModel):
    enabled: bool
    # Shown exactly once; only hashes are stored server-side.
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class MfaStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int
