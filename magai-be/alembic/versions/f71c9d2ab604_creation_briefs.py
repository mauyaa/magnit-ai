"""Persist customer creation briefs.

Revision ID: f71c9d2ab604
Revises: e6a2c4f91b70
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f71c9d2ab604"
down_revision: str | None = "e6a2c4f91b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widgets", sa.Column("creation_brief", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("widgets", "creation_brief")
