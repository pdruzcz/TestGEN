"""Add user_flows and flow_steps tables — Epic 3, Story 3.7: cross-diagram analysis

Revision ID: 011
Revises: 010
Create Date: 2026-06-11

Creates ``user_flows`` and ``flow_steps`` tables plus their enums
(flow_source_type, flow_status) to persist user flows reconstructed by
``CrossDiagramAnalyzer`` from parsed UML diagrams. Tenant isolation on
``user_flows`` is enforced via RLS, analogous to ``uml_diagrams``.

Uses raw SQL throughout to avoid Alembic's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
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

    # --- 1. Enum types (idempotent) ----------------------------------------
    _create_enum(conn, "flow_source_type", "'uml', 'gui', 'uml_and_gui'")
    _create_enum(conn, "flow_status", "'draft', 'validated', 'tests_generated'")

    # --- 2. user_flows -----------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS user_flows (
                id          UUID PRIMARY KEY,
                tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                source_type flow_source_type NOT NULL DEFAULT 'uml',
                source_ids  JSONB,
                name        VARCHAR(500) NOT NULL,
                steps       JSONB,
                status      flow_status NOT NULL DEFAULT 'draft',
                warnings    JSONB,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_flows_tenant_id ON user_flows (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_flows_project_id ON user_flows (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_flows_source_type ON user_flows (source_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_flows_status ON user_flows (status)"))

    # --- 3. flow_steps -----------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS flow_steps (
                id                  UUID PRIMARY KEY,
                flow_id             UUID NOT NULL REFERENCES user_flows(id) ON DELETE CASCADE,
                sequence            INTEGER NOT NULL DEFAULT 0,
                action              TEXT NOT NULL,
                actor               VARCHAR(255),
                target_element      VARCHAR(500),
                expected_result     TEXT,
                source_diagram_id   UUID REFERENCES uml_diagrams(id) ON DELETE SET NULL,
                source_screenshot_id UUID,
                source              VARCHAR(20) NOT NULL DEFAULT 'native',
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at          TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_flow_steps_flow_id ON flow_steps (flow_id)"))

    # --- 4. RLS — tenant isolation -----------------------------------------
    conn.execute(sa.text("ALTER TABLE user_flows ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE user_flows FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON user_flows "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON user_flows "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON user_flows"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON user_flows"))
    conn.execute(sa.text("ALTER TABLE user_flows DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS flow_steps"))
    conn.execute(sa.text("DROP TABLE IF EXISTS user_flows"))
    conn.execute(sa.text("DROP TYPE IF EXISTS flow_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS flow_source_type"))
