"""Integration tests for Story 3.15 traceability matrix routes.

Covers GET /traceability (pagination + summary serialization + provenance
exposure, AC3), POST /traceability/build (202 async dispatch) and GET
/traceability/export. CSV/JSON are native; XLSX/PDF are produced by openpyxl /
reportlab (Story 3-15 closure, AC5 — installed as runtime deps) and additionally
degrade to 501 if the libs are ever absent (defense-in-depth, still tested).
The Celery task and service layer are patched so the tests exercise routing +
serialization only.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.schemas.traceability import (
    CoverageBreakdown,
    TraceabilitySummaryOut,
)
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, tenant_id=None):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()
    user._tenant_id = _tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = "user"
        request.state.is_admin = False
        return user

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _make_entry(name="Logowanie", source_type="uml", status="covered"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_type=source_type,
        source_element_id=uuid.uuid4(),
        source_element_type="use_case",
        source_element_name=name,
        source_diagram_id=uuid.uuid4(),
        source_screenshot_id=None,
        linked_flow_id=uuid.uuid4(),
        linked_gherkin_id=uuid.uuid4(),
        test_case_id=None,
        code_reference="Feature: Logowanie",
        code_framework="gherkin/bdd",
        coverage_status=status,
        created_at=None,
    )


def _make_summary():
    return TraceabilitySummaryOut(
        uml_total=2,
        gui_total=1,
        uml_coverage_pct=50.0,
        gui_coverage_pct=0.0,
        code_coverage_pct=33.3,
        breakdown_per_uml_type=[CoverageBreakdown(key="use_case", total=2, covered=1, partial=0, uncovered=1)],
        breakdown_per_gui_category=[],
    )


class TestGetMatrixRoute:
    async def test_get_paginated_with_summary(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        rows = [_make_entry("A"), _make_entry("B")]

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=(rows, 2))
            instance.get_summary = AsyncMock(return_value=_make_summary())
            response = await client.get(f"/api/v1/projects/{project_id}/traceability?page=1&page_size=20")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["elements"]) == 2
        assert body["summary"]["uml_total"] == 2
        assert body["summary"]["code_coverage_pct"] == 33.3
        app.dependency_overrides = {}

    async def test_get_exposes_provenance(self, client, app):
        # AC3: source/confidence are exposed on each element in the response.
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry("KlasaOCR", source_type="uml", status="covered")
        entry.source = "ocr"
        entry.confidence = 0.55

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            instance.get_summary = AsyncMock(return_value=_make_summary())
            response = await client.get(f"/api/v1/projects/{project_id}/traceability")

        assert response.status_code == 200
        el = response.json()["elements"][0]
        assert el["source"] == "ocr"
        assert el["confidence"] == 0.55
        app.dependency_overrides = {}

    async def test_get_passes_filters(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([], 0))
            instance.get_summary = AsyncMock(return_value=_make_summary())
            response = await client.get(
                f"/api/v1/projects/{project_id}/traceability?source_type=gui&coverage_status=uncovered"
            )

        assert response.status_code == 200
        instance.get_matrix.assert_awaited_once()
        _, kwargs = instance.get_matrix.call_args
        assert kwargs["source_type"] == "gui"
        assert kwargs["coverage_status"] == "uncovered"
        app.dependency_overrides = {}

    async def test_invalid_filter_returns_422(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.get(f"/api/v1/projects/{project_id}/traceability?source_type=bogus")

        assert response.status_code == 422
        app.dependency_overrides = {}


class TestBuildRoute:
    async def test_build_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch("app.api.routes.traceability.build_traceability_matrix.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-7")
            response = await client.post(f"/api/v1/projects/{project_id}/traceability/build")

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-7"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id))
        app.dependency_overrides = {}


class TestExportRoute:
    async def test_export_csv(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry("Logowanie")
        entry.to_dict = lambda: {
            "source_type": "uml",
            "source_element_type": "use_case",
            "source_element_name": "Logowanie",
            "coverage_status": "covered",
            "linked_flow_id": str(entry.linked_flow_id),
            "linked_gherkin_id": str(entry.linked_gherkin_id),
            "test_case_id": None,
            "code_reference": "Feature: Logowanie",
            "code_framework": "gherkin/bdd",
        }

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            response = await client.get(f"/api/v1/projects/{project_id}/traceability/export?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        text = response.content.decode("utf-8")
        assert text.startswith("\ufeff")
        assert "Logowanie" in text
        assert ";" in text
        app.dependency_overrides = {}

    async def test_export_json(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry("Logowanie")
        entry.to_dict = lambda: {"source_element_name": "Logowanie"}

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            response = await client.get(f"/api/v1/projects/{project_id}/traceability/export?format=json")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()[0]["source_element_name"] == "Logowanie"
        app.dependency_overrides = {}

    async def test_export_xlsx_graceful_501_when_lib_absent(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry()
        entry.to_dict = lambda: {"source_element_name": "X"}

        with (
            patch("app.api.routes.traceability.TraceabilityService") as service_cls,
            patch("app.api.routes.traceability._build_xlsx", return_value=None),
        ):
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            response = await client.get(f"/api/v1/projects/{project_id}/traceability/export?format=xlsx")

        assert response.status_code == 501
        app.dependency_overrides = {}

    async def test_export_pdf_graceful_501_when_lib_absent(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry()
        entry.to_dict = lambda: {"source_element_name": "X"}

        with (
            patch("app.api.routes.traceability.TraceabilityService") as service_cls,
            patch("app.api.routes.traceability._build_pdf", return_value=None),
        ):
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            response = await client.get(f"/api/v1/projects/{project_id}/traceability/export?format=pdf")

        assert response.status_code == 501
        app.dependency_overrides = {}

    async def test_export_xlsx_functional(self, client, app):
        # AC5: with openpyxl installed the endpoint returns a real XLSX (not 501).
        pytest.importorskip("openpyxl")
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry("Logowanie")
        entry.to_dict = lambda: {
            "source_type": "uml",
            "source_element_type": "use_case",
            "source_element_name": "Logowanie",
            "coverage_status": "covered",
            "linked_flow_id": None,
            "linked_gherkin_id": None,
            "test_case_id": None,
            "code_reference": "Feature: Logowanie",
            "code_framework": "gherkin/bdd",
        }

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            response = await client.get(f"/api/v1/projects/{project_id}/traceability/export?format=xlsx")

        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        # XLSX is a ZIP archive — starts with the PK magic bytes.
        assert response.content[:2] == b"PK"
        app.dependency_overrides = {}

    async def test_export_pdf_functional(self, client, app):
        # AC5: with reportlab installed the endpoint returns a real PDF (not 501).
        pytest.importorskip("reportlab")
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        entry = _make_entry("Logowanie")
        entry.to_dict = lambda: {"source_element_name": "Logowanie"}

        with patch("app.api.routes.traceability.TraceabilityService") as service_cls:
            instance = service_cls.return_value
            instance.get_matrix = AsyncMock(return_value=([entry], 1))
            response = await client.get(f"/api/v1/projects/{project_id}/traceability/export?format=pdf")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        # PDF files start with the %PDF magic.
        assert response.content[:4] == b"%PDF"
        app.dependency_overrides = {}
