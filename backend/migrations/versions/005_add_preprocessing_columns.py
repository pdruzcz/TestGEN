"""add_preprocessing_columns_to_source_files

Revision ID: 005
Revises: 04765b21814a
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "04765b21814a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_files",
        sa.Column(
            "requires_manual_classification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "source_files",
        sa.Column(
            "loc_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        op.f("ix_source_files_detected_language"),
        "source_files",
        ["detected_language"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_source_files_detected_language"), table_name="source_files")
    op.drop_column("source_files", "loc_count")
    op.drop_column("source_files", "requires_manual_classification")
