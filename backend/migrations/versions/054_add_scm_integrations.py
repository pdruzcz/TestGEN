"""Add scm_integrations + integration_events (GitHub/GitLab) — Epic 8, Story 8.1

Revision ID: 054
Revises: 053
Create Date: 2026-09-23

``scm_integrations`` — podłączone repozytoria: token OAuth (AES-256-GCM pod
kluczem tenanta), identyfikator i sekret webhooka u dostawcy. Odrębna tabela
od ``integration_configs`` (Jira/ADO): tamte są per projekt i trzymają
poświadczenia użytkownika, te są per repozytorium.

Unikalność ``(provider, repo_full_name)`` jest **globalna**, nie per tenant:
webhook przychodzi bez kontekstu tenanta i niesie tylko nazwę repozytorium,
więc dwa tenanty na tym samym repo dałyby niejednoznaczne trasowanie zdarzeń.

``integration_events`` — ślad audytowy zdarzeń i stan ich przetwarzania.

Obie tabele tenant-scoped z RLS jak 042/044/045/047-050/053. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "054"
down_revision: str | None = "053"
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


def _create_enum(conn: sa.engine.Connection, name: str, values: Sequence[str]) -> None:
    labels = ", ".join(f"'{v}'" for v in values)
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    _create_enum(conn, "scm_provider", ["github", "gitlab"])
    _create_enum(conn, "scm_event_type", ["push", "pull_request", "merge_request"])
    _create_enum(
        conn, "scm_event_status", ["pending", "processing", "completed", "failed", "skipped"]
    )

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS scm_integrations (
                id                       UUID PRIMARY KEY,
                tenant_id                UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id               UUID REFERENCES projects(id) ON DELETE SET NULL,
                provider                 scm_provider NOT NULL,
                repo_full_name           VARCHAR(255) NOT NULL,
                repo_url                 VARCHAR(500) NOT NULL,
                default_branch           VARCHAR(255) NOT NULL DEFAULT 'main',
                access_token_encrypted   TEXT NOT NULL,
                refresh_token_encrypted  TEXT,
                hook_id                  VARCHAR(100),
                webhook_secret_encrypted TEXT,
                config                   JSONB,
                is_active                BOOLEAN NOT NULL DEFAULT true,
                created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at               TIMESTAMPTZ,
                CONSTRAINT uq_scm_integrations_provider_repo UNIQUE (provider, repo_full_name)
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_scm_integrations_tenant_id ON scm_integrations (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_scm_integrations_user_id ON scm_integrations (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_scm_integrations_project_id ON scm_integrations (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_scm_integrations_provider ON scm_integrations (provider)",
        "CREATE INDEX IF NOT EXISTS ix_scm_integrations_repo_full_name ON scm_integrations (repo_full_name)",
        "CREATE INDEX IF NOT EXISTS ix_scm_integrations_is_active ON scm_integrations (is_active)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "scm_integrations")

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS integration_events (
                id             UUID PRIMARY KEY,
                tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                integration_id UUID NOT NULL REFERENCES scm_integrations(id) ON DELETE CASCADE,
                event_type     scm_event_type NOT NULL,
                action         VARCHAR(50),
                repo_full_name VARCHAR(255) NOT NULL,
                branch         VARCHAR(255),
                base_branch    VARCHAR(255),
                commit_sha     VARCHAR(40),
                pr_number      INT,
                status         scm_event_status NOT NULL DEFAULT 'pending',
                task_id        VARCHAR(255),
                payload        JSONB,
                error_message  TEXT,
                completed_at   TIMESTAMPTZ,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at     TIMESTAMPTZ
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_integration_events_tenant_id ON integration_events (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_integration_events_integration_id ON integration_events (integration_id)",
        "CREATE INDEX IF NOT EXISTS ix_integration_events_event_type ON integration_events (event_type)",
        "CREATE INDEX IF NOT EXISTS ix_integration_events_repo_full_name ON integration_events (repo_full_name)",
        "CREATE INDEX IF NOT EXISTS ix_integration_events_status ON integration_events (status)",
        # Lista „ostatnie 10 zdarzeń" per integracja (AC6).
        "CREATE INDEX IF NOT EXISTS ix_integration_events_integration_created "
        "ON integration_events (integration_id, created_at DESC)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "integration_events")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS integration_events"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scm_integrations"))
    conn.execute(sa.text("DROP TYPE IF EXISTS scm_event_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS scm_event_type"))
    conn.execute(sa.text("DROP TYPE IF EXISTS scm_provider"))
