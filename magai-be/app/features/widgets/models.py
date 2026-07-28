import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base
from app.platform.db.mixins import TimestampMixin
from app.platform.db.types import JSONType, UUIDType

WIDGET_STATUSES = ("analyzed", "building", "active", "failed")
ENTITLEMENT_STATUSES = ("preview", "checkout_pending", "paid", "complimentary")
HEAL_CHECK_TYPES = ("brand_drift", "deploy_health")
HEAL_STATUSES = ("detected", "healing", "healed", "failed", "no_drift")


class Widget(Base, TimestampMixin):
    __tablename__ = "widgets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('analyzed', 'building', 'active', 'failed')",
            name="ck_widgets_status",
        ),
        CheckConstraint("lead_cap >= 0", name="ck_widgets_lead_cap_non_negative"),
        CheckConstraint("leads_count >= 0", name="ck_widgets_leads_count_non_negative"),
        CheckConstraint("impressions_count >= 0", name="ck_widgets_impressions_non_negative"),
        CheckConstraint("starts_count >= 0", name="ck_widgets_starts_non_negative"),
        CheckConstraint("completions_count >= 0", name="ck_widgets_completions_non_negative"),
        CheckConstraint("cta_clicks_count >= 0", name="ck_widgets_cta_clicks_non_negative"),
        CheckConstraint(
            "entitlement_status IN ('preview', 'checkout_pending', 'paid', 'complimentary')",
            name="ck_widgets_entitlement_status",
        ),
        Index("ix_widgets_user_created", "user_id", "created_at"),
        # Partial index matching the heal-sweep predicate exactly: the sweep only
        # ever scans active widgets under the failure threshold, so indexing the
        # rest is dead weight on every write.
        Index(
            "ix_widgets_heal_due",
            "last_heal_check_at",
            postgresql_where=text("status = 'active' AND heal_failure_count < 3"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="analyzed")

    blueprints: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    creation_brief: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    # The model is only allowed to reason over this crawler-produced source map.
    source_evidence: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    source_content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_brand_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand_tokens: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    visual_language: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    widget_logic: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    copywriting: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    design_tokens: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    deployment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embed_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    leads_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Views recorded by the deployed widget. The denominator for conversion rate —
    # without it, "submissions" is a number with nothing to compare against.
    impressions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cta_clicks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plan_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="one_time")
    lead_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    entitlement_status: Mapped[str] = mapped_column(String(20), nullable=False, default="preview")

    # What the visitor sees after they finish, as the owner has edited it: score
    # bands, the advice under each one, the email-capture copy, the closing call
    # to action and the suggested next steps.
    #
    # Kept apart from `widget_logic` on purpose. That column holds what the model
    # designed and is replaced wholesale on every regeneration; this one holds
    # what a person decided and has to survive a rebuild. Merging the two is how
    # an owner's edited result copy would silently revert the next time the site
    # was re-read.
    outcome_config: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    # Customer-approved launch and delivery settings. The signing secret is a
    # webhook authenticity credential generated by Magnit, not a third-party key.
    launch_settings: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    delivery_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_webhook_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    build_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    build_progress: Mapped[float | None] = mapped_column(nullable=True)
    build_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heal_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_brand_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Consecutive failed heal attempts, used to back off a widget that keeps
    # failing instead of burning an AI call on it every sweep.
    heal_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="widgets")
    leads = relationship("Lead", back_populates="widget", cascade="all, delete-orphan")
    heal_events = relationship(
        "WidgetHealEvent",
        back_populates="widget",
        cascade="all, delete-orphan",
        order_by="WidgetHealEvent.detected_at.desc()",
    )
    deployments = relationship(
        "WidgetDeployment",
        back_populates="widget",
        cascade="all, delete-orphan",
        order_by="WidgetDeployment.created_at.desc()",
    )
    interactions = relationship(
        "WidgetInteraction",
        back_populates="widget",
        cascade="all, delete-orphan",
    )


class WidgetInteraction(Base, TimestampMixin):
    """One privacy-light visitor session used to calculate a real funnel."""

    __tablename__ = "widget_interactions"
    __table_args__ = (
        UniqueConstraint(
            "widget_id",
            "session_hash",
            name="uq_widget_interactions_widget_session",
        ),
        Index("ix_widget_interactions_widget_created", "widget_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 of the random browser session id. No IP address or fingerprint.
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cta_clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lead_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribution: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    widget = relationship("Widget", back_populates="interactions")


class WidgetHealEvent(Base, TimestampMixin):
    __tablename__ = "widget_heal_events"
    __table_args__ = (
        CheckConstraint(
            "check_type IN ('brand_drift', 'deploy_health')",
            name="ck_heal_events_check_type",
        ),
        CheckConstraint(
            "status IN ('detected', 'healing', 'healed', 'failed', 'no_drift')",
            name="ck_heal_events_status",
        ),
        Index("ix_heal_events_widget_detected", "widget_id", "detected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    diff_summary: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    healed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    widget = relationship("Widget", back_populates="heal_events")


class WidgetDeployment(Base, TimestampMixin):
    """Immutable log of every successful deploy, so a bad deploy can roll back.

    ``is_current`` marks the deployment the widget's ``deployment_url`` points at;
    the newest healthy row that is not current is the rollback candidate.
    """

    __tablename__ = "widget_deployments"
    __table_args__ = (Index("ix_widget_deployments_widget_created", "widget_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deployment_url: Mapped[str] = mapped_column(Text, nullable=False)
    # "build" | "redeploy" | "heal_brand_drift" | "heal_deploy_health" | "rollback"
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True)

    widget = relationship("Widget", back_populates="deployments")
