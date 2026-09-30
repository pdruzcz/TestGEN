"""Unit tests for auth_service: register, verify_email, invite_user, accept_invitation, login, refresh, logout."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fakeredis.aioredis import FakeRedis

from app.core.exceptions import AuthError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.user_tenant import TenantRole
from app.services.auth.auth_service import (
    AccountLockedError,
    accept_invitation,
    invite_user,
    login,
    logout,
    refresh_tokens,
    register,
    verify_email,
)
from app.services.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.services.auth.token_store import store_refresh_token


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestRegister:
    async def test_register_happy_path(self, mock_db):
        from app.models.subscription_plan import PlanName

        freemium_plan = MagicMock()
        freemium_plan.id = uuid.uuid4()
        freemium_plan.name = PlanName.FREEMIUM
        # First execute: SET LOCAL (RLS clear), subsequent: email/NIP duplicate checks,
        # potem subskrypcja freemium (AC2): check istniejącej + fetch planu
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # email check
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # subskrypcja: brak
                MagicMock(scalar_one_or_none=MagicMock(return_value=freemium_plan)),  # plan freemium
            ]
        )

        user, token = await register(
            mock_db,
            email="new@company.com",
            password="StrongPass12345!",
            company_name="Acme Corp",
        )

        assert user.email == "new@company.com"
        assert user.is_admin is False
        assert user.is_active is False
        assert len(token) == 64  # hex(32)
        assert mock_db.add.call_count == 6  # user, tenant, user_tenant, subscription, verification, audit_log
        # Verify password was hashed with Argon2id (not stored as plaintext)
        assert user.password_hash.startswith("$argon2id$")
        assert verify_password("StrongPass12345!", user.password_hash)

    async def test_register_creates_freemium_subscription(self, mock_db):
        """AC2 (Story 7.1): rejestracja tworzy aktywną subskrypcję Freemium."""
        from app.models.subscription import Subscription, SubscriptionStatus
        from app.models.subscription_plan import PlanName

        freemium_plan = MagicMock()
        freemium_plan.id = uuid.uuid4()
        freemium_plan.name = PlanName.FREEMIUM
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # email check
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # brak subskrypcji
                MagicMock(scalar_one_or_none=MagicMock(return_value=freemium_plan)),  # plan freemium
            ]
        )

        _user, _token = await register(mock_db, "sub@company.com", "StrongPass12345!", "Sub Corp")

        subs = [c.args[0] for c in mock_db.add.call_args_list if isinstance(c.args[0], Subscription)]
        assert len(subs) == 1
        assert subs[0].plan_id == freemium_plan.id
        assert subs[0].status == SubscriptionStatus.ACTIVE

    async def test_register_weak_password_raises(self, mock_db):
        with pytest.raises(ValidationError, match="at least 12 characters"):
            await register(mock_db, "a@b.com", "short", "Company")

    async def test_register_duplicate_nip_raises(self, mock_db):
        existing_tenant = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # email check — no dup
                MagicMock(scalar_one_or_none=MagicMock(return_value=existing_tenant)),  # NIP check — dup
            ]
        )

        with pytest.raises(ConflictError, match="NIP already registered"):
            await register(mock_db, "new@test.com", "StrongPass12345!", "Company", nip="5252248481")

    async def test_register_duplicate_email_raises(self, mock_db):
        existing_user = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=existing_user)),
            ]
        )

        with pytest.raises(ConflictError, match="already registered"):
            await register(mock_db, "dup@test.com", "StrongPass12345!", "Company")


class TestVerifyEmail:
    async def test_verify_email_valid_token(self, mock_db):
        verification = MagicMock()
        verification.used_at = None
        verification.expires_at = datetime.now(UTC) + timedelta(hours=12)
        verification.user_id = uuid.uuid4()

        user = MagicMock()
        user.is_active = False

        # First execute: SET LOCAL (RLS clear), second: token query, third: user query, fourth: user_tenant query
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL app.current_tenant (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=verification)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=MagicMock())))),
            ]
        )

        result = await verify_email(mock_db, "valid_token")
        assert result.is_active is True
        assert verification.used_at is not None  # token marked as consumed

    async def test_verify_email_invalid_token(self, mock_db):
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            ]
        )
        with pytest.raises(NotFoundError, match="Invalid verification token"):
            await verify_email(mock_db, "bad_token")

    async def test_verify_email_expired_token(self, mock_db):
        verification = MagicMock()
        verification.used_at = None
        verification.expires_at = datetime.now(UTC) - timedelta(hours=1)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=verification)),
            ]
        )
        with pytest.raises(ValidationError, match="expired"):
            await verify_email(mock_db, "expired_token")

    async def test_verify_email_used_token(self, mock_db):
        verification = MagicMock()
        verification.used_at = datetime.now(UTC)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=verification)),
            ]
        )
        with pytest.raises(ValidationError, match="already used"):
            await verify_email(mock_db, "used_token")

    async def test_verify_email_rejects_invitation_token(self, mock_db):
        """Invitation token must NOT be usable for email verification (type filter)."""
        # The DB query filters by type=REGISTRATION, so an INVITATION token returns None
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # filtered out
            ]
        )
        with pytest.raises(NotFoundError, match="Invalid verification token"):
            await verify_email(mock_db, "invitation_token_value")


class TestInviteUser:
    async def test_invite_happy_path(self, mock_db):
        owner = MagicMock()
        owner.id = uuid.uuid4()
        owner.is_admin = False
        tenant_id = uuid.uuid4()

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        user, token = await invite_user(
            mock_db, owner, owner_tenant_id=tenant_id, owner_role="owner", email="new@test.com"
        )
        assert user.email == "new@test.com"
        assert len(token) == 64

    async def test_invite_unauthorized_user_raises(self, mock_db):
        regular_user = MagicMock()
        regular_user.is_admin = False

        with pytest.raises(ValidationError, match="Only owners"):
            await invite_user(
                mock_db, regular_user, owner_tenant_id=uuid.uuid4(), owner_role="user", email="new@test.com"
            )

    async def test_owner_cannot_invite_owner_role(self, mock_db):
        """Owner cannot assign OWNER role — only admins can."""
        owner = MagicMock()
        owner.id = uuid.uuid4()
        owner.is_admin = False
        tenant_id = uuid.uuid4()

        with pytest.raises(ForbiddenError, match="owner role"):
            await invite_user(
                mock_db,
                owner,
                owner_tenant_id=tenant_id,
                owner_role="owner",
                email="new@test.com",
                role=TenantRole.OWNER,
            )


class TestAcceptInvitation:
    async def test_accept_invitation_happy_path(self, mock_db):
        verification = MagicMock()
        verification.used_at = None
        verification.expires_at = datetime.now(UTC) + timedelta(hours=12)
        verification.user_id = uuid.uuid4()

        user = MagicMock()
        user.is_active = False
        user.password_hash = "!INVITATION_PENDING!"

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=verification)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=MagicMock())))),
            ]
        )

        result = await accept_invitation(mock_db, "valid_token", "StrongPass12345!")
        assert result.is_active is True
        assert result.email_verified_at is not None
        # Verify password was hashed with Argon2id (not placeholder)
        assert result.password_hash.startswith("$argon2id$")
        assert verify_password("StrongPass12345!", result.password_hash)

    async def test_accept_invitation_invalid_token(self, mock_db):
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            ]
        )
        with pytest.raises(NotFoundError, match="Invalid invitation token"):
            await accept_invitation(mock_db, "bad_token", "StrongPass12345!")

    async def test_accept_invitation_expired_token(self, mock_db):
        verification = MagicMock()
        verification.used_at = None
        verification.expires_at = datetime.now(UTC) - timedelta(hours=1)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=verification)),
            ]
        )
        with pytest.raises(ValidationError, match="expired"):
            await accept_invitation(mock_db, "expired_token", "StrongPass12345!")

    async def test_accept_invitation_used_token(self, mock_db):
        verification = MagicMock()
        verification.used_at = datetime.now(UTC)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL (RLS clear)
                MagicMock(scalar_one_or_none=MagicMock(return_value=verification)),
            ]
        )
        with pytest.raises(ValidationError, match="already used"):
            await accept_invitation(mock_db, "used_token", "StrongPass12345!")

    async def test_accept_invitation_weak_password(self, mock_db):
        with pytest.raises(ValidationError, match="at least 12"):
            await accept_invitation(mock_db, "token", "short")


# --- Fixtures for login/refresh/logout tests ---

_TEST_PASSWORD = "StrongPass12345!"


@pytest.fixture
async def redis():
    return FakeRedis(decode_responses=True)


@pytest.fixture
def active_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@company.com"
    user.is_admin = False
    user.is_active = True
    user.is_blocked = False
    user.password_hash = hash_password(_TEST_PASSWORD)
    user.mfa = None
    return user


def _mock_db_for_login(user, mfa_record=None, user_tenant=None):
    """Create mock db for login flow: SET LOCAL + user lookup + UserTenant lookup + Tenant lookup [+ extra for audit]."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    ut_mock = user_tenant or MagicMock(tenant_id=uuid.uuid4(), role=TenantRole.OWNER)
    tenant_mock = MagicMock(id=ut_mock.tenant_id, name="Test Corp")

    def _scalars_result(items):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items
        return r

    # Use return_value as fallback for any extra execute calls (audit log, etc.)
    default_execute = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    side_effects = [
        MagicMock(),  # SET LOCAL (RLS clear)
        MagicMock(scalar_one_or_none=MagicMock(return_value=user)),  # user lookup
        _scalars_result([ut_mock]),  # UserTenant
        _scalars_result([tenant_mock]),  # Tenant lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # MFA check (no MFA)
    ]

    db.execute = AsyncMock(side_effect=side_effects + [default_execute] * 10)
    return db


