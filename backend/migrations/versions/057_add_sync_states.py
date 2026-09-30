"""Add sync_states + sync_conflicts — Epic 8, Story 8.11 (AC1, AC4)

Revision ID: 057
Revises: 056
Create Date: 2026-09-25

Dwukierunkowa synchronizacja z TMS: ``sync_states`` to konfiguracja i stan
jednej integracji (kierunek, odstęp, zdrowie), ``sync_conflicts`` to zapis
kolizji wraz z obiema wersjami przypadku.

Stan trzymamy w tabeli, a nie w ``integration_configs.settings``, bo
harmonogram musi dać się odpytać indeksem — bez tego beat przeglądałby
wszystkie integracje co pięć minut.

Indeks ``(is_active, last_sync_at)`` obsługuje właśnie to pytanie, a
``(sync_state_id, resolution)`` listę nierozstrzygniętych konfliktów w UI.

Obie tabele tenant-scoped z RLS jak 042/044/045/047-050/053-055.
Idempotentny raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "057"
down_revision: str | None = "056"
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


def _create_enum(conn: sa.engine.Connection, name: str, values: tuple[str, ...]) -> None:
    labels = ", ".join(f"'{value}'" for value in values)
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    _create_enum(conn, "sync_direction", ("push", "pull", "bidirectional"))
    _create_enum(conn, "sync_conflict_strategy", ("last_write_wins", "manual"))
    _create_enum(conn, "sync_health", ("active", "degraded"))
    _create_enum(
        conn, "sync_conflict_resolution", ("pending", "testgen_wins", "tms_wins", "manual")
    )
    # ``sync_status`` istnieje od Epiku 5 (integration_sync_logs) — tu jest
    # ponownie użyty, a nie tworzony.

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS sync_states (
                id                   UUID PRIMARY KEY,
                tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                integration_id       UUID NOT NULL REFERENCES integration_configs(id) ON DELETE CASCADE,
                project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                direction            sync_direction NOT NULL DEFAULT 'bidirectional',
                conflict_strategy    sync_conflict_strategy NOT NULL DEFAULT 'last_write_wins',
                interval_minutes     INT NOT NULL DEFAULT 15,
                is_active            BOOLEAN NOT NULL DEFAULT false,
                last_sync_at         TIMESTAMPTZ,
                last_sync_status     sync_status,
                last_error           TEXT,
                consecutive_failures INT NOT NULL DEFAULT 0,
                health               sync_health NOT NULL DEFAULT 'active',
                synced_count         INT NOT NULL DEFAULT 0,
                provider             VARCHAR(32) NOT NULL DEFAULT 'testrail',
                created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at           TIMESTAMPTZ,
                CONSTRAINT uq_sync_states_integration_id UNIQUE (integration_id)
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_sync_states_tenant_id ON sync_states (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_sync_states_integration_id ON sync_states (integration_id)",
        "CREATE INDEX IF NOT EXISTS ix_sync_states_project_id ON sync_states (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_sync_states_is_active ON sync_states (is_active)",
        "CREATE INDEX IF NOT EXISTS ix_sync_states_health ON sync_states (health)",
        # Pytanie beat-a co 5 minut: które aktywne synchronizacje są zaległe.
        "CREATE INDEX IF NOT EXISTS ix_sync_states_due "
        "ON sync_states (is_active, last_sync_at)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "sync_states")

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS sync_conflicts (
                id               UUID PRIMARY KEY,
                tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                sync_state_id    UUID NOT NULL REFERENCES sync_states(id) ON DELETE CASCADE,
                test_case_id     UUID NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
                tms_test_id      VARCHAR(64) NOT NULL,
                testgen_version  JSONB NOT NULL DEFAULT '{}'::jsonb,
                tms_version      JSONB NOT NULL DEFAULT '{}'::jsonb,
                resolution       sync_conflict_resolution NOT NULL DEFAULT 'pending',
                resolved_at      TIMESTAMPTZ,
                resolved_by      UUID REFERENCES users(id) ON DELETE SET NULL,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at       TIMESTAMPTZ
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_sync_conflicts_tenant_id ON sync_conflicts (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_sync_conflicts_sync_state_id ON sync_conflicts (sync_state_id)",
        "CREATE INDEX IF NOT EXISTS ix_sync_conflicts_test_case_id ON sync_conflicts (test_case_id)",
        "CREATE INDEX IF NOT EXISTS ix_sync_conflicts_resolution ON sync_conflicts (resolution)",
        # Lista nierozstrzygniętych konfliktów danej synchronizacji (AC5).
        "CREATE INDEX IF NOT EXISTS ix_sync_conflicts_state_resolution "
        "ON sync_conflicts (sync_state_id, resolution)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "sync_conflicts")

    # Powiązanie przypadku z jego odpowiednikiem w TMS (AC5). Kolumny siedzą
    # na ``test_cases``, a nie w osobnej tabeli mapowań: relacja jest jeden
    # do jednego, a lista przypadków i tak czyta ten wiersz.
    for stmt in (
        "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS tms_external_id VARCHAR(64)",
        "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS tms_synced_at TIMESTAMPTZ",
    ):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    conn = op.get_bind()
    for stmt in (
        "ALTER TABLE test_cases DROP COLUMN IF EXISTS tms_synced_at",
        "ALTER TABLE test_cases DROP COLUMN IF EXISTS tms_external_id",
    ):
        conn.execute(sa.text(stmt))
    conn.execute(sa.text("DROP TABLE IF EXISTS sync_conflicts"))
    conn.execute(sa.text("DROP TABLE IF EXISTS sync_states"))
    conn.execute(sa.text("DROP TYPE IF EXISTS sync_conflict_resolution"))
    conn.execute(sa.text("DROP TYPE IF EXISTS sync_health"))
    conn.execute(sa.text("DROP TYPE IF EXISTS sync_conflict_strategy"))
    conn.execute(sa.text("DROP TYPE IF EXISTS sync_direction"))
    # ``sync_status`` zostaje — należy do integration_sync_logs z Epiku 5.
