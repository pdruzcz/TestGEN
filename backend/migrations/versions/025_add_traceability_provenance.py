"""Add provenance columns to traceability_matrix — Epic 3, Story 3-15 closure

Revision ID: 025
Revises: 024
Create Date: 2026-07-13

Adds ``source`` (VARCHAR(20)) and ``confidence`` (DOUBLE PRECISION) to
``traceability_matrix`` so each row records how its source element was derived
— ``source = 'parser'`` for structural XMI/PlantUML, ``source = 'ocr'`` for the
visual/OCR path (with the matching OCR ``confidence``), and both ``NULL`` for
GUI components. Story 3-15 closure, AC3 (provenance consistency post-3-1b).

Idempotent raw SQL, matching the repo's migration convention (revisions 010 /
015). No new enum type and no RLS change — the columns inherit the table's
existing tenant_isolation / admin_bypass policies.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE traceability_matrix ADD COLUMN IF NOT EXISTS source VARCHAR(20)"))
    conn.execute(sa.text("ALTER TABLE traceability_matrix ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE traceability_matrix DROP COLUMN IF EXISTS confidence"))
    conn.execute(sa.text("ALTER TABLE traceability_matrix DROP COLUMN IF EXISTS source"))
