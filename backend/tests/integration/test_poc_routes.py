"""Integration tests for Story 4.10 PoC routes.

Covers POST /security-findings/{id}/generate-poc and GET .../poc. The DB session
is mocked so the test exercises routing + PoC-generator wiring + serialization.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


def _finding(project_id, **kw):
    from app.models.security_finding import Severity

    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        project_id=project_id,
        vulnerability_type=kw.get("vuln", "sql_injection"),
        severity=kw.get("severity", Severity.HIGH),
        file_path=kw.get("file_path", "app/db.py"),
        code_snippet=kw.get("code_snippet", 'execute("SELECT * FROM users WHERE id=" + uid)'),
        poc_payload=kw.get("poc_payload"),
        poc_steps=kw.get("poc_steps"),
        poc_expected_effect=kw.get("poc_expected_effect"),
    )


class TestGeneratePoC:
    async def test_generate_native_poc(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(project_id)
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/generate-poc",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "OR 1=1" in body["payload"]
        assert body["is_safe"] is True
        assert body["disclaimer"].startswith("PoC służy wyłącznie")
        assert len(body["reproduction_steps"]) >= 2
        # Persisted on the finding.
        assert finding.poc_payload == body["payload"]
        db.commit.assert_awaited()
        app.dependency_overrides = {}

    async def test_unsupported_type_returns_422(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(project_id, vuln="weak_cryptography")
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/generate-poc",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 422
        app.dependency_overrides = {}

    async def test_missing_finding_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        db.get.return_value = None
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-findings/{uuid.uuid4()}/generate-poc",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 404
        app.dependency_overrides = {}


class TestGetPoC:
    async def test_get_existing_poc(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(
            project_id,
            poc_payload="' OR 1=1--",
            poc_steps={"steps": ["1. krok", "2. krok"]},
            poc_expected_effect="zwraca dane",
        )
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/poc"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["payload"] == "' OR 1=1--"
        assert body["reproduction_steps"] == ["1. krok", "2. krok"]
        app.dependency_overrides = {}

    async def test_get_poc_not_generated_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(project_id, poc_payload=None)
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/poc"
        )

        assert response.status_code == 404
        app.dependency_overrides = {}
