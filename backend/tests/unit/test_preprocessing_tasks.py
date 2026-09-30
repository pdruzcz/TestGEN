"""Unit tests for preprocessing Celery task."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestPreprocessImpl:
    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    @patch(
        "app.services.project.preprocessing_service.PreprocessingService._read_file_content",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("app.core.database.task_session")
    async def test_task_runs_preprocessing(self, mock_ses_factory, mock_read, mock_redis, mock_session):
        mock_ses_factory.return_value = _mock_session_ctx(mock_session)

        sf = MagicMock()
        sf.id = uuid.uuid4()
        sf.filename = "readme.txt"
        sf.project_id = uuid.uuid4()
        sf.tenant_id = uuid.uuid4()
        sf.detected_language = None
        sf.detected_framework = None
        sf.requires_manual_classification = False
        sf.loc_count = 0
        sf.file_size = 100

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [sf]
        mock_session.execute.side_effect = [
            MagicMock(),  # SET LOCAL
            MagicMock(),  # update(PROCESSING)
            result_mock,  # select(SourceFile) inside run_preprocessing
            MagicMock(),  # update(READY)
        ]

        mock_redis_inst = AsyncMock()
        mock_redis.return_value = mock_redis_inst

        from app.workers.tasks.preprocessing_tasks import _preprocess_impl

        project_id = uuid.uuid4()
        tenant_id = sf.tenant_id
        result = await _preprocess_impl(str(project_id), str(tenant_id))

        assert result["status"] == "completed"
        assert "project_id" in result

    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    @patch("app.core.database.task_session")
    async def test_task_handles_empty_project(self, mock_ses_factory, mock_redis, mock_session):
        mock_ses_factory.return_value = _mock_session_ctx(mock_session)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [
            MagicMock(),  # SET LOCAL
            MagicMock(),  # update(PROCESSING)
            result_mock,  # select(SourceFile) → empty (inside run_preprocessing)
            MagicMock(),  # update(READY)
        ]

        mock_redis_inst = AsyncMock()
        mock_redis.return_value = mock_redis_inst

        from app.workers.tasks.preprocessing_tasks import _preprocess_impl

        result = await _preprocess_impl(str(uuid.uuid4()), str(uuid.uuid4()))

        assert result["status"] == "completed"
        assert result["total_loc"] == 0
