"""Integration tests for Story 1.6 upload + git-connect routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import NotFoundError, QuotaExceededError, ValidationError
from app.main import create_app
from app.services.project.git_service import GitConnectOutcome
from app.services.project.upload_service import FileAcceptance, UploadOutcome
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def _override_auth(app, user, tenant_id=None, role="user", is_admin=False):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = role
        request.state.is_admin = is_admin
        return user

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db


def _make_accepted(filename: str = "service.py") -> FileAcceptance:
    mock_source_file = MagicMock()
    mock_source_file.id = uuid.uuid4()
    return FileAcceptance(
        source_file=mock_source_file,
        filename=filename,
        file_size=12,
        mime_type="text/x-python",
        sha256_hash="a" * 64,
        status="accepted",
    )


def _make_rejected(filename: str = "bad.exe") -> FileAcceptance:
    return FileAcceptance(
        source_file=None,
        filename=filename,
        file_size=0,
        mime_type="application/octet-stream",
        sha256_hash=None,
        status="rejected",
        rejection_reason="Unsupported file extension.",
    )


class TestUploadRoute:
    async def test_upload_returns_201_and_split_lists(self, client, app):
        """AC1, AC5: returns 201 with accepted/rejected breakdown."""
        user = make_user()
        _override_auth(app, user)
        outcome = UploadOutcome(
            accepted=[_make_accepted()],
            rejected=[_make_rejected()],
        )
        project_id = uuid.uuid4()

        with patch(
            "app.api.routes.uploads.upload_files",
            new_callable=AsyncMock,
            return_value=outcome,
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/upload",
                files=[
                    ("files", ("service.py", b"print('hi')\n", "text/x-python")),
                    ("files", ("bad.exe", b"MZ", "application/octet-stream")),
                ],
            )

        assert response.status_code == 201
        body = response.json()
        assert body["total_accepted"] == 1
        assert body["total_rejected"] == 1
        assert body["accepted_files"][0]["filename"] == "service.py"
        assert body["rejected_files"][0]["status"] == "rejected"

        app.dependency_overrides = {}

    async def test_upload_quota_exceeded_returns_429(self, client, app):
        """AC2: file too big -> 429."""
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uploads.upload_files",
            new_callable=AsyncMock,
            side_effect=QuotaExceededError("File size limit (100MB) exceeded for Basic plan"),
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/upload",
                files=[("files", ("huge.py", b"x" * 10, "text/x-python"))],
            )

        assert response.status_code == 429
        assert "Basic plan" in response.json()["detail"]
        app.dependency_overrides = {}

    async def test_upload_nonexistent_project_returns_404(self, client, app):
        """AC7: project not found -> 404."""
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uploads.upload_files",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Project not found"),
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/upload",
                files=[("files", ("a.py", b"x", "text/x-python"))],
            )
        assert response.status_code == 404
        app.dependency_overrides = {}

    @pytest.mark.parametrize(
        "role,is_admin",
        [("user", False), ("owner", False), ("user", True)],
    )
    async def test_upload_allowed_for_all_roles(self, client, app, role, is_admin):
        """AC8: every authenticated role can upload (user, owner, admin)."""
        user = make_user(is_admin=is_admin)
        _override_auth(app, user, role=role, is_admin=is_admin)

        outcome = UploadOutcome(accepted=[_make_accepted()], rejected=[])
        with patch(
            "app.api.routes.uploads.upload_files",
            new_callable=AsyncMock,
            return_value=outcome,
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/upload",
                files=[("files", ("a.py", b"x", "text/x-python"))],
            )

        assert response.status_code == 201
        app.dependency_overrides = {}

    async def test_upload_without_auth_returns_401(self, client):
        response = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/upload",
            files=[("files", ("a.py", b"x", "text/x-python"))],
        )
        assert response.status_code == 401


class TestConnectRepoRoute:
    async def test_connect_repo_returns_201(self, client, app):
        """AC3 happy path."""
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch(
            "app.api.routes.uploads.connect_repo",
            new_callable=AsyncMock,
            return_value=GitConnectOutcome(
                duplicates_skipped=0, files_indexed=3, message="Repository connected. 3 files indexed."
            ),
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/connect-repo",
                json={
                    "repo_url": "https://github.com/org/repo.git",
                    "branch": "main",
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["files_indexed"] == 3
        assert body["branch"] == "main"
        app.dependency_overrides = {}

    async def test_connect_repo_rejects_non_https_at_schema(self, client, app):
        """AC3: Pydantic validator blocks non-HTTPS URL -> 422."""
        user = make_user()
        _override_auth(app, user)

        response = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/connect-repo",
            json={"repo_url": "http://github.com/org/repo", "branch": "main"},
        )
        assert response.status_code == 422
        app.dependency_overrides = {}

    async def test_connect_repo_rejects_unknown_host(self, client, app):
        user = make_user()
        _override_auth(app, user)

        response = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/connect-repo",
            json={"repo_url": "https://evil.example.com/repo", "branch": "main"},
        )
        assert response.status_code == 422
        app.dependency_overrides = {}

    async def test_connect_repo_service_error_surfaces_as_rfc7807(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uploads.connect_repo",
            new_callable=AsyncMock,
            side_effect=ValidationError("Git clone failed: not found"),
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/connect-repo",
                json={
                    "repo_url": "https://github.com/org/nope",
                    "branch": "main",
                },
            )

        assert response.status_code == 422
        body = response.json()
        assert "Git clone failed" in body["detail"]
        app.dependency_overrides = {}


class TestListFilesRoute:
    async def test_list_returns_200_and_headers(self, client, app):
        user = make_user()
        _override_auth(app, user)

        source = MagicMock()
        source.id = uuid.uuid4()
        source.project_id = uuid.uuid4()
        source.tenant_id = uuid.uuid4()
        source.filename = "service.py"
        source.original_path = None
        source.file_size = 12
        source.mime_type = "text/x-python"
        source.sha256_hash = "a" * 64
        source.detected_language = None
        source.detected_framework = None
        source.requires_manual_classification = False
        source.loc_count = 0
        source.is_cleaned_up = False
        source.file_category = None
        source.doc_format = None
        source.page_count = None
        source.created_at = None
        source.updated_at = None
        # Processing lifecycle + klasyfikacja (późniejsze rozszerzenia
        # SourceFileResponse) — jawne wartości, inaczej MagicMock failsuje
        # walidację odpowiedzi (str).
        source.processing_status = "ready"
        source.error_message = None
        source.doc_type = None
        source.classification_confidence = None
        source.classification_justification = None

        with patch(
            "app.api.routes.uploads.list_project_files",
            new_callable=AsyncMock,
            return_value=([source], 1),
        ):
            response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/files")

        assert response.status_code == 200
        assert response.headers.get("x-total-count") == "1"
        data = response.json()
        assert data["total"] == 1
        assert data["files"][0]["filename"] == "service.py"
        app.dependency_overrides = {}

    async def test_list_without_auth_returns_401(self, client):
        response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/files")
        assert response.status_code == 401
