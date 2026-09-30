"""add_tenants_users_verification_audit

Revision ID: 001
Revises:
Create Date: 2026-03-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Enums ---
    plan_type = postgresql.ENUM("basic", "professional", name="plan_type", create_type=False)
    user_role = postgresql.ENUM("user", "owner", "admin", name="user_role", create_type=False)
    verification_type = postgresql.ENUM(
        "registration", "invitation", "password_reset", name="verification_type", create_type=False
    )
    plan_type.create(op.get_bind(), checkfirst=True)
    user_role.create(op.get_bind(), checkfirst=True)
    verification_type.create(op.get_bind(), checkfirst=True)

    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("nip", sa.String(20), unique=True, nullable=True),
        sa.Column("plan", plan_type, nullable=False, server_default="basic"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),  # ORM-level onupdate; no DB trigger
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "notification_preferences", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("invited_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),  # ORM-level onupdate; no DB trigger
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", "tenant_id", name="uq_users_email_tenant"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_invited_by", "users", ["invited_by"])

    # --- email_verifications ---
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("type", verification_type, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),  # ORM-level onupdate; no DB trigger
        sa.PrimaryKeyConstraint("id", name="pk_email_verifications"),
    )
    op.create_index("ix_email_verifications_user_id", "email_verifications", ["user_id"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"])
    op.create_index("ix_audit_logs_tenant_id_created_at", "audit_logs", ["tenant_id", "created_at"])

    # --- RLS Policies ---
    conn = op.get_bind()
    # email_verifications has no tenant_id — access is scoped via user_id joins, no RLS needed
    for table in ("users", "audit_logs"):
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        conn.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"FOR ALL "
                f"USING (tenant_id = current_setting('app.current_tenant')::uuid) "
                f"WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
            )
        )

    # tenants table — RLS by id (tenant sees only own record)
    conn.execute(sa.text("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE tenants FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON tenants "
            "FOR ALL "
            "USING (id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (id = current_setting('app.current_tenant')::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("tenants", "users", "audit_logs"):
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    op.drop_table("audit_logs")
    op.drop_table("email_verifications")
    op.drop_table("users")
    op.drop_table("tenants")

    op.execute("DROP TYPE IF EXISTS verification_type")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS plan_type")
