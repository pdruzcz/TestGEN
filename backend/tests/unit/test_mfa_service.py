"""Unit tests for MFA service: setup, confirm, verify, disable, backup codes."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from fakeredis.aioredis import FakeRedis

from app.core.encryption import encrypt
from app.core.exceptions import AuthError, ValidationError
from app.core.security import hash_password
from app.models.mfa import UserMFA
from app.models.user_tenant import TenantRole
from app.services.auth.jwt_handler import create_mfa_token
from app.services.auth.mfa_service import (
    confirm_mfa,
    disable_mfa,
    regenerate_backup_codes,
    setup_mfa,
    verify_mfa_login,
)

_TEST_PASSWORD = "StrongPass12345!"


@pytest.fixture
async def redis():
    return FakeRedis(decode_responses=True)


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    return db


class TestSetupMfa:
    async def test_setup_returns_secret_and_uri(self, user_id):
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        result = await setup_mfa(db, user_id, "test@company.com")
        assert "secret" in result
        assert "provisioning_uri" in result
        assert "TestGEN" in result["provisioning_uri"]

    async def test_setup_fails_if_already_enabled(self, user_id):
        db = _mock_db()
        existing = MagicMock()
        existing.is_enabled = True
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
        with pytest.raises(ValidationError, match="already enabled"):
            await setup_mfa(db, user_id, "test@company.com")


class TestConfirmMfa:
    async def test_confirm_with_valid_code(self, user_id):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = False
        mfa.backup_codes_hash = []

        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)))

        backup_codes = await confirm_mfa(db, user_id, valid_code)
        assert len(backup_codes) == 10
        assert mfa.is_enabled is True

    async def test_confirm_with_invalid_code(self, user_id):
        secret = pyotp.random_base32()
        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = False

        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)))

        with pytest.raises(ValidationError, match="Invalid TOTP"):
            await confirm_mfa(db, user_id, "000000")

    async def test_confirm_without_setup(self, user_id):
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        with pytest.raises(ValidationError, match="not initiated"):
            await confirm_mfa(db, user_id, "123456")


class TestVerifyMfaLogin:
    async def test_verify_totp_success(self, redis, user_id, tenant_id):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        mfa_token = create_mfa_token(user_id)

        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = True
        mfa.backup_codes_hash = []

        user = MagicMock()
        user.id = user_id
        user.is_admin = False
        user.is_active = True

        user_tenant = MagicMock()
        user_tenant.tenant_id = tenant_id
        user_tenant.role = TenantRole.OWNER

        db = _mock_db()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user_tenant)))),
            ]
        )

        access, refresh = await verify_mfa_login(db, redis, mfa_token, valid_code)
        assert access is not None
        assert refresh is not None

    async def test_verify_backup_code(self, redis, user_id, tenant_id):
        secret = pyotp.random_base32()
        backup_code = "abcd1234"

        mfa_token = create_mfa_token(user_id)

        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = True
        mfa.backup_codes_hash = [hash_password(backup_code)]

        user = MagicMock()
        user.id = user_id
        user.is_admin = False
        user.is_active = True

        user_tenant = MagicMock()
        user_tenant.tenant_id = tenant_id
        user_tenant.role = TenantRole.OWNER

        db = _mock_db()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user_tenant)))),
            ]
        )

        access, _refresh = await verify_mfa_login(db, redis, mfa_token, backup_code)
        assert access is not None

    async def test_verify_invalid_code(self, redis, user_id):
        secret = pyotp.random_base32()
        mfa_token = create_mfa_token(user_id)

        mfa = MagicMock(spec=UserMFA)
        mfa.totp_secret = encrypt(secret)
        mfa.is_enabled = True
        mfa.backup_codes_hash = []

        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)))

        with pytest.raises(AuthError, match="Invalid TOTP"):
            await verify_mfa_login(db, redis, mfa_token, "000000")


class TestDisableMfa:
    async def test_disable_with_correct_password(self, user_id):
        user = MagicMock()
        user.password_hash = hash_password(_TEST_PASSWORD)

        mfa = MagicMock(spec=UserMFA)
        mfa.is_enabled = True

        db = _mock_db()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),
            ]
        )

        await disable_mfa(db, user_id, _TEST_PASSWORD)
        db.delete.assert_called_once_with(mfa)

    async def test_disable_with_wrong_password(self, user_id):
        user = MagicMock()
        user.password_hash = hash_password(_TEST_PASSWORD)

        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

        with pytest.raises(AuthError, match="Invalid password"):
            await disable_mfa(db, user_id, "WrongPassword123!")


class TestRegenerateBackupCodes:
    async def test_regenerate_with_correct_password(self, user_id):
        user = MagicMock()
        user.password_hash = hash_password(_TEST_PASSWORD)

        mfa = MagicMock(spec=UserMFA)
        mfa.is_enabled = True
        mfa.backup_codes_hash = []

        db = _mock_db()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),
            ]
        )

        codes = await regenerate_backup_codes(db, user_id, _TEST_PASSWORD)
        assert len(codes) == 10
