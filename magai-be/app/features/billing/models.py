import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db.base import Base
from app.platform.db.mixins import TimestampMixin
from app.platform.db.types import JSONType, UUIDType

USAGE_KINDS = ("build", "publish")


class UsageRecord(Base, TimestampMixin):
    """One metered event against a workspace's monthly allowance.

    A dedicated row rather than a count derived from another table. The obvious
    shortcut — counting deployments, or ``generation_usage`` rows with the codegen
    stage — undercounts exactly the case the quota exists to bound: a build that
    consumed a full generation run and then failed. Metering has to record the
    attempt, not the success.

    ``occurred_at`` is separate from ``created_at`` so a backfill or a replayed
    event can be attributed to the period it belongs to rather than to the moment
    the row happened to be written.
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        CheckConstraint("kind IN ('build', 'publish')", name="ck_usage_records_kind"),
        # The quota query is always "this user, this kind, since this instant",
        # so the index carries all three in that order.
        Index("ix_usage_records_user_kind_time", "user_id", "kind", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable and SET NULL: deleting a tool must not erase the record that its
    # build was metered, or a customer could reclaim quota by deleting evidence.
    widget_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("widgets.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # The plan in force when the event was metered, so a later upgrade cannot
    # retroactively change what an old period is judged against.
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    context: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
