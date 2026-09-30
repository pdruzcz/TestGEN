"""Testy trasy POST /chat/message — Story 6.14, Task 8 (AC2, AC7)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.chat import chat_service
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app):
    from fastapi import Request

    from app.core.dependencies import get_current_user

    user = make_user()
    tenant_id = uuid.uuid4()

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = "user"
        request.state.is_admin = False
        return user

    app.dependency_overrides[get_current_user] = override_user
    return tenant_id


@pytest.fixture(autouse=True)
def fake_stream(monkeypatch):
    """Podmienia gateway na deterministyczny strumień dwóch tokenów."""
    seen: dict = {}

    class _Gateway:
        async def stream_complete(self, **kwargs):
            seen.update(kwargs)
            yield "Masz "
            yield "3 luki."

    monkeypatch.setattr(chat_service, "get_llm_gateway", lambda: _Gateway())
    return seen


class TestPostChatMessage:
    async def test_zwraca_strumien_sse(self, app, client):
        _override_auth(app)
        try:
            response = await client.post("/api/v1/chat/message", json={"message": "Ile mam luk?"})
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    async def test_strumien_zawiera_tokeny_i_done(self, app, client):
        _override_auth(app)
        try:
            response = await client.post("/api/v1/chat/message", json={"message": "Ile mam luk?"})
        finally:
            app.dependency_overrides = {}

        body = response.text
        assert "event: token" in body
        assert '"content": "Masz "' in body
        assert "event: done" in body

    async def test_wylacza_buforowanie_proxy(self, app, client):
        _override_auth(app)
        try:
            response = await client.post("/api/v1/chat/message", json={"message": "test"})
        finally:
            app.dependency_overrides = {}

        assert response.headers["x-accel-buffering"] == "no"
        assert response.headers["cache-control"] == "no-cache"

    async def test_przekazuje_tenant_id_do_rozliczenia(self, app, client, fake_stream):
        tenant_id = _override_auth(app)
        try:
            await client.post("/api/v1/chat/message", json={"message": "test"})
        finally:
            app.dependency_overrides = {}

        assert fake_stream["tenant_id"] == tenant_id
        assert fake_stream["module"] == "chatbot"

    async def test_odrzuca_pusta_wiadomosc(self, app, client):
        _override_auth(app)
        try:
            response = await client.post("/api/v1/chat/message", json={"message": ""})
        finally:
            app.dependency_overrides = {}

        assert response.status_code == 422

    async def test_wymaga_uwierzytelnienia(self, client):
        response = await client.post("/api/v1/chat/message", json={"message": "test"})
        assert response.status_code in (401, 403)
