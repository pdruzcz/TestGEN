"""Add CVSS / risk fields to security_findings — Epic 4, Story 4.8

Revision ID: 018
Revises: 017
Create Date: 2026-06-12

The risk engine computes a CVSS v3.1 base score, vector string, repair priority,
effort estimate and an escalation reason per finding. These columns persist that
risk assessment so the dashboard and findings list can sort/filter by it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("security_findings", sa.Column("cvss_score", sa.Float(), nullable=True))
    op.add_column("security_findings", sa.Column("cvss_vector", sa.String(length=100), nullable=True))
    op.add_column("security_findings", sa.Column("priority", sa.Integer(), nullable=True))
    op.add_column("security_findings", sa.Column("effort", sa.String(length=10), nullable=True))
    op.add_column("security_findings", sa.Column("escalation_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("security_findings", "escalation_reason")
    op.drop_column("security_findings", "effort")
    op.drop_column("security_findings", "priority")
    op.drop_column("security_findings", "cvss_vector")
    op.drop_column("security_findings", "cvss_score")
