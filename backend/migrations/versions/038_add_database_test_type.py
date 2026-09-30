"""Add ``database`` value to ``test_case_type`` enum — Epic 1, Story 1.53 (FR70)

Revision ID: 038
Revises: 037
Create Date: 2026-07-22

Adds the ``database`` member to the native PG enum ``test_case_type`` so
generated database-layer test cases (constraints, FK integrity, CRUD,
transactions, migrations) can be stored on ``test_cases.type``.

Renumbered from 037 → 038 to resolve a revision-ID collision with
``037_add_admin_management`` (Story 6.15, origin) — both were created off
``036`` during the same sprint.  ``down_revision`` now chains onto origin's
``037``.  See the repo's migration-collision pattern note.

Idempotent: ``ADD VALUE IF NOT EXISTS`` is a no-op on repeated runs and is
safe inside a transaction on PostgreSQL >= 12 (asyncpg target).  Mirrors the
repo's raw-SQL migration convention (revisions 010 / 030 / 036).  Only the
new ``database`` value is added here — pre-existing drift on other enum
members (performance/accessibility/semantic/...) is out of scope for this
story; the model already carries them and tests mock the DB.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: str | None = "037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "test_case_type"
NEW_VALUE = "database"


def upgrade() -> None:
    """Add the ``database`` enum value (idempotent)."""
    op.execute(sa.text(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'"))


def downgrade() -> None:
    """Downgrade is a no-op.

    PostgreSQL cannot remove a single value from an enum in-place (it requires
    recreating the type).  Removing ``database`` is intentionally unsupported —
    the value is additive and harmless to existing rows.
    """
