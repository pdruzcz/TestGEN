"""Add recommendations table — Epic 5, Story 5.5

Revision ID: 031
Revises: 030
Create Date: 2026-07-14

Creates the ``recommendations`` table for actionable recommendations
derived from gap findings and code errors.  Each row has a priority (P1–P4),
confidence score (0–1), and optional suggestion.  Tenant isolation via RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: str | None = "030"
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

    _create_enum(
        conn,
        "recommendation_priority",
        "'P1', 'P2', 'P3', 'P4'",
    )

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                gap_finding_id  UUID REFERENCES gap_findings(id) ON DELETE SET NULL,
                code_error_id   UUID REFERENCES code_errors(id) ON DELETE SET NULL,
                title           VARCHAR(500) NOT NULL,
                description     TEXT NOT NULL,
                priority        recommendation_priority NOT NULL,
                confidence      FLOAT NOT NULL DEFAULT 0.5,
                source_type     VARCHAR(30) NOT NULL DEFAULT 'gap_finding',
                source_ref      VARCHAR(500),
                suggestion      TEXT,
                context         JSONB,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recommendations_tenant_id ON recommendations (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recommendations_project_id ON recommendations (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recommendations_gap_finding_id ON recommendations (gap_finding_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recommendations_code_error_id ON recommendations (code_error_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recommendations_priority ON recommendations (priority)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recommendations_confidence ON recommendations (confidence)"))

    _enable_rls(conn, "recommendations")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON recommendations"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON recommendations"))
    conn.execute(sa.text("ALTER TABLE recommendations DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS recommendations"))
    conn.execute(sa.text("DROP TYPE IF EXISTS recommendation_priority"))
