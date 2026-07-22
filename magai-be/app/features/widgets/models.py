import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base
from app.platform.db.mixins import TimestampMixin


class Widget(Base, TimestampMixin):
    __tablename__ = "widgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="analyzing")

    blueprints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    brand_tokens: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    visual_language: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    widget_logic: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    copywriting: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    design_tokens: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    deployment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embed_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    leads_count: Mapped[int] = mapped_column(default=0)

    plan_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="one_time")
    lead_cap: Mapped[int] = mapped_column(default=500)

    build_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    build_progress: Mapped[float | None] = mapped_column(nullable=True)
    build_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    leads = relationship("Lead", back_populates="widget", cascade="all, delete-orphan")
