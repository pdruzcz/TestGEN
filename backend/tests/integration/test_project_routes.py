"""Integration tests for project API routes.

Routes are tested with mocked auth and service layer to focus on HTTP contract:
status codes, headers, payload shape, RBAC enforcement.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    QuotaExceededError,
)
from app.main import create_app
from app.models.project import ProjectStatus
from tests.factories import make_tenant, make_user


def _make_project(tenant_id: uuid.UUID, name: str = "Sample Project"):
    project = MagicMock()
    project.id = uuid.uuid4()
    project.tenant_id = tenant_id
    project.name = name
    project.description = "desc"
    project.language_hint = "python"
    project.status = ProjectStatus.CREATED.value
    project.created_at = None
    project.updated_at = None
    project.is_deleted = False
    return project


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


class TestCreateProjectRoute:
    async def test_user_create_returns_201_with_location(self, client, app):
        """AC1: POST returns 201 and Location header."""
        user = make_user()
        tenant = make_tenant()
        project = _make_project(tenant.id, "New Proj")
        _override_auth(app, user, tenant_id=tenant.id)

        with patch(
            "app.api.routes.projects.create_project",
            new_callable=AsyncMock,
            return_value=project,
        ):
            response = await client.post(
                "/api/v1/projects",
                json={"name": "New Proj", "description": "desc", "language_hint": "python"},
            )

        assert response.status_code == 201
        assert response.headers["location"] == f"/api/v1/projects/{project.id}"
        data = response.json()
        assert data["name"] == "New Proj"
        assert data["status"] == "created"

        app.dependency_overrides = {}

    async def test_create_empty_name_returns_422(self, client, app):
        """AC7: empty name -> 422."""
        user = make_user()
        _override_auth(app, user)

        response = await client.post("/api/v1/projects", json={"name": ""})
        assert response.status_code == 422

        app.dependency_overrides = {}

    async def test_create_blank_whitespace_name_returns_422(self, client, app):
        """AC7: whitespace-only name -> 422."""
        user = make_user()
        _override_auth(app, user)

        response = await client.post("/api/v1/projects", json={"name": "   "})
        assert response.status_code == 422

        app.dependency_overrides = {}

    async def test_create_too_long_name_returns_422(self, client, app):
        """AC7: name > 255 chars -> 422."""
        user = make_user()
        _override_auth(app, user)

        response = await client.post("/api/v1/projects", json={"name": "x" * 256})
        assert response.status_code == 422

        app.dependency_overrides = {}

    async def test_create_quota_exceeded_returns_429(self, client, app):
        """AC8: quota exceeded -> 429 RFC 7807."""
        user = make_user()
        _override_auth(app, user, role="owner")

        with patch(
            "app.api.routes.projects.create_project",
            new_callable=AsyncMock,
            side_effect=QuotaExceededError("Project limit (10) reached for Basic plan"),
        ):
            response = await client.post("/api/v1/projects", json={"name": "Extra"})

        assert response.status_code == 429
        body = response.json()
        assert body["status"] == 429
        assert "Basic plan" in body["detail"]

        app.dependency_overrides = {}

    async def test_create_duplicate_returns_409(self, client, app):
        user = make_user()
        _override_auth(app, user, role="owner")

        with patch(
            "app.api.routes.projects.create_project",
            new_callable=AsyncMock,
            side_effect=ConflictError("Project with name 'Dup' already exists"),
        ):
            response = await client.post("/api/v1/projects", json={"name": "Dup"})

        assert response.status_code == 409

        app.dependency_overrides = {}


class TestListProjectsRoute:
    async def test_list_returns_200_with_headers(self, client, app):
        """AC2: list returns 200 + X-Total-Count + Link headers."""
        user = make_user()
        tenant = make_tenant()
        projects = [_make_project(tenant.id, f"P{i}") for i in range(3)]
        _override_auth(app, user, tenant_id=tenant.id)

        with patch(
            "app.api.routes.projects.list_projects",
            new_callable=AsyncMock,
            return_value=(projects, 3),
        ):
            response = await client.get("/api/v1/projects")

        assert response.status_code == 200
        assert response.headers.get("x-total-count") == "3"
        assert "link" in response.headers
        data = response.json()
        assert data["total"] == 3
        assert len(data["projects"]) == 3

        app.dependency_overrides = {}

    async def test_list_with_filters_and_pagination(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.projects.list_projects",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_list:
            response = await client.get(
                "/api/v1/projects?page=2&page_size=5&status=active&language=python&sort_by=name&sort_order=asc"
            )

        assert response.status_code == 200
        # Verify query params propagated to service layer
        kwargs = mock_list.call_args.kwargs
        assert kwargs["page"] == 2
        assert kwargs["page_size"] == 5
        assert kwargs["status"] == "active"
        assert kwargs["language"] == "python"
        assert kwargs["sort_by"] == "name"
        assert kwargs["sort_order"] == "asc"

        app.dependency_overrides = {}


class TestGetProjectRoute:
    async def test_get_returns_200(self, client, app):
        """AC3: GET single returns project details."""
        user = make_user()
        tenant = make_tenant()
        project = _make_project(tenant.id)
        _override_auth(app, user, tenant_id=tenant.id)

        with patch(
            "app.api.routes.projects.get_project",
            new_callable=AsyncMock,
            return_value=project,
        ):
            response = await client.get(f"/api/v1/projects/{project.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(project.id)

        app.dependency_overrides = {}

    async def test_get_not_found_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.projects.get_project",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Project not found"),
        ):
            response = await client.get(f"/api/v1/projects/{uuid.uuid4()}")

        assert response.status_code == 404

        app.dependency_overrides = {}


class TestUpdateProjectRoute:
    async def test_owner_can_update(self, client, app):
        """AC4: Owner can update."""
        user = make_user()
        tenant = make_tenant()
        project = _make_project(tenant.id)
        _override_auth(app, user, tenant_id=tenant.id, role="owner")

        with patch(
            "app.api.routes.projects.update_project",
            new_callable=AsyncMock,
            return_value=project,
        ):
            response = await client.put(
                f"/api/v1/projects/{project.id}",
                json={"name": "Updated"},
            )

        assert response.status_code == 200

        app.dependency_overrides = {}

    async def test_admin_can_update(self, client, app):
        user = make_user(is_admin=True)
        tenant = make_tenant()
        project = _make_project(tenant.id)
        _override_auth(app, user, tenant_id=tenant.id, is_admin=True)

        with patch(
            "app.api.routes.projects.update_project",
            new_callable=AsyncMock,
            return_value=project,
        ):
            response = await client.put(
                f"/api/v1/projects/{project.id}",
                json={"description": "Updated desc"},
            )

        assert response.status_code == 200

        app.dependency_overrides = {}

    async def test_regular_user_update_returns_403(self, client, app):
        """AC6: User role cannot update."""
        user = make_user()
        _override_auth(app, user)

        response = await client.put(
            f"/api/v1/projects/{uuid.uuid4()}",
            json={"name": "Updated"},
        )
        assert response.status_code == 403

        app.dependency_overrides = {}

    async def test_update_not_found_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user, role="owner")

        with patch(
            "app.api.routes.projects.update_project",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Project not found"),
        ):
            response = await client.put(
                f"/api/v1/projects/{uuid.uuid4()}",
                json={"name": "X"},
            )

        assert response.status_code == 404

        app.dependency_overrides = {}


class TestDeleteProjectRoute:
    async def test_owner_can_delete_returns_204(self, client, app):
        """AC5: DELETE returns 204 No Content."""
        user = make_user()
        _override_auth(app, user, role="owner")

        with patch(
            "app.api.routes.projects.delete_project",
            new_callable=AsyncMock,
        ):
            response = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")

        assert response.status_code == 204
        assert response.content == b""

        app.dependency_overrides = {}

    async def test_admin_can_delete(self, client, app):
        user = make_user(is_admin=True)
        _override_auth(app, user, is_admin=True)

        with patch(
            "app.api.routes.projects.delete_project",
            new_callable=AsyncMock,
        ):
            response = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")

        assert response.status_code == 204

        app.dependency_overrides = {}

    async def test_regular_user_delete_returns_403(self, client, app):
        """AC6: User role cannot delete."""
        user = make_user()
        _override_auth(app, user)

        response = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")
        assert response.status_code == 403

        app.dependency_overrides = {}

    async def test_delete_not_found_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user, role="owner")

        with patch(
            "app.api.routes.projects.delete_project",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Project not found"),
        ):
            response = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")

        assert response.status_code == 404

        app.dependency_overrides = {}


class TestUnauthenticated:
    async def test_create_without_auth_returns_401(self, client):
        response = await client.post("/api/v1/projects", json={"name": "X"})
        assert response.status_code == 401

    async def test_list_without_auth_returns_401(self, client):
        response = await client.get("/api/v1/projects")
        assert response.status_code == 401


class TestListDocumentsEnrichment:
    """Story 2.3 (AC7): the documents list enriches each file with its latest
    completed classification so the UI chip renders without an extra call."""

    def _auth_with_db(self, app, user, db, tenant_id):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = "user"
            request.state.is_admin = False
            return user

        async def override_db():
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

    async def test_list_includes_classification_fields(self, client, app):
        user = make_user()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        db = AsyncMock()
        doc = SimpleNamespace(
            id=doc_id,
            project_id=project_id,
            tenant_id=tenant_id,
            filename="api.pdf",
            original_path=None,
            file_size=1024,
            mime_type=None,
            sha256_hash="abc",
            detected_language=None,
            detected_framework=None,
            requires_manual_classification=False,
            loc_count=0,
            is_cleaned_up=False,
            created_at=None,
            updated_at=None,
            file_category="documentation",
            doc_format="pdf",
            page_count=3,
            processing_status="ready",
            error_message=None,
        )
        ar = SimpleNamespace(
            source_file_id=doc_id,
            created_at=None,
            result_data={
                "doc_type": "opis_api",
                "confidence": 92.0,
                "reasoning": "REST",
                "source": "native",
            },
        )
        docs_res = MagicMock()
        docs_res.scalars.return_value.all.return_value = [doc]
        cls_res = MagicMock()
        cls_res.scalars.return_value.all.return_value = [ar]
        db.execute.side_effect = [docs_res, cls_res]

        self._auth_with_db(app, user, db, tenant_id)

        with patch("app.api.routes.projects.get_active_project", new=AsyncMock()):
            response = await client.get(f"/api/v1/projects/{project_id}/documents")

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 1
        assert body[0]["doc_type"] == "opis_api"
        assert body[0]["classification_confidence"] == 92.0
        assert body[0]["classification_justification"] == "REST"
        app.dependency_overrides = {}

    async def test_list_without_classification_leaves_fields_null(self, client, app):
        user = make_user()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        db = AsyncMock()
        doc = SimpleNamespace(
            id=doc_id,
            project_id=project_id,
            filename="spec.pdf",
            original_path=None,
            file_size=512,
            mime_type=None,
            sha256_hash="zzz",
            detected_language=None,
            detected_framework=None,
            requires_manual_classification=False,
            loc_count=0,
            is_cleaned_up=False,
            created_at=None,
            updated_at=None,
            file_category="documentation",
            doc_format="pdf",
            page_count=None,
            processing_status="processing",
            error_message=None,
        )
        docs_res = MagicMock()
        docs_res.scalars.return_value.all.return_value = [doc]
        cls_res = MagicMock()
        cls_res.scalars.return_value.all.return_value = []  # no classification
        db.execute.side_effect = [docs_res, cls_res]

        self._auth_with_db(app, user, db, tenant_id)

        with patch("app.api.routes.projects.get_active_project", new=AsyncMock()):
            response = await client.get(f"/api/v1/projects/{project_id}/documents")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body[0]["doc_type"] is None
        assert body[0]["classification_confidence"] is None
        app.dependency_overrides = {}
