"""Add payment_tokens + subscription dunning columns — Epic 7, Story 7.2

Revision ID: 045
Revises: 044
Create Date: 2026-09-02

F2 — płatności cykliczne. ``payment_tokens``: zapisane metody płatności
(token karty / alias BLIK) — wartość AES-256-GCM per-tenant (wzorzec 1.54),
deterministyczny ``value_digest`` do wyszukiwania (nonce GCM losowy),
``registration_id`` (cliAuth) koreluje rejestrację ``POST /tokens`` z
notyfikacją ``data.token``. Tabela tenant-scoped z RLS jak 042/044.

``subscriptions``: FK aktywnej metody (``payment_token_id``, SET NULL) +
stan dunningu (``dunning_attempt``, ``dunning_next_retry_at``, ``grace_until``,
``previous_plan_id`` — CR#2: downgrade zawsze do Freemium z 7-dniowym grace
na planie, który był). Idempotentny raw SQL, konwencja repo (wzorce z 044).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "045"
down_revision: str | None = "044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enums(conn: sa.engine.Connection) -> None:
    # 23505 obok 42710 — obrona na równoległy CREATE TYPE (patrz 044).
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE payment_token_kind AS ENUM "
            "('card_token', 'blik_alias_uid', 'blik_alias_payid'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE tpay_token_status AS ENUM "
            "('pending', 'active', 'suspended', 'deleted'); "
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
            CREATE TABLE IF NOT EXISTS payment_tokens (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                kind            payment_token_kind NOT NULL,
                value_encrypted BYTEA NOT NULL DEFAULT ''::bytea,
                value_digest    VARCHAR(64) NOT NULL DEFAULT '',
                card_tail       VARCHAR(4),
                card_brand      VARCHAR(20),
                expires_at      TIMESTAMPTZ,
                tpay_status     tpay_token_status NOT NULL DEFAULT 'pending',
                is_default      BOOLEAN NOT NULL DEFAULT FALSE,
                registration_id VARCHAR(64),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_payment_tokens_tenant_id ON payment_tokens (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_payment_tokens_value_digest ON payment_tokens (value_digest)"))
    # cliAuth — korelacja notyfikacji data.token z rejestracją (AC2).
    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_tokens_registration_id ON payment_tokens (registration_id)"
        )
    )
    _enable_rls(conn, "payment_tokens")

    # --- subscriptions: aktywna metoda płatności + stan dunningu (AC1/AC5/AC6) ---
    conn.execute(
        sa.text(
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS payment_token_id UUID "
            "REFERENCES payment_tokens(id) ON DELETE SET NULL"
        )
    )
    conn.execute(
        sa.text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS dunning_attempt INTEGER NOT NULL DEFAULT 0")
    )
    conn.execute(sa.text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS dunning_next_retry_at TIMESTAMPTZ"))
    conn.execute(sa.text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS grace_until TIMESTAMPTZ"))
    conn.execute(
        sa.text(
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS previous_plan_id UUID "
            "REFERENCES subscription_plans(id) ON DELETE RESTRICT"
        )
    )
    # Przyśpieszenie skanu scheduler'a (next_charge_at jest od 042).
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_next_charge_at ON subscriptions (next_charge_at)")
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_next_charge_at"))
    conn.execute(sa.text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS previous_plan_id"))
    conn.execute(sa.text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS grace_until"))
    conn.execute(sa.text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS dunning_next_retry_at"))
    conn.execute(sa.text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS dunning_attempt"))
    conn.execute(sa.text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS payment_token_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS payment_tokens"))
    conn.execute(sa.text("DROP TYPE IF EXISTS tpay_token_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS payment_token_kind"))
