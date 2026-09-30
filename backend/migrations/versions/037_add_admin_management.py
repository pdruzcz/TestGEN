"""Add admin management columns and platform settings — Epic 6, Story 6.15

Revision ID: 037
Revises: 036
Create Date: 2026-07-28

Dodaje kolumny potrzebne panelowi administracyjnemu:
``users.is_blocked`` (odwracalna blokada konta) oraz ``users.deleted_at``
(miękkie usunięcie — rekord zostaje, by log audytu zachował spójność).

Tworzy też globalną tabelę ``platform_settings`` (jeden wiersz na sekcję
konfiguracji).  Tabela nie ma ``tenant_id`` ani RLS — dotyczy całej instalacji
i jest dostępna wyłącznie dla roli admin.  Idempotentny surowy SQL, zgodnie
z konwencją repozytorium (rewizje 010 / 030 / 036).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. users: blokada i miękkie usunięcie -----------------------------
    conn.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN NOT NULL DEFAULT false")
    )
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_deleted_at ON users (deleted_at) WHERE deleted_at IS NULL"
        )
    )

    # --- 2. platform_settings ---------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS platform_settings (
                key        VARCHAR(100) PRIMARY KEY,
                value      JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS platform_settings"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_deleted_at"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_blocked"))
