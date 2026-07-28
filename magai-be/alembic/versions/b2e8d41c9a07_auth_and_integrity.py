"""auth columns, real user FKs, deployment history, integrity constraints

Revision ID: b2e8d41c9a07
Revises: a1f9c3d7e2b4
Create Date: 2026-07-25 00:00:00.000000

Data migration note
-------------------
Before this revision ``widgets.user_id`` was a free-text column that the API
always filled with the literal string ``"anonymous"``, and ``users`` rows had no
password. Rather than delete that data, this migration provisions a single
placeholder account and reparents every orphaned widget and payment onto it.

The placeholder is created with an unusable password hash, so nobody can log in
as it. To recover the data, an operator assigns those widgets to a real account:

    UPDATE widgets SET user_id = '<real-user-uuid>'
     WHERE user_id = (SELECT id FROM users WHERE email = 'legacy-import@magnitai.invalid');

Existing users (created through the old password-less endpoint) also receive the
unusable hash and must use password reset to regain access.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.platform.db.types import UUIDType

revision: str = "b2e8d41c9a07"
down_revision: str | None = "a1f9c3d7e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_EMAIL = "legacy-import@magnitai.invalid"
# Deliberately not a valid Argon2 hash: verification always fails, so this
# account cannot authenticate.
UNUSABLE_PASSWORD_HASH = "!unusable-password-reset-required"

# UUIDs are generated in Python rather than with gen_random_uuid() so the
# migration does not depend on a Postgres extension or a specific server version.
LEGACY_USER_ID = str(uuid.uuid4())

# Matches the canonical 8-4-4-4-12 UUID form.
UUID_REGEX = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    # ---- users: authentication columns ---------------------------------- #
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            server_default=UNUSABLE_PASSWORD_HASH,
        ),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="owner"),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_email", "users", ["email"])
    if is_postgres:
        op.create_check_constraint("ck_users_role", "users", "role IN ('owner', 'admin')")

    # Drop the server defaults: they exist only to backfill existing rows. New
    # inserts must supply a real hash rather than silently getting the placeholder.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", server_default=None)
        batch_op.alter_column("role", server_default=None)

    # ---- placeholder account for pre-auth data -------------------------- #
    # Created unconditionally so the reparenting statements below always have a
    # target; it is removed again at the end if nothing needed it.
    if is_postgres:
        op.execute(
            sa.text(
                """
                INSERT INTO users (id, email, password_hash, is_active, role,
                                   created_at, updated_at)
                VALUES (CAST(:uid AS uuid), :email, :pwhash, false, 'owner', now(), now())
                ON CONFLICT (email) DO NOTHING
                """
            ).bindparams(uid=LEGACY_USER_ID, email=LEGACY_EMAIL, pwhash=UNUSABLE_PASSWORD_HASH)
        )
    else:
        op.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO users (id, email, password_hash, is_active, role,
                                              created_at, updated_at)
                VALUES (:uid, :email, :pwhash, 0, 'owner', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ).bindparams(uid=LEGACY_USER_ID, email=LEGACY_EMAIL, pwhash=UNUSABLE_PASSWORD_HASH)
        )

    # ---- widgets: real FK to users -------------------------------------- #
    op.add_column("widgets", sa.Column("user_id_uuid", UUIDType(), nullable=True))
    if is_postgres:
        op.execute(
            sa.text(
                """
                UPDATE widgets
                   SET user_id_uuid = CASE
                         WHEN CAST(user_id AS text) ~ :uuid_re
                           THEN CAST(CAST(user_id AS text) AS uuid)
                         ELSE (SELECT id FROM users WHERE email = :email)
                       END
                """
            ).bindparams(uuid_re=UUID_REGEX, email=LEGACY_EMAIL)
        )
        # Any widget whose owner id does not correspond to a real user is reparented
        # onto the placeholder, so the NOT NULL + FK below cannot fail.
        op.execute(
            sa.text(
                """
                UPDATE widgets
                   SET user_id_uuid = (SELECT id FROM users WHERE email = :email)
                 WHERE user_id_uuid IS NULL
                    OR NOT EXISTS (SELECT 1 FROM users u WHERE u.id = widgets.user_id_uuid)
                """
            ).bindparams(email=LEGACY_EMAIL)
        )
        # Widgets that still have no owner can only exist if there was nothing to
        # reparent them to; remove them rather than leaving the column nullable.
        op.execute(sa.text("DELETE FROM widgets WHERE user_id_uuid IS NULL"))
    else:
        op.execute(sa.text("UPDATE widgets SET user_id_uuid = user_id"))

    with op.batch_alter_table("widgets") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.alter_column("user_id_uuid", new_column_name="user_id", nullable=False)
    if is_postgres:
        op.create_foreign_key(
            "fk_widgets_user_id_users",
            "widgets",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # ---- widgets: heal backoff counter + indexes + constraints ---------- #
    op.add_column(
        "widgets",
        sa.Column("heal_failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("widgets") as batch_op:
        batch_op.alter_column("heal_failure_count", server_default=None)

    op.create_index("ix_widgets_user_id", "widgets", ["user_id"])
    op.create_index("ix_widgets_user_created", "widgets", ["user_id", "created_at"])
    op.create_index("ix_widgets_status_heal_check", "widgets", ["status", "last_heal_check_at"])

    # Normalize any status outside the supported set before constraining it.
    op.execute(
        sa.text(
            "UPDATE widgets SET status = 'failed' "
            "WHERE status NOT IN ('analyzed', 'building', 'active', 'failed')"
        )
    )
    if is_postgres:
        op.create_check_constraint(
            "ck_widgets_status",
            "widgets",
            "status IN ('analyzed', 'building', 'active', 'failed')",
        )
        op.create_check_constraint("ck_widgets_lead_cap_non_negative", "widgets", "lead_cap >= 0")
        op.create_check_constraint(
            "ck_widgets_leads_count_non_negative", "widgets", "leads_count >= 0"
        )

    # ---- leads: cascade + composite index ------------------------------- #
    if is_postgres:
        op.drop_constraint("leads_widget_id_fkey", "leads", type_="foreignkey")
        op.create_foreign_key(
            "fk_leads_widget_id_widgets",
            "leads",
            "widgets",
            ["widget_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index("ix_leads_widget_id", "leads", ["widget_id"])
    op.create_index("ix_leads_widget_created", "leads", ["widget_id", "created_at"])

    # ---- payments: real FKs, unique session, constraints ---------------- #
    op.add_column("payments", sa.Column("user_id_uuid", UUIDType(), nullable=True))
    if is_postgres:
        op.execute(
            sa.text(
                """
                UPDATE payments
                   SET user_id_uuid = CASE
                         WHEN CAST(user_id AS text) ~ :uuid_re
                           THEN CAST(CAST(user_id AS text) AS uuid)
                         ELSE (SELECT id FROM users WHERE email = :email)
                       END
                """
            ).bindparams(uuid_re=UUID_REGEX, email=LEGACY_EMAIL)
        )
        op.execute(
            sa.text(
                """
                UPDATE payments
                   SET user_id_uuid = (SELECT id FROM users WHERE email = :email)
                 WHERE user_id_uuid IS NULL
                    OR NOT EXISTS (SELECT 1 FROM users u WHERE u.id = payments.user_id_uuid)
                """
            ).bindparams(email=LEGACY_EMAIL)
        )
        op.execute(sa.text("DELETE FROM payments WHERE user_id_uuid IS NULL"))
    else:
        op.execute(sa.text("UPDATE payments SET user_id_uuid = user_id"))

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.alter_column("user_id_uuid", new_column_name="user_id", nullable=False)
    if is_postgres:
        op.create_foreign_key(
            "fk_payments_user_id_users",
            "payments",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.execute(
        sa.text(
            "UPDATE payments SET widget_id = NULL WHERE widget_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM widgets w WHERE w.id = payments.widget_id)"
        )
    )
    if is_postgres:
        op.create_foreign_key(
            "fk_payments_widget_id_widgets",
            "payments",
            "widgets",
            ["widget_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    if is_postgres:
        op.create_unique_constraint(
            "uq_payments_stripe_session_id", "payments", ["stripe_session_id"]
        )
    op.create_index("ix_payments_stripe_session_id", "payments", ["stripe_session_id"])
    if is_postgres:
        op.create_check_constraint(
            "ck_payments_status",
            "payments",
            "status IN ('pending', 'confirmed', 'failed', 'refunded')",
        )
        op.create_check_constraint("ck_payments_amount_non_negative", "payments", "amount >= 0")

    # ---- widget_heal_events: constraints + composite index -------------- #
    if is_postgres:
        op.create_check_constraint(
            "ck_heal_events_check_type",
            "widget_heal_events",
            "check_type IN ('brand_drift', 'deploy_health')",
        )
        op.create_check_constraint(
            "ck_heal_events_status",
            "widget_heal_events",
            "status IN ('detected', 'healing', 'healed', 'failed', 'no_drift')",
        )
    op.create_index(
        "ix_heal_events_widget_detected",
        "widget_heal_events",
        ["widget_id", "detected_at"],
    )

    # ---- widget_deployments: rollback history --------------------------- #
    op.create_table(
        "widget_deployments",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("widget_id", UUIDType(), nullable=False),
        sa.Column("deployment_url", sa.Text(), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_widget_deployments_widget_id", "widget_deployments", ["widget_id"])
    op.create_index(
        "ix_widget_deployments_widget_created",
        "widget_deployments",
        ["widget_id", "created_at"],
    )

    # Seed history from widgets already live
    if is_postgres:
        op.execute(
            sa.text(
                """
                INSERT INTO widget_deployments
                       (id, widget_id, deployment_url, trigger, is_current,
                        created_at, updated_at)
                SELECT CAST(md5(CAST(id AS text) || deployment_url) AS uuid),
                       id, deployment_url, 'build', true,
                       COALESCE(deployed_at, now()), now()
                  FROM widgets
                 WHERE deployment_url IS NOT NULL AND deployment_url <> ''
                """
            )
        )

    # Drop the placeholder account if nothing ended up needing it, so a clean
    # install is not left with a stray user row.
    op.execute(
        sa.text(
            """
            DELETE FROM users
             WHERE email = :email
               AND NOT EXISTS (SELECT 1 FROM widgets w WHERE w.user_id = users.id)
               AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.id)
            """
        ).bindparams(email=LEGACY_EMAIL)
    )


def downgrade() -> None:
    op.drop_index("ix_widget_deployments_widget_created", table_name="widget_deployments")
    op.drop_index("ix_widget_deployments_widget_id", table_name="widget_deployments")
    op.drop_table("widget_deployments")

    op.drop_index("ix_heal_events_widget_detected", table_name="widget_heal_events")
    op.drop_constraint("ck_heal_events_status", "widget_heal_events", type_="check")
    op.drop_constraint("ck_heal_events_check_type", "widget_heal_events", type_="check")

    op.drop_constraint("ck_payments_amount_non_negative", "payments", type_="check")
    op.drop_constraint("ck_payments_status", "payments", type_="check")
    op.drop_index("ix_payments_stripe_session_id", table_name="payments")
    op.drop_constraint("uq_payments_stripe_session_id", "payments", type_="unique")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_constraint("fk_payments_widget_id_widgets", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_user_id_users", "payments", type_="foreignkey")
    op.alter_column("payments", "user_id", new_column_name="user_id_uuid")
    op.add_column("payments", sa.Column("user_id", sa.String(length=255), nullable=True))
    op.execute(sa.text("UPDATE payments SET user_id = user_id_uuid::text"))
    op.alter_column("payments", "user_id", nullable=False)
    op.drop_column("payments", "user_id_uuid")

    op.drop_index("ix_leads_widget_created", table_name="leads")
    op.drop_index("ix_leads_widget_id", table_name="leads")
    op.drop_constraint("fk_leads_widget_id_widgets", "leads", type_="foreignkey")
    op.create_foreign_key("leads_widget_id_fkey", "leads", "widgets", ["widget_id"], ["id"])

    op.drop_constraint("ck_widgets_leads_count_non_negative", "widgets", type_="check")
    op.drop_constraint("ck_widgets_lead_cap_non_negative", "widgets", type_="check")
    op.drop_constraint("ck_widgets_status", "widgets", type_="check")
    op.drop_index("ix_widgets_status_heal_check", table_name="widgets")
    op.drop_index("ix_widgets_user_created", table_name="widgets")
    op.drop_index("ix_widgets_user_id", table_name="widgets")
    op.drop_column("widgets", "heal_failure_count")
    op.drop_constraint("fk_widgets_user_id_users", "widgets", type_="foreignkey")
    op.alter_column("widgets", "user_id", new_column_name="user_id_uuid")
    op.add_column("widgets", sa.Column("user_id", sa.String(length=255), nullable=True))
    op.execute(sa.text("UPDATE widgets SET user_id = user_id_uuid::text"))
    op.alter_column("widgets", "user_id", nullable=False)
    op.drop_column("widgets", "user_id_uuid")

    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "role")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
