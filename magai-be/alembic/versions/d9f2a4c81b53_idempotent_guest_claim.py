"""One claimed tool per guest session, not one per retry.

The claim request is sent from a browser at the moment an account is created,
which is precisely where retries happen: a refresh, an impatient second click,
a timeout the client cannot tell from a failure. Each of those created another
copy of the tool, so a customer's first sight of their workspace could be three
of the thing they asked for once.

Revision ID: d9f2a4c81b53
Revises: c3d5e7a91f42
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9f2a4c81b53"
down_revision: str | None = "c3d5e7a91f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widgets", sa.Column("claim_key", sa.String(length=64), nullable=True))
    # Null claim keys do not collide, so tools created any other way are
    # unaffected by the constraint.
    op.create_unique_constraint("uq_widgets_user_claim_key", "widgets", ["user_id", "claim_key"])


def downgrade() -> None:
    op.drop_constraint("uq_widgets_user_claim_key", "widgets", type_="unique")
    op.drop_column("widgets", "claim_key")
