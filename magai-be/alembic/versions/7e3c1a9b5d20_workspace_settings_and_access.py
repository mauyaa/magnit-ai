"""Add durable workspace settings, access, domains and team invitations.

Revision ID: 7e3c1a9b5d20
Revises: 4d9e7a1c2b35
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import JSONType, UUIDType

revision: str = "7e3c1a9b5d20"
down_revision: str | None = "4d9e7a1c2b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("workspace_owner_id", UUIDType(), nullable=True))
    op.add_column("users", sa.Column("workspace_name", sa.String(120), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "workspace_timezone",
            sa.String(80),
            nullable=False,
            server_default="UTC",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_weekly_summary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_product_updates",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "labs_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_users_workspace_owner_id", "users", ["workspace_owner_id"])
    op.create_foreign_key(
        "fk_users_workspace_owner",
        "users",
        "users",
        ["workspace_owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
        op.create_check_constraint(
            "ck_users_role",
            "users",
            "role IN ('owner', 'admin', 'member')",
        )

    op.create_table(
        "workspace_invites",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("owner_id", UUIDType(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_workspace_invites_token_hash"),
        sa.CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_workspace_invites_role",
        ),
    )
    op.create_index("ix_workspace_invites_owner_id", "workspace_invites", ["owner_id"])
    op.create_index(
        "ix_workspace_invites_owner_email",
        "workspace_invites",
        ["owner_id", "email"],
    )

    op.create_table(
        "api_keys",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("owner_id", UUIDType(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_owner_id", "api_keys", ["owner_id"])
    op.create_index(
        "ix_api_keys_owner_active",
        "api_keys",
        ["owner_id", "revoked_at"],
    )

    op.create_table(
        "custom_domains",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("owner_id", UUIDType(), nullable=False),
        sa.Column("widget_id", UUIDType(), nullable=False),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("verification", JSONType(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname", name="uq_custom_domains_hostname"),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'error')",
            name="ck_custom_domains_status",
        ),
    )
    op.create_index("ix_custom_domains_owner_id", "custom_domains", ["owner_id"])
    op.create_index("ix_custom_domains_widget_id", "custom_domains", ["widget_id"])
    op.create_index(
        "ix_custom_domains_owner",
        "custom_domains",
        ["owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_custom_domains_owner", table_name="custom_domains")
    op.drop_index("ix_custom_domains_widget_id", table_name="custom_domains")
    op.drop_index("ix_custom_domains_owner_id", table_name="custom_domains")
    op.drop_table("custom_domains")
    op.drop_index("ix_api_keys_owner_active", table_name="api_keys")
    op.drop_index("ix_api_keys_owner_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_workspace_invites_owner_email", table_name="workspace_invites")
    op.drop_index("ix_workspace_invites_owner_id", table_name="workspace_invites")
    op.drop_table("workspace_invites")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
        op.create_check_constraint(
            "ck_users_role",
            "users",
            "role IN ('owner', 'admin')",
        )
    op.drop_constraint("fk_users_workspace_owner", "users", type_="foreignkey")
    op.drop_index("ix_users_workspace_owner_id", table_name="users")
    op.drop_column("users", "labs_enabled")
    op.drop_column("users", "notify_product_updates")
    op.drop_column("users", "notify_weekly_summary")
    op.drop_column("users", "workspace_timezone")
    op.drop_column("users", "workspace_name")
    op.drop_column("users", "workspace_owner_id")
    op.drop_column("users", "display_name")
