"""GUI DOM source columns + ``gui_dom`` file category — Story 1.51-zakańczenie (FR69)

Revision ID: 039
Revises: 038
Create Date: 2026-07-29

Adds the data model for HTML/DOM-as-GUI-source analysis (Story 1.51-zakańczenie,
Part A) so DOM-extracted components can attach to a ``GUIAnalysisResult`` that is
*not* backed by a screenshot:

* ``gui_analysis_results.source_type`` — native enum ``gui_analysis_source_type``
  ('screenshot' | 'dom'), default 'screenshot' (backfills every existing row).
* ``gui_analysis_results.source_file_id`` — nullable FK to ``source_files`` with
  ``ON DELETE SET NULL`` (the analysis history survives source cleanup).
* ``gui_analysis_results.version_label`` — optional tag for before/after healing
  selection (Story 1.51-zakańczenie, Part B).
* ``gui_analysis_results.screenshot_id`` — now nullable (DOM analyses carry none).
* ``file_category`` enum gains ``gui_dom`` so DOM HTML is routed to the GUI/DOM
  channel and never to the E2 documentation parser (origin-based routing, A1).

Raw-SQL convention mirrors revisions 010 / 030 / 036 / 038. ``ADD VALUE IF NOT
EXISTS`` is idempotent and safe in-transaction on PostgreSQL >= 12 (asyncpg).
The ``attributes`` JSONB column on ``gui_components`` already exists (Story 3.8)
and is unchanged — DOM extraction simply populates it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "gui_analysis_results"
SOURCE_ENUM = "gui_analysis_source_type"


def upgrade() -> None:
    """Create the source-type enum, add DOM columns, relax screenshot_id."""
    op.execute(f"CREATE TYPE {SOURCE_ENUM} AS ENUM ('screenshot', 'dom')")

    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN source_type {SOURCE_ENUM} NOT NULL DEFAULT 'screenshot'")
    op.add_column(TABLE, sa.Column("source_file_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_gui_analysis_results_source_file_id",
        TABLE,
        "source_files",
        ["source_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(TABLE, sa.Column("version_label", sa.String(100), nullable=True))
    op.alter_column(TABLE, "screenshot_id", nullable=True)

    op.create_index(f"ix_{TABLE}_source_type", TABLE, ["source_type"])
    op.create_index(f"ix_{TABLE}_source_file_id", TABLE, ["source_file_id"])

    op.execute("ALTER TYPE file_category ADD VALUE IF NOT EXISTS 'gui_dom'")


def downgrade() -> None:
    """Reverse the additive DOM columns (best-effort).

    ``screenshot_id`` is left nullable on downgrade: forcing ``NOT NULL`` back
    would fail if any DOM-sourced analysis rows still exist, so it is not
    restored. ``file_category.gui_dom`` cannot be removed from a PG enum
    in-place (same limitation as revision 038) and is left in place.
    """
    op.drop_index(f"ix_{TABLE}_source_file_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_source_type", table_name=TABLE)
    op.drop_column(TABLE, "version_label")
    op.drop_constraint("fk_gui_analysis_results_source_file_id", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "source_file_id")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN source_type")
    op.execute(f"DROP TYPE {SOURCE_ENUM}")
