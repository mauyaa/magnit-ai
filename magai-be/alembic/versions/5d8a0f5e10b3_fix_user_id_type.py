"""fix user_id type

Revision ID: 5d8a0f5e10b3
Revises: bef37ed6fedf
Create Date: 2026-07-04 10:06:05.582941
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5d8a0f5e10b3"
down_revision: str | None = "bef37ed6fedf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The initial schema declared widgets.user_id as a UUID foreign key to
    # users.id. PostgreSQL cannot keep that constraint across a change to
    # VARCHAR, so drop it first; b2e8d41c9a07 restores a UUID foreign key.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE widgets DROP CONSTRAINT IF EXISTS widgets_user_id_fkey")
    with op.batch_alter_table("widgets") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.UUID(),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    # Convert back to UUID before restoring the foreign key; the constraint
    # cannot be created while the column is still VARCHAR.
    op.alter_column(
        "widgets",
        "user_id",
        existing_type=sa.String(length=255),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.create_foreign_key(op.f("widgets_user_id_fkey"), "widgets", "users", ["user_id"], ["id"])
