"""usage_counters + spokrewnione kolumny: INTEGER → BIGINT (hotfix 2026-09-29)

Revision ID: 059
Revises: 058
Create Date: 2026-09-29

Limity planów w bajtach (Basic: 10 GiB = 10 737 418 240) nie mieszczą się
w int32 (max 2 147 483 647) — INSERT licznika ``storage_bytes`` kończył się
``value out of int32 range`` (asyncpg), czyli każdy upload pliku zwracał 500.

Ta sama klasa ryzyka w dwóch sąsiednich tabelach (domykamy naraz):
- ``usage_history.value`` — snapshot ``storage_bytes`` = skumulowane bajty
  (int32 kończy się przy ~2 GiB),
- ``notifications.current_value``/``limit_value`` — przenoszą limit/użycie
  planu w bajtach w powiadomieniach progów 80/90/100.

ALTER TYPE BIGINT na mikro-tablicach; ``file_size`` w tabelach plików
zostaje INTEGER — cap uploadu jest daleko poniżej 2 GiB.

Serwer dev dostał zmianę ``usage_counters`` ręcznie (ALTER + restart
backendu) — ALTER TYPE BIGINT jest idempotentny, ponowne wykonanie bezpieczne.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "059"
down_revision: str | None = "058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE usage_counters ALTER COLUMN value TYPE BIGINT, ALTER COLUMN limit_value TYPE BIGINT")
    )
    op.execute(sa.text("ALTER TABLE usage_history ALTER COLUMN value TYPE BIGINT"))
    op.execute(
        sa.text(
            "ALTER TABLE notifications ALTER COLUMN current_value TYPE BIGINT, ALTER COLUMN limit_value TYPE BIGINT"
        )
    )


def downgrade() -> None:
    # Zwrotne zawężenie tylko wtedy, gdy dane mieszczą się w int32.
    op.execute(
        sa.text("ALTER TABLE usage_counters ALTER COLUMN value TYPE INTEGER, ALTER COLUMN limit_value TYPE INTEGER")
    )
    op.execute(sa.text("ALTER TABLE usage_history ALTER COLUMN value TYPE INTEGER"))
    op.execute(
        sa.text(
            "ALTER TABLE notifications ALTER COLUMN current_value TYPE INTEGER, ALTER COLUMN limit_value TYPE INTEGER"
        )
    )
