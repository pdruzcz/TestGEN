"""Add api_keys (klucze API do automatyzacji CI/CD) — Epic 8, Story 8.6 (AC1)

Revision ID: 053
Revises: 052
Create Date: 2026-09-23

``api_keys`` — uwierzytelnianie bezhasłowe dla CI/CD i skryptów. W bazie
wyłącznie SHA-256 hash klucza (``key_hash``, unique — lookup po hashu przy
każdym requeście) oraz ``key_prefix`` do identyfikacji na liście. Klucz
plaintext nie jest nigdzie zapisywany.

Stan klucza wynika z ``revoked_at`` (soft delete) i ``expires_at``;
indeks ``(tenant_id, revoked_at)`` obsługuje listę aktywnych kluczy tenanta.

Tabela tenant-scoped z RLS jak 042/044/045/047/048/049/050. Idempotentny
raw SQL (konwencja repo).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "053"
down_revision: str | None = "052"
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
            "DO $$ BEGIN CREATE TYPE api_key_scope AS ENUM ('read_only', 'full_access'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "WHEN unique_violation THEN NULL; END $$;"
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id           UUID PRIMARY KEY,
                tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key_prefix   VARCHAR(8) NOT NULL,
                key_hash     VARCHAR(64) NOT NULL,
                name         VARCHAR(100) NOT NULL,
                scope        api_key_scope NOT NULL DEFAULT 'read_only',
                expires_at   TIMESTAMPTZ,
                last_used_at TIMESTAMPTZ,
                revoked_at   TIMESTAMPTZ,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ,
                CONSTRAINT uq_api_keys_key_hash UNIQUE (key_hash)
            )
            """
        )
    )
    # Lookup przy każdym uwierzytelnieniu — po samym hashu (bez kontekstu tenanta).
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys (key_hash)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id)"))
    # Lista kluczy tenanta z podziałem aktywne/odwołane (AC5).
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_revoked ON api_keys (tenant_id, revoked_at)")
    )
    _enable_rls(conn, "api_keys")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_api_keys_tenant_revoked"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_api_keys_user_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_api_keys_tenant_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_api_keys_key_hash"))
    conn.execute(sa.text("DROP TABLE IF EXISTS api_keys"))
    conn.execute(sa.text("DROP TYPE IF EXISTS api_key_scope"))
