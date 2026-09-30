"""Integration tests for Story 3.1 UML upload + listing routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import NotFoundError, QuotaExceededError
from app.main import create_app
from app.models.uml_diagram import DiagramType, UMLDiagramStatus, UMLFormat, UMLModelSource
from app.services.analysis.uml.upload_service import (
    UMLFileAcceptance,
    UMLUploadOutcome,
)
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


def _make_accepted(filename: str = "seq.puml") -> UMLFileAcceptance:
    diagram = MagicMock()
    diagram.id = uuid.uuid4()
    diagram.tenant_id = uuid.uuid4()
    return UMLFileAcceptance(
        diagram=diagram,
        filename=filename,
        format=UMLFormat.PLANTUML,
        status="accepted",
    )


def _make_rejected(filename: str = "bad.txt") -> UMLFileAcceptance:
    return UMLFileAcceptance(
        diagram=None,
        filename=filename,
        format=None,
        status="rejected",
        rejection_reason="Nieobsługiwane rozszerzenie.",
    )


class TestUploadUmlRoute:
    async def test_upload_returns_202_with_split_lists(self, client, app):
        """AC: upload returns 202 with accepted/rejected breakdown + task id."""
        user = make_user()
        _override_auth(app, user)
        outcome = UMLUploadOutcome(
            accepted=[_make_accepted()],
            rejected=[_make_rejected()],
        )
        project_id = uuid.uuid4()

        with (
            patch(
                "app.api.routes.uml.upload_uml",
                new_callable=AsyncMock,
                return_value=outcome,
            ),
            patch("app.api.routes.uml.parse_uml_diagram.delay") as delay_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-123")
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/upload",
                files=[
                    ("files", ("seq.puml", b"@startuml\n@enduml", "text/plain")),
                    ("files", ("bad.txt", b"nope", "text/plain")),
                ],
            )

        assert response.status_code == 202
        body = response.json()
        assert body["total_accepted"] == 1
        assert body["total_rejected"] == 1
        assert body["accepted"][0]["task_id"] == "task-123"
        assert body["rejected"][0]["status"] == "rejected"
        delay_mock.assert_called_once()
        app.dependency_overrides = {}

    async def test_upload_quota_exceeded_returns_429(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uml.upload_uml",
            new_callable=AsyncMock,
            side_effect=QuotaExceededError("File size limit (100MB) exceeded for Basic plan"),
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/uml/upload",
                files=[("files", ("huge.xmi", b"<xmi/>", "text/xml"))],
            )

        assert response.status_code == 429
        assert "Basic plan" in response.json()["detail"]
        app.dependency_overrides = {}

    async def test_upload_nonexistent_project_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uml.upload_uml",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Project not found"),
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/uml/upload",
                files=[("files", ("a.puml", b"@startuml\n@enduml", "text/plain"))],
            )

        assert response.status_code == 404
        app.dependency_overrides = {}


class TestListUmlRoute:
    async def test_list_returns_diagrams_and_total(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = uuid.uuid4()
        diagram.project_id = project_id
        diagram.filename = "seq.puml"
        diagram.format = UMLFormat.PLANTUML
        diagram.diagram_type = DiagramType.SEQUENCE
        diagram.status = UMLDiagramStatus.COMPLETED
        diagram.file_size = 42
        diagram.created_at = None

        with patch(
            "app.api.routes.uml.list_uml_diagrams",
            new_callable=AsyncMock,
            return_value=([diagram], 1),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/uml")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["diagrams"][0]["filename"] == "seq.puml"
        app.dependency_overrides = {}


class TestGetUmlRoute:
    async def test_get_returns_diagram_with_parsed_model(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id
        diagram.project_id = project_id
        diagram.filename = "model.xmi"
        diagram.format = UMLFormat.XMI
        diagram.diagram_type = DiagramType.CLASS
        diagram.status = UMLDiagramStatus.COMPLETED
        diagram.file_size = 100
        diagram.created_at = None

        parsed = MagicMock()
        parsed.model_type = DiagramType.CLASS
        parsed.participants = [{"name": "Account", "participant_type": "Class"}]
        parsed.elements = [{"name": "Account"}]
        parsed.relationships = []
        parsed.fragments = []
        parsed.flows = []
        parsed.source = UMLModelSource.PARSER
        parsed.confidence = None

        with (
            patch(
                "app.api.routes.uml.get_uml_diagram",
                new_callable=AsyncMock,
                return_value=diagram,
            ),
            patch(
                "app.api.routes.uml.get_parsed_model",
                new_callable=AsyncMock,
                return_value=parsed,
            ),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/uml/{diagram_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["diagram"]["filename"] == "model.xmi"
        assert body["parsed_model"]["diagram_type"] == "class"
        app.dependency_overrides = {}

    async def test_get_missing_diagram_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uml.get_uml_diagram",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/uml/{uuid.uuid4()}")

        assert response.status_code == 404
        app.dependency_overrides = {}
