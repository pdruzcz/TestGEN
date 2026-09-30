"""Integration tests for the real diagram↔code comparison (Story 3.4 closure).

These exercise the full ``compare-code`` route with the REAL
``LogicStructuresCodeProvider`` (mapping a controlled ``logic_structures`` seed)
and the REAL ``DiagramCodeComparator``. Only the data sources
(``get_uml_diagram`` / ``get_parsed_model`` / ``fetch_logic_structures``) are
patched — the comparison path itself is not stubbed (AC4 / AC5).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.uml_diagram import DiagramType
from tests.factories import make_user

_FETCH = "app.services.analysis.uml.code_structure_provider.fetch_logic_structures"


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


def _override_auth(app, user):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = uuid.uuid4()

    async def override_user(request: Request):
        # request.state.tenant_id — źródło dla get_tenant (require_feature 7.13).
        request.state.tenant_id = _tenant_id
        return user

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db


def _diagram_elements():
    """A CLASS diagram: Account (partial match) + Ghost (diagram-only)."""
    return [
        {
            "element_kind": "class",
            "name": "Account",
            "is_abstract": False,
            "package": None,
            "attributes": [
                {"name": "balance", "type": "Decimal"},
                {"name": "owner", "type": "String"},
            ],
            "methods": [
                {"name": "deposit", "parameters": [], "return_type": "void"},
                {"name": "withdraw", "parameters": [], "return_type": "void"},
            ],
        },
        {
            "element_kind": "class",
            "name": "Ghost",
            "is_abstract": False,
            "package": None,
            "attributes": [],
            "methods": [],
        },
    ]


def _logic_structures_payload():
    """Code side: Account (with discrepancies) + Extra (code-only)."""
    return {
        "classes": [
            {
                "name": "Account",
                "is_interface": False,
                "attributes": [{"name": "balance", "type": "int", "visibility": "private"}],
                "methods": [{"name": "deposit", "parameters": [], "return_type": "None"}],
            },
            {"name": "Extra", "is_interface": False, "attributes": [], "methods": []},
        ],
        "functions": [],
        "modules": [],
    }


def _parsed_class(elements):
    parsed = MagicMock()
    parsed.model_type = DiagramType.CLASS
    parsed.elements = elements
    parsed.relationships = []
    parsed.fragments = []
    return parsed


class TestCompareCodeRealComparison:
    """AC4 — real comparison against seeded logic_structures."""

    async def test_real_comparison_matches_and_discrepancies(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id

        with (
            patch("app.api.routes.uml.get_uml_diagram", new_callable=AsyncMock, return_value=diagram),
            patch(
                "app.api.routes.uml.get_parsed_model",
                new_callable=AsyncMock,
                return_value=_parsed_class(_diagram_elements()),
            ),
            patch(_FETCH, new_callable=AsyncMock, return_value=_logic_structures_payload()),
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/{diagram_id}/compare-code",
                json={},
            )

        assert response.status_code == 200
        body = response.json()
        app.dependency_overrides = {}

        # Account matches by name (real mapping from logic_structures).
        assert [m["diagram_class"] for m in body["matching_classes"]] == ["Account"]

        # Ghost is diagram-only; Extra exists only in code.
        assert body["diagram_only_classes"] == ["Ghost"]
        assert body["code_only_classes"] == ["Extra"]

        kinds = {d["type"] for d in body["discrepancies"]}
        assert "type_mismatch" in kinds  # balance: Decimal (diagram) vs int (code)
        assert "missing_attribute" in kinds  # owner present on diagram, absent in code
        assert "missing_method" in kinds  # withdraw on diagram, absent in code
        assert "missing_in_code" in kinds  # Ghost
        assert "extra_in_code" in kinds  # Extra


class TestCompareCodeFallback:
    """AC5 — no logic_structures analysis → empty code structure, diagram-only."""

    async def test_no_code_analysis_reports_diagram_only(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        diagram = MagicMock()
        diagram.id = diagram_id

        with (
            patch("app.api.routes.uml.get_uml_diagram", new_callable=AsyncMock, return_value=diagram),
            patch(
                "app.api.routes.uml.get_parsed_model",
                new_callable=AsyncMock,
                return_value=_parsed_class(_diagram_elements()),
            ),
            patch(_FETCH, new_callable=AsyncMock, return_value=None),
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/{diagram_id}/compare-code",
                json={},
            )

        assert response.status_code == 200
        body = response.json()
        app.dependency_overrides = {}

        assert body["matching_classes"] == []
        assert body["code_only_classes"] == []
        assert sorted(body["diagram_only_classes"]) == ["Account", "Ghost"]
