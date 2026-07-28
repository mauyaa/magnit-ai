"""Grounded evidence, commercial entitlement and buyer funnel.

Revision ID: e6a2c4f91b70
Revises: d4b1f37c2e59
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import UUIDType

revision: str = "e6a2c4f91b70"
down_revision: str | None = "d4b1f37c2e59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"
    op.add_column("widgets", sa.Column("source_evidence", sa.JSON(), nullable=True))
    op.add_column(
        "widgets", sa.Column("source_content_fingerprint", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "widgets", sa.Column("source_brand_fingerprint", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "widgets",
        sa.Column("starts_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "widgets",
        sa.Column("completions_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "widgets",
        sa.Column("cta_clicks_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "widgets",
        sa.Column(
            "entitlement_status",
            sa.String(length=20),
            nullable=False,
            server_default="preview",
        ),
    )
    op.add_column("widgets", sa.Column("launch_settings", sa.JSON(), nullable=True))
    op.add_column("widgets", sa.Column("delivery_webhook_url", sa.Text(), nullable=True))
    op.add_column(
        "widgets", sa.Column("delivery_webhook_secret", sa.String(length=128), nullable=True)
    )
    op.add_column("widgets", sa.Column("consent_text", sa.Text(), nullable=True))
    op.add_column(
        "widgets", sa.Column("last_brand_check_at", sa.DateTime(timezone=True), nullable=True)
    )

    if is_postgres:
        op.create_check_constraint("ck_widgets_starts_non_negative", "widgets", "starts_count >= 0")
        op.create_check_constraint(
            "ck_widgets_completions_non_negative", "widgets", "completions_count >= 0"
        )
        op.create_check_constraint(
            "ck_widgets_cta_clicks_non_negative", "widgets", "cta_clicks_count >= 0"
        )
        op.create_check_constraint(
            "ck_widgets_entitlement_status",
            "widgets",
            "entitlement_status IN ('preview', 'checkout_pending', 'paid', 'complimentary')",
        )

    # Existing live tools were created before entitlement existed. Preserve them
    # as complimentary instead of locking their owners out after migration.
    op.execute(
        sa.text(
            "UPDATE widgets SET entitlement_status = 'complimentary' "
            "WHERE status IN ('active', 'building')"
        )
    )

    with op.batch_alter_table("widgets") as batch_op:
        batch_op.alter_column("starts_count", server_default=None)
        batch_op.alter_column("completions_count", server_default=None)
        batch_op.alter_column("cta_clicks_count", server_default=None)
        batch_op.alter_column("entitlement_status", server_default=None)

    op.create_table(
        "widget_interactions",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("widget_id", UUIDType(), nullable=False),
        sa.Column("session_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cta_clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lead_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_step", sa.String(length=100), nullable=True),
        sa.Column("result_key", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("attribution", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "widget_id",
            "session_hash",
            name="uq_widget_interactions_widget_session",
        ),
    )
    op.create_index(
        "ix_widget_interactions_widget_id",
        "widget_interactions",
        ["widget_id"],
    )
    op.create_index(
        "ix_widget_interactions_widget_created",
        "widget_interactions",
        ["widget_id", "created_at"],
    )
    op.create_table(
        "generation_usage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("widget_id", sa.UUID(), nullable=True),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_microusd", sa.Integer(), nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_usage_widget_id", "generation_usage", ["widget_id"])
    op.create_index(
        "ix_generation_usage_widget_created",
        "generation_usage",
        ["widget_id", "created_at"],
    )
    op.create_index(
        "ix_generation_usage_stage_created",
        "generation_usage",
        ["stage", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_usage_stage_created", table_name="generation_usage")
    op.drop_index("ix_generation_usage_widget_created", table_name="generation_usage")
    op.drop_index("ix_generation_usage_widget_id", table_name="generation_usage")
    op.drop_table("generation_usage")
    op.drop_index("ix_widget_interactions_widget_created", table_name="widget_interactions")
    op.drop_index("ix_widget_interactions_widget_id", table_name="widget_interactions")
    op.drop_table("widget_interactions")

    op.drop_constraint("ck_widgets_entitlement_status", "widgets", type_="check")
    op.drop_constraint("ck_widgets_cta_clicks_non_negative", "widgets", type_="check")
    op.drop_constraint("ck_widgets_completions_non_negative", "widgets", type_="check")
    op.drop_constraint("ck_widgets_starts_non_negative", "widgets", type_="check")
    op.drop_column("widgets", "last_brand_check_at")
    op.drop_column("widgets", "consent_text")
    op.drop_column("widgets", "delivery_webhook_secret")
    op.drop_column("widgets", "delivery_webhook_url")
    op.drop_column("widgets", "launch_settings")
    op.drop_column("widgets", "entitlement_status")
    op.drop_column("widgets", "cta_clicks_count")
    op.drop_column("widgets", "completions_count")
    op.drop_column("widgets", "starts_count")
    op.drop_column("widgets", "source_brand_fingerprint")
    op.drop_column("widgets", "source_content_fingerprint")
    op.drop_column("widgets", "source_evidence")
