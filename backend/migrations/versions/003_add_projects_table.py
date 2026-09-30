"""add_projects_table

Revision ID: 003
Revises: 002
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    project_status = postgresql.ENUM(
        "created",
        "active",
        "analyzing",
        "completed",
        "archived",
        name="project_status",
        create_type=False,
    )
    project_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language_hint", sa.String(50), nullable=True),
        sa.Column("status", project_status, nullable=False, server_default="created"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )

    # Partial unique index: name must be unique per tenant only for non-deleted projects
    op.execute("CREATE UNIQUE INDEX uq_projects_name_tenant ON projects (name, tenant_id) WHERE is_deleted = false")
    op.create_index(op.f("ix_projects_tenant_id"), "projects", ["tenant_id"])

    # RLS policy — tenant isolation
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE projects ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE projects FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON projects "
            "FOR ALL "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    # Admin bypass — NIL_UUID context set for platform admins
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON projects "
            "FOR ALL "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON projects"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON projects"))
    conn.execute(sa.text("ALTER TABLE projects DISABLE ROW LEVEL SECURITY"))

    op.drop_index(op.f("ix_projects_tenant_id"), table_name="projects")
    op.drop_table("projects")

    op.execute("DROP TYPE IF EXISTS project_status")
