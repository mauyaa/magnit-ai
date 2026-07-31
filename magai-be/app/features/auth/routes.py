from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.auth.google import (
    GoogleAuthNotConfigured,
    InvalidGoogleCredential,
    verify_google_credential,
)
from app.features.auth.mfa import (
    InvalidMfaCode,
    MfaAlreadyEnabled,
    MfaNotEnrolled,
    begin_enrollment,
    confirm_enrollment,
    disable_mfa,
    remaining_recovery_codes,
    verify_second_factor,
)
from app.features.auth.recovery import (
    InvalidToken,
    request_password_reset,
    reset_password,
    send_verification_email,
    verify_email,
)
from app.features.auth.schemas import (
    AcknowledgedResponse,
    ForgotPasswordRequest,
    GoogleCredentialRequest,
    LoginRequest,
    LogoutResponse,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaEnrollResponse,
    MfaStatusResponse,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenPairResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.features.auth.service import (
    AccountDisabled,
    EmailAlreadyRegistered,
    GoogleIdentityConflict,
    InvalidCredentials,
    authenticate,
    authenticate_google_identity,
    create_user,
    get_active_user,
)
from app.features.users.models import User
from app.platform.config.settings import settings
from app.platform.db.session import get_async_session
from app.platform.observability.metrics import product_activation_events_total
from app.platform.security.passwords import PasswordPolicyError
from app.platform.security.rate_limit import rate_limit
from app.platform.security.revocation import is_revoked, revoke
from app.platform.security.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid_credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_INVALID_TOKEN = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_token"
)


def _issue_tokens(user: User) -> TokenPairResponse:
    access, _ = create_access_token(str(user.id))
    refresh, _ = create_refresh_token(str(user.id))
    return TokenPairResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        created_at=user.created_at.isoformat(),
        email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled,
        notify_on_lead=user.notify_on_lead,
        display_name=user.display_name,
        workspace_name=user.resolved_workspace_name,
        workspace_timezone=user.workspace_timezone,
        workspace_id=str(user.workspace_id),
        notify_weekly_summary=user.notify_weekly_summary,
        notify_product_updates=user.notify_product_updates,
        labs_enabled=user.labs_enabled,
    )


# --------------------------------------------------------------------------- #
# Registration and sign-in
# --------------------------------------------------------------------------- #


@router.post(
    "/signup",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit("auth")],
)
async def signup(
    payload: SignupRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenPairResponse:
    try:
        user = await create_user(db, payload.email, payload.password)
    except EmailAlreadyRegistered:
        # Signup cannot hide that an address is taken and remain usable, so the
        # disclosure is accepted here and bounded by the rate limit.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email_already_registered"
        ) from None
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    await send_verification_email(db, user)
    product_activation_events_total.labels("account", "created").inc()
    return _issue_tokens(user)


@router.post("/login", response_model=TokenPairResponse, dependencies=[rate_limit("auth")])
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenPairResponse:
    """Authenticate, with a second-factor challenge when MFA is enrolled.

    The MFA check happens only after the password verifies, so the 428 response
    cannot be used to discover which accounts have MFA without valid credentials.
    """
    try:
        user = await authenticate(db, payload.email, payload.password)
    except InvalidCredentials:
        raise _INVALID_CREDENTIALS from None
    except AccountDisabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="account_disabled"
        ) from None

    if user.mfa_enabled:
        if not payload.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="mfa_required"
            )
        if not await verify_second_factor(db, user, payload.mfa_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_mfa_code")

    return _issue_tokens(user)


@router.post("/google", response_model=TokenPairResponse, dependencies=[rate_limit("auth")])
async def google_login(
    payload: GoogleCredentialRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenPairResponse:
    """Exchange a backend-verified Google ID token for a Magnitai session."""
    try:
        identity = await verify_google_credential(payload.credential)
    except GoogleAuthNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google_auth_not_configured",
        ) from None
    except InvalidGoogleCredential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_google_credential",
        ) from None

    try:
        user = await authenticate_google_identity(db, identity.subject, identity.email)
    except GoogleIdentityConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="google_identity_conflict",
        ) from None
    except AccountDisabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_disabled",
        ) from None

    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPairResponse, dependencies=[rate_limit("auth")])
