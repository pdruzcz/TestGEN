"""Integration tests for Story 3.2 UML parse route (POST /uml/parse)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.uml_diagram import DiagramType, UMLDiagramStatus, UMLFormat, UMLModelSource
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


class TestParseRoute:
    async def test_parse_dispatches_task_returns_202(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id
        diagram.tenant_id = uuid.uuid4()

        with (
            patch(
                "app.api.routes.uml.get_uml_diagram",
                new_callable=AsyncMock,
                return_value=diagram,
            ),
            patch("app.api.routes.uml.parse_uml_diagram.delay") as delay_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-xyz")
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/parse",
                json={"diagram_id": str(diagram_id)},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["task_id"] == "task-xyz"
        assert body["status"] == "parsing"
        delay_mock.assert_called_once_with(str(diagram_id), str(diagram.tenant_id))
        app.dependency_overrides = {}

    async def test_parse_missing_diagram_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uml.get_uml_diagram",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/uml/parse",
                json={"diagram_id": str(uuid.uuid4())},
            )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_get_returns_sequence_parsed_model(self, client, app):
        """GET returns parsed sequence model (messages stored in relationships)."""
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id
        diagram.project_id = project_id
        diagram.filename = "seq.puml"
        diagram.format = UMLFormat.PLANTUML
        diagram.diagram_type = DiagramType.SEQUENCE
        diagram.status = UMLDiagramStatus.COMPLETED
        diagram.file_size = 64
        diagram.created_at = None

        parsed = MagicMock()
        parsed.model_type = DiagramType.SEQUENCE
        parsed.participants = [{"name": "User", "alias": "User", "participant_type": "actor"}]
        parsed.elements = []
        parsed.relationships = [
            {"from_alias": "User", "to_alias": "UI", "label": "login", "message_type": "sync", "sequence_number": 0}
        ]
        parsed.fragments = []
        parsed.flows = [{"path_type": "happy", "steps": [], "preconditions": [], "initiating_actor": "User"}]
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
        assert body["parsed_model"]["diagram_type"] == "sequence"
        # Messages live in relationships; test paths in flows.
        assert body["parsed_model"]["relationships"][0]["label"] == "login"
        assert body["parsed_model"]["flows"][0]["path_type"] == "happy"
        app.dependency_overrides = {}


class TestCompareCodeRoute:
    """Integration tests for Story 3.4 compare-code route."""

    async def test_compare_code_returns_comparison(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id

        parsed = MagicMock()
        parsed.model_type = DiagramType.CLASS
        parsed.elements = [
            {
                "element_kind": "class",
                "name": "User",
                "is_abstract": False,
                "attributes": [],
                "methods": [],
                "package": None,
            }
        ]
        parsed.relationships = []
        parsed.fragments = []

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
            patch(
                "app.services.analysis.uml.code_structure_provider.fetch_logic_structures",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/{diagram_id}/compare-code",
                json={},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["diagram_id"] == str(diagram_id)
        # No logic_structures analysis → provider yields no code classes → the
        # diagram class is diagram-only (fallback, AC5).
        assert "User" in body["diagram_only_classes"]
        app.dependency_overrides = {}

    async def test_compare_code_missing_diagram_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uml.get_uml_diagram",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/uml/{uuid.uuid4()}/compare-code",
                json={},
            )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_compare_code_non_class_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id

        parsed = MagicMock()
        parsed.model_type = DiagramType.SEQUENCE

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
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/uml/{diagram_id}/compare-code",
                json={},
            )

        assert response.status_code == 400
        app.dependency_overrides = {}
