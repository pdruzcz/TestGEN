"""Add plan_change_history — Epic 7, Story 7.5 (upgrade/downgrade z prorated billing)

Revision ID: 047
Revises: 046
Create Date: 2026-09-03 (renumber 046→047 w Story 7.6: kolizja headów
z 046_webhook_events_error_message — wzorzec alembic-migration-collision)

Historia zmian planu (AC4): rekord audytowy każdej zmiany (upgrade
natychmiastowy / downgrade na koniec okresu) z lokalnym wyliczeniem
proration w ``proration_details`` (JSONB) — D2: proration liczymy sami,
tpay nie ma odpowiednika ``proration_behavior``. ``from_plan``/``to_plan``
współdzielą natywny enum ``subscription_plan_name`` (042). Tabela
tenant-scoped z RLS jak 042/044/045. Idempotentny raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: str | None = "046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enums(conn: sa.engine.Connection) -> None:
    # 23505 obok 42710 — obrona na równoległy CREATE TYPE (patrz 044).
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE plan_change_type AS ENUM "
            "('upgrade', 'downgrade'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE plan_change_status AS ENUM "
            "('pending', 'completed', 'canceled'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
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
    _create_enums(conn)

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS plan_change_history (
                id                UUID PRIMARY KEY,
                tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                from_plan         subscription_plan_name NOT NULL,
                to_plan           subscription_plan_name NOT NULL,
                change_type       plan_change_type NOT NULL,
                effective_at      TIMESTAMPTZ,
                requested_at      TIMESTAMPTZ NOT NULL,
                requested_by      UUID REFERENCES users(id) ON DELETE SET NULL,
                status            plan_change_status NOT NULL DEFAULT 'pending',
                proration_details JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at        TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_plan_change_history_tenant_id ON plan_change_history (tenant_id)")
    )
    # Szybkie wyszukanie oczekującej zmiany tenanta (cancel-pending, scheduler).
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_plan_change_history_tenant_pending "
            "ON plan_change_history (tenant_id) WHERE status = 'pending'"
        )
    )
    _enable_rls(conn, "plan_change_history")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_plan_change_history_tenant_pending"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_plan_change_history_tenant_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS plan_change_history"))
    conn.execute(sa.text("DROP TYPE IF EXISTS plan_change_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS plan_change_type"))