async def refresh_tokens(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenPairResponse:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError:
        raise _INVALID_CREDENTIALS from None

    if await is_revoked(claims.jti):
        raise _INVALID_CREDENTIALS

    user = await get_active_user(db, claims.subject)
    if user is None:
        raise _INVALID_CREDENTIALS

    # Rotate: the presented token is single-use, so a stolen copy stops working as
    # soon as the legitimate client refreshes.
    await revoke(claims.jti, claims.expires_at)
    return _issue_tokens(user)


@router.post("/logout", response_model=LogoutResponse)
async def logout(payload: RefreshRequest, user: CurrentUser) -> LogoutResponse:
    """Revoke the supplied refresh token, ending the session."""
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError:
        # Nothing to revoke, but don't reveal whether the token was ever valid.
        return LogoutResponse(revoked=True)

    if claims.subject == str(user.id):
        await revoke(claims.jti, claims.expires_at)
    else:
        logger.warning("User %s tried to revoke a token belonging to %s", user.id, claims.subject)

    return LogoutResponse(revoked=True)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return _user_response(user)


# --------------------------------------------------------------------------- #
# Email verification
# --------------------------------------------------------------------------- #


@router.post("/verify-email", response_model=UserResponse, dependencies=[rate_limit("auth")])
async def verify_email_endpoint(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    try:
        user = await verify_email(db, payload.token)
    except InvalidToken:
        raise _INVALID_TOKEN from None
    return _user_response(user)


@router.post(
    "/resend-verification",
    response_model=AcknowledgedResponse,
    dependencies=[rate_limit("auth")],
)
async def resend_verification(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> AcknowledgedResponse:
    """Re-send the verification link to the signed-in user's own address."""
    await send_verification_email(db, user)
    return AcknowledgedResponse()


# --------------------------------------------------------------------------- #
# Password reset
# --------------------------------------------------------------------------- #


@router.post(
    "/forgot-password",
    response_model=AcknowledgedResponse,
    dependencies=[rate_limit("auth")],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_async_session),
) -> AcknowledgedResponse:
    """Begin a password reset.

    Always returns the same acknowledgement, whether or not the address has an
    account — otherwise this endpoint becomes a user-enumeration oracle.
    """
    await request_password_reset(db, payload.email)
    return AcknowledgedResponse()


@router.post(
    "/reset-password",
    response_model=TokenPairResponse,
    dependencies=[rate_limit("auth")],
)
async def reset_password_endpoint(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenPairResponse:
    """Complete a reset and sign the user straight in."""
    try:
        user = await reset_password(db, payload.token, payload.new_password)
    except InvalidToken:
        raise _INVALID_TOKEN from None
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    return _issue_tokens(user)


# --------------------------------------------------------------------------- #
# Multi-factor authentication
# --------------------------------------------------------------------------- #


@router.get("/mfa", response_model=MfaStatusResponse)
async def mfa_status(user: CurrentUser) -> MfaStatusResponse:
    return MfaStatusResponse(
        enabled=user.mfa_enabled,
        recovery_codes_remaining=remaining_recovery_codes(user),
    )


@router.post("/mfa/enroll", response_model=MfaEnrollResponse, dependencies=[rate_limit("auth")])
async def mfa_enroll(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> MfaEnrollResponse:
    """Start enrolment: returns a secret and a QR-scannable URI.

    MFA is not active until ``/mfa/confirm`` succeeds, so a mis-scanned code cannot
    lock the user out.
    """
    try:
        secret, uri = await begin_enrollment(db, user)
    except MfaAlreadyEnabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="mfa_already_enabled"
        ) from None
    return MfaEnrollResponse(secret=secret, provisioning_uri=uri)


@router.post("/mfa/confirm", response_model=MfaConfirmResponse, dependencies=[rate_limit("auth")])
async def mfa_confirm(
    payload: MfaConfirmRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> MfaConfirmResponse:
    try:
        codes = await confirm_enrollment(db, user, payload.code)
    except MfaAlreadyEnabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="mfa_already_enabled"
        ) from None
    except MfaNotEnrolled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="mfa_enrollment_not_started"
        ) from None
    except InvalidMfaCode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_mfa_code"
        ) from None

    return MfaConfirmResponse(enabled=True, recovery_codes=codes)


@router.post("/mfa/disable", response_model=MfaStatusResponse, dependencies=[rate_limit("auth")])
async def mfa_disable(
    payload: MfaDisableRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> MfaStatusResponse:
    """Turn MFA off. Requires a current code, so a stolen token cannot strip it."""
    try:
        await disable_mfa(db, user, payload.code)
    except MfaNotEnrolled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="mfa_not_enabled"
        ) from None
    except InvalidMfaCode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_mfa_code"
        ) from None

    return MfaStatusResponse(enabled=False, recovery_codes_remaining=0)
