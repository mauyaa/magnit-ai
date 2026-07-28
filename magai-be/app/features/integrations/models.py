import uuid
from datetime import datetime

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base
from app.platform.db.mixins import TimestampMixin
from app.platform.db.types import JSONType, UUIDType

INTEGRATION_STATUSES = ("connected", "error", "disabled")
DELIVERY_STATUSES = ("pending", "delivered", "failed", "skipped")


class Integration(Base, TimestampMixin):
    """One connection between a workspace and an outside system.

    Workspace-scoped rather than widget-scoped: someone with four tools connects
    HubSpot once. ``widget_ids`` narrows which tools feed it, and ``None`` means
    all of them — including tools built after the connection was made, which is
    what an owner expects when they connect their CRM before building anything.
    """

    __tablename__ = "integrations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('connected', 'error', 'disabled')",
            name="ck_integrations_status",
        ),
        # One connection per provider per workspace. Connecting HubSpot twice is
        # always a mistake, and two live connections would double every lead.
        UniqueConstraint("user_id", "provider", name="uq_integrations_user_provider"),
        Index("ix_integrations_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="connected")

    # Non-secret provider settings: a list id, a portal id, a spreadsheet name.
    # Safe to return to the client, and does so.
    config: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    # Fernet ciphertext, never plaintext, and never serialised into a response.
    # See app/platform/security/secrets.py for why this is encrypted rather than
    # hashed.
    credential_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The trailing characters of the credential, kept so the owner can recognise
    # which key is connected without us ever echoing the key itself.
    credential_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # For providers whose "connection" is a URL the customer pastes (Zapier,
    # Make, n8n, a custom endpoint) rather than a key we authenticate with.
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NULL means every tool, present or future. An empty list means none, which
    # is a deliberate state — it is how an owner pauses a connection without
    # deleting the credential they would have to paste again.
    widget_ids: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Running totals, so the connection card can show that it is actually doing
    # something rather than only that it is configured.
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    deliveries = relationship(
        "IntegrationDelivery",
        back_populates="integration",
        cascade="all, delete-orphan",
        order_by="IntegrationDelivery.created_at.desc()",
    )


class IntegrationDelivery(Base, TimestampMixin):
    """One attempt to hand one lead to one connection.

    Exists so "did my CRM get this?" has an answer that is not a guess. It is
    also what the lead timeline reads to show delivery as an event alongside the
    capture itself.
    """

    __tablename__ = "integration_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped')",
            name="ck_integration_deliveries_status",
        ),
        Index("ix_integration_deliveries_lead", "lead_id", "created_at"),
        Index("ix_integration_deliveries_integration", "integration_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True for the "send a test event" button, so a test cannot be mistaken for
    # a real lead in the delivery history.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    integration = relationship("Integration", back_populates="deliveries")
