"""Add healing tables — Epic 1, Story 1.51 (self-healing UI locators)

Revision ID: 036
Revises: 035
Create Date: 2026-07-17

Creates ``healing_reports`` (one self-healing run between two GUI/code
versions) and ``healing_items`` (one broken locator and its proposed
replacement).  Mirrors the gap-finding / recommendation shape: confidence
score, status enum, JSONB stats.  Tenant isolation via RLS.

Native PG enums ``healing_status`` and ``locator_strategy`` are created
first (both tables reference them).  Idempotent raw SQL, matching the repo's
migration convention (revisions 010 / 030).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: str | None = "035"
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

    # --- 1. Enum types ------------------------------------------------------
    _create_enum(
        conn,
        "healing_status",
        "'pending', 'healed', 'needs_review', 'failed', 'rejected'",
    )
    _create_enum(
        conn,
        "locator_strategy",
        "'data-testid', 'role+name', 'aria-label', 'id', 'css', 'xpath'",
    )

    # --- 2. healing_reports -------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS healing_reports (
                id           UUID PRIMARY KEY,
                tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                version_a    VARCHAR(255) NOT NULL,
                version_b    VARCHAR(255) NOT NULL,
                status       healing_status NOT NULL DEFAULT 'pending',
                stats        JSONB,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_reports_tenant_id ON healing_reports (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_reports_project_id ON healing_reports (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_reports_status ON healing_reports (status)"))

    # --- 3. healing_items ---------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS healing_items (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                report_id       UUID NOT NULL REFERENCES healing_reports(id) ON DELETE CASCADE,
                test_code_id    UUID NOT NULL REFERENCES test_codes(id) ON DELETE CASCADE,
                old_locator     TEXT NOT NULL,
                old_strategy    locator_strategy NOT NULL,
                new_locator     TEXT,
                new_strategy    locator_strategy,
                confidence      FLOAT NOT NULL DEFAULT 0.0,
                healing_method  VARCHAR(30) NOT NULL DEFAULT 'native',
                status          healing_status NOT NULL DEFAULT 'pending',
                diff_preview    TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_items_tenant_id ON healing_items (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_items_report_id ON healing_items (report_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_items_test_code_id ON healing_items (test_code_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_items_confidence ON healing_items (confidence)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_healing_items_status ON healing_items (status)"))

    # --- 4. RLS -------------------------------------------------------------
    _enable_rls(conn, "healing_reports")
    _enable_rls(conn, "healing_items")


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("healing_items", "healing_reports"):
        conn.execute(sa.text(f"DROP POLICY IF EXISTS admin_bypass ON {table}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))
    conn.execute(sa.text("DROP TYPE IF EXISTS locator_strategy"))
    conn.execute(sa.text("DROP TYPE IF EXISTS healing_status"))
