"""Add TMS providers to integration_provider — Epic 8, Stories 8.8/8.9 (AC1)

Revision ID: 056
Revises: 055
Create Date: 2026-09-24

Rozszerza enum ``integration_provider`` (z migracji 034) o systemy zarządzania
testami: TestRail (8.8) oraz Xray i Zephyr (8.9). Konfiguracja TMS mieszka
w istniejącej tabeli ``integration_configs``, bo — jak Jira i Azure DevOps —
jest per projekt: identyfikator projektu docelowego różni się między projektami
TestGEN.

Wartości dokładamy wszystkie trzy naraz, żeby Story 8.9 nie wymagała kolejnej
migracji na tym samym typie.

``ALTER TYPE ... ADD VALUE`` nie działa wewnątrz transakcji na starszych
PostgreSQL-ach, stąd ``COMMIT`` przed zmianą typu i idempotentne
``IF NOT EXISTS``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: str | None = "055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_VALUES = ("testrail", "xray", "zephyr")


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    for value in _NEW_VALUES:
        conn.execute(sa.text(f"ALTER TYPE integration_provider ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    # PostgreSQL nie pozwala usunąć wartości z enuma bez przebudowy typu
    # i wszystkich kolumn, które go używają. Wartości nieużywane nie szkodzą,
    # więc downgrade jest świadomie pusty.
    pass
