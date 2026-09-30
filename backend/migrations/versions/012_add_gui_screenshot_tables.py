"""Add gui_screenshots, gui_analysis_results, gui_components — Epic 3, Story 3.8

Revision ID: 012
Revises: 011
Create Date: 2026-06-11

Creates the GUI analysis tables plus their enums (gui_analysis_status,
gui_component_type) to persist uploaded screenshots and their OCR + Computer
Vision analysis. Tenant isolation on ``gui_screenshots`` is enforced via RLS,
analogous to ``uml_diagrams``.

Uses raw SQL throughout to avoid Alembic's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
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
    _create_enum(conn, "gui_analysis_status", "'pending', 'processing', 'completed', 'failed'")
    _create_enum(
        conn,
        "gui_component_type",
        "'button', 'input', 'dropdown', 'checkbox', 'radio',"
        " 'menu', 'link', 'table', 'form', 'modal', 'tab', 'unknown'",
    )

    # --- 2. gui_screenshots ------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS gui_screenshots (
                id              UUID PRIMARY KEY,
                tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                filename        VARCHAR(500) NOT NULL,
                storage_key     VARCHAR(1000) NOT NULL,
                screen_sequence INTEGER NOT NULL DEFAULT 0,
                status          gui_analysis_status NOT NULL DEFAULT 'pending',
                file_size       INTEGER NOT NULL DEFAULT 0,
                mime_type       VARCHAR(100),
                error_message   TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gui_screenshots_tenant_id ON gui_screenshots (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gui_screenshots_project_id ON gui_screenshots (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gui_screenshots_status ON gui_screenshots (status)"))

    # --- 3. gui_analysis_results -------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS gui_analysis_results (
                id                  UUID PRIMARY KEY,
                screenshot_id       UUID NOT NULL REFERENCES gui_screenshots(id) ON DELETE CASCADE,
                ocr_text_blocks     JSONB,
                layout_tree         JSONB,
                warnings            JSONB,
                processing_time_ms  INTEGER NOT NULL DEFAULT 0,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at          TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_gui_analysis_results_screenshot_id ON gui_analysis_results (screenshot_id)"
        )
    )

    # --- 4. gui_components -------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS gui_components (
                id              UUID PRIMARY KEY,
                analysis_id     UUID NOT NULL REFERENCES gui_analysis_results(id) ON DELETE CASCADE,
                sequence        INTEGER NOT NULL DEFAULT 0,
                component_type  gui_component_type NOT NULL,
                label           VARCHAR(500),
                bbox            JSONB,
                confidence      FLOAT NOT NULL DEFAULT 0,
                attributes      JSONB,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gui_components_analysis_id ON gui_components (analysis_id)"))
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_gui_components_component_type ON gui_components (component_type)")
    )

    # --- 5. RLS — tenant isolation -----------------------------------------
    conn.execute(sa.text("ALTER TABLE gui_screenshots ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE gui_screenshots FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON gui_screenshots "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON gui_screenshots "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON gui_screenshots"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON gui_screenshots"))
    conn.execute(sa.text("ALTER TABLE gui_screenshots DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS gui_components"))
    conn.execute(sa.text("DROP TABLE IF EXISTS gui_analysis_results"))
    conn.execute(sa.text("DROP TABLE IF EXISTS gui_screenshots"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gui_component_type"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gui_analysis_status"))
