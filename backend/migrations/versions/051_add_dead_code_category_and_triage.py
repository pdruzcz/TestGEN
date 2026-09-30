"""Add ``dead_code`` error category + code error triage — Epic 5, Story 5.10

Revision ID: 051
Revises: 050
Create Date: 2026-09-20

Two additive changes to ``code_errors``:

1. ``dead_code`` member on the native PG enum ``error_category`` so the
   new dead-code detector (uncalled private/internal code) can persist
   findings.
2. Triage columns for AC4: ``status`` (``open`` / ``false_positive`` —
   mirrors the security finding workflow) and ``fingerprint``
   (``{file}:{name}:{sha8}`` stable key).  Findings dismissed as false
   positive survive rescans (the rescan DELETE keeps them) and suppress
   re-detection of the same code state.

Idempotent: ``ADD VALUE IF NOT EXISTS`` is a no-op on repeated runs and
is safe inside a transaction on PostgreSQL >= 12 (asyncpg target),
mirroring revision 038.  Raw-SQL convention per 030.  Downgrade cannot
remove a single enum value in-place (type recreation required) — the
value is additive and harmless; only the columns are dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: str | None = "050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "error_category"
NEW_VALUE = "dead_code"


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. New enum value (idempotent) ----------------------------------
    op.execute(sa.text(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'"))

    # --- 2. Triage columns ------------------------------------------------
    conn.execute(sa.text("ALTER TABLE code_errors ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'open'"))
    conn.execute(sa.text("ALTER TABLE code_errors ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(300)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_status ON code_errors (status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_code_errors_fingerprint ON code_errors (fingerprint)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_code_errors_fingerprint"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_code_errors_status"))
    conn.execute(sa.text("ALTER TABLE code_errors DROP COLUMN IF EXISTS fingerprint"))
    conn.execute(sa.text("ALTER TABLE code_errors DROP COLUMN IF EXISTS status"))
    # ``dead_code`` enum value intentionally kept (PostgreSQL cannot remove
    # a single enum member in-place; the value is additive and harmless).
