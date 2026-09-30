"""Add webhook_events.error_message — Epic 7, Story 7.3

Revision ID: 046
Revises: 045
Create Date: 2026-09-03

F2 — niezawodność webhooków tpay. ``webhook_events``: ``error_message``
(przyczyna odrzucenia/błędu przy audycie — AC4/AC5; pełne stack trace'e w
logach strukturalnych, tu zwięzły opz dla panelu/replay). Nowe wartości
``processing_status`` (``skipped``, ``rejected_payload``) nie wymagają
migracji — kolumna to VARCHAR(30), nie enum natywny. Idempotentny raw SQL,
konwencja repo (wzorce z 044/045).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: str | None = "045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS error_message TEXT"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE webhook_events DROP COLUMN IF EXISTS error_message"))
