from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.deps import CurrentUser
from app.features.billing.deps import CurrentEntitlements, upgrade_required
from app.features.billing.entitlements import FeatureLocked
from app.features.billing.plans import Feature
from app.features.leads.models import Lead
from app.features.users.brand import (
    FONT_PAIRINGS,
    FONT_PAIRINGS_BY_ID,
    get_brand,
    is_configured,
    upsert_brand,
)
from app.features.users.models import (
    ApiKey,
    CustomDomain,
    User,
    WorkspaceBrand,
    WorkspaceInvite,
)
from app.features.users.schemas import (
    AcceptWorkspaceInviteRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    CreateApiKeyRequest,
    CreateCustomDomainRequest,
    CreatedApiKeyResponse,
    CreateWorkspaceInviteRequest,
    CustomDomainListResponse,
    CustomDomainResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
    FontPairingResponse,
    NotificationSettingsRequest,
    TeamMemberResponse,
    TeamResponse,
    UpdateLabsRequest,
    UpdateProfileRequest,
    UpdateWorkspaceBrandRequest,
    UpdateWorkspaceRequest,
    UserResponse,
    WorkspaceBrandResponse,
    WorkspaceInviteResponse,
)
from app.features.users.service import IncorrectPassword, change_password, delete_account
from app.features.widgets.models import Widget
from app.features.widgets.service import WidgetNotFound, get_owned_widget
from app.platform.clients.deployment import (
    add_project_domain,
    remove_project_domain,
    verify_project_domain,
)
from app.platform.config.settings import settings
from app.platform.db.session import get_async_session
from app.platform.email.sender import EmailDeliveryError, send_email
from app.platform.security.passwords import PasswordPolicyError
from app.platform.security.rate_limit import rate_limit
from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url

router = APIRouter(prefix="/api/users", tags=["users"])

_INCORRECT_PASSWORD = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="incorrect_password"
)


def _to_response(user: CurrentUser) -> UserResponse:
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


def _require_workspace_owner(user: CurrentUser) -> None:
    if user.role != "owner" or user.workspace_owner_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _api_key_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(key.id),
        name=key.name,
        prefix=key.prefix,
        created_at=key.created_at.isoformat(),
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
    )


def _domain_response(domain: CustomDomain) -> CustomDomainResponse:
    return CustomDomainResponse(
        id=str(domain.id),
        widget_id=str(domain.widget_id),
        hostname=domain.hostname,
        status=domain.status,
        verification=domain.verification or [],
        last_checked_at=(domain.last_checked_at.isoformat() if domain.last_checked_at else None),
        last_error=domain.last_error,
        created_at=domain.created_at.isoformat(),
    )


_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _normalise_hostname(value: str) -> str:
    hostname = value.strip().lower().rstrip(".")
    if "://" in hostname:
        from urllib.parse import urlsplit

        parsed = urlsplit(hostname)
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("domain_must_be_hostname")
        hostname = parsed.hostname or ""
    if any(char in hostname for char in ("/", ":", "*", " ")):
        raise ValueError("domain_must_be_hostname")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid_domain") from exc
    labels = hostname.split(".")
    if (
        len(labels) < 2
        or len(hostname) > 253
        or not all(_DOMAIN_LABEL.fullmatch(x) for x in labels)
    ):
        raise ValueError("invalid_domain")
    return hostname


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    return _to_response(user)


@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    display_name = payload.display_name.strip() if payload.display_name else None
    await db.execute(update(User).where(User.id == user.id).values(display_name=display_name))
    user.display_name = display_name
    return _to_response(user)


