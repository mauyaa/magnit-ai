"""Align uniqueness and JSON column types with the models.

Revision ID: f3c8e1a6b2d4
Revises: e4b7c2d19a68
Create Date: 2026-10-22 12:00:00

``alembic check`` reported drift between the migrations and the models:

* Five columns were created as ``json`` while the models declare ``JSONType``,
  which is ``jsonb`` on PostgreSQL.
* ``users.email`` and ``payments.stripe_session_id`` were unique through a
  table constraint plus a separate non-unique index; the models declare a
  single unique index.
* ``subscriptions`` carried unique constraints that duplicate the unique
  indexes the models already declare.

Uniqueness is never dropped before its replacement exists, and every step is
guarded with IF EXISTS / IF NOT EXISTS so the revision also applies to a
database that was created from the models rather than from these migrations.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3c8e1a6b2d4"
down_revision: str | None = "e4b7c2d19a68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_COLUMNS = (
    ("users", "mfa_recovery_codes"),
    ("widget_interactions", "attribution"),
    ("widgets", "creation_brief"),
    ("widgets", "launch_settings"),
    ("widgets", "source_evidence"),
)

# (table, column, unique index the models declare, legacy unique constraint)
UNIQUE_INDEXES = (
    ("users", "email", "ix_users_email", "users_email_key"),
    (
        "payments",
        "stripe_session_id",
        "ix_payments_stripe_session_id",
        "uq_payments_stripe_session_id",
    ),
)

REDUNDANT_CONSTRAINTS = (
    ("subscriptions", "subscriptions_stripe_session_id_key", "stripe_session_id"),
    ("subscriptions", "subscriptions_stripe_subscription_id_key", "stripe_subscription_id"),
    ("subscriptions", "subscriptions_user_id_key", "user_id"),
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    for table, column in JSON_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE jsonb USING {column}::jsonb")

    for table, column, index, constraint in UNIQUE_INDEXES:
        # Build the unique index under a temporary name first, so the column
        # stays unique at every point in the transaction.
        op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index}_tmp ON {table} ({column})")
        op.execute(f"DROP INDEX IF EXISTS {index}")
        op.execute(f"ALTER INDEX {index}_tmp RENAME TO {index}")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")

    for table, constraint, _column in REDUNDANT_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")


def downgrade() -> None:
    if not _is_postgres():
        return

    for table, constraint, column in REDUNDANT_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} UNIQUE ({column})")

    for table, column, index, constraint in UNIQUE_INDEXES:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} UNIQUE ({column})")
        op.execute(f"DROP INDEX IF EXISTS {index}")
        op.execute(f"CREATE INDEX {index} ON {table} ({column})")

    for table, column in JSON_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE json USING {column}::json")
