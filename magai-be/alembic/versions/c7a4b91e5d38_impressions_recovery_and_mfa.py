"""widget impressions, heal-due partial index, account recovery and MFA columns

Revision ID: c7a4b91e5d38
Revises: b2e8d41c9a07
Create Date: 2026-07-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import UUIDType

revision: str = "c7a4b91e5d38"
down_revision: str | None = "b2e8d41c9a07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    # ---- widgets: impression counter ------------------------------------- #
    op.add_column(
        "widgets",
        sa.Column("impressions_count", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("widgets") as batch_op:
        batch_op.alter_column("impressions_count", server_default=None)
    if is_postgres:
        op.create_check_constraint(
            "ck_widgets_impressions_non_negative", "widgets", "impressions_count >= 0"
        )

    # Replace the broad two-column index with a partial index matching the
    # heal-sweep predicate constraint.
    op.drop_index("ix_widgets_status_heal_check", table_name="widgets")
    if is_postgres:
        op.create_index(
            "ix_widgets_heal_due",
            "widgets",
            ["last_heal_check_at"],
            postgresql_where=sa.text("status = 'active' AND heal_failure_count < 3"),
        )
    else:
        op.create_index("ix_widgets_heal_due", "widgets", ["last_heal_check_at"])

    # ---- users: email verification, MFA ---------------------------------- #
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Base32 TOTP shared secret. Null until enrolment begins.
    op.add_column("users", sa.Column("mfa_secret", sa.String(length=64), nullable=True))
    # Argon2 hashes of single-use recovery codes, so a database leak does not
    # hand over usable codes.
    op.add_column(
        "users",
        sa.Column("mfa_recovery_codes", sa.JSON(), nullable=True),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email_verified", server_default=None)
        batch_op.alter_column("mfa_enabled", server_default=None)

    # Accounts that already existed predate verification. Marking them verified
    # avoids locking out real users on deploy; new signups start unverified.
    if is_postgres:
        op.execute(sa.text("UPDATE users SET email_verified = true"))
    else:
        op.execute(sa.text("UPDATE users SET email_verified = 1"))

    # ---- auth_tokens: email verification + password reset ---------------- #
    # Single-use, hashed, expiring tokens. The raw value only ever exists in the
    # email that was sent; only its hash is stored, so a database leak cannot be
    # replayed to seize accounts.
    op.create_table(
        "auth_tokens",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("user_id", UUIDType(), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')", name="ck_auth_tokens_purpose"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index("ix_auth_tokens_user_purpose", "auth_tokens", ["user_id", "purpose"])
    op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_expires_at", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_purpose", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_column("users", "mfa_recovery_codes")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")

    op.drop_index("ix_widgets_heal_due", table_name="widgets")
    op.create_index("ix_widgets_status_heal_check", "widgets", ["status", "last_heal_check_at"])

    op.drop_constraint("ck_widgets_impressions_non_negative", "widgets", type_="check")
    op.drop_column("widgets", "impressions_count")
