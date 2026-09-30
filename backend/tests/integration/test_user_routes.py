"""Integration tests for user API routes.

These tests verify route behavior with mocked authentication.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.user_tenant import TenantRole
from tests.factories import make_user, make_user_tenant


def _make_mock_user_with_context(
    role: TenantRole = TenantRole.OWNER,
    tenant_id: uuid.UUID | None = None,
    is_admin: bool = False,
    email: str = "owner@test.com",
    name: str = "Owner",
):
    """Create a mock user + tenant_id for route tests using factories."""
    user = make_user(email=email, name=name, is_admin=is_admin)
    _tenant_id = tenant_id or uuid.uuid4()
    return user, _tenant_id, role


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def _override_auth(app, user, tenant_id, role="owner", is_admin=False):
    """Override get_current_user to set request.state attributes."""
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = role
        request.state.is_admin = is_admin
        return user

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db


class TestGetMe:
    async def test_get_me_returns_200(self, client, app):
        user, tenant_id, role = _make_mock_user_with_context()

        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        async def override(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = role
            request.state.is_admin = False
            return user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = override
        app.dependency_overrides[get_db] = override_db

        response = await client.get("/api/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "owner@test.com"
        assert data["mfa_enabled"] is False

        app.dependency_overrides = {}


class TestUpdateMe:
    async def test_update_me_returns_200(self, client, app):
        user, tenant_id, role = _make_mock_user_with_context()

        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = role
            request.state.is_admin = False
            return user

        async def override_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        response = await client.put(
            "/api/v1/users/me",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200

        app.dependency_overrides = {}


class TestChangePassword:
    async def test_change_password_returns_200(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db
        from app.core.security import hash_password

        user, tenant_id, role = _make_mock_user_with_context()
        user.password_hash = hash_password("OldPassword123!")

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = role
            request.state.is_admin = False
            return user

        async def override_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        with patch("app.services.user.user_service.log_action", new_callable=AsyncMock):
            response = await client.put(
                "/api/v1/users/me/password",
                json={
                    "old_password": "OldPassword123!",
                    "new_password": "NewStrongPass123!",
                },
            )
        assert response.status_code == 200

        app.dependency_overrides = {}


class TestListUsers:
    async def test_list_users_returns_200_with_total_header(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        tenant_id = uuid.uuid4()
        owner, _, _ = _make_mock_user_with_context(role=TenantRole.OWNER, tenant_id=tenant_id, email="owner@test.com")
        member = make_user(email="member@test.com", name="Member")
        owner_ut = make_user_tenant(user_id=owner.id, tenant_id=tenant_id, role=TenantRole.OWNER)
        member_ut = make_user_tenant(user_id=member.id, tenant_id=tenant_id, role=TenantRole.USER)

        async def override_user(request: Request):
            request.state.user = owner
            request.state.tenant_id = tenant_id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
            return owner

        async def override_db():
            db = AsyncMock()
            count_result = MagicMock()
            count_result.scalar.return_value = 2
            ut_result = MagicMock()
            ut_result.scalars.return_value.all.return_value = [owner_ut, member_ut]
            user_result = MagicMock()
            user_result.scalars.return_value.all.return_value = [owner, member]
            db.execute = AsyncMock(side_effect=[count_result, ut_result, user_result])
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        response = await client.get("/api/v1/users")
        assert response.status_code == 200
        assert response.headers.get("x-total-count") == "2"
        data = response.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2

        app.dependency_overrides = {}

    async def test_list_users_forbidden_for_regular_user(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user

        user, tenant_id, _ = _make_mock_user_with_context(role=TenantRole.USER)

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = TenantRole.USER
            request.state.is_admin = False
            return user

        app.dependency_overrides[get_current_user] = override_user

        response = await client.get("/api/v1/users")
        assert response.status_code == 403

        app.dependency_overrides = {}

    async def test_owner_tenant_id_param_ignored(self, client, app):
        """Owner cannot list other tenants' users via tenant_id query param."""
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        owner_tenant_id = uuid.uuid4()
        other_tenant_id = uuid.uuid4()
        owner, _, _ = _make_mock_user_with_context(role=TenantRole.OWNER, tenant_id=owner_tenant_id)
        owner_ut = make_user_tenant(user_id=owner.id, tenant_id=owner_tenant_id, role=TenantRole.OWNER)

        async def override_user(request: Request):
            request.state.user = owner
            request.state.tenant_id = owner_tenant_id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
            return owner

        async def override_db():
            db = AsyncMock()
            count_result = MagicMock()
            count_result.scalar.return_value = 1
            ut_result = MagicMock()
            ut_result.scalars.return_value.all.return_value = [owner_ut]
            user_result = MagicMock()
            user_result.scalars.return_value.all.return_value = [owner]
            db.execute = AsyncMock(side_effect=[count_result, ut_result, user_result])
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        # Owner passes another tenant_id — should be silently ignored
        response = await client.get(f"/api/v1/users?tenant_id={other_tenant_id}")
        assert response.status_code == 200
        data = response.json()
        # Verify only own tenant's users returned
        for user in data["users"]:
            assert user["tenant_id"] == str(owner_tenant_id)

        app.dependency_overrides = {}


