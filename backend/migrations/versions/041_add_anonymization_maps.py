"""Add anonymization_maps table — Epic 1, Story 1.54 (FR72)

Revision ID: 041
Revises: 040
Create Date: 2026-08-14

Creates ``anonymization_maps`` — the encrypted placeholder→original mapping
of one anonymization run (tokenize before LLM, detokenize after).  The
``encrypted_map`` blob is AES-256-GCM ciphertext; only counts (``token_count``,
``secret_count``) are stored in the clear.  Tenant isolation via RLS,
mirroring the healing tables (revision 036).  Idempotent raw SQL, matching
the repo's migration convention.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: str | None = "040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(conn: sa.engine.Connection, table: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
    )
    conn.execute(sa.text(f"DROP POLICY IF EXISTS admin_bypass ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY admin_bypass ON {table} "
            "USING (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid) "
            "WITH CHECK (current_setting('app.current_tenant', true)::uuid = '00000000-0000-0000-0000-000000000000'::uuid)"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS anonymization_maps (
                id            UUID PRIMARY KEY,
                tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                analysis_id   UUID REFERENCES analysis_results(id) ON DELETE CASCADE,
                encrypted_map BYTEA NOT NULL,
                token_count   INTEGER NOT NULL DEFAULT 0,
                secret_count  INTEGER NOT NULL DEFAULT 0,
                expires_at    TIMESTAMPTZ NOT NULL,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at    TIMESTAMPTZ
            )
            """
        )
    )

    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_anonymization_maps_tenant_id ON anonymization_maps (tenant_id)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_anonymization_maps_project_id ON anonymization_maps (project_id)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_anonymization_maps_analysis_id ON anonymization_maps (analysis_id)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_anonymization_maps_expires_at ON anonymization_maps (expires_at)")
    )

    _enable_rls(conn, "anonymization_maps")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS admin_bypass ON anonymization_maps"))
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON anonymization_maps"))
    conn.execute(sa.text("ALTER TABLE anonymization_maps DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DROP TABLE IF EXISTS anonymization_maps"))