@router.patch("/me/workspace", response_model=UserResponse)
async def update_workspace(
    payload: UpdateWorkspaceRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")

    name = payload.name.strip()
    timezone = payload.timezone.strip()
    owner_id = user.workspace_id
    await db.execute(
        update(User)
        .where(or_(User.id == owner_id, User.workspace_owner_id == owner_id))
        .values(workspace_name=name, workspace_timezone=timezone)
    )
    user.workspace_name = name
    user.workspace_timezone = timezone
    return _to_response(user)


@router.patch("/me/notifications", response_model=UserResponse)
async def update_notifications(
    payload: NotificationSettingsRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Turn lead notification emails on or off.

    No password re-entry: this only changes what lands in the owner's own inbox,
    and gating an unsubscribe behind a credential prompt is how people end up
    marking the mail as spam instead.
    """
    # An explicit UPDATE rather than mutate-and-add: `user` comes from the auth
    # dependency and is not guaranteed to be attached to *this* session, and
    # db.add() on an instance owned by another session raises outright.
    values = payload.model_dump(exclude_none=True)
    if values:
        await db.execute(update(User).where(User.id == user.id).values(**values))
        for key, value in values.items():
            setattr(user, key, value)
    return _to_response(user)


@router.patch("/me/labs", response_model=UserResponse)
async def update_labs(
    payload: UpdateLabsRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")
    owner_id = user.workspace_id
    await db.execute(
        update(User)
        .where(or_(User.id == owner_id, User.workspace_owner_id == owner_id))
        .values(labs_enabled=payload.enabled)
    )
    user.labs_enabled = payload.enabled
    return _to_response(user)


@router.patch(
    "/me/password",
    response_model=ChangePasswordResponse,
    dependencies=[rate_limit("auth")],
)
async def update_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> ChangePasswordResponse:
    try:
        await change_password(db, user, payload.current_password, payload.new_password)
    except IncorrectPassword:
        raise _INCORRECT_PASSWORD from None
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    return ChangePasswordResponse(changed=True)


def _brand_to_response(brand: WorkspaceBrand | None) -> WorkspaceBrandResponse:
    return WorkspaceBrandResponse(
        accent_color=brand.accent_color if brand else None,
        background_color=brand.background_color if brand else None,
        font_pairing=brand.font_pairing if brand else None,
        corner_radius=brand.corner_radius if brand else None,
        tone=brand.tone if brand else None,
        logo_url=brand.logo_url if brand else None,
        brand_personality=brand.brand_personality if brand else None,
        configured=is_configured(brand),
        font_pairings=[
            FontPairingResponse(
                id=pairing.id,
                label=pairing.label,
                heading=pairing.heading,
                body=pairing.body,
                note=pairing.note,
            )
            for pairing in FONT_PAIRINGS
        ],
    )


@router.get("/me/brand", response_model=WorkspaceBrandResponse)
async def get_workspace_brand(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> WorkspaceBrandResponse:
    """The workspace's house style, plus the font pairings it can choose from.

    Readable on every plan even though editing is gated: showing someone the
    screen they would get is a better upgrade argument than hiding it.
    """
    return _brand_to_response(await get_brand(db, user.workspace_id))


@router.put("/me/brand", response_model=WorkspaceBrandResponse)
async def update_workspace_brand(
    payload: UpdateWorkspaceBrandRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> WorkspaceBrandResponse:
    try:
        entitlements.require(Feature.BRAND_KIT)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    values = payload.model_dump(exclude_unset=True)
    if "font_pairing" in values and values["font_pairing"] is not None:
        if values["font_pairing"] not in FONT_PAIRINGS_BY_ID:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="unknown_font_pairing",
            )
    if values.get("logo_url"):
        # The URL ends up in an <img> inside a page served on the customer's own
        # domain, so it is validated the same way every other customer-supplied
        # destination is.
        try:
            values["logo_url"] = validate_target_url(values["logo_url"])
        except UnsafeTargetURL as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from None

    brand = await upsert_brand(db, user.workspace_id, values)
    return _brand_to_response(brand)


@router.get("/me/team", response_model=TeamResponse)
async def get_team(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> TeamResponse:
    owner_id = user.workspace_id
    members = list(
        (
            await db.scalars(
                select(User)
                .where(or_(User.id == owner_id, User.workspace_owner_id == owner_id))
                .order_by(User.created_at)
            )
        ).all()
    )
    now = datetime.now(UTC)
    invitations = list(
        (
            await db.scalars(
                select(WorkspaceInvite)
                .where(
                    WorkspaceInvite.owner_id == owner_id,
                    WorkspaceInvite.accepted_at.is_(None),
                    WorkspaceInvite.revoked_at.is_(None),
                    WorkspaceInvite.expires_at > now,
                )
                .order_by(WorkspaceInvite.created_at.desc())
            )
        ).all()
    )
    return TeamResponse(
        members=[
            TeamMemberResponse(
                id=str(member.id),
                email=member.email,
                display_name=member.display_name,
                role=member.role,
                joined_at=member.created_at.isoformat(),
                is_current_user=member.id == user.id,
            )
            for member in members
        ],
        invitations=[
            WorkspaceInviteResponse(
                id=str(invite.id),
                email=invite.email,
                role=invite.role,
                expires_at=invite.expires_at.isoformat(),
                created_at=invite.created_at.isoformat(),
            )
            for invite in invitations
        ],
        can_manage=user.role == "owner" and user.workspace_owner_id is None,
    )


@router.post(
    "/me/team/invitations",
    response_model=WorkspaceInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team_invitation(
    payload: CreateWorkspaceInviteRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> WorkspaceInviteResponse:
    _require_workspace_owner(user)
    email = str(payload.email).strip().lower()
    if email == user.email.lower():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_a_member")

    existing_member = await db.scalar(
        select(User.id).where(
            User.workspace_owner_id == user.id,
            User.email == email,
        )
    )
    if existing_member:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_a_member")

    await db.execute(
        update(WorkspaceInvite)
        .where(
            WorkspaceInvite.owner_id == user.id,
            WorkspaceInvite.email == email,
            WorkspaceInvite.accepted_at.is_(None),
            WorkspaceInvite.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )

    raw_token = secrets.token_urlsafe(36)
    invite = WorkspaceInvite(
        owner_id=user.id,
        email=email,
        role=payload.role,
        token_hash=_hash_secret(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()

    invite_url = (
        f"{settings.frontend_base_url.rstrip('/')}/dashboard/settings?invite={raw_token}#team"
    )
    try:
        await send_email(
            email,
            f"Join {user.resolved_workspace_name} on Magnitai",
            (
                f"{user.display_name or user.email} invited you to collaborate in "
                f"{user.resolved_workspace_name}.\n\n"
                f"Sign in with {email} and accept the invitation:\n{invite_url}\n\n"
                "This invitation expires in 7 days."
            ),
        )
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="email_delivery_failed",
        ) from None

    return WorkspaceInviteResponse(
        id=str(invite.id),
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at.isoformat(),
        created_at=invite.created_at.isoformat(),
    )


@router.post("/me/team/invitations/accept", response_model=UserResponse)
async def accept_team_invitation(
    payload: AcceptWorkspaceInviteRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    invite = await db.scalar(
        select(WorkspaceInvite).where(
            WorkspaceInvite.token_hash == _hash_secret(payload.token),
            WorkspaceInvite.accepted_at.is_(None),
            WorkspaceInvite.revoked_at.is_(None),
            WorkspaceInvite.expires_at > datetime.now(UTC),
        )
    )
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="invalid_or_expired_invite"
        )
    if invite.email.lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invite_email_mismatch")
    if invite.owner_id == user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_a_member")
    if user.workspace_owner_id and user.workspace_owner_id != invite.owner_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_in_a_workspace")

    owner = await db.get(User, invite.owner_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace_not_found")

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            workspace_owner_id=owner.id,
            role=invite.role,
            workspace_name=owner.resolved_workspace_name,
            workspace_timezone=owner.workspace_timezone,
            labs_enabled=owner.labs_enabled,
        )
    )
    user.workspace_owner_id = owner.id
    user.role = invite.role
    user.workspace_name = owner.resolved_workspace_name
    user.workspace_timezone = owner.workspace_timezone
    user.labs_enabled = owner.labs_enabled
    invite.accepted_at = datetime.now(UTC)
    await db.flush()
    return _to_response(user)


@router.delete(
    "/me/team/invitations/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_team_invitation(
    invite_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    _require_workspace_owner(user)
    invite = await db.scalar(
        select(WorkspaceInvite).where(
            WorkspaceInvite.id == invite_id,
            WorkspaceInvite.owner_id == user.id,
            WorkspaceInvite.accepted_at.is_(None),
        )
    )
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite_not_found")
    invite.revoked_at = datetime.now(UTC)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    member_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    _require_workspace_owner(user)
    member = await db.scalar(
        select(User).where(
            User.id == member_id,
            User.workspace_owner_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member_not_found")
    member.workspace_owner_id = None
    member.workspace_name = None
    member.role = "owner"
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> ApiKeyListResponse:
    keys = list(
        (
            await db.scalars(
                select(ApiKey)
                .where(
                    ApiKey.owner_id == user.workspace_id,
                    ApiKey.revoked_at.is_(None),
                )
                .order_by(ApiKey.created_at.desc())
            )
        ).all()
    )
    return ApiKeyListResponse(keys=[_api_key_response(key) for key in keys])


@router.post(
    "/me/api-keys",
    response_model=CreatedApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: CreateApiKeyRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> CreatedApiKeyResponse:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    try:
        entitlements.require(Feature.API_ACCESS)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    raw_key = f"magai_{secrets.token_urlsafe(32)}"
    created = ApiKey(
        owner_id=user.workspace_id,
        name=payload.name.strip(),
        prefix=raw_key[:14],
        key_hash=_hash_secret(raw_key),
        expires_at=(
            datetime.now(UTC) + timedelta(days=payload.expires_in_days)
            if payload.expires_in_days
            else None
        ),
    )
    db.add(created)
    await db.flush()
    base = _api_key_response(created)
    return CreatedApiKeyResponse(**base.model_dump(), key=raw_key)


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    key = await db.scalar(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.owner_id == user.workspace_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api_key_not_found")
    key.revoked_at = datetime.now(UTC)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/domains", response_model=CustomDomainListResponse)
async def list_custom_domains(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> CustomDomainListResponse:
    domains = list(
        (
            await db.scalars(
                select(CustomDomain)
                .where(CustomDomain.owner_id == user.workspace_id)
                .order_by(CustomDomain.created_at.desc())
            )
        ).all()
    )
    return CustomDomainListResponse(domains=[_domain_response(domain) for domain in domains])


@router.post(
    "/me/domains",
    response_model=CustomDomainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_domain(
    payload: CreateCustomDomainRequest,
    user: CurrentUser,
    entitlements: CurrentEntitlements,
    db: AsyncSession = Depends(get_async_session),
) -> CustomDomainResponse:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    try:
        entitlements.require(Feature.CUSTOM_DOMAINS)
    except FeatureLocked as exc:
        raise upgrade_required(exc) from None

    try:
        widget_id = uuid.UUID(payload.widget_id)
        hostname = _normalise_hostname(payload.hostname)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_domain"
        ) from None

    try:
        widget = await get_owned_widget(db, str(widget_id), user.workspace_id)
    except WidgetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget_not_found"
        ) from None
    if not widget.deployment_url:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="widget_not_deployed")
    existing = await db.scalar(select(CustomDomain.id).where(CustomDomain.hostname == hostname))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_in_use")

    try:
        remote = await add_project_domain(str(widget.id), hostname)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="domain_provider_error"
        ) from None

    checked_at = datetime.now(UTC)
    domain = CustomDomain(
        owner_id=user.workspace_id,
        widget_id=widget.id,
        hostname=hostname,
        status="verified" if remote.get("verified") else "pending",
        verification=remote.get("verification") or [],
        last_checked_at=checked_at,
    )
    db.add(domain)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain_in_use") from None
    return _domain_response(domain)


@router.post("/me/domains/{domain_id}/verify", response_model=CustomDomainResponse)
async def verify_custom_domain(
    domain_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> CustomDomainResponse:
    domain = await db.scalar(
        select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.owner_id == user.workspace_id,
        )
    )
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="domain_not_found")
    try:
        remote = await verify_project_domain(str(domain.widget_id), domain.hostname)
    except RuntimeError:
        domain.status = "error"
        domain.last_checked_at = datetime.now(UTC)
        domain.last_error = "The domain provider could not verify the DNS records."
        return _domain_response(domain)
    domain.status = "verified" if remote.get("verified") else "pending"
    domain.verification = remote.get("verification") or domain.verification or []
    domain.last_checked_at = datetime.now(UTC)
    domain.last_error = None
    return _domain_response(domain)


@router.delete("/me/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_domain(
    domain_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    domain = await db.scalar(
        select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.owner_id == user.workspace_id,
        )
    )
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="domain_not_found")
    try:
        await remove_project_domain(str(domain.widget_id), domain.hostname)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="domain_provider_error"
        ) from None
    await db.delete(domain)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/export")
async def export_workspace_data(
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    """Portable, secret-free copy of the customer's workspace data."""
    widgets = list(
        (
            await db.scalars(
                select(Widget)
                .where(Widget.user_id == user.workspace_id)
                .order_by(Widget.created_at)
            )
        ).all()
    )
    widget_ids = [widget.id for widget in widgets]
    leads = (
        list(
            (
                await db.scalars(
                    select(Lead).where(Lead.widget_id.in_(widget_ids)).order_by(Lead.created_at)
                )
            ).all()
        )
        if widget_ids
        else []
    )
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "workspace": {
            "id": str(user.workspace_id),
            "name": user.resolved_workspace_name,
            "timezone": user.workspace_timezone,
        },
        "account": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
        },
        "tools": [
            {
                "id": str(widget.id),
                "title": widget.title,
                "type": widget.widget_type,
                "source_url": widget.target_url,
                "status": widget.status,
                "deployment_url": widget.deployment_url,
                "leads_count": widget.leads_count,
                "impressions_count": widget.impressions_count,
                "starts_count": widget.starts_count,
                "completions_count": widget.completions_count,
                "cta_clicks_count": widget.cta_clicks_count,
                "created_at": widget.created_at.isoformat(),
                "deployed_at": (widget.deployed_at.isoformat() if widget.deployed_at else None),
            }
            for widget in widgets
        ],
        "leads": [
            {
                "id": str(lead.id),
                "tool_id": str(lead.widget_id),
                "email": lead.email,
                "name": lead.name,
                "score": lead.score,
                "answers": lead.answers,
                "status": lead.status,
                "tags": lead.tags or [],
                "created_at": lead.created_at.isoformat(),
                "contacted_at": (lead.contacted_at.isoformat() if lead.contacted_at else None),
            }
            for lead in leads
        ],
    }


@router.delete("/me", response_model=DeleteAccountResponse)
async def remove_account(
    payload: DeleteAccountRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_async_session),
) -> DeleteAccountResponse:
    """Irreversibly delete the account and every widget, lead and record it owns."""
    try:
        await delete_account(db, user, payload.current_password)
    except IncorrectPassword:
        raise _INCORRECT_PASSWORD from None

    return DeleteAccountResponse(deleted=True)
