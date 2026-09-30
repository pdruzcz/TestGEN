"""Add documentation support to source_files

Revision ID: 009
Revises: 008
Create Date: 2026-06-05

Adds file_category, doc_format, and page_count columns to source_files table
to support Epic 2: Documentation analysis and discrepancy detection.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create file_category enum
    file_category = sa.Enum(
        "code",
        "documentation",
        "uml",
        "gui",
        name="file_category",
        native_enum=True,
    )
    file_category.create(conn, checkfirst=True)

    # Create document_format enum
    document_format = sa.Enum(
        "pdf",
        "docx",
        "md",
        "html",
        "txt",
        name="document_format",
        native_enum=True,
    )
    document_format.create(conn, checkfirst=True)

    # Add columns to source_files
    op.add_column(
        "source_files",
        sa.Column("file_category", file_category, nullable=False, server_default="code"),
    )
    op.create_index("ix_source_files_file_category", "source_files", ["file_category"])

    op.add_column(
        "source_files",
        sa.Column("doc_format", document_format, nullable=True),
    )

    op.add_column(
        "source_files",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop columns
    op.drop_column("source_files", "page_count")
    op.drop_column("source_files", "doc_format")
    op.drop_column("source_files", "file_category")

    # Drop enums
    conn.execute(sa.text("DROP TYPE IF EXISTS file_category"))
    conn.execute(sa.text("DROP TYPE IF EXISTS document_format"))
