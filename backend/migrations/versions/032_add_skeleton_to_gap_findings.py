"""Add skeleton_code + skeleton_language to gap_findings — Epic 5, Story 5.6

Revision ID: 032
Revises: 031
Create Date: 2026-07-15

Adds two nullable columns to ``gap_findings``:
- ``skeleton_code`` (Text) — generated skeleton source
- ``skeleton_language`` (String 20) — e.g. python, typescript, java, csharp
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: str | None = "031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gap_findings",
        sa.Column("skeleton_code", sa.Text(), nullable=True),
    )
    op.add_column(
        "gap_findings",
        sa.Column("skeleton_language", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gap_findings", "skeleton_language")
    op.drop_column("gap_findings", "skeleton_code")
