"""Add seller_krs/seller_regon to invoices — dane rejestrowe wystawcy (2026-09-22)

Revision ID: 052
Revises: 051
Create Date: 2026-09-22

Faktury VAT muszą prezentować pełne dane rejestrowe spółki: NIP, KRS,
REGON i adres siedziby. NIP/adres były już snapshotowane (Story 7.6);
dodajemy kolumny snapshot ``seller_krs`` / ``seller_regon`` (nullable —
faktury wystawione przed tą zmianą ich nie mają i pozostają ważne).
Wartości domyślne configu (``INVOICE_SELLER_*``) niosą realne dane
spółki, więc deployment nie wymaga nowych envów.

Idempotentne (ADD COLUMN IF NOT EXISTS), wzorzec 051.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: str | None = "051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS seller_krs VARCHAR(20)"))
    conn.execute(sa.text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS seller_regon VARCHAR(20)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE invoices DROP COLUMN IF EXISTS seller_regon"))
    conn.execute(sa.text("ALTER TABLE invoices DROP COLUMN IF EXISTS seller_krs"))
