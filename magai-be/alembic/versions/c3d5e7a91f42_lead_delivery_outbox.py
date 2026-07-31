"""A durable outbox for captured leads.

Delivery used to be three fire-and-forget background tasks: one attempt each,
no record of what happened, and nothing at all if the process restarted between
the response and the task. A business relying on this product to receive its
leads had no way to know when it had not.

Each row is one lead's obligation to one destination, written in the same
transaction as the lead itself, with its attempts, its backoff and its last
error visible to the owner.

Revision ID: c3d5e7a91f42
Revises: b8c1f4d29e07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import UUIDType

revision: str = "c3d5e7a91f42"
down_revision: str | None = "b8c1f4d29e07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_deliveries",
        sa.Column("id", UUIDType(), primary_key=True),
        sa.Column(
            "lead_id",
            UUIDType(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column(
            "integration_id",
            UUIDType(),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "channel IN ('owner_email', 'webhook', 'integration')",
            name="ck_lead_deliveries_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped')",
            name="ck_lead_deliveries_status",
        ),
    )
    op.create_index("ix_lead_deliveries_lead_id", "lead_deliveries", ["lead_id"])
    op.create_index("ix_lead_deliveries_integration_id", "lead_deliveries", ["integration_id"])
    op.create_index("ix_lead_deliveries_lead", "lead_deliveries", ["lead_id", "created_at"])
    # Matches the sweep's predicate exactly: everything still owed, oldest first.
    op.create_index("ix_lead_deliveries_due", "lead_deliveries", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_lead_deliveries_due", table_name="lead_deliveries")
    op.drop_index("ix_lead_deliveries_lead", table_name="lead_deliveries")
    op.drop_index("ix_lead_deliveries_integration_id", table_name="lead_deliveries")
    op.drop_index("ix_lead_deliveries_lead_id", table_name="lead_deliveries")
    op.drop_table("lead_deliveries")
