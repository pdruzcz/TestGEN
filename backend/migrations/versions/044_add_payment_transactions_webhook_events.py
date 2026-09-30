"""Add payment_transactions, webhook_events — Epic 7, Story 7.4

Revision ID: 044
Revises: 043
Create Date: 2026-09-01

tpay checkout redirect + webhook transakcyjny (F1). ``payment_transactions``
to lokalne lustro transakcji u dostawcy (korelacja wyłącznie po
``hidden_description`` = ``order_id`` = ``tr_crc``; ``transaction_id``
trzymany długoterminowo — wymóg BOK tpay). ``webhook_events`` to audyt +
idempotencja każdej notyfikacji (``event_uid`` = ``tr_id:tr_status``) —
tabela systemowa bez ``tenant_id`` (bez RLS), bo notyfikacja może być
odrzucona zanim skoreluje się z tenantem. Kolumna ``metadata`` (JSONB) —
atrybut modelu nazywa się ``meta`` (kolizja z DeclarativeBase.metadata).
``payment_transactions`` tenant-scoped z RLS jak tablice 041/042. Procesor
webhooka (przepływ bez JWT) ustawia kontekst admina (NIL UUID). Idempotentny
raw SQL, konwencja repo (wzorce z 042).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "044"
down_revision: str | None = "043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enums(conn: sa.engine.Connection) -> None:
    # unique_violation (23505) obok duplicate_object (42710): przy równoległym
    # starcie backend+celery-worker przegrywający CREATE TYPE dostaje 23505
    # z pg_type_typname_nsp_index zamiast 42710 (deploy 2026-09-02). Głównym
    # zabezpieczeniem jest advisory lock w migrations/env.py; to jest obrona
    # dla migracji uruchomionych poza nim (np. ręcznie z dwóch sesji).
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE payment_status AS ENUM "
            "('pending', 'paid', 'charged_back', 'refunded'); "
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
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id                 UUID PRIMARY KEY,
                tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                provider           VARCHAR(20) NOT NULL DEFAULT 'tpay',
                transaction_id     VARCHAR(100),
                title              VARCHAR(100),
                hidden_description VARCHAR(64) NOT NULL,
                amount             NUMERIC(10, 2) NOT NULL,
                currency           VARCHAR(3) NOT NULL DEFAULT 'PLN',
                status             payment_status NOT NULL DEFAULT 'pending',
                paid_amount        NUMERIC(10, 2),
                test_mode          BOOLEAN NOT NULL DEFAULT FALSE,
                metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at         TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_payment_transactions_tenant_id ON payment_transactions (tenant_id)")
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_payment_transactions_transaction_id ON payment_transactions (transaction_id)"
        )
    )
    # Korelacja webhook↔zamówienie wyłącznie po hidden_description — unique.
    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_transactions_hidden_description ON payment_transactions (hidden_description)"
        )
    )
    _enable_rls(conn, "payment_transactions")

    # Tabela systemowa (audyt + idempotencja) — bez tenant_id, bez RLS.
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                id                UUID PRIMARY KEY,
                event_uid         VARCHAR(150) NOT NULL,
                provider          VARCHAR(20) NOT NULL DEFAULT 'tpay',
                type              VARCHAR(50) NOT NULL DEFAULT 'transaction',
                raw               JSONB NOT NULL,
                processing_status VARCHAR(30) NOT NULL,
                processed_at      TIMESTAMPTZ,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at        TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_webhook_events_event_uid ON webhook_events (event_uid)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS webhook_events"))
    conn.execute(sa.text("DROP TABLE IF EXISTS payment_transactions"))
    conn.execute(sa.text("DROP TYPE IF EXISTS payment_status"))
