"""Unit tests for admin bootstrap service."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.core.security import verify_password
from app.models.tenant import PlanType
from app.models.user import User
from app.models.user_tenant import UserTenant
from app.services.auth.bootstrap import bootstrap_admin


def _make_settings(bootstrap: bool = True, email: str = "admin@testgen.pl", password: str = "AdminPass123!@"):
    """Create a minimal settings-like object for bootstrap tests."""
    s = MagicMock()
    s.bootstrap_admin = bootstrap
    s.admin_email = email
    s.admin_password = password
    return s


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


class TestBootstrapAdmin:
    async def test_creates_admin_when_none_exists(self):
        db = _mock_db()
        settings = _make_settings()

        # SET LOCAL + admin check (none) + email check (none) + no system tenant
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no admin
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no email dup
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no system tenant
            ]
        )

        await bootstrap_admin(db, settings)

        # Verify tenant + user + user_tenant + audit_log were added
        assert db.add.call_count == 4

        # Extract the created user
        added_objects = [call.args[0] for call in db.add.call_args_list]
        user = next(o for o in added_objects if isinstance(o, User))

        assert user.email == "admin@testgen.pl"
        assert user.is_admin is True
        assert user.is_active is True
        assert user.email_verified_at is not None
        assert user.name == "Platform Admin"
        assert verify_password("AdminPass123!@", user.password_hash)

        # Verify UserTenant was created
        user_tenant = next(o for o in added_objects if isinstance(o, UserTenant))
        assert user_tenant.role.value == "owner"

        assert db.commit.called

    async def test_creates_system_tenant_with_premium_plan(self):
        db = _mock_db()
        settings = _make_settings()

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no admin
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no email dup
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no system tenant
            ]
        )

        await bootstrap_admin(db, settings)

        from app.models.tenant import Tenant

        added_objects = [call.args[0] for call in db.add.call_args_list]
        tenant = next(o for o in added_objects if isinstance(o, Tenant))

        assert tenant.name == "__system__"
        assert tenant.plan == PlanType.PREMIUM
        assert tenant.is_active is True

    async def test_reuses_existing_system_tenant(self):
        db = _mock_db()
        settings = _make_settings()

        existing_tenant = MagicMock(id=uuid.uuid4())

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no admin
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no email dup
                MagicMock(scalar_one_or_none=MagicMock(return_value=existing_tenant)),  # system tenant exists
            ]
        )

        await bootstrap_admin(db, settings)

        # user + user_tenant + audit_log added (no new tenant)
        assert db.add.call_count == 3

    async def test_skips_when_admin_already_exists(self):
        db = _mock_db()
        settings = _make_settings()

        existing_admin = MagicMock(is_admin=True)

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=existing_admin)),  # admin exists
            ]
        )

        await bootstrap_admin(db, settings)

        assert db.add.call_count == 0
        assert not db.commit.called

    async def test_skips_when_email_taken_by_non_admin(self):
        db = _mock_db()
        settings = _make_settings()

        existing_user = MagicMock(is_admin=False)

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no admin
                MagicMock(scalar_one_or_none=MagicMock(return_value=existing_user)),  # email taken
            ]
        )

        await bootstrap_admin(db, settings)

        assert db.add.call_count == 0
        assert not db.commit.called

    async def test_skips_when_bootstrap_disabled(self):
        db = _mock_db()
        settings = _make_settings(bootstrap=False)

        await bootstrap_admin(db, settings)

        assert db.execute.call_count == 0
        assert db.add.call_count == 0

    async def test_skips_when_email_missing(self):
        db = _mock_db()
        settings = _make_settings(email="")

        await bootstrap_admin(db, settings)

        assert db.execute.call_count == 0

    async def test_skips_when_password_missing(self):
        db = _mock_db()
        settings = _make_settings(password="")

        await bootstrap_admin(db, settings)

        assert db.execute.call_count == 0

    async def test_idempotent_multiple_starts(self):
        """Simulate second startup — admin already exists from first run."""
        db = _mock_db()
        settings = _make_settings()

        existing_admin = MagicMock(is_admin=True)
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                MagicMock(scalar_one_or_none=MagicMock(return_value=existing_admin)),
            ]
        )

        await bootstrap_admin(db, settings)

        assert db.add.call_count == 0
