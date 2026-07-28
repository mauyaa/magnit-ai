import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base
from app.platform.db.mixins import TimestampMixin
from app.platform.db.types import JSONType, UUIDType

ROLES = ("owner", "admin", "member")
TOKEN_PURPOSES = ("verify_email", "reset_password")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Google's stable account identifier. Email is verified but can change, so
    # it is used only to link the first login and never as the provider identity.
    google_subject: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Null for the owner. Members point at the owner whose records form the
    # shared workspace. Existing ownership columns therefore remain stable while
    # every workspace-scoped query can resolve one canonical id.
    workspace_owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    workspace_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    workspace_timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Base32 TOTP shared secret; present during enrolment, before confirmation.
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Argon2 hashes of unused single-use recovery codes — never the codes themselves.
    mfa_recovery_codes: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    # Email the owner when one of their tools captures a lead. Defaults on: a
    # lead nobody hears about is the one failure mode this product cannot have.
    # Opt-out rather than opt-in, but genuinely switchable — a tool that starts
    # converting well would otherwise turn into an inbox flood.
    notify_on_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_weekly_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_product_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    labs_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    widgets = relationship("Widget", back_populates="user", cascade="all, delete-orphan")
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    brand = relationship(
        "WorkspaceBrand",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def workspace_id(self) -> uuid.UUID:
        """The id used by every workspace-owned record."""
        return self.workspace_owner_id or self.id

    @property
    def resolved_workspace_name(self) -> str:
        """A stable, data-derived label before the owner names the workspace."""
        if self.workspace_name and self.workspace_name.strip():
            return self.workspace_name.strip()
        domain = self.email.partition("@")[2].partition(".")[0].strip()
        return f"{domain.replace('-', ' ').title()} workspace" if domain else "My workspace"


class WorkspaceInvite(Base, TimestampMixin):
    """Single-use invitation to an existing owner's workspace."""

    __tablename__ = "workspace_invites"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_workspace_invites_role"),
        UniqueConstraint("token_hash", name="uq_workspace_invites_token_hash"),
        Index("ix_workspace_invites_owner_email", "owner_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiKey(Base, TimestampMixin):
    """Workspace API credential.

    The raw key is returned by the create endpoint exactly once. Only its SHA-256
    digest and a short, non-secret prefix survive in the database.
    """

    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        Index("ix_api_keys_owner_active", "owner_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomDomain(Base, TimestampMixin):
    """A customer-owned hostname assigned to one deployed tool project."""

    __tablename__ = "custom_domains"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'verified', 'error')",
            name="ck_custom_domains_status",
        ),
        UniqueConstraint("hostname", name="uq_custom_domains_hostname"),
        Index("ix_custom_domains_owner", "owner_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    widget_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    verification: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkspaceBrand(Base, TimestampMixin):
    """House style applied to every tool this workspace builds.

    The pipeline already extracts a brand from each target site, and for a single
    business that is exactly right. It stops being right for an agency running
    tools across five client sites, or for an owner whose site is off-brand
    relative to the identity they actually want in front of customers. This is
    the override: whatever is set here wins over what was read from the page,
    and whatever is left blank keeps deferring to the site.

    Every field is nullable for that reason. A partially-filled brand kit is the
    normal case, not an incomplete one.
    """

    __tablename__ = "workspace_brands"
    __table_args__ = (
        CheckConstraint(
            "corner_radius IS NULL OR (corner_radius >= 0 AND corner_radius <= 32)",
            name="ck_workspace_brands_corner_radius",
        ),
        CheckConstraint(
            "tone IS NULL OR tone IN ('light', 'soft', 'deep')",
            name="ck_workspace_brands_tone",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    accent_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    background_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    # A named pairing from the catalogue in service.py, not two free-text font
    # names: the generated widget can only load fonts we know how to request, so
    # accepting arbitrary names would produce silent fallbacks.
    font_pairing: Mapped[str | None] = mapped_column(String(40), nullable=True)
    corner_radius: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Prose the Architect stage receives as voice direction, e.g. "calm,
    # trustworthy, clarity-driven".
    brand_personality: Mapped[str | None] = mapped_column(String(240), nullable=True)

    user = relationship("User", back_populates="brand")


class AuthToken(Base, TimestampMixin):
    """Single-use, expiring token for email verification and password reset.

    Only a hash is stored. The raw token exists solely in the email that was sent,
    so a database leak cannot be replayed to take over accounts — the same reason
    passwords are hashed.
    """

    __tablename__ = "auth_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')", name="ck_auth_tokens_purpose"
        ),
        UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
        Index("ix_auth_tokens_user_purpose", "user_id", "purpose"),
        Index("ix_auth_tokens_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="auth_tokens")

    @property
    def is_usable(self) -> bool:
        """Unused and unexpired. Also enforced in the lookup query."""
        return self.used_at is None and self.expires_at > datetime.now(UTC)
