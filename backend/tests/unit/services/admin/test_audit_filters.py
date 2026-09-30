"""Testy filtrów logu audytu — Story 6.15, Task 10 (AC6)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin.audit_service import count_logs, list_actions, query_logs


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _scalars(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _scalar(value) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = value
    return result


class TestQueryLogsFilters:
    async def test_filtr_zakresu_dat(self, mock_db):
        mock_db.execute.return_value = _scalars([])

        logs = await query_logs(
            mock_db,
            date_from=datetime(2026, 1, 1, tzinfo=UTC),
            date_to=datetime(2026, 2, 1, tzinfo=UTC),
        )

        assert logs == []
        stmt = mock_db.execute.await_args.args[0]
        assert "created_at >=" in str(stmt.whereclause)
        assert "created_at <=" in str(stmt.whereclause)

    async def test_filtr_typu_zasobu(self, mock_db):
        mock_db.execute.return_value = _scalars([])

        await query_logs(mock_db, resource_type="tenant")

        stmt = mock_db.execute.await_args.args[0]
        assert "resource_type" in str(stmt.whereclause)

    async def test_laczy_wiele_filtrow(self, mock_db):
        mock_db.execute.return_value = _scalars([])

        await query_logs(
            mock_db,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            action="user.blocked",
            resource_type="user",
            date_from=datetime(2026, 1, 1, tzinfo=UTC),
        )

        clause = str(mock_db.execute.await_args.args[0].whereclause)
        for column in ("tenant_id", "user_id", "action", "resource_type", "created_at"):
            assert column in clause

    async def test_brak_filtrow_nie_dodaje_warunkow(self, mock_db):
        mock_db.execute.return_value = _scalars([])

        await query_logs(mock_db)

        assert mock_db.execute.await_args.args[0].whereclause is None


class TestCountLogs:
    async def test_zwraca_liczbe_wpisow(self, mock_db):
        mock_db.execute.return_value = _scalar(42)

        total = await count_logs(mock_db)

        assert total == 42

    async def test_zwraca_zero_gdy_brak_wyniku(self, mock_db):
        mock_db.execute.return_value = _scalar(None)

        assert await count_logs(mock_db) == 0

    async def test_uwzglednia_te_same_filtry_co_query_logs(self, mock_db):
        mock_db.execute.return_value = _scalar(0)

        await count_logs(mock_db, action="platform.config_updated", resource_type="platform_config")

        clause = str(mock_db.execute.await_args.args[0].whereclause)
        assert "action" in clause
        assert "resource_type" in clause


class TestListActions:
    async def test_zwraca_posortowane_unikalne_akcje(self, mock_db):
        mock_db.execute.return_value = _scalars(["user.blocked", "tenant.plan_changed"])

        actions = await list_actions(mock_db)

        assert actions == ["tenant.plan_changed", "user.blocked"]
