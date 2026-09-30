"""Integration tests for MFA API routes."""

from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.core.encryption import encrypt
from app.core.redis import get_redis
from app.main import create_app
from app.models.mfa import UserMFA
from app.models.user_tenant import TenantRole
from app.services.auth.jwt_handler import create_mfa_token
from tests.factories import make_tenant, make_user, make_user_tenant


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def fake_redis():
    return FakeRedis(decode_responses=True)


@pytest.fixture
def owner_user():
    tenant = make_tenant()
    user = make_user(email="mfa@test.com", name="MFA User")
    _user_tenant = make_user_tenant(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER)
    return user, tenant


@pytest.fixture
def authenticated_app(app, owner_user, fake_redis):
    user, tenant = owner_user
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def _override_user(request=None):
        if request:
            request.state.user = user
            request.state.tenant_id = tenant.id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
        return user

    async def _override_db():
        yield mock_db

    async def _override_redis():
        return fake_redis

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis
    yield app, mock_db
    app.dependency_overrides.clear()


class TestMfaSetupRoute:
    async def test_mfa_setup_returns_secret(self, authenticated_app):
        app, mock_db = authenticated_app
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/mfa/setup")

        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "provisioning_uri" in data

    async def test_mfa_setup_already_enabled_400(self, authenticated_app):
        """Cannot setup MFA if already enabled."""
        app, mock_db = authenticated_app
        existing_mfa = MagicMock(spec=UserMFA)
        existing_mfa.is_enabled = True
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_mfa)))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/mfa/setup")

        assert resp.status_code == 422


class TestMfaConfirmRoute:
    async def test_mfa_confirm_returns_backup_codes(self, authenticated_app):
        app, mock_db = authenticated_app

        secret = pyotp.random_base32()

        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = False
        mfa.backup_codes_hash = []

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)))

        valid_code = pyotp.TOTP(secret).now()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/mfa/confirm", json={"code": valid_code})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["backup_codes"]) == 10

    async def test_mfa_confirm_invalid_code_422(self, authenticated_app):
        """Invalid TOTP code returns 422."""
        app, mock_db = authenticated_app

        secret = pyotp.random_base32()
        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = False

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/mfa/confirm", json={"code": "000000"})

        assert resp.status_code == 422


class TestMfaVerifyRoute:
    async def test_mfa_verify_valid_totp(self, authenticated_app, owner_user, fake_redis):
        """AC4: valid MFA token + TOTP code -> 200 + auth cookies."""
        app, mock_db = authenticated_app
        user, _tenant = owner_user

        secret = pyotp.random_base32()
        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = True
        mfa.backup_codes_hash = []

        # First call: MFA lookup, second: User lookup, third: UserTenant lookup
        mock_ut = MagicMock()
        mock_ut.tenant_id = _tenant.id
        mock_ut.role = MagicMock(value="owner")
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_ut)))),
            ]
        )

        mfa_token = create_mfa_token(user.id)
        valid_code = pyotp.TOTP(secret).now()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_token": mfa_token, "code": valid_code},
            )

        assert resp.status_code == 200
        # Should set auth cookies
        set_cookies = {c.split("=")[0] for c in resp.headers.get_list("set-cookie")}
        assert "access_token" in set_cookies
        assert "refresh_token" in set_cookies

    async def test_mfa_verify_invalid_code_401(self, authenticated_app, owner_user, fake_redis):
        """Invalid TOTP code returns 401."""
        app, mock_db = authenticated_app
        user, _tenant = owner_user

        secret = pyotp.random_base32()
        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = True
        mfa.backup_codes_hash = []

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)))

        mfa_token = create_mfa_token(user.id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_token": mfa_token, "code": "000000"},
            )

        assert resp.status_code == 401


class TestMfaDisableRoute:
    async def test_mfa_disable_with_valid_password(self, authenticated_app, owner_user):
        """DELETE /mfa with valid password disables MFA."""
        app, mock_db = authenticated_app
        user, _tenant = owner_user

        mfa = MagicMock(spec=UserMFA)
        mfa.is_enabled = True

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),  # user lookup
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),  # mfa lookup
            ]
        )
        mock_db.delete = AsyncMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.request(
                "DELETE",
                "/api/v1/auth/mfa",
                json={"password": "SecurePassword123!"},
            )

        assert resp.status_code == 200
        assert resp.json()["message"] == "MFA zostało wyłączone"

    async def test_mfa_disable_wrong_password_401(self, authenticated_app, owner_user):
        """DELETE /mfa with wrong password returns 401."""
        app, mock_db = authenticated_app
        user, _tenant = owner_user

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.request(
                "DELETE",
                "/api/v1/auth/mfa",
                json={"password": "WrongPassword123!"},
            )

        assert resp.status_code == 401


class TestMfaBackupCodesRoute:
    async def test_regenerate_backup_codes(self, authenticated_app, owner_user):
        """POST /mfa/backup-codes regenerates backup codes."""
        app, mock_db = authenticated_app
        user, _tenant = owner_user

        mfa = MagicMock(spec=UserMFA)
        mfa.is_enabled = True
        mfa.backup_codes_hash = []

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),  # user lookup
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),  # mfa lookup
            ]
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/mfa/backup-codes",
                json={"password": "SecurePassword123!"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["backup_codes"]) == 10
