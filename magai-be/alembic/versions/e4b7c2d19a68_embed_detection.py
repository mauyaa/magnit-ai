"""Record where a tool is actually installed.

Installation used to be inferred from an interaction carrying a referrer, which
was wrong in both directions at once: a correctly pasted embed nobody had
touched yet could not be verified, while the owner clicking through the preview
inside their own dashboard verified it falsely — and those same preview views
inflated the visitor count their conversion rate was measured against.

A view carrying a referrer from the customer's own host is the honest signal,
and these two columns are where it lands.

Revision ID: e4b7c2d19a68
Revises: d9f2a4c81b53
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b7c2d19a68"
down_revision: str | None = "d9f2a4c81b53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "widgets", sa.Column("first_embedded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("widgets", sa.Column("embed_host", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("widgets", "embed_host")
    op.drop_column("widgets", "first_embedded_at")
