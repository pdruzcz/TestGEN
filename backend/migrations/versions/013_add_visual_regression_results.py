"""Add visual_regression_results — Epic 3, Story 3.10

Revision ID: 013
Revises: 012
Create Date: 2026-06-11

Creates the visual_regression_results table plus its enum (comparison_status) to
persist comparisons between two GUI screenshots (baseline vs comparison): the
pixel-diff percentage, per-component semantic delta, classified changes and an
optional diff-image key. Tenant isolation is enforced via RLS, analogous to
``gui_screenshots``.

Uses raw SQL throughout to avoid Alembic's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
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
    _create_enum(conn, "comparison_status", "'match', 'minor_diff', 'major_diff', 'error'")

    # --- 2. visual_regression_results --------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS visual_regression_results (
                id                      UUID PRIMARY KEY,
                tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                baseline_screenshot_id  UUID NOT NULL REFERENCES gui_screenshots(id) ON DELETE CASCADE,
                comparison_screenshot_id UUID NOT NULL REFERENCES gui_screenshots(id) ON DELETE CASCADE,
                pixel_diff_percentage   FLOAT NOT NULL DEFAULT 0,
                semantic_diff           JSONB,
                changes                 JSONB,
                diff_image_key          VARCHAR(1000),
                status                  comparison_status NOT NULL DEFAULT 'match',
                warnings                JSONB,
                created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at              TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_visual_regression_results_tenant_id ON visual_regression_results (tenant_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_visual_regression_results_project_id ON visual_regression_results (project_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_visual_regression_results_baseline_screenshot_id"
            " ON visual_regression_results (baseline_screenshot_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_visual_regression_results_comparison_screenshot_id"
            " ON visual_regression_results (comparison_screenshot_id)"
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_visual_regression_results_status ON visual_regression_results (status)")
    )

    # --- 3. RLS — tenant isolation -----------------------------------------
    conn.execute(sa.text("ALTER TABLE visual_regression_results ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE visual_regression_results FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON visual_regression_results "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON visual_regression_results "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON visual_regression_results"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON visual_regression_results"))
    conn.execute(sa.text("ALTER TABLE visual_regression_results DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS visual_regression_results"))
    conn.execute(sa.text("DROP TYPE IF EXISTS comparison_status"))
