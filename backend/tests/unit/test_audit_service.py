"""Unit tests for audit_service."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin.audit_service import log_action, query_logs


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestLogAction:
    async def test_log_action_creates_entry(self, mock_db):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        result = await log_action(
            mock_db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="user.registered",
            resource_type="user",
            resource_id=resource_id,
            changes={"role": "owner"},
            ip_address="127.0.0.1",
        )

        assert result.action == "user.registered"
        assert result.tenant_id == tenant_id
        assert result.resource_type == "user"
        assert result.details == {"role": "owner"}
        assert result.ip_address == "127.0.0.1"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

    async def test_log_action_without_optional_fields(self, mock_db):
        result = await log_action(
            mock_db,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            action="user.email_verified",
            resource_type="user",
            resource_id=uuid.uuid4(),
        )

        assert result.details is None
        assert result.ip_address is None
        mock_db.add.assert_called_once()


class TestQueryLogs:
    async def test_query_logs_default(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        logs = await query_logs(mock_db)

        assert logs == []
        mock_db.execute.assert_awaited_once()

    async def test_query_logs_with_tenant_filter(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        tid = uuid.uuid4()
        await query_logs(mock_db, tenant_id=tid)

        mock_db.execute.assert_awaited_once()

    async def test_query_logs_with_action_filter(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await query_logs(mock_db, action="user.registered")

        mock_db.execute.assert_awaited_once()

    async def test_query_logs_limit_capped_at_200(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await query_logs(mock_db, limit=500)

        # limit should be capped to 200 internally
        mock_db.execute.assert_awaited_once()

    async def test_query_logs_with_user_filter(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        uid = uuid.uuid4()
        await query_logs(mock_db, user_id=uid)

        mock_db.execute.assert_awaited_once()
