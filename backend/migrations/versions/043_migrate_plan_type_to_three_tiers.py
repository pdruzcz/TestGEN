"""Migrate plan_type enum to 3-tier model — Epic 7, Story 7.1 (Task 2b)

Revision ID: 043
Revises: 042
Create Date: 2026-08-31

CR#2 (2026-08-28): ``basic|professional`` → ``freemium|basic|premium``.
Mapowanie danych: stary ``basic`` (darmowy) → ``freemium``, stary
``professional`` → ``premium``. PostgreSQL nie pozwala modyfikować
wartości enumu in place — tworzony jest nowy typ, kolumna przełączana
z ``USING CASE``, stary typ usuwany. Idempotentny raw SQL, konwencja repo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _type_exists(conn: sa.engine.Connection, name: str) -> bool:
    return bool(conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": name}).scalar())


def upgrade() -> None:
    conn = op.get_bind()

    if not _type_exists(conn, "plan_type_v3"):
        conn.execute(sa.text("CREATE TYPE plan_type_v3 AS ENUM ('freemium', 'basic', 'premium')"))

    already = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relname = 'tenants' AND a.attname = 'plan' "
            "AND format_type(a.atttypid, NULL) = 'plan_type_v3'"
        )
    ).scalar()
    if already:
        return  # już po migracji (idempotentność)

    conn.execute(sa.text("ALTER TABLE tenants ALTER COLUMN plan DROP DEFAULT"))
    conn.execute(
        sa.text(
            "ALTER TABLE tenants ALTER COLUMN plan TYPE plan_type_v3 "
            "USING CASE plan::text WHEN 'basic' THEN 'freemium' WHEN 'professional' THEN 'premium' "
            "ELSE plan::text END::plan_type_v3"
        )
    )
    conn.execute(sa.text("DROP TYPE plan_type"))
    conn.execute(sa.text("ALTER TYPE plan_type_v3 RENAME TO plan_type"))
    # Nowy plan domyślny: nowy tenant → Freemium (AC2)
    conn.execute(sa.text("ALTER TABLE tenants ALTER COLUMN plan SET DEFAULT 'freemium'::plan_type"))


def downgrade() -> None:
    conn = op.get_bind()

    if not _type_exists(conn, "plan_type_v2"):
        conn.execute(sa.text("CREATE TYPE plan_type_v2 AS ENUM ('basic', 'professional')"))

    conn.execute(
        sa.text(
            "ALTER TABLE tenants ALTER COLUMN plan TYPE plan_type_v2 "
            "USING CASE plan::text WHEN 'freemium' THEN 'basic' WHEN 'basic' THEN 'professional' "
            "WHEN 'premium' THEN 'professional' ELSE 'basic' END::plan_type_v2"
        )
    )
    conn.execute(sa.text("DROP TYPE plan_type"))
    conn.execute(sa.text("ALTER TYPE plan_type_v2 RENAME TO plan_type"))
