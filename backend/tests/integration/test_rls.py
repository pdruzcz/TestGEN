"""Integration tests for Row Level Security (RLS) — real PostgreSQL database.

These tests verify actual PostgreSQL RLS policies enforce tenant isolation
on SELECT, INSERT, UPDATE, and DELETE operations on user_tenants.

Each test runs inside a transaction that is rolled back after the test.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Use a role WITHOUT BYPASSRLS so RLS policies are actually enforced
_RLS_TEST_DB_URL = "postgresql+asyncpg://testgen_rls_test:testgen_rls_test@localhost:5432/testgen"
# Use the main role (WITH BYPASSRLS) for data setup that bypasses RLS
_SETUP_DB_URL = "postgresql+asyncpg://testgen:testgen_dev_password@localhost:5432/testgen"


@pytest.fixture
async def rls_session():
    """Per-test async session using a role WITHOUT BYPASSRLS, so RLS is enforced.

    Requires testgen_rls_test role. Run `python scripts/setup_test_db.py` to create it.
    """
    try:
        engine = create_async_engine(_RLS_TEST_DB_URL, pool_size=1)
        async with engine.connect() as conn:
            txn = await conn.begin()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            yield session
            await session.close()
            await txn.rollback()
        await engine.dispose()
    except Exception as exc:
        if "password authentication failed" in str(exc).lower() or "does not exist" in str(exc).lower():
            pytest.skip("testgen_rls_test role not available. Run: python scripts/setup_test_db.py")
        raise
    await engine.dispose()


async def _set_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set RLS tenant context."""
    await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))


async def _insert_tenant(session: AsyncSession, tenant_id: uuid.UUID, name: str) -> None:
    await _set_tenant(session, tenant_id)
    # slug (NOT NULL, unique) — kolumna doszła do schematu po napisaniu tych testów;
    # unikalny sufiks z tenant_id, bo testy biegną w Rolled-back transactionach
    # na wspólnej bazie.
    await session.execute(
        text(
            "INSERT INTO tenants (id, name, slug, plan, is_active, created_at) "
            "VALUES (:id, :name, :slug, 'basic', true, now())"
        ),
        {"id": str(tenant_id), "name": name, "slug": f"t-{tenant_id.hex[:16]}"},
    )


async def _insert_user_and_tenant_link(
    session: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID, email: str, role: str = "user"
) -> None:
    """Insert user (no tenant_id column) + user_tenants link. Uses setup role to bypass RLS on users."""
    # Users table has no RLS, but we still need to be in a tenant context for tenants FK
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, name, is_admin, is_active, created_at) "
            "VALUES (:id, :email, 'placeholder', 'Test', false, true, now())"
        ),
        {"id": str(user_id), "email": email},
    )
    await _set_tenant(session, tenant_id)
    await session.execute(
        text(
            "INSERT INTO user_tenants (id, user_id, tenant_id, role, created_at) VALUES (:id, :uid, :tid, :role, now())"
        ),
        {"id": str(uuid.uuid4()), "uid": str(user_id), "tid": str(tenant_id), "role": role},
    )


# ─── SELECT isolation ───


class TestRLSSelect:
    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_users(self, rls_session):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")
        await _insert_user_and_tenant_link(rls_session, user_a, tenant_a, "a@test.com")
        await _insert_user_and_tenant_link(rls_session, user_b, tenant_b, "b@test.com")

        await _set_tenant(rls_session, tenant_a)
        result = await rls_session.execute(text("SELECT user_id FROM user_tenants"))
        visible_ids = {str(row[0]) for row in result.fetchall()}

        assert str(user_a) in visible_ids
        assert str(user_b) not in visible_ids

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_see_tenant_a_users(self, rls_session):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")
        await _insert_user_and_tenant_link(rls_session, user_a, tenant_a, "a2@test.com")
        await _insert_user_and_tenant_link(rls_session, user_b, tenant_b, "b2@test.com")

        await _set_tenant(rls_session, tenant_b)
        result = await rls_session.execute(text("SELECT user_id FROM user_tenants"))
        visible_ids = {str(row[0]) for row in result.fetchall()}

        assert str(user_b) in visible_ids
        assert str(user_a) not in visible_ids


# ─── INSERT isolation (WITH CHECK) ───


class TestRLSInsert:
    @pytest.mark.asyncio
    async def test_cannot_insert_user_for_other_tenant(self, rls_session):
        """RLS WITH CHECK prevents inserting a user_tenants entry for a different tenant."""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        evil_user = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")
        # Insert user without tenant context
        await rls_session.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name, is_admin, is_active, created_at) "
                "VALUES (:id, :email, 'hash', 'Evil', false, true, now())"
            ),
            {"id": str(evil_user), "email": "evil@test.com"},
        )

        await _set_tenant(rls_session, tenant_a)

        with pytest.raises(Exception) as exc_info:
            await rls_session.execute(
                text(
                    "INSERT INTO user_tenants (id, user_id, tenant_id, role, created_at) "
                    "VALUES (:id, :uid, :tid, 'user', now())"
                ),
                {"id": str(uuid.uuid4()), "uid": str(evil_user), "tid": str(tenant_b)},
            )
        error_msg = str(exc_info.value).lower()
        assert (
            "row-level security" in error_msg
            or "policy" in error_msg
            or "polityk" in error_msg
            or "insufficientprivilege" in error_msg
        )

    @pytest.mark.asyncio
    async def test_can_insert_user_for_own_tenant(self, rls_session):
        """RLS WITH CHECK allows inserting a user_tenants entry with matching tenant_id."""
        tenant_a = uuid.uuid4()
        good_user = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await rls_session.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name, is_admin, is_active, created_at) "
                "VALUES (:id, :email, 'hash', 'Good', false, true, now())"
            ),
            {"id": str(good_user), "email": "good@test.com"},
        )
        await _set_tenant(rls_session, tenant_a)

        await rls_session.execute(
            text(
                "INSERT INTO user_tenants (id, user_id, tenant_id, role, created_at) "
                "VALUES (:id, :uid, :tid, 'user', now())"
            ),
            {"id": str(uuid.uuid4()), "uid": str(good_user), "tid": str(tenant_a)},
        )


