"""Integration tests for preprocessing API endpoints."""

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


class TestPreprocessEndpoint:
    @patch("app.api.routes.projects.preprocessing_detect_language")
    async def test_post_preprocess_returns_202(self, mock_task, client, mock_db):
        mock_task.delay.return_value = MagicMock(id="task-uuid-123")

        project_id = uuid.uuid4()
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.is_deleted = False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_project
        mock_db.execute.return_value = mock_result

        response = await client.post(f"/api/v1/projects/{project_id}/preprocess")

        assert response.status_code == 202
        body = response.json()
        assert "task_id" in body
        assert body["status"] == "pending"
        mock_task.delay.assert_called_once()

    async def test_post_preprocess_project_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.post(f"/api/v1/projects/{uuid.uuid4()}/preprocess")

        assert response.status_code == 404


class TestPreprocessingReportEndpoint:
    @patch("app.api.routes.projects.PreprocessingService")
    async def test_get_report_returns_cached(self, mockservice, client):
        mock_service_instance = MagicMock()
        from app.services.project.preprocessing_service import PreprocessingReport

        report = PreprocessingReport(
            project_id=uuid.uuid4(),
            languages=[],
            detected_frameworks=[],
            total_loc=0,
            unknown_files=[],
        )
        mock_service_instance.get_cached_report = AsyncMock(return_value=report)
        mockservice.return_value = mock_service_instance

        response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/preprocessing-report")

        assert response.status_code == 200

    @patch("app.api.routes.projects.PreprocessingService")
    async def test_get_report_not_found(self, mockservice, client):
        mock_service = MagicMock()
        mock_service.get_cached_report = AsyncMock(return_value=None)
        mockservice.return_value = mock_service

        response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/preprocessing-report")

        assert response.status_code == 404


class TestPatchSourceFile:
    async def test_patch_classify_language(self, client, mock_db):
        project_id = uuid.uuid4()
        file_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_sf = MagicMock()
        mock_sf.id = file_id
        mock_sf.project_id = project_id
        mock_sf.tenant_id = tenant_id
        mock_sf.filename = "unknown_file"
        mock_sf.original_path = None
        mock_sf.file_size = 100
        mock_sf.mime_type = "text/plain"
        mock_sf.sha256_hash = "abc123"
        mock_sf.detected_language = "python"
        mock_sf.detected_framework = None
        mock_sf.requires_manual_classification = False
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
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sf
        mock_db.execute.return_value = mock_result

        response = await client.patch(
            f"/api/v1/projects/{project_id}/source-files/{file_id}",
            json={"detected_language": "python"},
        )

        assert response.status_code == 200

    async def test_patch_source_file_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.patch(
            f"/api/v1/projects/{uuid.uuid4()}/source-files/{uuid.uuid4()}",
            json={"detected_language": "python"},
        )

        assert response.status_code == 404
