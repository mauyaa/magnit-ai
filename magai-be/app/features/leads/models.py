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
