"""Add pattern_images column to test_codes — Epic 3, Story 3-13-domknięcie

Revision ID: 026
Revises: 025
Create Date: 2026-07-15

Adds ``pattern_images`` (JSONB) to ``test_codes`` so each SikuliX record can
record the cropped PNG patterns it references —
``[{"name": "button_login.png", "storage_key": "...", "component_id": "..."}]``.
Closes AC-2 of Story 3.13: the generated script no longer points at
``Pattern("images/...")`` files that never get produced, because the pipeline
fetches screenshots from MinIO, crops each bbox via ``PatternCropper``, uploads
the PNGs back to MinIO and records their storage keys here.

Idempotent raw SQL, matching the repo's migration convention (revisions 010 /
015 / 025). No RLS change — the column inherits the table's existing policies.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: str | None = "025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE test_codes ADD COLUMN IF NOT EXISTS pattern_images JSONB"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE test_codes DROP COLUMN IF EXISTS pattern_images"))
