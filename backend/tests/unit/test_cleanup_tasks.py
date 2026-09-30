"""Unit tests for the source-file cleanup Celery task (Story 1.6 — AC4)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_source_file(sf_id=None, storage_key="t/p/f.py"):
    sf = MagicMock()
    sf.id = sf_id or uuid.uuid4()
    sf.tenant_id = uuid.uuid4()
    sf.project_id = uuid.uuid4()
    sf.storage_key = storage_key
    sf.is_cleaned_up = False
    return sf


def _mock_session_ctx(mock_session):
    """Build a mock async context manager mimicking ``task_session()``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.fixture()
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestCleanupImpl:
    @patch("app.core.storage.delete_file")
    @patch("app.core.database.task_session")
    async def test_marks_cleaned_up_after_minio_delete(self, mock_ses_factory, mock_delete, mock_session):
        mock_ses_factory.return_value = _mock_session_ctx(mock_session)

        sf = _make_source_file()
        tenant_id = uuid.uuid4()

        tenant_result = MagicMock()
        tenant_result.scalars.return_value.all.return_value = [tenant_id]

        sf_result = MagicMock()
        sf_result.scalars.return_value.all.return_value = [sf]

        mock_session.execute = AsyncMock(
            side_effect=[
                tenant_result,  # select(Tenant.id)
                MagicMock(),  # SET LOCAL
                MagicMock(rowcount=0),  # delete(AnonymizationMap) — Story 1.54
                sf_result,  # select(SourceFile)...
                MagicMock(),  # update(SourceFile)...
            ]
        )

        from app.workers.tasks.cleanup_tasks import _cleanup_source_files_impl

        result = await _cleanup_source_files_impl()

        assert result["removed"] == 1
        assert result["failed"] == 0
        assert result["scanned"] == 1
        assert result["mappings_removed"] == 0
        mock_delete.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("app.core.storage.delete_file")
    @patch("app.core.database.task_session")
    async def test_counts_failed_when_minio_delete_raises(self, mock_ses_factory, mock_delete, mock_session):
        mock_ses_factory.return_value = _mock_session_ctx(mock_session)

        sf = _make_source_file()
        tenant_id = uuid.uuid4()

        tenant_result = MagicMock()
        tenant_result.scalars.return_value.all.return_value = [tenant_id]

        sf_result = MagicMock()
        sf_result.scalars.return_value.all.return_value = [sf]

        mock_session.execute = AsyncMock(
            side_effect=[
                tenant_result,
                MagicMock(),
                MagicMock(rowcount=0),
                sf_result,
            ]
        )

        mock_delete.side_effect = OSError("connection refused")

        from app.workers.tasks.cleanup_tasks import _cleanup_source_files_impl

        result = await _cleanup_source_files_impl()

        assert result["removed"] == 0
        assert result["failed"] == 1
        assert result["mappings_removed"] == 0

    @patch("app.core.storage.delete_file")
    @patch("app.core.database.task_session")
    async def test_no_tenants_returns_empty(self, mock_ses_factory, mock_delete, mock_session):
        mock_ses_factory.return_value = _mock_session_ctx(mock_session)

        tenant_result = MagicMock()
        tenant_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(return_value=tenant_result)

        from app.workers.tasks.cleanup_tasks import _cleanup_source_files_impl

        result = await _cleanup_source_files_impl()

        assert result["removed"] == 0
        assert result["failed"] == 0
        assert result["scanned"] == 0
        assert result["mappings_removed"] == 0
        mock_delete.assert_not_called()

    @patch("app.core.storage.delete_file")
    @patch("app.core.database.task_session")
    async def test_deletes_anonymization_mappings(self, mock_ses_factory, mock_delete, mock_session):
        """Story 1.54 (FR72): mappingi kasowane razem z kodem (retencja/terminal)."""
        mock_ses_factory.return_value = _mock_session_ctx(mock_session)

        tenant_id = uuid.uuid4()
        tenant_result = MagicMock()
        tenant_result.scalars.return_value.all.return_value = [tenant_id]

        sf_result = MagicMock()
        sf_result.scalars.return_value.all.return_value = []

        map_delete = MagicMock(rowcount=3)

        mock_session.execute = AsyncMock(
            side_effect=[
                tenant_result,  # select(Tenant.id)
                MagicMock(),  # SET LOCAL
                map_delete,  # delete(AnonymizationMap)
                sf_result,  # select(SourceFile) — pusto
            ]
        )

        from app.workers.tasks.cleanup_tasks import _cleanup_source_files_impl

        result = await _cleanup_source_files_impl()

        assert result["mappings_removed"] == 3
        assert result["removed"] == 0
        mock_delete.assert_not_called()
        # DELETE Celery na anonymization_maps (terminal project LUB expires_at)
        delete_call = mock_session.execute.await_args_list[2]
        stmt_sql = str(delete_call.args[0])
        assert "anonymization_maps" in stmt_sql
        assert "expires_at" in stmt_sql
        assert "project_id" in stmt_sql
