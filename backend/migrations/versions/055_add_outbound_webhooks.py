"""Add outbound_webhooks + webhook_deliveries — Epic 8, Story 8.7 (AC1, AC5)

Revision ID: 055
Revises: 054
Create Date: 2026-09-24

Webhooki wychodzące: ``outbound_webhooks`` to endpointy klienta wraz z listą
subskrybowanych zdarzeń i sekretem (AES-256-GCM pod kluczem tenanta),
``webhook_deliveries`` to osobny wiersz na każdą próbę dostarczenia —
historia prób jest tym, po czym klient diagnozuje własny endpoint.

Indeks ``(status, next_retry_at)`` obsługuje zamiatacz ponowień (beat co
minutę), a ``(webhook_id, created_at DESC)`` listę ostatnich dostaw w UI.

Obie tabele tenant-scoped z RLS jak 042/044/045/047-050/053/054. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: str | None = "054"
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
            "DO $$ BEGIN CREATE TYPE webhook_delivery_status AS ENUM "
            "('pending', 'delivered', 'failed'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS outbound_webhooks (
                id                   UUID PRIMARY KEY,
                tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                url                  VARCHAR(2048) NOT NULL,
                secret_encrypted     TEXT NOT NULL,
                description          VARCHAR(200),
                events               VARCHAR(50)[] NOT NULL DEFAULT '{}',
                is_active            BOOLEAN NOT NULL DEFAULT true,
                last_delivery_at     TIMESTAMPTZ,
                last_delivery_status webhook_delivery_status,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at           TIMESTAMPTZ
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_outbound_webhooks_tenant_id ON outbound_webhooks (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_outbound_webhooks_user_id ON outbound_webhooks (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_outbound_webhooks_is_active ON outbound_webhooks (is_active)",
        # Wyszukanie subskrybentów zdarzenia: tenant + aktywne, potem filtr po tablicy.
        "CREATE INDEX IF NOT EXISTS ix_outbound_webhooks_tenant_active "
        "ON outbound_webhooks (tenant_id, is_active)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "outbound_webhooks")

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                webhook_id      UUID NOT NULL REFERENCES outbound_webhooks(id) ON DELETE CASCADE,
                event_type      VARCHAR(50) NOT NULL,
                payload         JSONB NOT NULL,
                response_status INT,
                response_body   VARCHAR(1024),
                error_message   VARCHAR(500),
                attempt_number  INT NOT NULL DEFAULT 1,
                status          webhook_delivery_status NOT NULL DEFAULT 'pending',
                delivered_at    TIMESTAMPTZ,
                next_retry_at   TIMESTAMPTZ,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_tenant_id ON webhook_deliveries (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_webhook_id ON webhook_deliveries (webhook_id)",
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_event_type ON webhook_deliveries (event_type)",
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_status ON webhook_deliveries (status)",
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_next_retry_at ON webhook_deliveries (next_retry_at)",
        # Zamiatacz ponowień (beat co minutę) — pending z zaległym terminem.
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_retry_sweep "
        "ON webhook_deliveries (status, next_retry_at)",
        # Historia ostatnich dostaw danego webhooka (AC5).
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_webhook_created "
        "ON webhook_deliveries (webhook_id, created_at DESC)",
    ):
        conn.execute(sa.text(stmt))
    _enable_rls(conn, "webhook_deliveries")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS webhook_deliveries"))
    conn.execute(sa.text("DROP TABLE IF EXISTS outbound_webhooks"))
    conn.execute(sa.text("DROP TYPE IF EXISTS webhook_delivery_status"))
