"""Integration tests for document analysis routes (Epic 2).

Regression coverage for the engine_mode refactor: these routes used to 500
because they called ``extract_requirements(doc, mode=...)`` while the function
signature is ``extract_requirements(doc)``, and then indexed the returned
dataclass with dict syntax. Both are fixed; engine_mode now comes from
``Settings`` instead of a request param.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, tenant_id=None):
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
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _make_requirement(**kw):
    return SimpleNamespace(
        req_id=kw.get("req_id", "REQ-1"),
        text=kw.get("text", "System musi wysyłać e-mail."),
        type=kw.get("type", "functional"),
        priority=kw.get("priority", "high"),
        source_section_id=kw.get("source_section_id", "sec-1"),
        confidence=kw.get("confidence", 0.9),
        extraction_method=kw.get("extraction_method", "native"),
    )


def _req_item(**kw):
    """A persisted requirement element as stored in result_data."""
    return {
        "req_id": kw.get("req_id", "REQ-1"),
        "text": kw.get("text", "System musi wysyłać e-mail."),
        "type": kw.get("type", "functional"),
        "priority": kw.get("priority", "high"),
        "source_section_id": kw.get("source_section_id", "sec-1"),
        "source_section_title": kw.get("source_section_title", "Logowanie"),
        "confidence": kw.get("confidence", 0.9),
        "extraction_method": kw.get("extraction_method", "native"),
        "source": kw.get("source", "native"),
        "reasoning": kw.get("reasoning"),
        "status": kw.get("status", "extracted"),
    }


class TestRequirementsRoute:
    async def test_get_requirements_returns_200_from_persistence(self, client, app):
        """AC2: GET /requirements reads the persisted AnalysisResult instead of
        live extraction. Returns the list with workflow statuses."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = SimpleNamespace(
            result_data={"requirements": [_req_item()]},
            engine_mode=SimpleNamespace(value="native"),
        )
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/requirements")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert body["filename"] == "spec.pdf"
        assert body["mode"] == "native"
        assert body["requirements"][0]["req_id"] == "REQ-1"
        assert body["requirements"][0]["status"] == "extracted"
        assert body["requirements"][0]["source_section_title"] == "Logowanie"
        # source defaults to native when not persisted (Story 2.5)
        assert body["requirements"][0]["source"] == "native"
        app.dependency_overrides = {}

    async def test_get_requirements_echoes_source_and_reasoning(self, client, app):
        """AC5: GET /requirements echoes the persisted ``source`` and ``reasoning``
        for an LLM-extracted requirement (Story 2.5)."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = SimpleNamespace(
            result_data={
                "requirements": [
                    _req_item(
                        source="llm",
                        reasoning="Wymaganie bezpieczeństwa logowania",
                    )
                ]
            },
            engine_mode=SimpleNamespace(value="llm"),
        )
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/requirements")

        assert response.status_code == 200, response.text
        item = response.json()["requirements"][0]
        assert item["source"] == "llm"
        assert item["reasoning"] == "Wymaganie bezpieczeństwa logowania"
        assert item["status"] == "extracted"
        app.dependency_overrides = {}

    async def test_get_requirements_returns_202_when_not_available(self, client, app):
        """AC2: 202 when preprocessing is done but requirements extraction is
        not yet persisted."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = None
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/requirements")
        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_requirements_returns_202_when_preprocessing_incomplete(self, client, app):
        """AC2: 202 when preprocessing has not finished yet."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = prep_mock

        response = await client.get(f"/api/v1/documents/{doc_id}/requirements")
        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_requirements_404_when_missing(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/requirements")
        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_accept_requirement_sets_accepted(self, client, app):
        """AC3: POST /accept mutates the element status to ``accepted`` and
        persists result_data."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        req_ar = SimpleNamespace(
            result_data={"requirements": [_req_item()]},
            engine_mode=SimpleNamespace(value="native"),
        )
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = req_ar
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.post(f"/api/v1/documents/{doc_id}/requirements/REQ-1/accept")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "accepted"
        assert body["req_id"] == "REQ-1"
        # result_data was mutated + committed
        assert req_ar.result_data["requirements"][0]["status"] == "accepted"
        db.commit.assert_awaited()
        app.dependency_overrides = {}

    async def test_reject_requirement_sets_rejected(self, client, app):
        """AC3: POST /reject sets status ``rejected``."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        req_ar = SimpleNamespace(
            result_data={"requirements": [_req_item()]},
            engine_mode=SimpleNamespace(value="native"),
        )
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = req_ar
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.post(f"/api/v1/documents/{doc_id}/requirements/REQ-1/reject")

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "rejected"
        assert req_ar.result_data["requirements"][0]["status"] == "rejected"
        app.dependency_overrides = {}

    async def test_update_requirement_marks_edited(self, client, app):
        """AC3: PUT with text change marks the element ``edited``."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        req_ar = SimpleNamespace(
            result_data={"requirements": [_req_item()]},
            engine_mode=SimpleNamespace(value="native"),
        )
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = req_ar
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/requirements/REQ-1",
            json={"text": "System musi wysyłać e-mail z potwierdzeniem."},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "edited"
        assert body["text"] == "System musi wysyłać e-mail z potwierdzeniem."
        app.dependency_overrides = {}

    async def test_update_requirement_undo_resets_to_extracted(self, client, app):
        """AC3/AC5: PUT with explicit status ``extracted`` undoes a decision."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        req_ar = SimpleNamespace(
            result_data={"requirements": [_req_item(status="accepted")]},
            engine_mode=SimpleNamespace(value="native"),
        )
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = req_ar
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/requirements/REQ-1",
            json={"status": "extracted"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "extracted"
        app.dependency_overrides = {}

    async def test_accept_requirement_404_when_req_missing(self, client, app):
        """AC3: 404 when the req_id is not found in result_data."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        req_ar = SimpleNamespace(
            result_data={"requirements": [_req_item(req_id="OTHER")]},
            engine_mode=SimpleNamespace(value="native"),
        )
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        req_mock = MagicMock()
        req_mock.scalar_one_or_none.return_value = req_ar
        db.execute.side_effect = [prep_mock, req_mock]

        response = await client.post(f"/api/v1/documents/{doc_id}/requirements/REQ-1/accept")
        assert response.status_code == 404, response.text
        app.dependency_overrides = {}