class TestLogin:
    async def test_login_success(self, redis, active_user):
        db = _mock_db_for_login(active_user)
        result = await login(db, redis, "test@company.com", _TEST_PASSWORD)
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.mfa_required is False

    async def test_login_wrong_password(self, redis, active_user):
        db = _mock_db_for_login(active_user)
        with pytest.raises(AuthError, match="Invalid credentials"):
            await login(db, redis, "test@company.com", "WrongPassword123!")

    async def test_login_user_not_found(self, redis):
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            ]
        )
        with pytest.raises(AuthError, match="Invalid credentials"):
            await login(db, redis, "nonexistent@test.com", _TEST_PASSWORD)

    async def test_login_inactive_user(self, redis, active_user):
        active_user.is_active = False
        db = _mock_db_for_login(active_user)
        with pytest.raises(AuthError, match="Invalid credentials"):
            await login(db, redis, "test@company.com", _TEST_PASSWORD)

    async def test_login_blocked_user(self, redis, active_user):
        """Story 6.15 (AC3): blokada administracyjna uniemożliwia logowanie."""
        active_user.is_blocked = True
        db = _mock_db_for_login(active_user)
        with pytest.raises(AuthError, match="Invalid credentials"):
            await login(db, redis, "test@company.com", _TEST_PASSWORD)

    async def test_login_locked_account(self, redis, active_user):
        from app.services.auth.token_store import lock_account

        await lock_account(redis, active_user.id)
        db = _mock_db_for_login(active_user)
        with pytest.raises(AccountLockedError):
            await login(db, redis, "test@company.com", _TEST_PASSWORD)

    async def test_login_brute_force_locks_after_5_attempts(self, redis, active_user):
        for _ in range(5):
            db = _mock_db_for_login(active_user)
            with pytest.raises(AuthError, match="Invalid credentials"):
                await login(db, redis, "test@company.com", "WrongPassword123!")

        db = _mock_db_for_login(active_user)
        with pytest.raises(AccountLockedError):
            await login(db, redis, "test@company.com", _TEST_PASSWORD)

    async def test_login_mfa_required(self, redis, active_user):
        mfa = MagicMock()
        mfa.is_enabled = True
        active_user.mfa = mfa

        ut_mock = MagicMock()
        ut_mock.tenant_id = uuid.uuid4()
        ut_mock.role = TenantRole.OWNER

        def _scalars_result(items):
            r = MagicMock()
            r.scalars.return_value.all.return_value = items
            return r

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=active_user)),  # user lookup
                _scalars_result([ut_mock]),  # UserTenant
                _scalars_result([MagicMock(id=ut_mock.tenant_id, name="Test")]),  # Tenant
                MagicMock(scalar_one_or_none=MagicMock(return_value=mfa)),  # MFA check
            ]
        )

        result = await login(db, redis, "test@company.com", _TEST_PASSWORD)
        assert result.mfa_required is True
        assert result.mfa_token is not None
        assert result.access_token is None


