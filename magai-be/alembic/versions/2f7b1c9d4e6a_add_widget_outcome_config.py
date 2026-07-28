"""Add owner-editable widget outcome configuration.

Revision ID: 2f7b1c9d4e6a
Revises: 9c4a2f8d1e63
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import JSONType

revision: str = "2f7b1c9d4e6a"
down_revision: str | None = "9c4a2f8d1e63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widgets", sa.Column("outcome_config", JSONType(), nullable=True))


def downgrade() -> None:
    op.drop_column("widgets", "outcome_config")
