"""Add usage_history (daily snapshots) — Epic 7, Story 7.9 (AC3)

Revision ID: 049
Revises: 048
Create Date: 2026-09-10

``usage_history`` — daily snapshot wartości liczników per tenant
(zadanie Celery, Task 2): dane wykresu historii zużycia (AC3) i prognozy
(AC4). Unique ``(tenant_id, counter_type, snapshot_date)`` — jeden snapshot
per dzień, idempotencja tasku. Enum ``usage_counter_type`` już istnieje
(migracja 042, UsageCounter) — reużyty.

Tabela tenant-scoped z RLS jak 042/044/045/047/048. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: str | None = "048"
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
            CREATE TABLE IF NOT EXISTS usage_history (
                id            UUID PRIMARY KEY,
                tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                counter_type  usage_counter_type NOT NULL,
                value         INT NOT NULL DEFAULT 0,
                snapshot_date DATE NOT NULL,
                period_start  DATE NOT NULL,
                period_end    DATE NOT NULL,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at    TIMESTAMPTZ,
                CONSTRAINT uq_usage_history_tenant_type_date UNIQUE (tenant_id, counter_type, snapshot_date)
            )
            """
        )
    )
    # Wykres historii (AC3): odczyt per tenant per typ po zakresie dat —
    # zapytania pokrywa indeks unique (tenant_id, counter_type, snapshot_date).
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_usage_history_tenant_id ON usage_history (tenant_id)"))
    _enable_rls(conn, "usage_history")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_usage_history_tenant_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS usage_history"))
