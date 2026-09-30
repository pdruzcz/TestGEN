"""Add source column to gap_findings for dual-path tracking — Epic 5, Story 5.10.

Revision ID: 035
Revises: 034
"""

from alembic import op
import sqlalchemy as sa

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gap_findings",
        sa.Column("source", sa.String(10), server_default="native", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("gap_findings", "source")
