"""rework_user_tenants_junction_email_global_unique

Revision ID: 04765b21814a
Revises: 004
Create Date: 2026-05-20 15:53:18.064946

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "04765b21814a"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Clean up partial state from failed previous runs (asyncpg may not roll back DDL)
    op.execute("DROP TABLE IF EXISTS user_tenants CASCADE")
    op.execute("DROP TYPE IF EXISTS tenant_role")

    # Create user_tenants table
    op.create_table(
        "user_tenants",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Enum("user", "owner", name="tenant_role"), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["invited_by"], ["users.id"], name=op.f("fk_user_tenants_invited_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_user_tenants_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_tenants_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_tenants")),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenants_user_tenant"),
    )
    op.create_index(op.f("ix_user_tenants_tenant_id"), "user_tenants", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_user_tenants_user_id"), "user_tenants", ["user_id"], unique=False)
    op.drop_index(op.f("ix_audit_logs_action_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_tenant_id_created_at"), table_name="audit_logs")
    op.alter_column("source_files", "file_size", existing_type=sa.BIGINT(), type_=sa.Integer(), existing_nullable=False)
    op.drop_constraint(op.f("uq_user_mfa_user_id"), "user_mfa", type_="unique")
    op.drop_index(op.f("ix_user_mfa_user_id"), table_name="user_mfa")
    op.create_index(op.f("ix_user_mfa_user_id"), "user_mfa", ["user_id"], unique=True)
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    # Data migration: populate user_tenants from existing users.tenant_id/role/invited_by
    op.execute("""
        INSERT INTO user_tenants (id, user_id, tenant_id, role, invited_by, created_at)
        SELECT gen_random_uuid(), u.id, u.tenant_id,
               CASE WHEN u.role::text = 'admin' THEN 'owner' ELSE u.role::text END::tenant_role,
               u.invited_by,
               COALESCE(u.created_at, now())
        FROM users u
        WHERE u.tenant_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    # Promote platform admins: set is_admin = true where role was 'admin'
    op.execute("""
        UPDATE users SET is_admin = true WHERE role::text = 'admin'
    """)

    # Deduplicate users: old model allowed same email across tenants.
    # Prefer keeping the active user; fall back to oldest if none are active.
    op.execute("""
        WITH duplicates AS (
            SELECT email,
                   COALESCE(
                       (array_agg(id ORDER BY created_at ASC, id ASC) FILTER (WHERE is_active))[1],
                       (array_agg(id ORDER BY created_at ASC, id ASC))[1]
                   ) AS keep_id
            FROM users
            GROUP BY email
            HAVING COUNT(*) > 1
        ),
        to_merge AS (
            SELECT u.id AS dup_id, d.keep_id
            FROM users u
            JOIN duplicates d ON u.email = d.email AND u.id != d.keep_id
        )
        UPDATE user_tenants ut
        SET user_id = tm.keep_id
        FROM to_merge tm
        WHERE ut.user_id = tm.dup_id
        AND NOT EXISTS (
            SELECT 1 FROM user_tenants ut2
            WHERE ut2.user_id = tm.keep_id AND ut2.tenant_id = ut.tenant_id
        )
    """)
    op.execute("""
        DELETE FROM users u
        USING (
            SELECT email,
                   COALESCE(
                       (array_agg(id ORDER BY created_at ASC, id ASC) FILTER (WHERE is_active))[1],
                       (array_agg(id ORDER BY created_at ASC, id ASC))[1]
                   ) AS keep_id
            FROM users
            GROUP BY email
            HAVING COUNT(*) > 1
        ) d
        WHERE u.email = d.email AND u.id != d.keep_id
    """)

    # Drop old RLS policies that reference users.tenant_id before dropping the column
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs")

    # Make audit_logs.tenant_id nullable — some events (login_failed) have no tenant context
    op.alter_column("audit_logs", "tenant_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint(op.f("fk_audit_logs_tenant_id_tenants"), "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_audit_logs_tenant_id_tenants"), "audit_logs", "tenants", ["tenant_id"], ["id"], ondelete="SET NULL"
    )

    op.drop_index(op.f("ix_users_invited_by"), table_name="users")
    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_constraint(op.f("uq_users_email_tenant"), "users", type_="unique")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.drop_constraint(op.f("fk_users_invited_by_users"), "users", type_="foreignkey")
    op.drop_constraint(op.f("fk_users_tenant_id_tenants"), "users", type_="foreignkey")
    op.drop_column("users", "role")
    op.drop_column("users", "invited_by")
    op.drop_column("users", "tenant_id")

    # Create new RLS policies on user_tenants instead of users
    op.execute("ALTER TABLE user_tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_tenants FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON user_tenants
        FOR ALL USING (tenant_id = current_setting('app.current_tenant')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)
    """)
    op.execute("""
        CREATE POLICY admin_bypass ON user_tenants
        FOR ALL USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000')
        WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000')
    """)
    # Re-enable RLS on tenants and audit_logs with updated policies
    op.execute("""
        CREATE POLICY tenant_isolation ON tenants
        FOR ALL USING (id = current_setting('app.current_tenant')::uuid)
        WITH CHECK (id = current_setting('app.current_tenant')::uuid)
    """)
    op.execute("""
        CREATE POLICY admin_bypass ON tenants
        FOR ALL USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000')
        WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000')
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON audit_logs
        FOR ALL USING (tenant_id = current_setting('app.current_tenant')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)
    """)
    op.execute("""
        CREATE POLICY admin_bypass ON audit_logs
        FOR ALL USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000')
        WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000')
    """)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("users", sa.Column("tenant_id", sa.UUID(), autoincrement=False, nullable=False))
    op.add_column("users", sa.Column("invited_by", sa.UUID(), autoincrement=False, nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "role",
            postgresql.ENUM("user", "owner", "admin", name="user_role"),
            server_default=sa.text("'user'::user_role"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_users_tenant_id_tenants"), "users", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        op.f("fk_users_invited_by_users"), "users", "users", ["invited_by"], ["id"], ondelete="SET NULL"
    )
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_unique_constraint(
        op.f("uq_users_email_tenant"), "users", ["email", "tenant_id"], postgresql_nulls_not_distinct=False
    )
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_users_invited_by"), "users", ["invited_by"], unique=False)
    op.drop_column("users", "is_admin")
    op.drop_index(op.f("ix_user_mfa_user_id"), table_name="user_mfa")
    op.create_index(op.f("ix_user_mfa_user_id"), "user_mfa", ["user_id"], unique=False)
    op.create_unique_constraint(
        op.f("uq_user_mfa_user_id"), "user_mfa", ["user_id"], postgresql_nulls_not_distinct=False
    )
    op.alter_column("source_files", "file_size", existing_type=sa.Integer(), type_=sa.BIGINT(), existing_nullable=False)
    op.create_index(op.f("ix_audit_logs_tenant_id_created_at"), "audit_logs", ["tenant_id", "created_at"], unique=False)
    op.create_index(op.f("ix_audit_logs_action_created_at"), "audit_logs", ["action", "created_at"], unique=False)
    op.drop_index(op.f("ix_user_tenants_user_id"), table_name="user_tenants")
    op.drop_index(op.f("ix_user_tenants_tenant_id"), table_name="user_tenants")
    op.drop_table("user_tenants")
    # ### end Alembic commands ###
