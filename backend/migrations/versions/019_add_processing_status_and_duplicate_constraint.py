"""Add processing_status, error_message, and sha256 unique constraint

Revision ID: 019
Revises: 018
Create Date: 2026-06-12

Adds:
- file_processing_status enum and column (universal status for all source files)
- error_message text column
- unique constraint on (project_id, sha256_hash) for duplicate detection
- Cleans up existing duplicate hashes before adding constraint

Uses raw SQL for enum creation to avoid Alembic's ``op.add_column`` emitting
unconditional ``CREATE TYPE`` for native PG enums.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create file_processing_status enum (idempotent)
    conn.execute(
        sa.text(
            "DO $$ BEGIN CREATE TYPE file_processing_status AS ENUM ('uploaded', 'processing', 'ready', 'failed');"
            " EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
        )
    )

    # 2. Add processing_status column (default 'uploaded' for existing rows)
    conn.execute(
        sa.text(
            "ALTER TABLE source_files"
            " ADD COLUMN IF NOT EXISTS processing_status file_processing_status NOT NULL DEFAULT 'uploaded'"
        )
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_source_files_processing_status ON source_files (processing_status)")
    )

    # 3. Add error_message column
    conn.execute(sa.text("ALTER TABLE source_files ADD COLUMN IF NOT EXISTS error_message TEXT"))

    # 4. Clean up duplicate hashes before adding unique constraint.
    #    Keep the oldest row per (project_id, sha256_hash), mark newer ones
    #    as cleaned up so they won't conflict.
    conn.execute(
        sa.text("""
        WITH duplicates AS (
            SELECT id, project_id, sha256_hash,
                   ROW_NUMBER() OVER (
                       PARTITION BY project_id, sha256_hash
                       ORDER BY created_at ASC
                   ) AS rn
            FROM source_files
            WHERE is_cleaned_up = false
        )
        UPDATE source_files
        SET is_cleaned_up = true
        FROM duplicates
        WHERE source_files.id = duplicates.id
          AND duplicates.rn > 1
    """)
    )

    # 5. Add unique constraint on (project_id, sha256_hash) — only for
    #    non-cleaned-up rows we use a partial unique index so that soft-deleted
    #    files don't block re-uploads of the same content.
    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_source_files_project_hash "
            "ON source_files (project_id, sha256_hash) "
            "WHERE is_cleaned_up = false"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_source_files_project_hash"))
    conn.execute(sa.text("ALTER TABLE source_files DROP COLUMN IF EXISTS error_message"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_source_files_processing_status"))
    conn.execute(sa.text("ALTER TABLE source_files DROP COLUMN IF EXISTS processing_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS file_processing_status"))