# ─── UPDATE isolation ───


class TestRLSUpdate:
    @pytest.mark.asyncio
    async def test_cannot_update_other_tenant_user(self, rls_session):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        user_b = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")
        await _insert_user_and_tenant_link(rls_session, user_b, tenant_b, "target@test.com")

        # Get the user_tenants ID for user_b
        result = await rls_session.execute(
            text("SELECT id FROM user_tenants WHERE user_id = :uid"), {"uid": str(user_b)}
        )
        ut_id = result.scalar()

        await _set_tenant(rls_session, tenant_a)
        result = await rls_session.execute(
            text("UPDATE user_tenants SET role = 'owner' WHERE id = :utid"),
            {"utid": str(ut_id)},
        )
        assert result.rowcount == 0

    @pytest.mark.asyncio
    async def test_can_update_own_tenant_user(self, rls_session):
        tenant_a = uuid.uuid4()
        user_a = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_user_and_tenant_link(rls_session, user_a, tenant_a, "own@test.com")

        # Get the user_tenants ID for user_a
        result = await rls_session.execute(
            text("SELECT id FROM user_tenants WHERE user_id = :uid"), {"uid": str(user_a)}
        )
        ut_id = result.scalar()

        await _set_tenant(rls_session, tenant_a)
        result = await rls_session.execute(
            text("UPDATE user_tenants SET role = 'owner' WHERE id = :utid"),
            {"utid": str(ut_id)},
        )
        assert result.rowcount == 1


# ─── DELETE isolation ───


class TestRLSDelete:
    @pytest.mark.asyncio
    async def test_cannot_delete_other_tenant_user(self, rls_session):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        user_b = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")
        await _insert_user_and_tenant_link(rls_session, user_b, tenant_b, "del-target@test.com")

        # Get the user_tenants ID for user_b
        result = await rls_session.execute(
            text("SELECT id FROM user_tenants WHERE user_id = :uid"), {"uid": str(user_b)}
        )
        ut_id = result.scalar()

        await _set_tenant(rls_session, tenant_a)
        result = await rls_session.execute(
            text("DELETE FROM user_tenants WHERE id = :utid"),
            {"utid": str(ut_id)},
        )
        assert result.rowcount == 0

    @pytest.mark.asyncio
    async def test_can_delete_own_tenant_user(self, rls_session):
        tenant_a = uuid.uuid4()
        user_a = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_user_and_tenant_link(rls_session, user_a, tenant_a, "del-own@test.com")

        # Get the user_tenants ID for user_a
        result = await rls_session.execute(
            text("SELECT id FROM user_tenants WHERE user_id = :uid"), {"uid": str(user_a)}
        )
        ut_id = result.scalar()

        await _set_tenant(rls_session, tenant_a)
        result = await rls_session.execute(
            text("DELETE FROM user_tenants WHERE id = :utid"),
            {"utid": str(ut_id)},
        )
        assert result.rowcount == 1


# ─── Audit logs isolation ───


class TestRLSAuditLogs:
    @pytest.mark.asyncio
    async def test_audit_log_insert_cross_tenant_blocked(self, rls_session):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")

        await _set_tenant(rls_session, tenant_a)

        with pytest.raises(Exception) as exc_info:
            await rls_session.execute(
                text(
                    "INSERT INTO audit_logs (id, tenant_id, action, resource_type, resource_id, created_at) "
                    "VALUES (:id, :tid, 'test', 'user', :rid, now())"
                ),
                {"id": str(uuid.uuid4()), "tid": str(tenant_b), "rid": str(uuid.uuid4())},
            )
        error_msg = str(exc_info.value).lower()
        assert (
            "row-level security" in error_msg
            or "policy" in error_msg
            or "polityk" in error_msg
            or "insufficientprivilege" in error_msg
        )

    @pytest.mark.asyncio
    async def test_audit_log_select_cross_tenant_hidden(self, rls_session):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        user_a = uuid.uuid4()

        await _insert_tenant(rls_session, tenant_a, "Company A")
        await _insert_tenant(rls_session, tenant_b, "Company B")
        await _insert_user_and_tenant_link(rls_session, user_a, tenant_a, "audit@test.com")

        await _set_tenant(rls_session, tenant_a)
        log_id = uuid.uuid4()
        await rls_session.execute(
            text(
                "INSERT INTO audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, created_at) "
                "VALUES (:id, :tid, :uid, 'test.action', 'user', :rid, now())"
            ),
            {"id": str(log_id), "tid": str(tenant_a), "uid": str(user_a), "rid": str(user_a)},
        )

        await _set_tenant(rls_session, tenant_b)
        result = await rls_session.execute(text("SELECT id FROM audit_logs"))
        visible_ids = {str(row[0]) for row in result.fetchall()}
        assert str(log_id) not in visible_ids
