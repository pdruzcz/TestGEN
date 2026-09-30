"""Add security_scans and security_findings — Epic 4, Story 4.1

Revision ID: 016
Revises: 015
Create Date: 2026-06-12

Creates the security module's central tables plus their enums. ``security_scans``
tracks one scan run (SAST/taint/dependency/config/DAST); ``security_findings``
stores each detected vulnerability. Tenant isolation is enforced via RLS,
analogous to ``analysis_results``.

Uses raw SQL throughout to avoid Alembic's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
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
    conn.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            f"CREATE POLICY admin_bypass ON {table} "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Enum types (idempotent) ----------------------------------------
    _create_enum(conn, "scan_type", "'sast', 'taint', 'dependency', 'config', 'dast'")
    _create_enum(conn, "scan_status", "'pending', 'running', 'completed', 'failed'")
    _create_enum(conn, "severity", "'critical', 'high', 'medium', 'low', 'info'")
    _create_enum(conn, "analysis_source", "'native', 'llm', 'hybrid'")
    _create_enum(conn, "finding_status", "'open', 'acknowledged', 'fixed', 'false_positive'")

    # --- 2. security_scans -------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS security_scans (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                scan_type       scan_type NOT NULL,
                engine_mode     VARCHAR(20) NOT NULL DEFAULT 'native',
                status          scan_status NOT NULL DEFAULT 'pending',
                task_id         VARCHAR(100),
                target_url      VARCHAR(1000),
                started_at      TIMESTAMPTZ,
                completed_at    TIMESTAMPTZ,
                findings_count  INTEGER NOT NULL DEFAULT 0,
                error_message   TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_scans_tenant_id ON security_scans (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_scans_project_id ON security_scans (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_scans_scan_type ON security_scans (scan_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_scans_status ON security_scans (status)"))

    # --- 3. security_findings ----------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS security_findings (
                id                  UUID PRIMARY KEY,
                tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                scan_id             UUID NOT NULL REFERENCES security_scans(id) ON DELETE CASCADE,
                scan_type           scan_type NOT NULL,
                vulnerability_type  VARCHAR(100) NOT NULL,
                severity            severity NOT NULL,
                cwe_id              VARCHAR(20),
                owasp_category      VARCHAR(50),
                file_path           VARCHAR(1000),
                line_start          INTEGER,
                line_end            INTEGER,
                code_snippet        TEXT,
                description         TEXT NOT NULL,
                confidence          FLOAT NOT NULL DEFAULT 0,
                source              analysis_source NOT NULL DEFAULT 'native',
                status              finding_status NOT NULL DEFAULT 'open',
                taint_path          JSONB,
                recommendation      TEXT,
                finding_metadata    JSONB,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at          TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_findings_tenant_id ON security_findings (tenant_id)"))
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_security_findings_project_id ON security_findings (project_id)")
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_findings_scan_id ON security_findings (scan_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_findings_scan_type ON security_findings (scan_type)"))
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_security_findings_vulnerability_type ON security_findings (vulnerability_type)"
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_findings_severity ON security_findings (severity)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_security_findings_status ON security_findings (status)"))

    # --- 4. RLS — tenant isolation -----------------------------------------
    _enable_rls(conn, "security_scans")
    _enable_rls(conn, "security_findings")


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("security_findings", "security_scans"):
        conn.execute(sa.text(f"DROP POLICY IF EXISTS admin_bypass ON {table}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS security_findings"))
    conn.execute(sa.text("DROP TABLE IF EXISTS security_scans"))
    for name in ("finding_status", "analysis_source", "severity", "scan_status", "scan_type"):
        conn.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))
