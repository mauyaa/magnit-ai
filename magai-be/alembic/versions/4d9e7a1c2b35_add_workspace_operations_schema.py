"""Add lead follow-up, integrations, brand and usage tables.

Revision ID: 4d9e7a1c2b35
Revises: 2f7b1c9d4e6a
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import JSONType, UUIDType

revision: str = "4d9e7a1c2b35"
down_revision: str | None = "2f7b1c9d4e6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
    )
    op.add_column("leads", sa.Column("tags", JSONType(), nullable=True))
    op.add_column(
        "leads",
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_leads_widget_status", "leads", ["widget_id", "status"])
    if op.get_bind().dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_leads_status",
            "leads",
            "status IN ('new', 'contacted', 'qualified', 'won', 'lost')",
        )

    op.create_table(
        "lead_notes",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("lead_id", UUIDType(), nullable=False),
        sa.Column("author_id", UUIDType(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_notes_lead_id", "lead_notes", ["lead_id"])
    op.create_index(
        "ix_lead_notes_lead_created",
        "lead_notes",
        ["lead_id", "created_at"],
    )

    op.create_table(
        "workspace_brands",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("user_id", UUIDType(), nullable=False),
        sa.Column("accent_color", sa.String(length=9), nullable=True),
        sa.Column("background_color", sa.String(length=9), nullable=True),
        sa.Column("font_pairing", sa.String(length=40), nullable=True),
        sa.Column("corner_radius", sa.Integer(), nullable=True),
        sa.Column("tone", sa.String(length=20), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("brand_personality", sa.String(length=240), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "corner_radius IS NULL OR (corner_radius >= 0 AND corner_radius <= 32)",
            name="ck_workspace_brands_corner_radius",
        ),
        sa.CheckConstraint(
            "tone IS NULL OR tone IN ('light', 'soft', 'deep')",
            name="ck_workspace_brands_tone",
        ),
    )
    op.create_index(
        "ix_workspace_brands_user_id",
        "workspace_brands",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "usage_records",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("user_id", UUIDType(), nullable=False),
        sa.Column("widget_id", UUIDType(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column("context", JSONType(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('build', 'publish')",
            name="ck_usage_records_kind",
        ),
    )
    op.create_index("ix_usage_records_user_id", "usage_records", ["user_id"])
    op.create_index(
        "ix_usage_records_occurred_at",
        "usage_records",
        ["occurred_at"],
    )
    op.create_index(
        "ix_usage_records_user_kind_time",
        "usage_records",
        ["user_id", "kind", "occurred_at"],
    )

    op.create_table(
        "integrations",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("user_id", UUIDType(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("config", JSONType(), nullable=True),
        sa.Column("credential_encrypted", sa.Text(), nullable=True),
        sa.Column("credential_hint", sa.String(length=32), nullable=True),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("widget_ids", JSONType(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_integrations_user_provider",
        ),
        sa.CheckConstraint(
            "status IN ('connected', 'error', 'disabled')",
            name="ck_integrations_status",
        ),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])
    op.create_index(
        "ix_integrations_user_status",
        "integrations",
        ["user_id", "status"],
    )

    op.create_table(
        "integration_deliveries",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("integration_id", UUIDType(), nullable=False),
        sa.Column("lead_id", UUIDType(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["integrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped')",
            name="ck_integration_deliveries_status",
        ),
    )
    op.create_index(
        "ix_integration_deliveries_integration_id",
        "integration_deliveries",
        ["integration_id"],
    )
    op.create_index(
        "ix_integration_deliveries_lead_id",
        "integration_deliveries",
        ["lead_id"],
    )
    op.create_index(
        "ix_integration_deliveries_lead",
        "integration_deliveries",
        ["lead_id", "created_at"],
    )
    op.create_index(
        "ix_integration_deliveries_integration",
        "integration_deliveries",
        ["integration_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_deliveries_integration",
        table_name="integration_deliveries",
    )
    op.drop_index(
        "ix_integration_deliveries_lead",
        table_name="integration_deliveries",
    )
    op.drop_index(
        "ix_integration_deliveries_lead_id",
        table_name="integration_deliveries",
    )
    op.drop_index(
        "ix_integration_deliveries_integration_id",
        table_name="integration_deliveries",
    )
    op.drop_table("integration_deliveries")
    op.drop_index("ix_integrations_user_status", table_name="integrations")
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
    op.drop_index("ix_usage_records_user_kind_time", table_name="usage_records")
    op.drop_index("ix_usage_records_occurred_at", table_name="usage_records")
    op.drop_index("ix_usage_records_user_id", table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index("ix_workspace_brands_user_id", table_name="workspace_brands")
    op.drop_table("workspace_brands")
    op.drop_index("ix_lead_notes_lead_created", table_name="lead_notes")
    op.drop_index("ix_lead_notes_lead_id", table_name="lead_notes")
    op.drop_table("lead_notes")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_leads_status", "leads", type_="check")
    op.drop_index("ix_leads_widget_status", table_name="leads")
    op.drop_column("leads", "contacted_at")
    op.drop_column("leads", "tags")
    op.drop_column("leads", "status")
