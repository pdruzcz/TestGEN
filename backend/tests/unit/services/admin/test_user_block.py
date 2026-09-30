"""Testy blokowania i miękkiego usuwania użytkownika — Story 6.15, Task 10 (AC3)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.user_tenant import TenantRole
from app.services.user.user_service import deactivate_user, set_user_blocked
from tests.factories import make_user, make_user_tenant


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    return db


def _scalar_one(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _audit_entries(mock_db) -> list:
    return [call.args[0] for call in mock_db.add.call_args_list if hasattr(call.args[0], "action")]


class TestSetUserBlocked:
    async def test_blokuje_uzytkownika(self, mock_db):
        admin = make_user(is_admin=True)
        target = make_user(email="target@test.com")
        mock_db.execute.side_effect = [_scalar_one(target)]

        result = await set_user_blocked(
            mock_db,
            admin=admin,
            target_user_id=target.id,
            blocked=True,
            tenant_id=uuid.uuid4(),
        )

        assert result.is_blocked is True

    async def test_odblokowuje_uzytkownika(self, mock_db):
        admin = make_user(is_admin=True)
        target = make_user()
        target.is_blocked = True
        mock_db.execute.side_effect = [_scalar_one(target)]

        result = await set_user_blocked(
            mock_db,
            admin=admin,
            target_user_id=target.id,
            blocked=False,
            tenant_id=uuid.uuid4(),
        )

        assert result.is_blocked is False

    async def test_zapisuje_wpis_audytu_z_akcja_blocked(self, mock_db):
        admin = make_user(is_admin=True)
        target = make_user()
        mock_db.execute.side_effect = [_scalar_one(target)]

        await set_user_blocked(
            mock_db,
            admin=admin,
            target_user_id=target.id,
            blocked=True,
            tenant_id=uuid.uuid4(),
            ip_address="10.0.0.5",
        )

        entries = _audit_entries(mock_db)
        assert [entry.action for entry in entries] == ["user.blocked"]
        assert entries[0].ip_address == "10.0.0.5"
        assert entries[0].resource_id == target.id

    async def test_zapisuje_wpis_audytu_z_akcja_unblocked(self, mock_db):
        target = make_user()
        target.is_blocked = True
        mock_db.execute.side_effect = [_scalar_one(target)]

        await set_user_blocked(
            mock_db,
            admin=make_user(is_admin=True),
            target_user_id=target.id,
            blocked=False,
            tenant_id=uuid.uuid4(),
        )

        assert [entry.action for entry in _audit_entries(mock_db)] == ["user.unblocked"]

    async def test_bez_zmiany_stanu_nie_tworzy_wpisu_audytu(self, mock_db):
        target = make_user()
        target.is_blocked = False
        mock_db.execute.side_effect = [_scalar_one(target)]

        await set_user_blocked(
            mock_db,
            admin=make_user(is_admin=True),
            target_user_id=target.id,
            blocked=False,
            tenant_id=uuid.uuid4(),
        )

        assert _audit_entries(mock_db) == []

    async def test_nie_mozna_zablokowac_siebie(self, mock_db):
        admin = make_user(is_admin=True)
        mock_db.execute.side_effect = [_scalar_one(admin)]

        with pytest.raises(ForbiddenError):
            await set_user_blocked(
                mock_db,
                admin=admin,
                target_user_id=admin.id,
                blocked=True,
                tenant_id=uuid.uuid4(),
            )

    async def test_tylko_admin_moze_blokowac(self, mock_db):
        with pytest.raises(ForbiddenError):
            await set_user_blocked(
                mock_db,
                admin=make_user(is_admin=False),
                target_user_id=uuid.uuid4(),
                blocked=True,
                tenant_id=uuid.uuid4(),
            )

    async def test_nieznany_uzytkownik_konczy_sie_bledem(self, mock_db):
        mock_db.execute.side_effect = [_scalar_one(None)]

        with pytest.raises(NotFoundError):
            await set_user_blocked(
                mock_db,
                admin=make_user(is_admin=True),
                target_user_id=uuid.uuid4(),
                blocked=True,
                tenant_id=uuid.uuid4(),
            )


class TestSoftDelete:
    async def test_admin_stempluje_deleted_at(self, mock_db):
        admin = make_user(is_admin=True)
        target = make_user(email="target@test.com")
        tenant_id = uuid.uuid4()
        target_ut = make_user_tenant(user_id=target.id, tenant_id=tenant_id, role=TenantRole.USER)
        mock_db.execute.side_effect = [_scalar_one(target), _scalar_one(target_ut)]

        result = await deactivate_user(
            mock_db,
            actor=admin,
            target_user_id=target.id,
            current_tenant_id=tenant_id,
            is_admin=True,
        )

        assert result.deleted_at is not None
        assert result.is_active is False

    async def test_owner_nie_stempluje_deleted_at(self, mock_db):
        owner = make_user()
        target = make_user(email="target@test.com")
        tenant_id = uuid.uuid4()
        owner_ut = make_user_tenant(user_id=owner.id, tenant_id=tenant_id, role=TenantRole.OWNER)
        target_ut = make_user_tenant(user_id=target.id, tenant_id=tenant_id, role=TenantRole.USER)
        mock_db.execute.side_effect = [
            _scalar_one(owner_ut),
            _scalar_one(target),
            _scalar_one(target_ut),
        ]

        result = await deactivate_user(
            mock_db,
            actor=owner,
            target_user_id=target.id,
            current_tenant_id=tenant_id,
            is_admin=False,
        )

        assert result.deleted_at is None
