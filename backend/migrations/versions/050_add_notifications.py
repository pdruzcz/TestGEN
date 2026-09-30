"""Add notifications (limit warnings in-app) — Epic 7, Story 7.11 (AC4)

Revision ID: 050
Revises: 049
Create Date: 2026-09-10

``notifications`` — powiadomienia in-app (dzwonek w navbarze); typ
``limit_warning`` z progów zużycia (80/90/100%, task Celery co godzinę),
typy ``payment_failed``/``subscription_changed``/``invoice_ready`` —
rezerwacja pod przyszłe story. Deduplikacja progów: unique
``(tenant_id, type, resource_type, threshold_percentage, billing_period)``
— jedno powiadomienie per próg per zasób per okres rozliczeniowy (AC1).
Indeks ``(user_id, is_read, created_at)`` — szybkie zapytanie o nieprzeczytane.

Tabela tenant-scoped z RLS jak 042/044/045/047/048/049. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: str | None = "049"
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
    # Enumy (idempotentnie — jeden DO-block per execute, konwencja 048;
    # 23505 obok 42710 — obrona na równoległy CREATE TYPE).
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE notification_type AS ENUM "
            "('limit_warning', 'payment_failed', 'subscription_changed', 'invoice_ready'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE notification_severity AS ENUM "
            "('info', 'warning', 'critical'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id                   UUID PRIMARY KEY,
                tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type                 notification_type NOT NULL,
                severity             notification_severity NOT NULL,
                title                VARCHAR(255) NOT NULL,
                message              VARCHAR(2000) NOT NULL,
                resource_type        VARCHAR(100),
                current_value        INT,
                limit_value          INT,
                percentage           INT,
                threshold_percentage INT,
                billing_period       VARCHAR(7),
                is_read              BOOLEAN NOT NULL DEFAULT false,
                cta_url              VARCHAR(500),
                metadata             JSONB,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at           TIMESTAMPTZ,
                CONSTRAINT uq_notifications_dedup UNIQUE (tenant_id, type, resource_type, threshold_percentage, billing_period)
            )
            """
        )
    )
    # Nieprzeczytane per user (Task 1.3) + odczyt per tenant (RLS).
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_user_read_created "
            "ON notifications (user_id, is_read, created_at)"
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notifications_tenant_id ON notifications (tenant_id)"))
    _enable_rls(conn, "notifications")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_notifications_tenant_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_notifications_user_read_created"))
    conn.execute(sa.text("DROP TABLE IF EXISTS notifications"))
    conn.execute(sa.text("DROP TYPE IF EXISTS notification_severity"))
    conn.execute(sa.text("DROP TYPE IF EXISTS notification_type"))
