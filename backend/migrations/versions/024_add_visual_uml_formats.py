"""Add visual UML formats + parsed-model source/confidence — Story 3.1b

Revision ID: 024
Revises: 023
Create Date: 2026-06-23

Extends Tier 1 (XMI/PlantUML) with Tier 2 visual formats:

* adds ``svg`` / ``pdf`` / ``raster`` values to the ``uml_format`` enum so UML
  diagrams can be uploaded as SVG, PDF or raster images (PNG/JPEG);
* adds a ``uml_model_source`` enum (``parser`` / ``ocr``) plus ``source`` and
* ``confidence`` columns to ``parsed_uml_models`` so OCR-inferred models are
  marked ``source = ocr`` with a confidence score (Story 3.1b, AC5).

Uses raw SQL throughout (matching revision 010) to control native PG enum DDL.

Renumbered 022 → 024 after origin landed Story 5.1's ``022_add_gap_findings_table``;
migration content is unchanged, only ``revision``/``down_revision`` were bumped to
keep the chain linear (022 gap → 023 widen_owasp → 024 visual).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(conn: sa.engine.Connection, name: str, values: str) -> None:
    """Create a PG native enum, silently skip if it already exists."""
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({values}); EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
        )
    )


def _add_enum_value(conn: sa.engine.Connection, type_name: str, value: str) -> None:
    """Idempotently add a value to an existing PG native enum."""
    conn.execute(sa.text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Extend uml_format with visual formats (Tier 2) ---------------
    _add_enum_value(conn, "uml_format", "svg")
    _add_enum_value(conn, "uml_format", "pdf")
    _add_enum_value(conn, "uml_format", "raster")

    # --- 2. New uml_model_source enum + parsed-model provenance columns ---
    _create_enum(conn, "uml_model_source", "'parser', 'ocr'")
    conn.execute(
        sa.text(
            "ALTER TABLE parsed_uml_models ADD COLUMN IF NOT EXISTS source uml_model_source NOT NULL DEFAULT 'parser'"
        )
    )
    conn.execute(sa.text("ALTER TABLE parsed_uml_models ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE parsed_uml_models DROP COLUMN IF EXISTS confidence"))
    conn.execute(sa.text("ALTER TABLE parsed_uml_models DROP COLUMN IF EXISTS source"))
    conn.execute(sa.text("DROP TYPE IF EXISTS uml_model_source"))
    # Removing individual enum values is not supported by PostgreSQL; the
    # svg/pdf/raster values remain on uml_format (harmless for Tier 1 paths).
