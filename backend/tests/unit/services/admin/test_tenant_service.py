"""Testy tenant_service — Story 6.15, Task 10 (AC4, AC5)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.models.tenant import PlanType
from app.services.admin import tenant_service
from tests.factories import make_tenant


def _scalar(value) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _scalar_one(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _rows(rows: list) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.fixture()
def mock_db():
    return AsyncMock()


class TestListTenants:
    async def test_zwraca_pusta_liste_gdy_brak_tenantow(self, mock_db):
        mock_db.execute.side_effect = [_scalar(0), _scalars([])]

        tenants, total = await tenant_service.list_tenants(mock_db)

        assert tenants == []
        assert total == 0

    async def test_zwraca_metryki_tenanta(self, mock_db):
        tenant = make_tenant(name="Acme", plan=PlanType.PREMIUM)
        mock_db.execute.side_effect = [
            _scalar(1),
            _scalars([tenant]),
            _rows([(tenant.id, 7)]),
            _rows([(tenant.id, 2048)]),
            _rows([(tenant.id, 3)]),
        ]

        tenants, total = await tenant_service.list_tenants(mock_db)

        assert total == 1
        assert tenants[0]["id"] == tenant.id
        assert tenants[0]["name"] == "Acme"
        assert tenants[0]["plan"] == "premium"
        assert tenants[0]["user_count"] == 7
        assert tenants[0]["storage_bytes"] == 2048
        assert tenants[0]["project_count"] == 3

    async def test_zeruje_metryki_bez_danych_agregacji(self, mock_db):
        tenant = make_tenant()
        mock_db.execute.side_effect = [
            _scalar(1),
            _scalars([tenant]),
            _rows([]),
            _rows([]),
            _rows([]),
        ]

        tenants, _ = await tenant_service.list_tenants(mock_db)

        assert tenants[0]["user_count"] == 0
        assert tenants[0]["storage_bytes"] == 0
        assert tenants[0]["project_count"] == 0

    async def test_page_size_ograniczony_do_maksimum(self, mock_db):
        mock_db.execute.side_effect = [_scalar(0), _scalars([])]

        await tenant_service.list_tenants(mock_db, page_size=5000)

        assert mock_db.execute.await_count == 2

    async def test_filtr_wyszukiwania_nie_psuje_zapytania(self, mock_db):
        mock_db.execute.side_effect = [_scalar(0), _scalars([])]

        tenants, total = await tenant_service.list_tenants(mock_db, search="acme")

        assert tenants == []
        assert total == 0


class TestGetTenantDetails:
    async def test_zwraca_szczegoly_tenanta(self, mock_db):
        tenant = make_tenant(name="Beta")
        mock_db.execute.side_effect = [
            _scalar_one(tenant),
            _scalar(4),
            _scalar(1024),
            _scalar(2),
        ]

        details = await tenant_service.get_tenant_details(mock_db, tenant.id)

        assert details["name"] == "Beta"
        assert details["user_count"] == 4
        assert details["storage_bytes"] == 1024
        assert details["project_count"] == 2

    async def test_nieznany_tenant_konczy_sie_bledem(self, mock_db):
        mock_db.execute.side_effect = [_scalar_one(None)]

        with pytest.raises(NotFoundError):
            await tenant_service.get_tenant_details(mock_db, uuid.uuid4())


class TestListTenantProjects:
    async def test_zwraca_projekty_tenanta(self, mock_db):
        from app.models.project import Project, ProjectStatus

        project = Project(id=uuid.uuid4(), tenant_id=uuid.uuid4(), name="API", status=ProjectStatus.ACTIVE)
        mock_db.execute.side_effect = [_scalar(1), _scalars([project])]

        projects, total = await tenant_service.list_tenant_projects(mock_db, project.tenant_id)

        assert total == 1
        assert projects[0]["name"] == "API"
        assert projects[0]["status"] == "active"

    async def test_pomija_projekty_usuniete(self, mock_db):
        mock_db.execute.side_effect = [_scalar(0), _scalars([])]

        projects, total = await tenant_service.list_tenant_projects(mock_db, uuid.uuid4())

        assert projects == []
        assert total == 0
        stmt = mock_db.execute.await_args_list[0].args[0]
        assert "is_deleted" in str(stmt)