class TestRefreshTokens:
    async def test_refresh_success(self, redis, active_user):
        refresh_tok = create_refresh_token(active_user.id)
        payload = decode_token(refresh_tok)
        await store_refresh_token(redis, payload["jti"], active_user.id, 86400)

        ut_mock = MagicMock(tenant_id=uuid.uuid4(), role=TenantRole.OWNER)

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = ut_mock

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=active_user)),  # user lookup
                MagicMock(scalars=MagicMock(return_value=scalars_mock)),  # UserTenant
            ]
        )

        access, new_refresh = await refresh_tokens(db, redis, refresh_tok)
        assert access is not None
        assert new_refresh is not None
        # Old token revoked
        from app.services.auth.token_store import is_refresh_token_valid

        assert await is_refresh_token_valid(redis, payload["jti"]) is False

    async def test_refresh_revoked_token(self, redis, active_user):
        refresh_tok = create_refresh_token(active_user.id)
        # Don't store in Redis — should fail
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock()])  # SET LOCAL
        with pytest.raises(AuthError, match="revoked"):
            await refresh_tokens(db, redis, refresh_tok)


class TestLogout:
    async def test_logout_blacklists_access_and_revokes_refresh(self, redis, active_user):
        access_tok = create_access_token(active_user.id, uuid.uuid4(), "owner", is_admin=False)
        refresh_tok = create_refresh_token(active_user.id)
        ref_payload = decode_token(refresh_tok)
        await store_refresh_token(redis, ref_payload["jti"], active_user.id, 86400)

        await logout(redis, access_tok, refresh_tok)

        from app.services.auth.token_store import is_access_token_blacklisted, is_refresh_token_valid

        acc_payload = decode_token(access_tok)
        assert await is_access_token_blacklisted(redis, acc_payload["jti"]) is True
        assert await is_refresh_token_valid(redis, ref_payload["jti"]) is False

    async def test_logout_graceful_with_invalid_tokens(self, redis):
        # Should not raise even with garbage tokens
        await logout(redis, "invalid-token", "also-invalid")
