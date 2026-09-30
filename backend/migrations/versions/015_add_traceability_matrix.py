"""Add traceability_matrix — Epic 3, Story 3.15

Revision ID: 015
Revises: 014
Create Date: 2026-06-11

Creates the traceability_matrix table plus its enum (coverage_status). Each row
links a project source element (UML diagram element or GUI component) to the
reconstructed user flow + generated Gherkin feature derived from it, with a
per-element coverage status. Tenant isolation is enforced via RLS, analogous to
``gherkin_features``.

Uses raw SQL throughout to avoid Alembic's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
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
    _create_enum(conn, "coverage_status", "'covered', 'partial', 'uncovered'")

    # --- 2. traceability_matrix --------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS traceability_matrix (
                id                      UUID PRIMARY KEY,
                tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                source_type             VARCHAR(10) NOT NULL,
                source_element_id       UUID NOT NULL,
                source_element_type     VARCHAR(50) NOT NULL,
                source_element_name     VARCHAR(500) NOT NULL,
                source_diagram_id       UUID REFERENCES uml_diagrams(id) ON DELETE SET NULL,
                source_screenshot_id    UUID REFERENCES gui_screenshots(id) ON DELETE SET NULL,
                linked_flow_id          UUID REFERENCES user_flows(id) ON DELETE SET NULL,
                linked_gherkin_id       UUID REFERENCES gherkin_features(id) ON DELETE SET NULL,
                test_case_id            UUID REFERENCES test_cases(id) ON DELETE SET NULL,
                code_reference          VARCHAR(1000),
                code_framework          VARCHAR(50),
                coverage_status         coverage_status NOT NULL DEFAULT 'uncovered',
                created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at              TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_traceability_matrix_tenant_id ON traceability_matrix (tenant_id)")
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_traceability_matrix_project_source ON traceability_matrix (project_id, source_type)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_traceability_matrix_project_coverage ON traceability_matrix (project_id, coverage_status)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_traceability_matrix_source_element_id ON traceability_matrix (source_element_id)"
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_traceability_matrix_test_case_id ON traceability_matrix (test_case_id)")
    )

    # --- 3. RLS — tenant isolation -----------------------------------------
    conn.execute(sa.text("ALTER TABLE traceability_matrix ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE traceability_matrix FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON traceability_matrix "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON traceability_matrix "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON traceability_matrix"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON traceability_matrix"))
    conn.execute(sa.text("ALTER TABLE traceability_matrix DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS traceability_matrix"))
    conn.execute(sa.text("DROP TYPE IF EXISTS coverage_status"))
