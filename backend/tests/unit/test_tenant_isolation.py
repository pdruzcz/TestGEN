"""HOTFIX izolacji tenantów (2026-09-15) — testy regresyjne.

Kontekst: rola DB z BYPASSRLS/SUPERUSER omija polityki RLS, więc
serwisy dostają JAWNY filtr ``tenant_id`` z ``db.info["tenant_scope"]``
(ustawiany w ``get_current_user`` / ``set_rls_context``). Wyciek wykryty
empirycznie na środowisku publicznym: ``GET /api/v1/projects`` zwracał
projekty obcych tenantów.

Te testy pilnują, żeby filtr TRWALE obecny był w zapytaniach choke-pointów:
- ``project_service.list_projects`` / ``_get_active_project``
- ``upload_service.get_active_project`` (uploady + listy plików)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.project.project_service import (
    _get_active_project,
    list_projects,
)
from app.services.project.upload_service import get_active_project

TENANT_A = "11111111-1111-4111-8111-111111111111"
TENANT_B = "22222222-2222-4222-8222-222222222222"


class _CaptureDB(AsyncMock):
    """AsyncSession mock przechwytujący stmt i zwracający sterowane wyniki."""

    def __init__(self, *a, scope=None, rows=None, scalar=None, **kw):
        super().__init__(*a, **kw)
        self.info = {"tenant_scope": scope} if scope is not None else {}
        self.captured: list = []
        self._rows = rows
        self._scalar = scalar

    async def execute(self, stmt, *a, **kw):
        self.captured.append(stmt)
        result = MagicMock()
        if self._rows is not None:
            result.scalars.return_value.all.return_value = self._rows
        result.scalar_one_or_none = MagicMock(return_value=self._scalar)
        result.scalar = MagicMock(return_value=self._scalar)
        return result


def _where(stmt) -> str:
    """Fragment SQL po 'WHERE' — tu szukamy filtra (nie w liście kolumn SELECT)."""
    return str(stmt).split("WHERE", 1)[-1]


def _actor(tenant_id: str) -> MagicMock:
    actor = MagicMock()
    actor.id = uuid.uuid4()
    actor._tenant_id = uuid.UUID(tenant_id)
    actor._tenant_role = "owner"
    return actor


class TestListProjectsTenantFilter:
    async def test_scope_filters_by_tenant_id(self):
        db = _CaptureDB(scope=TENANT_A, rows=[], scalar=0)
        await list_projects(db, _actor(TENANT_A))
        assert any("tenant_id" in _where(s) for s in db.captured), (
            "list_projects bez filtra tenant_id — wyciek między tenantami"
        )

    async def test_no_scope_no_filter(self):
        """Przepływy systemowe (webhooki/startup) — bez scope, bez filtra."""
        db = _CaptureDB(rows=[], scalar=0)
        await list_projects(db, _actor(TENANT_A))
        # WHERE bez filtra tenantów — przepływ systemowy
        assert all("tenant_id" not in _where(s) for s in db.captured)


class TestGetProjectTenantFilter:
    async def test_foreign_project_404(self):
        """Kluczowy scenariusz wycieku: obcy project_id → 404, nie dane."""
        db = _CaptureDB(scope=TENANT_A, scalar=None)  # filtr wyklucza wiersz
        with pytest.raises(NotFoundError):
            await _get_active_project(db, uuid.uuid4())
        assert "tenant_id" in _where(db.captured[0])

    async def test_admin_scope_no_filter(self):
        """Admin (NIL UUID) widzi wszystko — scope=None."""
        db = _CaptureDB(scope=None, scalar=MagicMock())
        await _get_active_project(db, uuid.uuid4())
        assert "tenant_id" not in _where(db.captured[0])


class TestUploadServiceChokePoint:
    async def test_get_active_project_filters_tenant(self):
        db = _CaptureDB(scope=TENANT_B, scalar=None)
        with pytest.raises(NotFoundError):
            await get_active_project(db, uuid.uuid4())
        assert "tenant_id" in _where(db.captured[0])

    async def test_get_active_project_system_flow_no_filter(self):
        db = _CaptureDB(scalar=MagicMock())
        await get_active_project(db, uuid.uuid4())
        assert "tenant_id" not in _where(db.captured[0])


class TestScopeRecording:
    """db.info["tenant_scope"] zapisywany przez kontekst żądania."""

    def test_set_rls_tenant_records_scope(self):
        from app.core.constants import NIL_UUID
        from app.core.dependencies import _set_rls_tenant

        db = MagicMock()
        db.execute = AsyncMock()
        db.info = {}

        import asyncio

        asyncio.run(_set_rls_tenant(db, TENANT_A))
        assert db.info["tenant_scope"] == TENANT_A

        asyncio.run(_set_rls_tenant(db, uuid.uuid4()))  # zwykły tenant
        assert db.info["tenant_scope"] != str(NIL_UUID)

        asyncio.run(_set_rls_tenant(db, NIL_UUID))  # admin → bez filtra
        assert db.info["tenant_scope"] is None
