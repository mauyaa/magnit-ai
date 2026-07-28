"""add widget_heal_events table and widgets.last_heal_check_at

Revision ID: a1f9c3d7e2b4
Revises: c436ec5a63f5
Create Date: 2026-07-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import JSONType, UUIDType

revision: str = "a1f9c3d7e2b4"
down_revision: str | None = "c436ec5a63f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_heal_events",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("widget_id", UUIDType(), nullable=False),
        sa.Column("check_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("diff_summary", JSONType(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column("healed_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_widget_heal_events_widget_id", "widget_heal_events", ["widget_id"])
    op.add_column(
        "widgets", sa.Column("last_heal_check_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("widgets", "last_heal_check_at")
    op.drop_index("ix_widget_heal_events_widget_id", table_name="widget_heal_events")
    op.drop_table("widget_heal_events")
