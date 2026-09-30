"""Add PoC fields to security_findings — Epic 4, Story 4.10

Revision ID: 020
Revises: 019
Create Date: 2026-06-12

The PoC generator produces a safe, non-destructive proof-of-concept per finding:
a payload, reproduction steps and the expected effect. These columns persist that
demonstration so the PoC viewer can render it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("security_findings", sa.Column("poc_payload", sa.Text(), nullable=True))
    op.add_column("security_findings", sa.Column("poc_steps", JSONB(), nullable=True))
    op.add_column("security_findings", sa.Column("poc_expected_effect", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("security_findings", "poc_expected_effect")
    op.drop_column("security_findings", "poc_steps")
    op.drop_column("security_findings", "poc_payload")
