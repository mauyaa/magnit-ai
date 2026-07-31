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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base
from app.platform.db.mixins import TimestampMixin
from app.platform.db.types import JSONType, UUIDType

# The pipeline a captured lead moves along. Deliberately short: this is a
# follow-up marker for a small business, not a CRM's opportunity stages, and a
# five-state pipeline nobody maintains is worse than none.
LEAD_STATUSES = ("new", "contacted", "qualified", "won", "lost")


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'won', 'lost')",
            name="ck_leads_status",
        ),
        Index("ix_leads_widget_created", "widget_id", "created_at"),
        # The leads screen filters by status inside one tool, so both columns
        # belong in the index that serves it.
        Index("ix_leads_widget_status", "widget_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answers: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    extra_meta: Mapped[dict | None] = mapped_column("lead_meta", JSONType, nullable=True)
    forwarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- owner-maintained fields --------------------------------------------
    #
    # Everything above is what the visitor gave us. Everything below is what the
    # owner has done about it since, which is why it is separated: a re-import or
    # a replayed submission must never overwrite the follow-up work.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    # Free-text labels. A list rather than a join table because they are per-lead
    # annotations with no life of their own, and nothing queries across them.
    tags: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    widget = relationship("Widget", back_populates="leads")
    notes = relationship(
        "LeadNote",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadNote.created_at.desc()",
    )
    deliveries = relationship(
        "LeadDelivery",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadDelivery.created_at.asc()",
    )


# Where a captured lead has to end up. One row per lead per destination, so
# "did this reach my inbox / my webhook / my CRM?" has three separate answers
# rather than one hopeful boolean.
DELIVERY_CHANNELS = ("owner_email", "webhook", "integration")
DELIVERY_STATUSES = ("pending", "delivered", "failed", "skipped")

# Roughly 1m, 5m, 30m, 2h, 6h. Five attempts spread over most of a working day:
# long enough to ride out a CRM's maintenance window, short enough that a lead
# is not delivered the following week, and bounded so a permanently broken
# endpoint stops consuming workers.
RETRY_BACKOFF_SECONDS = (60, 300, 1_800, 7_200, 21_600)
MAX_DELIVERY_ATTEMPTS = len(RETRY_BACKOFF_SECONDS)


class LeadDelivery(Base, TimestampMixin):
    """One lead's journey to one destination, written down.

    A transactional outbox. The rows are created in the same transaction that
    saves the lead, so a lead that exists always has a record of where it still
    owes a delivery — which is the property in-process background tasks could
    never provide. A process restart, a deploy mid-request, or an SMTP outage
    used to mean the lead was captured and silently never forwarded, and nothing
    anywhere knew it had happened.
    """

    __tablename__ = "lead_deliveries"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('owner_email', 'webhook', 'integration')",
            name="ck_lead_deliveries_channel",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped')",
            name="ck_lead_deliveries_status",
        ),
        Index("ix_lead_deliveries_lead", "lead_id", "created_at"),
        # The sweep's exact predicate: everything still owed, oldest first.
        Index("ix_lead_deliveries_due", "status", "next_attempt_at"),
    )

    # Doubles as the idempotency key sent downstream, so a retry after an
    # ambiguous timeout is recognisable as the same delivery rather than a
    # second copy of the same lead.
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    # Set only for the integration channel: which connection this row is for.
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("integrations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # When the sweep may try again. Null once the row is settled either way.
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead", back_populates="deliveries")


class LeadNote(Base, TimestampMixin):
    """Something the owner wrote about a lead after speaking to them.

    Stored as rows rather than one growing text field so each note keeps its own
    timestamp and can take its place in the activity timeline in order, beside
    the capture and the delivery attempts.
    """

    __tablename__ = "lead_notes"
    __table_args__ = (Index("ix_lead_notes_lead_created", "lead_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Who wrote it. Nullable so deleting a teammate does not delete the note they
    # left on a lead the business still needs.
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    lead = relationship("Lead", back_populates="notes")
