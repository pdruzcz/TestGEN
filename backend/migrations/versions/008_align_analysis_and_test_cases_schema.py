"""Align analysis_results and test_cases schema with models

Revision ID: 008
Revises: 007
Create Date: 2026-06-03

Adds missing columns to analysis_results and test_cases tables that were
added to SQLAlchemy models after migration 006.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── analysis_results: add missing columns ──────────────────────────────

    op.add_column(
        "analysis_results",
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_analysis_results_source_file_id", "analysis_results", ["source_file_id"])

    op.add_column(
        "analysis_results",
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.add_column(
        "analysis_results",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Extend analysis_status enum with missing values
    conn.execute(sa.text("ALTER TYPE analysis_status ADD VALUE IF NOT EXISTS 'timeout'"))
    conn.execute(sa.text("ALTER TYPE analysis_status ADD VALUE IF NOT EXISTS 'partial_failure'"))

    # ── test_cases: add missing columns ────────────────────────────────────

    op.add_column(
        "test_cases",
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_test_cases_source_file_id", "test_cases", ["source_file_id"])

    op.add_column("test_cases", sa.Column("framework", sa.String(50), nullable=True))
    op.add_column("test_cases", sa.Column("language", sa.String(50), nullable=True))

    # Create generation_engine enum and column
    generation_engine = sa.Enum("native", "llm", "hybrid", name="generation_engine", native_enum=True)
    generation_engine.create(conn, checkfirst=True)
    op.add_column(
        "test_cases",
        sa.Column("generation_engine", generation_engine, nullable=False, server_default="native"),
    )

    op.add_column("test_cases", sa.Column("source_function", sa.String(255), nullable=True))
    op.add_column("test_cases", sa.Column("source_class", sa.String(255), nullable=True))
    op.add_column("test_cases", sa.Column("source_endpoint", sa.String(255), nullable=True))

    op.add_column("test_cases", sa.Column("test_code", sa.Text(), nullable=True))
    op.add_column("test_cases", sa.Column("imports", sa.Text(), nullable=True))
    op.add_column("test_cases", sa.Column("setup_code", sa.Text(), nullable=True))
    op.add_column("test_cases", sa.Column("teardown_code", sa.Text(), nullable=True))

    op.add_column("test_cases", sa.Column("test_data", sa.dialects.postgresql.JSONB(), nullable=True))

    op.add_column("test_cases", sa.Column("scenario_description", sa.Text(), nullable=True))
    op.add_column("test_cases", sa.Column("scenario_rationale", sa.Text(), nullable=True))
    op.add_column("test_cases", sa.Column("edge_case_description", sa.Text(), nullable=True))
    op.add_column("test_cases", sa.Column("confidence_score", sa.Float(), nullable=True))

    # Create test_case_status enum and column
    test_case_status = sa.Enum(
        "draft",
        "ready",
        "passed",
        "failed",
        "skipped",
        "disabled",
        name="test_case_status",
        native_enum=True,
    )
    test_case_status.create(conn, checkfirst=True)
    op.add_column(
        "test_cases",
        sa.Column("status", test_case_status, nullable=False, server_default="draft"),
    )

    # Execution tracking columns
    op.add_column("test_cases", sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("test_cases", sa.Column("last_execution_result", sa.dialects.postgresql.JSONB(), nullable=True))
    op.add_column("test_cases", sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("test_cases", sa.Column("pass_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("test_cases", sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"))

    # Editing and review
    op.add_column("test_cases", sa.Column("is_edited", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("test_cases", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "test_cases",
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )

    # Tags and meta
    op.add_column("test_cases", sa.Column("tags", sa.dialects.postgresql.JSONB(), nullable=True))
    op.add_column("test_cases", sa.Column("meta", sa.dialects.postgresql.JSONB(), nullable=True))

    # Extend test_case_priority enum with 'critical'
    conn.execute(sa.text("ALTER TYPE test_case_priority ADD VALUE IF NOT EXISTS 'critical'"))

    # Extend test_case_type enum with missing values
    for value in ("performance", "positive", "negative", "boundary", "accessibility", "semantic"):
        conn.execute(sa.text(f"ALTER TYPE test_case_type ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    conn = op.get_bind()

    # test_cases: drop columns in reverse order
    for col in (
        "meta",
        "tags",
        "reviewed_by",
        "reviewed_at",
        "is_edited",
        "fail_count",
        "pass_count",
        "execution_count",
        "last_execution_result",
        "last_executed_at",
        "status",
        "confidence_score",
        "edge_case_description",
        "scenario_rationale",
        "scenario_description",
        "test_data",
        "teardown_code",
        "setup_code",
        "imports",
        "test_code",
        "source_endpoint",
        "source_class",
        "source_function",
        "generation_engine",
        "language",
        "framework",
        "source_file_id",
    ):
        op.drop_column("test_cases", col)

    conn.execute(sa.text("DROP TYPE IF EXISTS generation_engine"))
    conn.execute(sa.text("DROP TYPE IF EXISTS test_case_status"))

    # analysis_results: drop columns in reverse order
    for col in ("completed_at", "error_message", "source_file_id"):
        op.drop_column("analysis_results", col)
