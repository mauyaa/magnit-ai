"""Add the per-user lead notification preference.

Server default is true so existing accounts start notified: someone who signed
up before this migration still has tools that can capture leads, and silently
opting them out of ever hearing about one would be the wrong default.

Revision ID: d4b1f37c2e59
Revises: c7a4b91e5d38
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4b1f37c2e59"
down_revision: str | None = "c7a4b91e5d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notify_on_lead",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_on_lead")
