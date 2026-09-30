"""Add invoices + invoice_data — Epic 7, Story 7.6 (faktury VAT)

Revision ID: 048
Revises: 047
Create Date: 2026-09-10

``invoices`` — faktura VAT po każdej płatności (FR57): snapshot sprzedawcy
(config) i nabywcy (invoice_data) w chwili wystawienia, pozycje JSONB,
kwoty netto/VAT 23%/brutto, ``pdf_path`` = klucz obiektu w MinIO
(``invoices/{tenant_id}/{year}/{month}/{numer}.pdf``, AC2). Numeracja
sekwencyjna AC6: unique ``(year, month, sequential_number)`` + unique
``invoice_number`` — hard gwarancja braku duplikatów przy współbieżności.

``invoice_data`` — dane fakturowe tenanta (AC4), 1:1 z tenants.

Obie tabele tenant-scoped z RLS jak 042/044/045/047. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "048"
down_revision: str | None = "047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enums(conn: sa.engine.Connection) -> None:
    # 23505 obok 42710 — obrona na równoległy CREATE TYPE (patrz 044).
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE invoice_status AS ENUM "
            "('issued', 'canceled', 'corrected'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE invoice_payment_method AS ENUM "
            "('card', 'bank_transfer', 'blik'); "
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
            CREATE TABLE IF NOT EXISTS invoices (
                id                UUID PRIMARY KEY,
                tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                invoice_number    VARCHAR(40) NOT NULL,
                year              INT NOT NULL,
                month             INT NOT NULL,
                sequential_number INT NOT NULL,
                issue_date        DATE NOT NULL,
                sale_date         DATE NOT NULL,
                seller_name       VARCHAR(255) NOT NULL,
                seller_nip        VARCHAR(20) NOT NULL,
                seller_address    JSONB NOT NULL DEFAULT '{}'::jsonb,
                buyer_name        VARCHAR(255) NOT NULL,
                buyer_nip         VARCHAR(20),
                buyer_address     JSONB NOT NULL DEFAULT '{}'::jsonb,
                items             JSONB NOT NULL DEFAULT '[]'::jsonb,
                subtotal_net      NUMERIC(10,2) NOT NULL,
                vat_rate          NUMERIC(5,2) NOT NULL DEFAULT 23,
                vat_amount        NUMERIC(10,2) NOT NULL,
                total_gross       NUMERIC(10,2) NOT NULL,
                currency          VARCHAR(3) NOT NULL DEFAULT 'PLN',
                payment_method    invoice_payment_method NOT NULL DEFAULT 'card',
                payment_id        UUID REFERENCES payment_transactions(id) ON DELETE SET NULL,
                status            invoice_status NOT NULL DEFAULT 'issued',
                pdf_path          VARCHAR(500),
                pdf_generated_at  TIMESTAMPTZ,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at        TIMESTAMPTZ,
                CONSTRAINT uq_invoices_invoice_number UNIQUE (invoice_number),
                CONSTRAINT uq_invoices_year_month_seq UNIQUE (year, month, sequential_number)
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_invoices_tenant_id ON invoices (tenant_id)"))
    # Lista faktur tenanta malejąco po dacie (AC5) + sekwencja MAX+1 (AC6).
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_invoices_tenant_issue_date ON invoices (tenant_id, issue_date DESC)")
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_invoices_year_month ON invoices (year, month)"))
    _enable_rls(conn, "invoices")

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS invoice_data (
                id            UUID PRIMARY KEY,
                tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                company_name  VARCHAR(255) NOT NULL,
                nip           VARCHAR(20),
                address       JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at    TIMESTAMPTZ,
                CONSTRAINT uq_invoice_data_tenant_id UNIQUE (tenant_id)
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_invoice_data_tenant_id ON invoice_data (tenant_id)"))
    _enable_rls(conn, "invoice_data")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS invoice_data"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_invoices_year_month"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_invoices_tenant_issue_date"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_invoices_tenant_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS invoices"))
    conn.execute(sa.text("DROP TYPE IF EXISTS invoice_payment_method"))
    conn.execute(sa.text("DROP TYPE IF EXISTS invoice_status"))
