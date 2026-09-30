"""Testy tras panelu administracyjnego - Story 6.15, Task 10 (AC3-AC7)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from app.api.routes import admin as admin_routes
from app.core.dependencies import get_current_user, get_db
from app.main import create_app
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _authenticate(app, *, is_admin: bool = True, role: str = "admin"):
    """Podstawia zalogowanego użytkownika i atrapę sesji bazy."""
    user = make_user(is_admin=is_admin)
    tenant_id = uuid.uuid4()

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = role
        request.state.is_admin = is_admin
        return user

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return user


class TestListTenantsRoute:
    async def test_zwraca_liste_tenantow(self, app, client, monkeypatch):
        _authenticate(app)
        tenant_id = uuid.uuid4()
        monkeypatch.setattr(
            admin_routes,
            "list_tenants",
            AsyncMock(
                return_value=(
                    [
                        {
                            "id": tenant_id,
                            "name": "Acme",
                            "slug": "acme",
                            "plan": "premium",
                            "is_active": True,
                            "created_at": datetime.now(UTC),
                            "user_count": 5,
                            "storage_bytes": 1024,
                            "project_count": 2,
                        }
                    ],
                    1,
                )
            ),
        )
        try:
            response = await client.get("/api/v1/admin/tenants")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["tenants"][0]["name"] == "Acme"
        assert body["tenants"][0]["user_count"] == 5
        assert body["tenants"][0]["storage_bytes"] == 1024

    async def test_odmawia_dostepu_bez_roli_admin(self, app, client):
        _authenticate(app, is_admin=False, role="owner")
        try:
            response = await client.get("/api/v1/admin/tenants")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 403


class TestTenantDetailsRoute:
    async def test_zwraca_szczegoly(self, app, client, monkeypatch):
        _authenticate(app)
        tenant_id = uuid.uuid4()
        monkeypatch.setattr(
            admin_routes,
            "get_tenant_details",
            AsyncMock(
                return_value={
                    "id": tenant_id,
                    "name": "Beta",
                    "slug": "beta",
                    "plan": "basic",
                    "is_active": True,
                    "created_at": datetime.now(UTC),
                    "user_count": 1,
                    "storage_bytes": 0,
                    "project_count": 0,
                }
            ),
        )
        try:
            response = await client.get(f"/api/v1/admin/tenants/{tenant_id}")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.json()["name"] == "Beta"


class TestTenantProjectsRoute:
    async def test_zwraca_projekty_tenanta(self, app, client, monkeypatch):
        _authenticate(app)
        tenant_id = uuid.uuid4()
        monkeypatch.setattr(
            admin_routes,
            "list_tenant_projects",
            AsyncMock(
                return_value=(
                    [
                        {
                            "id": uuid.uuid4(),
                            "name": "API",
                            "status": "active",
                            "created_at": datetime.now(UTC),
                        }
                    ],
                    1,
                )
            ),
        )
        try:
            response = await client.get(f"/api/v1/admin/tenants/{tenant_id}/projects")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["projects"][0]["name"] == "API"


class TestAuditLogsRoute:
    async def test_zwraca_wpisy_z_paginacja(self, app, client, monkeypatch):
        _authenticate(app)
        entry = type(
            "Entry",
            (),
            {
                "id": uuid.uuid4(),
                "created_at": datetime.now(UTC),
                "user_id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "action": "user.blocked",
                "resource_type": "user",
                "resource_id": uuid.uuid4(),
                "details": {"old_blocked": False},
                "ip_address": "10.0.0.1",
            },
        )()
        monkeypatch.setattr(admin_routes, "query_logs", AsyncMock(return_value=[entry]))
        monkeypatch.setattr(admin_routes, "count_logs", AsyncMock(return_value=1))
        try:
            response = await client.get("/api/v1/admin/audit-logs?page=1&page_size=10")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["logs"][0]["action"] == "user.blocked"
        assert body["logs"][0]["ip_address"] == "10.0.0.1"

    async def test_przekazuje_filtry_do_serwisu(self, app, client, monkeypatch):
        _authenticate(app)
        spy = AsyncMock(return_value=[])
        monkeypatch.setattr(admin_routes, "query_logs", spy)
        monkeypatch.setattr(admin_routes, "count_logs", AsyncMock(return_value=0))
        user_id = uuid.uuid4()
        try:
            response = await client.get(
                "/api/v1/admin/audit-logs",
                params={
                    "date_from": "2026-01-01T00:00:00Z",
                    "date_to": "2026-02-01T00:00:00Z",
                    "user_id": str(user_id),
                    "action": "user.blocked",
                },
            )
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        kwargs = spy.await_args.kwargs
        assert kwargs["user_id"] == user_id
        assert kwargs["action"] == "user.blocked"
        assert kwargs["date_from"].year == 2026

    async def test_zwraca_liste_dostepnych_akcji(self, app, client, monkeypatch):
        _authenticate(app)
        monkeypatch.setattr(admin_routes, "list_actions", AsyncMock(return_value=["user.blocked"]))
        try:
            response = await client.get("/api/v1/admin/audit-logs/actions")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.json() == ["user.blocked"]


class TestConfigRoutes:
    async def test_zwraca_konfiguracje(self, app, client, monkeypatch):
        _authenticate(app)
        monkeypatch.setattr(
            admin_routes,
            "get_config",
            AsyncMock(
                return_value={
                    "limits": {
                        "max_file_size_mb": 100,
                        "max_projects_per_tenant": 50,
                        "max_users_per_tenant": 25,
                        "llm_cost_limit_usd": 100.0,
                    },
                    "llm": {
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-20250514",
                        "temperature": 0.2,
                        "max_tokens": 4096,
                        "timeout_seconds": 60,
                    },
                    "maintenance": {"enabled": False, "message": ""},
                    "feature_flags": {"ai_assistant": True},
                }
            ),
        )
        try:
            response = await client.get("/api/v1/admin/config")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        body = response.json()
        assert body["maintenance"]["enabled"] is False
        assert body["feature_flags"]["ai_assistant"] is True

    async def test_zapisuje_konfiguracje(self, app, client, monkeypatch):
        _authenticate(app)
        spy = AsyncMock(
            return_value={
                "limits": {
                    "max_file_size_mb": 250,
                    "max_projects_per_tenant": 50,
                    "max_users_per_tenant": 25,
                    "llm_cost_limit_usd": 100.0,
                },
                "llm": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "temperature": 0.2,
                    "max_tokens": 4096,
                    "timeout_seconds": 60,
                },
                "maintenance": {"enabled": True, "message": "Przerwa"},
                "feature_flags": {"ai_assistant": True},
            }
        )
        monkeypatch.setattr(admin_routes, "update_config", spy)
        try:
            response = await client.put(
                "/api/v1/admin/config",
                json={"maintenance": {"enabled": True, "message": "Przerwa"}},
            )
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.json()["maintenance"]["message"] == "Przerwa"
        assert spy.await_args.kwargs["sections"] == {"maintenance": {"enabled": True, "message": "Przerwa"}}

    async def test_odmawia_zapisu_bez_roli_admin(self, app, client):
        _authenticate(app, is_admin=False, role="owner")
        try:
            response = await client.put("/api/v1/admin/config", json={"maintenance": {"enabled": True}})
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 403


class TestBlockUserRoutes:
    async def test_blokuje_uzytkownika(self, app, client, monkeypatch):
        from app.api.routes import users as users_routes

        _authenticate(app)
        target = make_user(email="target@test.com")
        monkeypatch.setattr(users_routes, "set_user_blocked", AsyncMock(return_value=target))
        try:
            response = await client.post(f"/api/v1/users/{target.id}/block")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.json()["email"] == "target@test.com"

    async def test_odblokowuje_uzytkownika(self, app, client, monkeypatch):
        from app.api.routes import users as users_routes

        _authenticate(app)
        target = make_user(email="target@test.com")
        spy = AsyncMock(return_value=target)
        monkeypatch.setattr(users_routes, "set_user_blocked", spy)
        try:
            response = await client.post(f"/api/v1/users/{target.id}/unblock")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        assert spy.await_args.kwargs["blocked"] is False

    async def test_blokada_wymaga_roli_admin(self, app, client):
        _authenticate(app, is_admin=False, role="owner")
        try:
            response = await client.post(f"/api/v1/users/{uuid.uuid4()}/block")
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 403
