"""Setup test database: run migrations and create test-only roles.

Usage:
    python scripts/setup_test_db.py

Requires superuser connection (DATABASE_ADMIN_URL) to create roles.
Falls back to DATABASE_URL for migrations only.

This script is idempotent — safe to run multiple times.
"""

import asyncio
import os
import subprocess
import sys

import asyncpg


async def setup_test_roles() -> None:
    """Create test-only database roles (requires superuser)."""
    admin_url = os.environ.get(
        "DATABASE_ADMIN_URL",
        "postgresql://postgres:postgres@localhost:5432/testgen",
    )
    # --- Ensure app role has BYPASSRLS (required by architecture) ---
    try:
        conn = await asyncpg.connect(admin_url)
        try:
            # Grant BYPASSRLS to app role
            await conn.execute("ALTER ROLE testgen BYPASSRLS")
            print("✓ testgen role: BYPASSRLS granted")

            # Create RLS test role (NOBYPASSRLS) for integration tests
            exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", "testgen_rls_test")
            if not exists:
                await conn.execute("CREATE ROLE testgen_rls_test LOGIN PASSWORD 'testgen_rls_test' NOBYPASSRLS")
                print("✓ testgen_rls_test role: created")
            else:
                print("✓ testgen_rls_test role: already exists")

            # Grant table access to test role
            await conn.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO testgen_rls_test")
            await conn.execute("GRANT USAGE ON SCHEMA public TO testgen_rls_test")
            await conn.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO testgen_rls_test")
            print("✓ testgen_rls_test: table access granted")
        finally:
            await conn.close()
    except asyncpg.InvalidPasswordError:
        print(
            "⚠ Cannot connect as superuser — skipping role setup.\n"
            "  Set DATABASE_ADMIN_URL=postgresql://postgres:<password>@localhost:5432/testgen\n"
            "  Or create roles manually:\n"
            "    ALTER ROLE testgen BYPASSRLS;\n"
            "    CREATE ROLE testgen_rls_test LOGIN PASSWORD 'testgen_rls_test' NOBYPASSRLS;\n"
            "    GRANT ALL ON ALL TABLES IN SCHEMA public TO testgen_rls_test;\n"
            "    GRANT USAGE ON SCHEMA public TO testgen_rls_test;"
        )
    except Exception as e:
        print(f"⚠ Role setup failed: {e}")
        print("  RLS integration tests may not work without testgen_rls_test role.")


def run_migrations() -> None:
    """Run Alembic migrations."""
    print("Running Alembic migrations...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("✓ Migrations applied successfully")
    else:
        print(f"✗ Migration failed:\n{result.stderr}")
        sys.exit(1)


async def main() -> None:
    print("=== TestGEN Test Database Setup ===\n")
    run_migrations()
    print()
    await setup_test_roles()
    print("\n=== Setup complete ===")


if __name__ == "__main__":
    asyncio.run(main())
