"""Add cve_database table and security_scans.scan_metadata — Epic 4, Story 4.4

Revision ID: 017
Revises: 016
Create Date: 2026-06-12

``cve_database`` is a shared (non-tenant) cache of CVE entries pulled from
NVD/OSV/Snyk by the dependency scanner. ``security_scans.scan_metadata`` holds
per-scan payloads such as the generated SBOM.

Uses raw SQL for table creation to avoid Alembic's ``op.create_table``
emitting unconditional ``CREATE TYPE`` for the ``severity`` enum (created in
migration 016).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add scan_metadata column
    conn.execute(sa.text("ALTER TABLE security_scans ADD COLUMN IF NOT EXISTS scan_metadata JSONB"))

    # cve_database — reuses severity enum from migration 016 (already exists).
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS cve_database (
                id                UUID PRIMARY KEY,
                cve_id            VARCHAR(40) NOT NULL,
                package_name      VARCHAR(255) NOT NULL,
                ecosystem         VARCHAR(40) NOT NULL,
                cvss_score        FLOAT NOT NULL DEFAULT 0,
                severity          severity NOT NULL,
                description       TEXT NOT NULL DEFAULT '',
                affected_versions VARCHAR(500),
                fixed_version     VARCHAR(100),
                published_date    TIMESTAMPTZ,
                source_db         VARCHAR(20) NOT NULL DEFAULT 'osv',
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at        TIMESTAMPTZ
            )
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cve_database_cve_id ON cve_database (cve_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cve_database_package_name ON cve_database (package_name)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cve_database_ecosystem ON cve_database (ecosystem)"))

    # Unique constraint — can't use IF NOT EXISTS, wrap in DO block
    conn.execute(
        sa.text(
            "DO $$ BEGIN"
            " ALTER TABLE cve_database ADD CONSTRAINT uq_cve_database_cve_package UNIQUE (cve_id, package_name);"
            " EXCEPTION WHEN duplicate_object THEN NULL;"
            " END $$"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS cve_database"))
    conn.execute(sa.text("ALTER TABLE security_scans DROP COLUMN IF EXISTS scan_metadata"))
