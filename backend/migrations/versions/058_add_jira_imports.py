"""Add jira_imports — Epic 8, Story 8.12 (AC1, AC4)

Revision ID: 058
Revises: 057
Create Date: 2026-09-25

Import wymagań z Jiry: jeden wiersz na parę *projekt TestGEN ↔ projekt Jiry*.
Kluczowa kolumna to ``last_import_at`` — od niej zależy import przyrostowy
(JQL ``updated >= …``), więc przesuwa ją wyłącznie udany przebieg.

Tabela tenant-scoped z RLS jak 042/044/045/047-050/053-057. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "058"
down_revision: str | None = "057"
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
            "DO $$ BEGIN CREATE TYPE jira_import_status AS ENUM "
            "('pending', 'running', 'completed', 'failed'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS jira_imports (
                id                UUID PRIMARY KEY,
                tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                integration_id    UUID NOT NULL REFERENCES integration_configs(id) ON DELETE CASCADE,
                jira_project_key  VARCHAR(64) NOT NULL,
                issue_types       VARCHAR(32)[] NOT NULL DEFAULT '{}',
                status            jira_import_status NOT NULL DEFAULT 'pending',
                last_import_at    TIMESTAMPTZ,
                total_imported    INT NOT NULL DEFAULT 0,
                total_attachments INT NOT NULL DEFAULT 0,
                total_skipped     INT NOT NULL DEFAULT 0,
                last_error        TEXT,
                task_id           VARCHAR(64),
                document_file_id  UUID REFERENCES source_files(id) ON DELETE SET NULL,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at        TIMESTAMPTZ,
                CONSTRAINT uq_jira_imports_project_key UNIQUE (project_id, jira_project_key)
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_jira_imports_tenant_id ON jira_imports (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_jira_imports_project_id ON jira_imports (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_jira_imports_integration_id ON jira_imports (integration_id)",
        "CREATE INDEX IF NOT EXISTS ix_jira_imports_jira_project_key ON jira_imports (jira_project_key)",
        "CREATE INDEX IF NOT EXISTS ix_jira_imports_status ON jira_imports (status)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "jira_imports")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS jira_imports"))
    conn.execute(sa.text("DROP TYPE IF EXISTS jira_import_status"))
