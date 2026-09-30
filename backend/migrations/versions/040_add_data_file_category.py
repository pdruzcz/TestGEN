"""``data`` file_category value — Story 1.6-zakańczenie (FR2/FR6)

Revision ID: 040
Revises: 039
Create Date: 2026-07-30

Adds the ``data`` value to the native ``file_category`` enum so config/fixture
files (e.g. ``composer.json``, ``package.json``) uploaded as project data can be
categorized as DATA — distinct from CODE (AST-parsed) and DOCUMENTATION
(E2-parsed). DATA files stay available to autodetection (e.g. FrameworkDetector
reads ``composer.json`` via ``PreprocessingService._prepare_project_dir``)
without entering the documentation or AST code pipelines.

Raw-SQL convention mirrors revisions 008 / 038 / 039. ``ADD VALUE IF NOT
EXISTS`` is idempotent and safe in-transaction on PostgreSQL >= 12 (asyncpg).
PG enum values cannot be removed in-place, so the downgrade is a no-op (same
limitation documented in revisions 038 / 039).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ``data`` to the ``file_category`` enum."""
    op.execute(sa.text("ALTER TYPE file_category ADD VALUE IF NOT EXISTS 'data'"))


def downgrade() -> None:
    """No-op — PG enum values cannot be removed in-place."""
