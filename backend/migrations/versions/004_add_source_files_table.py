"""add_source_files_table

Revision ID: 004
Revises: 003
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_path", sa.String(1000), nullable=True),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("detected_language", sa.String(50), nullable=True),
        sa.Column("detected_framework", sa.String(100), nullable=True),
        sa.Column(
            "is_cleaned_up",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_files")),
        sa.UniqueConstraint("project_id", "storage_key", name="uq_source_files_project_storage_key"),
    )
    op.create_index(op.f("ix_source_files_tenant_id"), "source_files", ["tenant_id"])
    op.create_index(op.f("ix_source_files_project_id"), "source_files", ["project_id"])

    # RLS policy — tenant isolation
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE source_files ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE source_files FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON source_files "
            "FOR ALL "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON source_files"))
    conn.execute(sa.text("ALTER TABLE source_files DISABLE ROW LEVEL SECURITY"))

    op.drop_index(op.f("ix_source_files_project_id"), table_name="source_files")
    op.drop_index(op.f("ix_source_files_tenant_id"), table_name="source_files")
    op.drop_table("source_files")
