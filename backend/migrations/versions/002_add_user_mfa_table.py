"""add_user_mfa_table

Revision ID: 002
Revises: 001
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_mfa",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("totp_secret", sa.String(length=255), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("backup_codes_hash", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_mfa_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_mfa")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_mfa_user_id")),
    )
    op.create_index(op.f("ix_user_mfa_user_id"), "user_mfa", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_user_mfa_user_id"), table_name="user_mfa")
    op.drop_table("user_mfa")
