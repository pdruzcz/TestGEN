"""Add gherkin_features — Epic 3, Story 3.11

Revision ID: 014
Revises: 013
Create Date: 2026-06-11

Creates the gherkin_features table plus its enum (gherkin_status) to persist
Gherkin/BDD .feature files generated from reconstructed user flows: the
structured scenarios, the rendered raw feature text, the engine mode and
(non-blocking) validation warnings. Tenant isolation is enforced via RLS,
analogous to ``user_flows``.

Uses raw SQL throughout to avoid Alembic's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(conn: sa.engine.Connection, name: str, values: str) -> None:
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({values}); EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Enum type (idempotent) -----------------------------------------
    _create_enum(conn, "gherkin_status", "'generated', 'validated', 'approved'")

    # --- 2. gherkin_features -----------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS gherkin_features (
                id                  UUID PRIMARY KEY,
                tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                source_flow_id      UUID REFERENCES user_flows(id) ON DELETE SET NULL,
                feature_name        VARCHAR(500) NOT NULL,
                feature_description TEXT,
                scenarios           JSONB,
                raw_feature         TEXT NOT NULL DEFAULT '',
                engine_mode         VARCHAR(20) NOT NULL DEFAULT 'native',
                validation_warnings JSONB,
                status              gherkin_status NOT NULL DEFAULT 'generated',
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at          TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gherkin_features_tenant_id ON gherkin_features (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gherkin_features_project_id ON gherkin_features (project_id)"))
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_gherkin_features_source_flow_id ON gherkin_features (source_flow_id)")
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gherkin_features_status ON gherkin_features (status)"))

    # --- 3. RLS — tenant isolation -----------------------------------------
    conn.execute(sa.text("ALTER TABLE gherkin_features ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE gherkin_features FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON gherkin_features "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON gherkin_features "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON gherkin_features"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON gherkin_features"))
    conn.execute(sa.text("ALTER TABLE gherkin_features DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS gherkin_features"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gherkin_status"))
