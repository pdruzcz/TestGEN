"""Add cve_update_logs table — Epic 4, Story 4.12

Revision ID: 021
Revises: 020
Create Date: 2026-06-12

Persists one row per CVE auto-update pipeline run so the admin dashboard can show
the last update time, new/updated CVE counts, per-source status and error log.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cve_update_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_projects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sources_status", JSONB(), nullable=True),
        sa.Column("errors", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cve_update_logs")),
    )


def downgrade() -> None:
    op.drop_table("cve_update_logs")
