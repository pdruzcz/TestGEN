"""Add gap_findings table — Epic 5, Story 5.1

Revision ID: 022
Revises: 021
Create Date: 2026-07-07

Creates the ``gap_findings`` table for functional gap analysis (Epic 5).
Each row stores one identified gap between a documentation requirement and
code entity, with fuzzy-match metadata (score, method) and severity.
Tenant isolation via RLS, analogous to ``security_findings``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(conn: sa.engine.Connection, name: str, values: str) -> None:
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({values}); EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
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
    _create_enum(conn, "gap_type", "'missing', 'different', 'extra', 'inconsistent'")

    # --- 2. gap_findings ----------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS gap_findings (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                analysis_id     UUID REFERENCES analysis_results(id) ON DELETE SET NULL,
                requirement_id  VARCHAR(200),
                code_entity_id  VARCHAR(200),
                gap_type        gap_type NOT NULL,
                description     TEXT NOT NULL,
                requirement_text TEXT,
                code_reference  VARCHAR(500),
                match_score     FLOAT NOT NULL DEFAULT 0,
                match_method    VARCHAR(30),
                context         JSONB,
                severity        VARCHAR(10) NOT NULL DEFAULT 'warning',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gap_findings_tenant_id ON gap_findings (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gap_findings_project_id ON gap_findings (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gap_findings_gap_type ON gap_findings (gap_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gap_findings_match_score ON gap_findings (match_score)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gap_findings_analysis_id ON gap_findings (analysis_id)"))

    # --- 3. RLS -------------------------------------------------------------
    _enable_rls(conn, "gap_findings")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON gap_findings"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON gap_findings"))
    conn.execute(sa.text("ALTER TABLE gap_findings DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS gap_findings"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gap_type"))
