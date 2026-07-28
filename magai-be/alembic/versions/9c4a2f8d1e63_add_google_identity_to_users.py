"""Add Google identity linking to users.

Revision ID: 9c4a2f8d1e63
Revises: a82f604db139
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9c4a2f8d1e63"
down_revision: str | None = "a82f604db139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_subject", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_users_google_subject",
        "users",
        ["google_subject"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_column("users", "google_subject")
