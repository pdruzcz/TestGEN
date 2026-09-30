"""End-to-end tests for preprocessing flow — upload, preprocess, report, classify."""

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.user_tenant import TenantRole
from tests.factories import make_tenant, make_user, make_user_tenant


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def owner_user():
    tenant = make_tenant(name="Company A")
    user = make_user(email="owner@companya.com", name="Owner A")
    ut = make_user_tenant(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER)
    user._user_tenant = ut
    user._tenant_id = tenant.id
    user._role = "owner"
    return user


@pytest.fixture()
def mock_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture()
async def client(app, owner_user, mock_db):
    async def _override_get_current_user():
        return owner_user

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestFullPreprocessingFlow:
    """AC1-AC7: Full flow — preprocess → report → classify."""

    @patch("app.api.routes.projects.preprocessing_detect_language")
    async def test_preprocess_returns_202_with_task_id(self, mock_task, client, mock_db):
        project_id = uuid.uuid4()
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.is_deleted = False
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_project
        mock_db.execute.return_value = result

        mock_task.delay.return_value = MagicMock(id="task-abc-123")

        response = await client.post(f"/api/v1/projects/{project_id}/preprocess")

        assert response.status_code == 202
        body = response.json()
        assert body["task_id"] == "task-abc-123"
        assert body["status"] == "pending"
        assert "status_url" in body

    @patch("app.services.project.preprocessing_service.get_redis", new_callable=AsyncMock)
    async def test_preprocessing_report_returns_cached_data(self, mock_get_redis, client):
        project_id = uuid.uuid4()
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        report_data = json.dumps(
            {
                "project_id": str(project_id),
                "languages": [
                    {"language": "python", "count": 10, "loc": 2500},
                    {"language": "javascript", "count": 5, "loc": 800},
                ],
                "detected_frameworks": ["pytest", "jest"],
                "total_loc": 3300,
                "unknown_files": [{"filename": "readme.xyz", "file_id": str(uuid.uuid4())}],
            }
        )
        mock_redis.get.return_value = report_data

        response = await client.get(f"/api/v1/projects/{project_id}/preprocessing-report")

        assert response.status_code == 200
        body = response.json()
        assert body.get("total_loc") == 3300 or body.get("totalLoc") == 3300
        assert len(body.get("languages", [])) == 2
        frameworks = body.get("detected_frameworks", body.get("detectedFrameworks", []))
        assert "pytest" in frameworks
        unknown = body.get("unknown_files", body.get("unknownFiles", []))
        assert len(unknown) == 1
        assert unknown[0].get("filename") == "readme.xyz" or unknown[0].get("filename") == "readme.xyz"

    async def test_manual_classification_updates_language(self, client, mock_db):
        project_id = uuid.uuid4()
        file_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_sf = MagicMock()
        mock_sf.id = file_id
        mock_sf.project_id = project_id
        mock_sf.tenant_id = tenant_id
        mock_sf.filename = "mystery_file"
        mock_sf.original_path = None
        mock_sf.file_size = 500
        mock_sf.mime_type = "text/plain"
        mock_sf.sha256_hash = "def456"
        mock_sf.detected_language = "unknown"
        mock_sf.detected_framework = None
        mock_sf.requires_manual_classification = True
        mock_sf.loc_count = 0
        mock_sf.is_cleaned_up = False
        mock_sf.created_at = None
        mock_sf.updated_at = None
        mock_sf.file_category = None
        mock_sf.doc_format = None
        mock_sf.page_count = None
        # Processing lifecycle + klasyfikacja (późniejsze rozszerzenia
        # SourceFileResponse) — bez jawnego ustawienia atrybuty zostają
        # MagicMock-iem i walidacja odpowiedzi (str) failsuje.
        mock_sf.processing_status = "ready"
        mock_sf.error_message = None
        mock_sf.doc_type = None
        mock_sf.classification_confidence = None
        mock_sf.classification_justification = None

        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_sf
        mock_db.execute.return_value = result

        response = await client.patch(
            f"/api/v1/projects/{project_id}/source-files/{file_id}",
            json={"detected_language": "python"},
        )

        assert response.status_code == 200
        assert mock_sf.detected_language == "python"
        assert mock_sf.requires_manual_classification is False


class TestArchiveFiltering:
    """AC3: Archive extraction filters excluded dirs."""

    def test_excluded_dirs_list(self):
        from app.services.project.archive_extractor import EXCLUDED_DIRS

        assert "node_modules" in EXCLUDED_DIRS
        assert ".git" in EXCLUDED_DIRS
        assert "__pycache__" in EXCLUDED_DIRS
        assert "build" in EXCLUDED_DIRS
        assert "dist" in EXCLUDED_DIRS
        assert ".venv" in EXCLUDED_DIRS
        assert "venv" in EXCLUDED_DIRS
        assert "target" in EXCLUDED_DIRS
        assert "bin" in EXCLUDED_DIRS
        assert "obj" in EXCLUDED_DIRS

    def test_excluded_extensions_list(self):
        from app.services.project.archive_extractor import EXCLUDED_EXTENSIONS

        assert ".exe" in EXCLUDED_EXTENSIONS
        assert ".dll" in EXCLUDED_EXTENSIONS
        assert ".so" in EXCLUDED_EXTENSIONS
        assert ".dylib" in EXCLUDED_EXTENSIONS


class TestLanguageDetection:
    """AC1: Language detection for minimum 5 languages."""

    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("main.py", "python"),
            ("App.java", "java"),
            ("index.js", "javascript"),
            ("app.ts", "typescript"),
            ("Program.cs", "csharp"),
            ("main.c", "cpp"),
            ("utils.cpp", "cpp"),
        ],
    )
    def test_detects_minimum_languages(self, filename, expected):
        from app.services.project.language_detector import LanguageDetector

        detector = LanguageDetector()
        assert detector.detect(filename, "") == expected

    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("server.go", "go"),
            ("app.rb", "ruby"),
            ("index.php", "php"),
            ("ViewController.swift", "swift"),
            ("MainActivity.kt", "kotlin"),
        ],
    )
    def test_detects_future_languages(self, filename, expected):
        from app.services.project.language_detector import LanguageDetector

        detector = LanguageDetector()
        assert detector.detect(filename, "") == expected


class TestFrameworkDetection:
    """AC2: Framework detection for all major ecosystems."""

    @pytest.mark.parametrize(
        "language, config_file, content, expected",
        [
            ("python", "requirements.txt", "pytest\n", "pytest"),
            ("javascript", "package.json", '{"devDependencies": {"jest": "^29"}}', "jest"),
            (
                "java",
                "pom.xml",
                "<dependencies><dependency><groupId>org.junit.jupiter</groupId></dependency></dependencies>",
                "junit5",
            ),
            ("csharp", "app.csproj", '<PackageReference Include="xunit" Version="2.4" />', "xunit"),
            ("cpp", "CMakeLists.txt", "find_package(GTest REQUIRED)", "gtest"),
        ],
    )
    def test_detects_frameworks(self, tmp_path, language, config_file, content, expected):
        from app.services.project.framework_detector import FrameworkDetector

        path = os.path.join(str(tmp_path), config_file)
        with open(path, "w") as f:
            f.write(content)

        detector = FrameworkDetector()
        assert detector.detect_framework(str(tmp_path), language) == expected
