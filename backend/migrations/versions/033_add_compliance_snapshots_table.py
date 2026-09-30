"""Add compliance_snapshots table — Epic 5, Story 5.7

Revision ID: 033
Revises: 032
Create Date: 2026-07-17

Creates the ``compliance_snapshots`` table for storing point-in-time
compliance metrics.  Each row captures the score, gap-type counts, coverage
and average match score at the moment a snapshot is taken (automatically
after analysis or manually by the user).  Enables version comparison and
trend analysis.  Tenant isolation via RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS compliance_snapshots (
                id                  UUID PRIMARY KEY,
                tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                analysis_id         UUID REFERENCES analysis_results(id) ON DELETE SET NULL,
                score               FLOAT NOT NULL DEFAULT 100.0,
                total_findings      INTEGER NOT NULL DEFAULT 0,
                missing_count       INTEGER NOT NULL DEFAULT 0,
                different_count     INTEGER NOT NULL DEFAULT 0,
                extra_count         INTEGER NOT NULL DEFAULT 0,
                inconsistent_count  INTEGER NOT NULL DEFAULT 0,
                avg_match_score     FLOAT NOT NULL DEFAULT 0.0,
                coverage_percentage FLOAT NOT NULL DEFAULT 0.0,
                label               VARCHAR(200),
                notes               TEXT,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at          TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_compliance_snapshots_tenant_id ON compliance_snapshots (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_compliance_snapshots_project_id ON compliance_snapshots (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_compliance_snapshots_analysis_id ON compliance_snapshots (analysis_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_compliance_snapshots_created_at ON compliance_snapshots (created_at)"))

    _enable_rls(conn, "compliance_snapshots")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON compliance_snapshots"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON compliance_snapshots"))
    conn.execute(sa.text("ALTER TABLE compliance_snapshots DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS compliance_snapshots"))
