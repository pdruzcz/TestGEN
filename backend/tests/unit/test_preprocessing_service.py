"""Unit tests for PreprocessingService."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.project.preprocessing_service import PreprocessingService


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture()
def service():
    return PreprocessingService()


def _make_source_file(
    filename: str = "main.py",
    detected_language: str | None = None,
    project_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
):
    sf = MagicMock()
    sf.id = uuid.uuid4()
    sf.filename = filename
    sf.project_id = project_id or uuid.uuid4()
    sf.tenant_id = tenant_id or uuid.uuid4()
    sf.detected_language = detected_language
    sf.detected_framework = None
    sf.requires_manual_classification = False
    sf.loc_count = 0
    sf.storage_key = f"tenant/{sf.project_id}/{filename}"
    sf.file_size = 100
    return sf


class TestRunPreprocessing:
    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    async def test_detects_languages_and_frameworks(self, mock_get_redis, service, mock_db):
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        sf1 = _make_source_file("main.py", project_id=project_id, tenant_id=tenant_id)
        sf2 = _make_source_file("app.js", project_id=project_id, tenant_id=tenant_id)
        sf3 = _make_source_file("readme.xyz", project_id=project_id, tenant_id=tenant_id)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [sf1, sf2, sf3]
        mock_db.execute.return_value = result_mock

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        with patch.object(
            service,
            "_read_file_content",
            new_callable=AsyncMock,
            side_effect=[
                "def hello():\n    pass\n",
                "const x = 1;\nconsole.log(x);\n",
                "\x00\x01binary",
            ],
        ):
            report = await service.run_preprocessing(mock_db, project_id)

        assert report is not None
        assert report.total_loc > 0
        assert len(report.unknown_files) == 1
        assert report.unknown_files[0].filename == "readme.xyz"
        assert report.unknown_files[0].file_id == sf3.id
        mock_db.flush.assert_called()

    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    async def test_empty_project_returns_empty_report(self, mock_get_redis, service, mock_db):
        project_id = uuid.uuid4()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result_mock

        report = await service.run_preprocessing(mock_db, project_id)

        assert report.total_loc == 0
        assert report.languages == []
        assert report.detected_frameworks == []


class TestCountLoc:
    def test_counts_non_empty_lines(self, service):
        content = "def hello():\n\n    pass\n\n# comment\n"
        assert service._count_loc(content) == 3

    def test_empty_content(self, service):
        assert service._count_loc("") == 0

    def test_only_blank_lines(self, service):
        assert service._count_loc("\n\n\n") == 0


class TestEstimateLoc:
    def test_estimates_from_file_size(self, service):
        assert service._estimate_loc(3000) == 100

    def test_zero_size(self, service):
        assert service._estimate_loc(0) == 0

    def test_minimum_one_loc(self, service):
        assert service._estimate_loc(10) >= 1


class TestGetPreprocessingReport:
    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    async def test_returns_cached_report(self, mock_get_redis, service):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"project_id": "00000000-0000-0000-0000-000000000001", "languages": [], "detected_frameworks": [], "total_loc": 0, "unknown_files": []}'
        mock_get_redis.return_value = mock_redis

        report = await service.get_cached_report(uuid.uuid4())
        assert report is not None
        assert report.total_loc == 0

    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    async def test_returns_none_when_not_cached(self, mock_get_redis, service):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        report = await service.get_cached_report(uuid.uuid4())
        assert report is None


class TestPrepareProjectDir:
    async def test_data_category_composer_json_is_materialized(self, service):
        """Story 1.6-zakańczenie — uploaded ``composer.json`` must land on disk
        for FrameworkDetector even though its category is DATA: config-file
        selection is by *filename*, not by category, and must stay that way
        (a future ``file_category == CODE`` filter would silently break PHP
        framework detection)."""
        import os
        import shutil

        from app.models.source_file import FileCategory

        sf = _make_source_file(filename="composer.json")
        sf.file_category = FileCategory.DATA
        sf.original_path = "composer.json"

        async def fake_read(_sf):
            return '{"require-dev": {"phpunit/phpunit": "^10"}}'

        service._read_file_content = fake_read
        project_dir = await service._prepare_project_dir([sf])
        try:
            assert project_dir is not None
            assert os.path.isfile(os.path.join(project_dir, "composer.json"))
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)
