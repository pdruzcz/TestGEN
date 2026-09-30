"""Widen security_findings.owasp_category — Epic 4 bugfix

Revision ID: 023
Revises: 022
Create Date: 2026-07-09

Fixes a scan-failure where the full OWASP Top 10:2021 category strings
(e.g. ``A07:2021-Identification and Authentication Failures`` — 51 chars)
overflowed the original ``VARCHAR(50)`` column. The overflow aborted the whole
INSERT transaction, so SAST scans crashed with a DB error and (combined with
the error-handling fix in ``security_tasks``) reported no findings. The model
column is widened to ``VARCHAR(100)`` (matches ``app.models.security_finding``).

Uses raw SQL to control native PG DDL, matching revision 022.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE security_findings ALTER COLUMN owasp_category TYPE VARCHAR(100)"))


def downgrade() -> None:
    # Narrowing back to VARCHAR(50) only succeeds if no stored value exceeds 50
    # chars; safe to run only on a fresh/cleaned table.
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE security_findings ALTER COLUMN owasp_category TYPE VARCHAR(50)"))
