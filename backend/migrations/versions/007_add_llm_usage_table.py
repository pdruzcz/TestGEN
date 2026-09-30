"""Add llm_usage table for cost tracking

Revision ID: 007
Revises: 04765b21814a
Create Date: 2026-05-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False),
        sa.Column("tokens_output", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", postgresql.NUMERIC(precision=10, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("fallback_to_native", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")
        ),
    )
    op.create_index("ix_llm_usage_tenant_created", "llm_usage", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_tenant_created", table_name="llm_usage")
    op.drop_table("llm_usage")