class TestInviteUser:
    async def test_invite_returns_201(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        tenant_id = uuid.uuid4()
        owner, _, _ = _make_mock_user_with_context(role=TenantRole.OWNER, tenant_id=tenant_id)
        invited_user = make_user(email="invited@test.com", name="Invited")
        token = "test-token-123"

        async def override_user(request: Request):
            request.state.user = owner
            request.state.tenant_id = tenant_id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
            return owner

        async def override_db():
            mock_db = AsyncMock()
            # Mock the tenant query for email template
            tenant_mock = MagicMock()
            tenant_mock.name = "Test Company"
            tenant_result = MagicMock()
            tenant_result.scalar_one_or_none.return_value = tenant_mock
            mock_db.execute.return_value = tenant_result
            yield mock_db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        with (
            patch(
                "app.api.routes.users.invite_user",
                new_callable=AsyncMock,
                return_value=(invited_user, token),
            ),
            patch("app.api.routes.users.send_invitation_email_task"),
        ):
            response = await client.post(
                "/api/v1/users/invite",
                json={"email": "invited@test.com", "role": "user"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Zaproszenie zostało wysłane"
        assert "user_id" in data

        app.dependency_overrides = {}


class TestUpdateRole:
    async def test_update_role_returns_200(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        tenant_id = uuid.uuid4()
        owner, _, _ = _make_mock_user_with_context(role=TenantRole.OWNER, tenant_id=tenant_id)
        target_user = make_user(email="target@test.com", name="Target")

        async def override_user(request: Request):
            request.state.user = owner
            request.state.tenant_id = tenant_id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
            return owner

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        with patch(
            "app.api.routes.users.change_role",
            new_callable=AsyncMock,
            return_value=target_user,
        ):
            response = await client.put(
                f"/api/v1/users/{target_user.id}/role",
                json={"role": "owner"},
            )

        assert response.status_code == 200

        app.dependency_overrides = {}

    async def test_self_demotion_blocked(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db
        from app.core.exceptions import ForbiddenError

        tenant_id = uuid.uuid4()
        owner, _, _ = _make_mock_user_with_context(role=TenantRole.OWNER, tenant_id=tenant_id)

        async def override_user(request: Request):
            request.state.user = owner
            request.state.tenant_id = tenant_id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
            return owner

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        with patch(
            "app.api.routes.users.change_role",
            new_callable=AsyncMock,
            side_effect=ForbiddenError("Cannot change your own role"),
        ):
            response = await client.put(
                f"/api/v1/users/{owner.id}/role",
                json={"role": "user"},
            )

        assert response.status_code == 403

        app.dependency_overrides = {}


class TestDeleteUser:
    async def test_delete_user_returns_204(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        tenant_id = uuid.uuid4()
        owner, _, _ = _make_mock_user_with_context(role=TenantRole.OWNER, tenant_id=tenant_id)
        target_id = uuid.uuid4()

        async def override_user(request: Request):
            request.state.user = owner
            request.state.tenant_id = tenant_id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
            return owner

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        with patch(
            "app.api.routes.users.deactivate_user",
            new_callable=AsyncMock,
        ):
            response = await client.delete(f"/api/v1/users/{target_id}")

        assert response.status_code == 204

        app.dependency_overrides = {}
