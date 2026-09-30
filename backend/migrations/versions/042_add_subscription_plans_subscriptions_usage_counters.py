"""Add subscription_plans, subscriptions, usage_counters — Epic 7, Story 7.1

Revision ID: 042
Revises: 041
Create Date: 2026-08-31

Model 3-planowy (CR#2 2026-08-28): Freemium 0 PLN / Basic 30 / Premium 50,
tylko cykl miesięczny (bez pól rocznych), bez pól dostawcy płatności (D1/D2,
plan-integracji-tpay.md). Plans are global reference data (no RLS);
``subscriptions`` and ``usage_counters`` are tenant-scoped with RLS,
mirroring the anonymization tables (revision 041). Idempotent raw SQL,
matching the repo's migration convention. Plan rows are seeded at app
startup (``app.seed.seed_plans``), not in this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: str | None = "041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUMS = {
    "subscription_plan_name": ("freemium", "basic", "premium"),
    "subscription_status": ("active", "past_due", "canceled", "incomplete"),
    "usage_counter_type": ("analyses", "test_cases", "storage_bytes", "files_per_analysis"),
}


def _create_enums(conn: sa.engine.Connection) -> None:
    # unique_violation (23505) obok duplicate_object (42710) — patrz 044;
    # główna obrona: advisory lock w migrations/env.py.
    for name, values in _ENUMS.items():
        literals = ", ".join(f"'{v}'" for v in values)
        conn.execute(
            sa.text(
                f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({literals}); "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "WHEN unique_violation THEN NULL; END $$;"
            )
        )


def _drop_enums(conn: sa.engine.Connection) -> None:
    for name in reversed(list(_ENUMS)):
        conn.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))


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

    # Global reference data — no tenant_id, no RLS.
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id           UUID PRIMARY KEY,
                name         subscription_plan_name NOT NULL UNIQUE,
                display_name VARCHAR(100) NOT NULL,
                price_monthly NUMERIC(10, 2) NOT NULL DEFAULT 0,
                currency     VARCHAR(3) NOT NULL DEFAULT 'PLN',
                features     JSONB NOT NULL DEFAULT '{}'::jsonb,
                is_active    BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order   INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id                   UUID PRIMARY KEY,
                tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                plan_id              UUID NOT NULL REFERENCES subscription_plans(id) ON DELETE RESTRICT,
                status               subscription_status NOT NULL DEFAULT 'active',
                current_period_start TIMESTAMPTZ NOT NULL,
                current_period_end   TIMESTAMPTZ NOT NULL,
                next_charge_at       TIMESTAMPTZ,
                cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
                trial_end            TIMESTAMPTZ,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at           TIMESTAMPTZ
            )
            """
        )
    )
    # Exactly one subscription per tenant (unique index).
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_subscriptions_tenant_id ON subscriptions (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_plan_id ON subscriptions (plan_id)"))

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS usage_counters (
                id           UUID PRIMARY KEY,
                tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                counter_type usage_counter_type NOT NULL,
                value        INTEGER NOT NULL DEFAULT 0,
                limit_value  INTEGER NOT NULL,
                period_start TIMESTAMPTZ NOT NULL,
                period_end   TIMESTAMPTZ NOT NULL,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_usage_counters_tenant_id ON usage_counters (tenant_id)"))
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_usage_counters_tenant_type_period "
            "ON usage_counters (tenant_id, counter_type, period_start)"
        )
    )

    _enable_rls(conn, "subscriptions")
    _enable_rls(conn, "usage_counters")


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("usage_counters", "subscriptions"):
        conn.execute(sa.text(f"DROP POLICY IF EXISTS admin_bypass ON {table}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS usage_counters"))
    conn.execute(sa.text("DROP TABLE IF EXISTS subscriptions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS subscription_plans"))
    _drop_enums(conn)
