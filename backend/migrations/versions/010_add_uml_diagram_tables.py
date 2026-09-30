"""Add UML diagram tables — Epic 3: UML & GUI analysis

Revision ID: 010
Revises: 009
Create Date: 2026-06-11

Creates ``uml_diagrams`` and ``parsed_uml_models`` tables plus their enums
(uml_format, uml_diagram_type, uml_diagram_status) to support uploading and
parsing of XMI / PlantUML diagrams.

Uses raw SQL throughout to avoid SQLAlchemy's ``op.create_table`` emitting
unconditional ``CREATE TYPE`` for native PG enums (``create_type=False`` is
ignored in Alembic with asyncpg).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(conn: sa.engine.Connection, name: str, values: str) -> None:
    """Create a PG native enum, silently skip if it already exists."""
    conn.execute(
        sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({values}); EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Enum types (idempotent) ----------------------------------------
    _create_enum(conn, "uml_format", "'xmi', 'plantuml'")
    _create_enum(
        conn,
        "uml_diagram_type",
        "'sequence', 'use_case', 'class', 'activity', 'state_machine'",
    )
    _create_enum(conn, "uml_diagram_status", "'pending', 'parsing', 'completed', 'failed'")

    # --- 2. uml_diagrams ---------------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS uml_diagrams (
                id          UUID PRIMARY KEY,
                tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                filename    VARCHAR(500) NOT NULL,
                storage_key VARCHAR(1000) NOT NULL,
                format      uml_format NOT NULL,
                diagram_type uml_diagram_type,
                raw_content TEXT,
                status      uml_diagram_status NOT NULL DEFAULT 'pending',
                file_size   INTEGER NOT NULL DEFAULT 0,
                mime_type   VARCHAR(100),
                error_message TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_uml_diagrams_tenant_id ON uml_diagrams (tenant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_uml_diagrams_project_id ON uml_diagrams (project_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_uml_diagrams_format ON uml_diagrams (format)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_uml_diagrams_diagram_type ON uml_diagrams (diagram_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_uml_diagrams_status ON uml_diagrams (status)"))

    # --- 3. parsed_uml_models ----------------------------------------------
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS parsed_uml_models (
                id            UUID PRIMARY KEY,
                diagram_id    UUID NOT NULL REFERENCES uml_diagrams(id) ON DELETE CASCADE,
                model_type    uml_diagram_type NOT NULL,
                participants  JSONB,
                elements      JSONB,
                relationships JSONB,
                fragments     JSONB,
                flows         JSONB,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at    TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_parsed_uml_models_diagram_id ON parsed_uml_models (diagram_id)")
    )

    # --- 4. RLS — tenant isolation -----------------------------------------
    conn.execute(sa.text("ALTER TABLE uml_diagrams ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE uml_diagrams FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON uml_diagrams "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE POLICY admin_bypass ON uml_diagrams "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # RLS cleanup
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON uml_diagrams"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON uml_diagrams"))
    conn.execute(sa.text("ALTER TABLE uml_diagrams DISABLE ROW LEVEL SECURITY"))

    # Tables (IF EXISTS — safe for partial states)
    conn.execute(sa.text("DROP TABLE IF EXISTS parsed_uml_models"))
    conn.execute(sa.text("DROP TABLE IF EXISTS uml_diagrams"))

    # Enum types
    conn.execute(sa.text("DROP TYPE IF EXISTS uml_diagram_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS uml_diagram_type"))
    conn.execute(sa.text("DROP TYPE IF EXISTS uml_format"))
