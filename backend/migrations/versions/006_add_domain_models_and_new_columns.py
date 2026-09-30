"""add domain models and new columns

Revision ID: 006
Revises: 005
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- New columns on existing tables ---
    op.add_column("tenants", sa.Column("slug", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("settings", sa.dialects.postgresql.JSONB(), nullable=True))

    # Backfill slug from name for existing rows (idempotent)
    op.execute("UPDATE tenants SET slug = LOWER(REPLACE(name, ' ', '-')) WHERE slug IS NULL")

    # Now make slug NOT NULL and add constraints
    op.alter_column("tenants", "slug", nullable=False)
    op.create_unique_constraint("uq_tenants_slug", "tenants", ["slug"])
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # Add language and framework columns to projects
    op.add_column("projects", sa.Column("language", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("framework", sa.String(100), nullable=True))

    # Add last_login_at to users
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    # --- New tables ---

    # analysis_results
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "engine_mode",
            sa.Enum("native", "llm", "hybrid", name="analysis_engine_mode", native_enum=True),
            nullable=False,
            server_default="hybrid",
        ),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="analysis_status", native_enum=True),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("result_data", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_results")),
    )
    op.create_index(op.f("ix_analysis_results_tenant_id"), "analysis_results", ["tenant_id"])
    op.create_index(op.f("ix_analysis_results_project_id"), "analysis_results", ["project_id"])

    # test_cases
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_result_id", sa.Uuid(), sa.ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum("high", "medium", "low", name="test_case_priority", native_enum=True),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "type",
            sa.Enum("functional", "unit", "integration", "e2e", "security", name="test_case_type", native_enum=True),
            nullable=False,
            server_default="functional",
        ),
        sa.Column("preconditions", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("steps", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_cases")),
    )
    op.create_index(op.f("ix_test_cases_tenant_id"), "test_cases", ["tenant_id"])
    op.create_index(op.f("ix_test_cases_analysis_result_id"), "test_cases", ["analysis_result_id"])

    # test_codes
    op.create_table(
        "test_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("framework", sa.String(100), nullable=False),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_codes")),
    )
    op.create_index(op.f("ix_test_codes_tenant_id"), "test_codes", ["tenant_id"])
    op.create_index(op.f("ix_test_codes_test_case_id"), "test_codes", ["test_case_id"])

    # reports
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column(
            "format",
            sa.Enum("pdf", "html", "json", "csv", name="report_format", native_enum=True),
            nullable=False,
            server_default="json",
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_tenant_id"), "reports", ["tenant_id"])
    op.create_index(op.f("ix_reports_project_id"), "reports", ["project_id"])

    # --- RLS for new tables ---
    conn = op.get_bind()
    for table in ("analysis_results", "test_cases", "test_codes", "reports"):
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        conn.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {table} "
                "FOR ALL "
                f"USING (tenant_id = current_setting('app.current_tenant')::uuid) "
                f"WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop RLS and tables in reverse order
    for table in ("reports", "test_codes", "test_cases", "analysis_results"):
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    op.drop_table("reports")
    op.drop_table("test_codes")
    op.drop_table("test_cases")
    op.drop_table("analysis_results")

    # Drop new columns
    op.drop_column("users", "last_login_at")
    op.drop_column("projects", "framework")
    op.drop_column("projects", "language")

    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_constraint("uq_tenants_slug", "tenants")
    op.drop_column("tenants", "settings")
    op.drop_column("tenants", "slug")

    # Drop enum types
    for enum_name in (
        "analysis_engine_mode",
        "analysis_status",
        "test_case_priority",
        "test_case_type",
        "report_format",
    ):
        conn.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name}"))
