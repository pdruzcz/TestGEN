"""Add code_errors table — Epic 5, Story 5.4

Revision ID: 030
Revises: 028
Create Date: 2026-07-14

Creates the ``code_errors`` table for code error detection (Epic 5, Story 5.4).
Each row stores one detected error (syntax / logic / semantic / conformance)
with location, severity and suggestion.  Tenant isolation via RLS, analogous
to ``gap_findings``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: str | None = "028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(conn: sa.engine.Connection, name: str, values: str) -> None:
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({values}); "
            "EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
        )
    )


def _enable_rls(conn: sa.engine.Connection, table: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(sa.text(f"DROP POLICY IF EXISTS admin_bypass ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY admin_bypass ON {table} "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Enum type -------------------------------------------------------
    _create_enum(
        conn,
        "error_category",
        "'syntax', 'logic', 'semantic', 'conformance'",
    )

    # --- 2. code_errors -----------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS code_errors (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                source_file_id  UUID REFERENCES source_files(id) ON DELETE SET NULL,
                category        error_category NOT NULL,
                message         TEXT NOT NULL,
                file_path       VARCHAR(500),
                line_start      INTEGER,
                line_end        INTEGER,
                severity        VARCHAR(10) NOT NULL DEFAULT 'warning',
                rule_id         VARCHAR(100),
                suggestion      TEXT,
                context         JSONB,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_tenant_id ON code_errors (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_project_id ON code_errors (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_source_file_id ON code_errors (source_file_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_category ON code_errors (category)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_severity ON code_errors (severity)"))

    # --- 3. RLS -------------------------------------------------------------
    _enable_rls(conn, "code_errors")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON code_errors"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON code_errors"))
    conn.execute(sa.text("ALTER TABLE code_errors DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS code_errors"))
    conn.execute(sa.text("DROP TYPE IF EXISTS error_category"))
