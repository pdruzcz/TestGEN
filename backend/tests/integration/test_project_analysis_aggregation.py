"""Testy agregacji analiz dokumentacji per projekt (widoki nawigacji projektu).

GET /api/v1/projects/{id}/requirements|glossary|inconsistencies — suma
elementów ze wszystkich dokumentów projektu, każdy z document_id +
document_filename (UI pokazuje dokument źródłowy; bez tego widoki projektu
były puste, bo per-document endpointy wymagają documentId z query).
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.models.project import Project
from app.models.source_file import SourceFile
from tests.factories import make_user


def _fake_db(project: Project, module_rows: list[tuple[AnalysisResult, SourceFile]]):
    """db.execute rozróżnia zapytania po SQL: Project (dostęp) vs agregacja."""

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def scalar_one_or_none(self):
            return self._rows[0] if self._rows else None

        def all(self):
            return self._rows

        def scalars(self):
            return self

    async def fake_execute(q, *args, **kwargs):
        sql = str(q)
        if "FROM projects" in sql:
            return _Result([project])
        if "FROM analysis_results" in sql and "JOIN source_files" in sql:
            return _Result(module_rows)
        return _Result([])

    db = AsyncMock()
    db.execute = fake_execute
    return db


def _doc_row(filename: str, module: str, payload: dict) -> tuple[AnalysisResult, SourceFile]:
    sf = SourceFile(id=uuid4(), filename=filename, file_category="documentation", is_cleaned_up=False)
    ar = AnalysisResult(
        id=uuid4(),
        source_file_id=sf.id,
        module=module,
        status=AnalysisStatus.COMPLETED,
        result_data=payload,
    )
    return ar, sf


@pytest.fixture
def make_app():
    apps = []

    def _make(module_rows: list[tuple[AnalysisResult, SourceFile]]):
        app = create_app()
        project = Project(id=uuid4(), name="Projekt testowy")
        app.dependency_overrides[get_current_user] = lambda: make_user()
        app.dependency_overrides[get_db] = lambda: _fake_db(project, module_rows)
        apps.append(app)
        return app, project.id

    yield _make
    for a in apps:
        a.dependency_overrides.clear()


async def _get(app, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_project_requirements_aggregates_documents(make_app):
    rows = [
        _doc_row("wymagania-v1.docx", "requirements", {"requirements": [{"req_id": "WYM-1", "text": "Logowanie"}]}),
        _doc_row("wymagania-v2.docx", "requirements", {"requirements": [{"req_id": "WYM-2", "text": "MFA"}]}),
    ]
    app, pid = make_app(rows)
    resp = await _get(app, f"/api/v1/projects/{pid}/requirements")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["documents"] == 2
    filenames = {r["document_filename"] for r in body["requirements"]}
    assert filenames == {"wymagania-v1.docx", "wymagania-v2.docx"}
    assert {r["req_id"] for r in body["requirements"]} == {"WYM-1", "WYM-2"}


@pytest.mark.asyncio
async def test_project_glossary_marks_source_document(make_app):
    rows = [_doc_row("glos.docx", "glossary", {"terms": [{"term": "SLA", "definition": "Umowa"}]})]
    app, pid = make_app(rows)
    resp = await _get(app, f"/api/v1/projects/{pid}/glossary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["documents"] == 1
    assert body["terms"][0]["term"] == "SLA"
    assert body["terms"][0]["document_filename"] == "glos.docx"


@pytest.mark.asyncio
async def test_project_inconsistencies_uses_module_name(make_app):
    rows = [
        _doc_row(
            "niesp.docx",
            "inconsistencies",
            {"items": [{"inconsistency_id": "N-1", "type": "terminology", "severity": "medium", "description": "X"}]},
        )
    ]
    app, pid = make_app(rows)
    resp = await _get(app, f"/api/v1/projects/{pid}/inconsistencies")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["inconsistencies"][0]["inconsistency_id"] == "N-1"
    assert body["inconsistencies"][0]["document_filename"] == "niesp.docx"


@pytest.mark.asyncio
async def test_project_view_empty_when_no_documents(make_app):
    app, pid = make_app([])
    for path in ("requirements", "glossary", "inconsistencies"):
        resp = await _get(app, f"/api/v1/projects/{pid}/{path}")
        assert resp.status_code == 200, (path, resp.text)
        body = resp.json()
        assert body["total"] == 0
        assert body["documents"] == 0
