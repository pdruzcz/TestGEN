"""Add integration_configs + integration_sync_logs — Epic 5, Story 5.8

Revision ID: 034
Revises: 033
Create Date: 2026-07-17

Creates tables for external tool integrations (Jira / Azure DevOps):
- ``integration_configs`` — per-project configuration with encrypted credentials
- ``integration_sync_logs`` — per-sync audit trail with status and errors

Tenant isolation via RLS, analogous to other Epic 5 tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: str | None = "033"
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

    _create_enum(conn, "integration_provider", "'jira', 'azure_devops'")
    _create_enum(conn, "sync_status", "'pending', 'running', 'success', 'failed', 'partial'")

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS integration_configs (
                id                      UUID PRIMARY KEY,
                tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                provider                integration_provider NOT NULL,
                base_url                VARCHAR(500) NOT NULL,
                encrypted_credentials   TEXT NOT NULL,
                settings                JSONB,
                is_active               BOOLEAN NOT NULL DEFAULT true,
                created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at              TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_configs_tenant_id ON integration_configs (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_configs_project_id ON integration_configs (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_configs_provider ON integration_configs (provider)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_configs_is_active ON integration_configs (is_active)"))

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS integration_sync_logs (
                id                      UUID PRIMARY KEY,
                tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                integration_config_id   UUID NOT NULL REFERENCES integration_configs(id) ON DELETE CASCADE,
                project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                sync_type               VARCHAR(50) NOT NULL,
                status                  sync_status NOT NULL DEFAULT 'pending',
                items_total             INTEGER NOT NULL DEFAULT 0,
                items_synced            INTEGER NOT NULL DEFAULT 0,
                errors                  JSONB,
                created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at              TIMESTAMPTZ,
                completed_at            TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_sync_logs_tenant_id ON integration_sync_logs (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_sync_logs_integration_config_id ON integration_sync_logs (integration_config_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integration_sync_logs_project_id ON integration_sync_logs (project_id)"))

    _enable_rls(conn, "integration_configs")
    _enable_rls(conn, "integration_sync_logs")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON integration_sync_logs"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON integration_sync_logs"))
    conn.execute(sa.text("ALTER TABLE integration_sync_logs DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS integration_sync_logs"))
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON integration_configs"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON integration_configs"))
    conn.execute(sa.text("ALTER TABLE integration_configs DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS integration_configs"))
    conn.execute(sa.text("DROP TYPE IF EXISTS sync_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS integration_provider"))
