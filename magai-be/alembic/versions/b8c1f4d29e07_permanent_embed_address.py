"""A permanent address for every published tool.

The snippet a customer pastes onto their website used to point at the unique URL
of one particular build. Every rebuild, repair and rollback produced a different
one, so the page we cannot edit kept serving a deployment that was no longer the
tool — while the product told them the address was stable.

``widgets.embed_url`` is that address, written once on first publish and never
changed. ``widget_deployments.provider_deployment_id`` is what lets a rollback
move it back to an earlier build instead of only rewriting our own records.

Deliberately not backfilled. Copying the current ``deployment_url`` into
``embed_url`` would pin an already-published tool to one immutable build
forever, so its next rebuild would never reach visitors. Leaving it null means
the next publish establishes the permanent address, and until then nothing
changes for anyone.

Revision ID: b8c1f4d29e07
Revises: 7e3c1a9b5d20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c1f4d29e07"
down_revision: str | None = "7e3c1a9b5d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widgets", sa.Column("embed_url", sa.Text(), nullable=True))
    op.add_column(
        "widget_deployments",
        sa.Column("provider_deployment_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("widget_deployments", "provider_deployment_id")
    op.drop_column("widgets", "embed_url")
