"""Add metadata column to flow_steps — Epic 3, Story 3-11-domknięcie (AC1)

Revision ID: 028
Revises: 027
Create Date: 2026-07-15

Adds ``metadata`` (JSONB) to ``flow_steps`` so each reconstructed step can carry
UML relation / decision semantics consumed by the Gherkin mapper:

- ``relation_type`` — ``include`` / ``extend`` / ``none`` (use-case relationships),
- ``parameters``  — list of parameter values backing a ``Scenario Outline``
  ``Examples`` table (derived from an ``extend`` guard / preconditions),
- ``branch_label`` — guard of an activity ``DECISION`` branch (lifted out of the
  flattened ``[guard]`` ``expected_result`` text).

This closes AC-1: the reconstructed ``FlowStep`` now *carries* the relation /
decision metadata that the deterministic Gherkin mapper turns into a real
``Background`` (``include``), ``Scenario Outline`` + ``Examples`` (``extend``)
and per-branch ``Scenario`` blocks (decisions). The Python attribute is aliased
to ``meta`` (``mapped_column("metadata", ...)``) because ``metadata`` is reserved
on the declarative base.

Idempotent raw SQL, matching the repo's migration convention (revisions 011 /
026). No RLS change — the column inherits the table's existing policies.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: str | None = "026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE flow_steps ADD COLUMN IF NOT EXISTS metadata JSONB"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE flow_steps DROP COLUMN IF EXISTS metadata"))