def _glos_item(**kw):
    """A persisted glossary term element as stored in result_data (Story 2.6)."""
    return {
        "term": kw.get("term", "API"),
        "definition": kw.get("definition", "Interfejs programistyczny"),
        "occurrences_count": kw.get("occurrences_count", 3),
        "term_type": kw.get("term_type", "acronym"),
        "source_sections": kw.get("source_sections", [{"section_id": "g", "title": "Glosariusz"}]),
        "is_verified": kw.get("is_verified", False),
        "code_mappings": kw.get(
            "code_mappings",
            [
                {
                    "name": "ApiController",
                    "type": "class",
                    "similarity": 1.0,
                    "is_confirmed": False,
                }
            ],
        ),
    }


class TestGlossaryRoute:
    async def test_get_glossary_returns_200_from_persistence(self, client, app):
        """AC4: GET /glossary reads the persisted AnalysisResult (NOT live
        extraction) and returns serializable GlossaryTermResponse[] with
        code_mappings."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        glos_mock = MagicMock()
        glos_mock.scalar_one_or_none.return_value = SimpleNamespace(
            result_data={"terms": [_glos_item()]},
        )
        db.execute.side_effect = [prep_mock, glos_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/glossary")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filename"] == "spec.pdf"
        assert body["total"] == 1
        assert body["terms"][0]["term"] == "API"
        assert body["terms"][0]["term_type"] == "acronym"
        assert body["terms"][0]["code_mappings"][0]["name"] == "ApiController"
        app.dependency_overrides = {}

    async def test_get_glossary_returns_202_when_not_available(self, client, app):
        """AC4: 202 when preprocessing is done but glossary extraction is not yet
        persisted."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        glos_mock = MagicMock()
        glos_mock.scalar_one_or_none.return_value = None
        db.execute.side_effect = [prep_mock, glos_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/glossary")
        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_glossary_returns_202_when_preprocessing_incomplete(self, client, app):
        """AC4: 202 when preprocessing has not finished yet."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = prep_mock

        response = await client.get(f"/api/v1/documents/{doc_id}/glossary")
        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_glossary_404_when_missing(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/glossary")
        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_put_glossary_term_mutates_definition_and_verified(self, client, app):
        """AC4: PUT mutates definition/is_verified and persists result_data."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        glos_ar = SimpleNamespace(result_data={"terms": [_glos_item()]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        glos_mock = MagicMock()
        glos_mock.scalar_one_or_none.return_value = glos_ar
        db.execute.side_effect = [prep_mock, glos_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/glossary/API",
            json={"definition": "Nowa definicja", "is_verified": True},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["definition"] == "Nowa definicja"
        assert body["is_verified"] is True
        assert glos_ar.result_data["terms"][0]["definition"] == "Nowa definicja"
        assert glos_ar.result_data["terms"][0]["is_verified"] is True
        db.commit.assert_awaited()
        app.dependency_overrides = {}

    async def test_put_glossary_term_confirms_code_mappings(self, client, app):
        """AC4: PUT with confirmed_mapping_ids flips code_mappings[].is_confirmed."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        glos_ar = SimpleNamespace(result_data={"terms": [_glos_item()]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        glos_mock = MagicMock()
        glos_mock.scalar_one_or_none.return_value = glos_ar
        db.execute.side_effect = [prep_mock, glos_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/glossary/API",
            json={"confirmed_mapping_ids": ["ApiController"]},
        )

        assert response.status_code == 200, response.text
        assert response.json()["code_mappings"][0]["is_confirmed"] is True
        assert glos_ar.result_data["terms"][0]["code_mappings"][0]["is_confirmed"] is True
        app.dependency_overrides = {}

    async def test_put_glossary_term_404_when_term_missing(self, client, app):
        """AC4: 404 when the term is not found in result_data."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        glos_ar = SimpleNamespace(result_data={"terms": [_glos_item(term="OTHER")]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        glos_mock = MagicMock()
        glos_mock.scalar_one_or_none.return_value = glos_ar
        db.execute.side_effect = [prep_mock, glos_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/glossary/API",
            json={"definition": "x"},
        )
        assert response.status_code == 404, response.text
        app.dependency_overrides = {}

    async def test_map_to_code_updates_mappings(self, client, app):
        """AC4: POST /glossary/map-to-code rebuilds code_mappings in result_data
        via TerminologyMapper and returns the updated list."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        project_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, project_id=project_id, filename="spec.pdf", storage_key="k")
        glos_ar = SimpleNamespace(result_data={"terms": [_glos_item(code_mappings=[])]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        glos_mock = MagicMock()
        glos_mock.scalar_one_or_none.return_value = glos_ar
        db.execute.side_effect = [prep_mock, glos_mock]

        mapper_instance = MagicMock()
        mapper_instance.map_to_code = AsyncMock(
            return_value={
                "API": [
                    {
                        "name": "ApiController",
                        "type": "class",
                        "similarity": 1.0,
                        "is_confirmed": False,
                    }
                ]
            }
        )
        with patch(
            "app.api.routes.documents.TerminologyMapper",
            new=MagicMock(return_value=mapper_instance),
        ):
            response = await client.post(f"/api/v1/documents/{doc_id}/glossary/map-to-code")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["terms"][0]["code_mappings"][0]["name"] == "ApiController"
        assert glos_ar.result_data["terms"][0]["code_mappings"][0]["name"] == "ApiController"
        db.commit.assert_awaited()
        app.dependency_overrides = {}


def _inc_item(**kw):
    """A persisted inconsistency element as stored in result_data (Story 2.7)."""
    return {
        "inconsistency_id": kw.get("inconsistency_id", "inc-1"),
        "type": kw.get("type", "contradiction"),
        "severity": kw.get("severity", "critical"),
        "description": kw.get("description", "Sprzeczność: 'FR-1' vs 'FR-2'"),
        "affected_requirements": kw.get("affected_requirements", ["FR-1", "FR-2"]),
        "suggestion": kw.get("suggestion", "Rozważ zmodyfikację jednego z wymagań"),
        "source_section_id": kw.get("source_section_id", "s1"),
        "status": kw.get("status", "open"),
    }


class TestInconsistencyRoute:
    async def test_get_inconsistencies_returns_200_from_persistence(self, client, app):
        """AC3: GET /inconsistencies reads the persisted AnalysisResult (NOT live
        detection) and returns serializable InconsistencyResponse[] with status."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        inc_mock = MagicMock()
        inc_mock.scalar_one_or_none.return_value = SimpleNamespace(
            result_data={"items": [_inc_item()]},
        )
        db.execute.side_effect = [prep_mock, inc_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/inconsistencies")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filename"] == "spec.pdf"
        assert body["total"] == 1
        assert body["inconsistencies"][0]["inconsistency_id"] == "inc-1"
        assert body["inconsistencies"][0]["type"] == "contradiction"
        assert body["inconsistencies"][0]["status"] == "open"
        app.dependency_overrides = {}

    async def test_get_inconsistencies_returns_202_when_not_available(self, client, app):
        """AC3: 202 when preprocessing is done but inconsistency detection is
        not yet persisted."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        inc_mock = MagicMock()
        inc_mock.scalar_one_or_none.return_value = None
        db.execute.side_effect = [prep_mock, inc_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/inconsistencies")
        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_inconsistencies_returns_202_when_preprocessing_incomplete(self, client, app):
        """AC3: 202 when preprocessing has not finished yet."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = prep_mock

        response = await client.get(f"/api/v1/documents/{doc_id}/inconsistencies")
        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_inconsistencies_404_when_missing(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/inconsistencies")
        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_put_inconsistency_status_mutates_and_persists(self, client, app):
        """AC4: PUT mutates status and persists result_data (survives refresh)."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        inc_ar = SimpleNamespace(result_data={"items": [_inc_item()]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        inc_mock = MagicMock()
        inc_mock.scalar_one_or_none.return_value = inc_ar
        db.execute.side_effect = [prep_mock, inc_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/inconsistencies/inc-1",
            json={"status": "accepted"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "accepted"
        assert inc_ar.result_data["items"][0]["status"] == "accepted"
        db.commit.assert_awaited()
        app.dependency_overrides = {}

    async def test_put_inconsistency_404_when_id_missing(self, client, app):
        """AC4: 404 when the inconsistency_id is not found in result_data."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        inc_ar = SimpleNamespace(result_data={"items": [_inc_item(inconsistency_id="OTHER")]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        inc_mock = MagicMock()
        inc_mock.scalar_one_or_none.return_value = inc_ar
        db.execute.side_effect = [prep_mock, inc_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/inconsistencies/inc-1",
            json={"status": "fixed"},
        )
        assert response.status_code == 404, response.text
        app.dependency_overrides = {}

    async def test_put_inconsistency_rejects_invalid_status(self, client, app):
        """AC4: 422 for a status outside the allowed set (Pydantic Literal)."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")
        inc_ar = SimpleNamespace(result_data={"items": [_inc_item()]})
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        inc_mock = MagicMock()
        inc_mock.scalar_one_or_none.return_value = inc_ar
        db.execute.side_effect = [prep_mock, inc_mock]

        response = await client.put(
            f"/api/v1/documents/{doc_id}/inconsistencies/inc-1",
            json={"status": "bogus"},
        )
        assert response.status_code == 422, response.text
        app.dependency_overrides = {}


def _flat_sections():
    return [
        {
            "section_id": "s1",
            "title": "Wprowadzenie",
            "level": 1,
            "content": "aaa",
            "parent_section_id": None,
            "position": 0,
            "section_type": "unclassified",
            "page_number": 1,
        },
        {
            "section_id": "s2",
            "title": "Podsekcja",
            "level": 2,
            "content": "bbb",
            "parent_section_id": "s1",
            "position": 1,
            "section_type": "unclassified",
            "page_number": 1,
        },
        {
            "section_id": "s3",
            "title": "Kolejny rozdział",
            "level": 1,
            "content": "ccc",
            "parent_section_id": None,
            "position": 2,
            "section_type": "unclassified",
            "page_number": 2,
        },
    ]


def _prep_result_with(sections):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = SimpleNamespace(
        result_data={"sections": sections},
    )
    return result_mock


class TestSectionsRoute:
    async def test_get_sections_returns_tree_200(self, client, app):
        """AC1: GET /sections returns a parent-child tree reconstructed from the
        flat persisted list, with ``position`` and ``section_type`` present."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        db.execute.return_value = _prep_result_with(_flat_sections())

        response = await client.get(f"/api/v1/documents/{doc_id}/sections")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filename"] == "spec.pdf"
        assert body["total"] == 2  # two roots: s1, s3
        roots = body["sections"]
        assert [r["section_id"] for r in roots] == ["s1", "s3"]
        # s2 nested under s1 via parent_section_id reconstruction
        assert [c["section_id"] for c in roots[0]["children"]] == ["s2"]
        assert roots[0]["position"] == 0
        assert roots[0]["section_type"] == "unclassified"
        app.dependency_overrides = {}

    async def test_get_sections_returns_202_when_preprocessing_incomplete(self, client, app):
        """AC1: 202 when preprocessing AnalysisResult is not yet COMPLETED."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        response = await client.get(f"/api/v1/documents/{doc_id}/sections")

        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_sections_returns_404_when_document_missing(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/sections")
        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_get_section_detail_returns_200(self, client, app):
        """AC2: GET /sections/{id} returns the single section with content."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        db.execute.return_value = _prep_result_with(_flat_sections())

        response = await client.get(f"/api/v1/documents/{doc_id}/sections/s2")

        assert response.status_code == 200, response.text
        section = response.json()["section"]
        assert section["section_id"] == "s2"
        assert section["content"] == "bbb"
        app.dependency_overrides = {}

    async def test_get_section_detail_returns_404_when_missing(self, client, app):
        """AC2: 404 when section_id is unknown."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        db.execute.return_value = _prep_result_with(_flat_sections())

        response = await client.get(f"/api/v1/documents/{doc_id}/sections/does-not-exist")
        assert response.status_code == 404
        app.dependency_overrides = {}


# ── Classification routes — Story 2.3 closure ──────────────────────────────


def _fake_classification(**kw):
    """A stand-in for ClassificationResult returned by the (patched) classifier."""
    return SimpleNamespace(
        doc_type=SimpleNamespace(value=kw.get("doc_type", "opis_api")),
        confidence=kw.get("confidence", 92.0),
        source=SimpleNamespace(value=kw.get("source", "llm")),
        reasoning=kw.get("reasoning", "Endpointy REST"),
        native_confidence=kw.get("native_confidence", 80.0),
        llm_confidence=kw.get("llm_confidence", 92.0),
    )


class TestClassifyRoute:
    async def test_post_classify_returns_200_and_persists(self, client, app):
        """AC1: POST /classify echoes doc_type and upserts a classification
        AnalysisResult. engine_mode comes from Settings (no request body)."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        project_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, project_id=project_id, filename="spec.pdf", storage_key="k")
        # db.add is sync on a real AsyncSession — keep it a sync MagicMock so it
        # records the call without leaving an un-awaited coroutine.
        db.add = MagicMock()
        # No existing classification → the route takes the session.add branch.
        existing_mock = MagicMock()
        existing_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = existing_mock

        with (
            patch(
                "app.api.routes.documents._load_document_structure",
                return_value=SimpleNamespace(sections=[]),
            ),
            patch(
                "app.api.routes.documents.classify_document_async",
                new=AsyncMock(return_value=_fake_classification()),
            ),
        ):
            response = await client.post(f"/api/v1/documents/{doc_id}/classify")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["doc_type"] == "opis_api"
        assert body["confidence"] == 92.0
        assert body["source"] == "llm"

        # AnalysisResult(module="classification") was added with the result data
        assert db.add.called
        added = db.add.call_args.args[0]
        assert added.module == "classification"
        assert added.source_file_id == doc_id
        assert added.result_data["doc_type"] == "opis_api"
        app.dependency_overrides = {}

    async def test_post_classify_404_when_document_missing(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/classify")
        assert response.status_code == 404
        app.dependency_overrides = {}


class TestClassificationRoute:
    async def test_get_classification_returns_200_when_completed(self, client, app):
        """AC1: GET /classification → 200 when a COMPLETED classification exists."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        cls_mock = MagicMock()
        cls_mock.scalar_one_or_none.return_value = SimpleNamespace(
            result_data={
                "doc_type": "opis_api",
                "confidence": 92.0,
                "source": "llm",
                "reasoning": "REST",
                "native_confidence": 80.0,
                "llm_confidence": 92.0,
            }
        )
        db.execute.side_effect = [prep_mock, cls_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/classification")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["doc_type"] == "opis_api"
        assert body["confidence"] == 92.0
        app.dependency_overrides = {}

    async def test_get_classification_returns_202_when_not_available(self, client, app):
        """AC1: 202 when preprocessing is done but classification is missing."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf")
        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        cls_mock = MagicMock()
        cls_mock.scalar_one_or_none.return_value = None
        db.execute.side_effect = [prep_mock, cls_mock]

        response = await client.get(f"/api/v1/documents/{doc_id}/classification")

        assert response.status_code == 202, response.text
        app.dependency_overrides = {}

    async def test_get_classification_returns_404_when_document_missing(self, client, app):
        """AC1: 404 when the document does not exist."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/classification")
        assert response.status_code == 404
        app.dependency_overrides = {}


class TestReparseRoute:
    """POST /documents/{id}/reparse — on-demand re-analysis of a document.

    Re-dispatches the document parsing task (sections/requirements/glossary),
    NOT the source-code analysis pipeline (which is quota-gated via /analyze).
    """

    async def test_reparse_resets_status_and_dispatches_parsing(self, client, app):
        from app.models.source_file import FileCategory, FileProcessingStatus

        user = make_user()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        source_file = SimpleNamespace(
            id=doc_id,
            file_category=FileCategory.DOCUMENTATION,
            is_cleaned_up=False,
            processing_status=FileProcessingStatus.READY,
            error_message="stary błąd",
        )
        db.get.return_value = source_file
        db.commit = AsyncMock()

        with (
            patch("app.workers.tasks.document_tasks.parse_document_task") as mock_task,
            patch("app.services.task_progress_service.TaskProgressService") as mock_progress_cls,
        ):
            mock_task.delay.return_value = SimpleNamespace(id="task-abc")
            mock_progress = MagicMock()
            mock_progress_cls.return_value = mock_progress

            response = await client.post(f"/api/v1/documents/{doc_id}/reparse")

        assert response.status_code == 202, response.text
        body = response.json()
        assert body["task_id"] == "task-abc"
        assert body["status"] == "pending"
        assert source_file.processing_status == FileProcessingStatus.PROCESSING
        assert source_file.error_message is None
        mock_task.delay.assert_called_once_with(str(doc_id), str(tenant_id))
        mock_progress.init_task.assert_called_once()
        db.commit.assert_awaited_once()
        app.dependency_overrides = {}

    async def test_reparse_404_when_not_documentation(self, client, app):
        from app.models.source_file import FileCategory, FileProcessingStatus

        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = SimpleNamespace(
            id=uuid.uuid4(),
            file_category=FileCategory.CODE,
            is_cleaned_up=False,
            processing_status=FileProcessingStatus.READY,
            error_message=None,
        )
        db.commit = AsyncMock()

        response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/reparse")
        assert response.status_code == 404, response.text
        app.dependency_overrides = {}

    async def test_reparse_404_when_missing(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/reparse")
        assert response.status_code == 404
        app.dependency_overrides = {}


def _gap_item(**kw):
    """A persisted gap-analysis item element as stored in result_data (Story 2.8)."""
    return {
        "requirement_id": kw.get("requirement_id", "FR-3"),
        "requirement_text": kw.get("requirement_text", "System musi tworzyć zamówienia."),
        "status": kw.get("status", "not_implemented"),
        "mapped_entities": kw.get("mapped_entities", []),
        "issue_description": kw.get("issue_description", "Brak implementacji dla wymagania 'FR-3'"),
        "confidence": kw.get("confidence", 0.0),
    }


def _gap_payload(**kw):
    """A persisted gap-analysis result_data payload (Story 2.8)."""
    return {
        "summary": kw.get(
            "summary",
            {
                "total_requirements": 2,
                "implemented": 1,
                "not_implemented": 1,
                "partial": 0,
                "divergent": 0,
                "coverage_percentage": 50.0,
                "critical_gaps": ["FR-3"],
            },
        ),
        "items": kw.get("items", [_gap_item()]),
    }


class TestGapAnalysisRoute:
    """Story 2.8 — GET /documents/{id}/analysis reads gap_analysis from
    persistence (NOT a placeholder)."""

    async def test_analysis_returns_gap_analysis_from_persistence(self, client, app):
        """AC3: gap_analysis is read from AnalysisResult(module="gap_analysis")
        result_data, not the previous all-zero placeholder."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        ar_query_mock = MagicMock()
        ar_query_mock.scalars.return_value.all.return_value = [SimpleNamespace(module="gap_analysis")]
        gap_mock = MagicMock()
        gap_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data=_gap_payload())
        db.execute.side_effect = [prep_mock, ar_query_mock, gap_mock]

        with patch("app.api.routes.documents._load_document_structure"):
            response = await client.get(f"/api/v1/documents/{doc_id}/analysis")

        assert response.status_code == 200, response.text
        gap = response.json()["gap_analysis"]
        assert gap["summary"]["coverage_percentage"] == 50.0
        assert gap["summary"]["implemented"] == 1
        assert gap["summary"]["critical_gaps"] == ["FR-3"]
        assert gap["items"][0]["requirement_id"] == "FR-3"
        assert gap["items"][0]["status"] == "not_implemented"
        app.dependency_overrides = {}

    async def test_analysis_gap_analysis_falls_back_to_zero_when_not_persisted(self, client, app):
        """AC3: when gap_analysis has not run yet, the endpoint returns an
        all-zero summary + empty items (key always present) rather than the old
        placeholder derived from the requirement count."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        ar_query_mock = MagicMock()
        ar_query_mock.scalars.return_value.all.return_value = []  # no modules done
        db.execute.side_effect = [prep_mock, ar_query_mock]

        with patch("app.api.routes.documents._load_document_structure"):
            response = await client.get(f"/api/v1/documents/{doc_id}/analysis")

        assert response.status_code == 200, response.text
        gap = response.json()["gap_analysis"]
        assert gap["summary"]["coverage_percentage"] == 0.0
        assert gap["summary"]["total_requirements"] == 0
        assert gap["items"] == []
        app.dependency_overrides = {}


def _trace_item(**kw):
    """A persisted traceability entry as stored in result_data (Story 2.9)."""
    return {
        "requirement_id": kw.get("requirement_id", "FR-1"),
        "requirement_text": kw.get("requirement_text", "System musi używać funkcji login."),
        "code_entities": kw.get("code_entities", ["login"]),
        "test_cases": kw.get("test_cases", []),
        "coverage_status": kw.get("coverage_status", "partial"),
        "source_section_id": kw.get("source_section_id", "s1"),
    }


def _trace_payload(**kw):
    """A persisted traceability result_data payload — flat FE shape (Story 2.9).

    Unlike gap_analysis (summary/items), traceability is stored and served flat.
    """
    items = kw.get("items", [_trace_item()])
    return {
        "document_name": kw.get("document_name", "spec.pdf"),
        "total_requirements": kw.get("total_requirements", len(items)),
        "full_coverage": kw.get(
            "full_coverage",
            sum(1 for i in items if i["coverage_status"] == "full"),
        ),
        "partial_coverage": kw.get(
            "partial_coverage",
            sum(1 for i in items if i["coverage_status"] == "partial"),
        ),
        "no_coverage": kw.get(
            "no_coverage",
            sum(1 for i in items if i["coverage_status"] == "none"),
        ),
        "coverage_percentage": kw.get("coverage_percentage", 0.0),
        "entries": items,
    }


class TestTraceabilityRoute:
    """Story 2.9 — GET /documents/{id}/analysis reads traceability from
    persistence (NOT a placeholder)."""

    async def test_analysis_returns_traceability_from_persistence(self, client, app):
        """AC3: traceability is read from AnalysisResult(module="traceability")
        result_data (flat shape), not the previous all-zero placeholder."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        ar_query_mock = MagicMock()
        ar_query_mock.scalars.return_value.all.return_value = [SimpleNamespace(module="traceability")]
        trace_mock = MagicMock()
        trace_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data=_trace_payload())
        db.execute.side_effect = [prep_mock, ar_query_mock, trace_mock]

        with patch("app.api.routes.documents._load_document_structure"):
            response = await client.get(f"/api/v1/documents/{doc_id}/analysis")

        assert response.status_code == 200, response.text
        trace = response.json()["traceability"]
        assert trace["total_requirements"] == 1
        assert trace["partial_coverage"] == 1
        assert trace["coverage_percentage"] == 0.0
        assert trace["entries"][0]["requirement_id"] == "FR-1"
        assert trace["entries"][0]["coverage_status"] == "partial"
        assert trace["entries"][0]["code_entities"] == ["login"]
        app.dependency_overrides = {}

    async def test_analysis_traceability_falls_back_to_zero_when_not_persisted(self, client, app):
        """AC3: when traceability has not run yet, the endpoint returns an
        all-zero flat summary + empty entries (key always present) rather than
        the old placeholder derived from the requirement count."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        ar_query_mock = MagicMock()
        ar_query_mock.scalars.return_value.all.return_value = []  # no modules done
        db.execute.side_effect = [prep_mock, ar_query_mock]

        with patch("app.api.routes.documents._load_document_structure"):
            response = await client.get(f"/api/v1/documents/{doc_id}/analysis")

        assert response.status_code == 200, response.text
        trace = response.json()["traceability"]
        assert trace["total_requirements"] == 0
        assert trace["coverage_percentage"] == 0.0
        assert trace["no_coverage"] == 0
        assert trace["entries"] == []
        app.dependency_overrides = {}


def _test_generation_item(**kw):
    """A single serialized ``GeneratedTestCase`` (flat FE shape, Story 2.10)."""
    return {
        "test_id": kw.get("test_id", "TC-000"),
        "name": kw.get("name", "Test: Logowanie użytkownika"),
        "description": kw.get("description", "System wykonuje logowanie użytkownika"),
        "steps": kw.get("steps", ["Otwórz stronę logowania", "Weryfikuj wynik"]),
        "expected_result": kw.get("expected_result", "Użytkownik jest zalogowany do systemu"),
        "priority": kw.get("priority", "medium"),
        "requirement_id": kw.get("requirement_id", "FR-1"),
        "test_type": kw.get("test_type", "functional"),
        "automation_feasibility": kw.get("automation_feasibility", "auto"),
    }


def _test_generation_payload(**kw):
    """A persisted test-generation result_data payload — flat FE shape (Story
    2.10).

    Like traceability, test_generation is stored and served flat (no
    ``statistics`` leak — the previous live-dead API branch was the only
    consumer of it).
    """
    tests = kw.get("tests", [_test_generation_item()])
    return {
        "document_name": kw.get("document_name", "spec.pdf"),
        "total_requirements": kw.get("total_requirements", 1),
        "generated_tests": kw.get("generated_tests", len(tests)),
        "coverage_percentage": kw.get("coverage_percentage", 100.0),
        "tests": tests,
    }


class TestTestGenerationRoute:
    """Story 2.10 — GET /documents/{id}/analysis reads test_generation from
    persistence (NOT a live-dead generator call)."""

    async def test_analysis_returns_test_generation_from_persistence(self, client, app):
        """AC3: test_generation is read from
        AnalysisResult(module="test_generation") result_data (flat shape),
        not the previous live-dead ``generate_tests_from_requirements`` call."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        ar_query_mock = MagicMock()
        ar_query_mock.scalars.return_value.all.return_value = [SimpleNamespace(module="test_generation")]
        tg_mock = MagicMock()
        tg_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data=_test_generation_payload())
        db.execute.side_effect = [prep_mock, ar_query_mock, tg_mock]

        with patch("app.api.routes.documents._load_document_structure"):
            response = await client.get(f"/api/v1/documents/{doc_id}/analysis")

        assert response.status_code == 200, response.text
        tg = response.json()["test_generation"]
        assert tg["total_requirements"] == 1
        assert tg["generated_tests"] == 1
        assert tg["coverage_percentage"] == 100.0
        assert tg["tests"][0]["test_id"] == "TC-000"
        assert tg["tests"][0]["requirement_id"] == "FR-1"
        assert tg["tests"][0]["test_type"] == "functional"
        # No ``statistics`` leak (dropped in the flat serializer).
        assert "statistics" not in tg
        app.dependency_overrides = {}

    async def test_analysis_test_generation_falls_back_to_zero_when_not_persisted(self, client, app):
        """AC3: when test generation has not run yet, the endpoint returns an
        all-zero flat summary + empty tests (key always present) rather than the
        old live-dead generator call derived from the requirement count."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        doc_id = uuid.uuid4()
        db.get.return_value = SimpleNamespace(id=doc_id, filename="spec.pdf", storage_key="k")

        prep_mock = MagicMock()
        prep_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data={})
        ar_query_mock = MagicMock()
        ar_query_mock.scalars.return_value.all.return_value = []  # no modules done
        db.execute.side_effect = [prep_mock, ar_query_mock]

        with patch("app.api.routes.documents._load_document_structure"):
            response = await client.get(f"/api/v1/documents/{doc_id}/analysis")

        assert response.status_code == 200, response.text
        tg = response.json()["test_generation"]
        assert tg["total_requirements"] == 0
        assert tg["generated_tests"] == 0
        assert tg["coverage_percentage"] == 0.0
        assert tg["tests"] == []
        app.dependency_overrides = {}
