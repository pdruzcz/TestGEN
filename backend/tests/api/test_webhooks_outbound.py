"""API testy webhooków wychodzących — Story 8.7 (AC1, AC5, AC6; Task 7.3).

DB mockowana, serwis realny (wzorzec test_api_keys). Najważniejsza asercja
powtarza się w kilku testach: sekret nie wychodzi żadnym endpointem.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.outbound_webhook import DeliveryStatus, OutboundWebhook, WebhookDelivery
from tests.factories import make_user

BASE = "/api/v1/webhooks"
SECRET = "s" * 32
URL = "https://klient.example.com/hook"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _db() -> AsyncMock:
    db = AsyncMock()

    def _add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)

    db.add = MagicMock(side_effect=_add)
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _override(app, db, role: str = "owner") -> tuple[uuid.UUID, object]:
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    user = make_user(email="owner@a.com", name="Owner")
    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = role
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return tenant_id, user


def _webhook(tenant_id, user_id, **overrides) -> OutboundWebhook:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "url": URL,
        "secret_encrypted": "enc-sekret",
        "events": ["analysis.completed"],
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return OutboundWebhook(**defaults)


# ── tworzenie (AC1) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_zwraca_201_bez_sekretu(app, client):
    db = _db()
    _override(app, db)

    with patch("app.api.routes.webhooks.log_action", AsyncMock()):
        resp = await client.post(
            BASE,
            json={
                "url": URL,
                "secret": SECRET,
                "events": ["analysis.completed", "gap.detected"],
                "description": "Slack dyżuru",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["url"] == URL
    assert body["events"] == ["analysis.completed", "gap.detected"]
    assert body["is_active"] is True
    # Sekret nie wychodzi w żadnej postaci
    assert "secret" not in body
    assert "secret_encrypted" not in body
    assert SECRET not in resp.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_odrzuca_adres_http(app, client):
    _override(app, _db())

    resp = await client.post(
        BASE, json={"url": "http://klient.example.com/hook", "secret": SECRET, "events": ["gap.detected"]}
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_odrzuca_krotki_sekret(app, client):
    _override(app, _db())

    resp = await client.post(BASE, json={"url": URL, "secret": "krótki", "events": ["gap.detected"]})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_odrzuca_pusta_liste_zdarzen(app, client):
    _override(app, _db())

    resp = await client.post(BASE, json={"url": URL, "secret": SECRET, "events": []})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_odrzuca_nieznane_zdarzenie(app, client):
    _override(app, _db())

    resp = await client.post(
        BASE, json={"url": URL, "secret": SECRET, "events": ["wymyslone.zdarzenie"]}
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_wymaga_roli_wlasciciela(app, client):
    """Webhook wynosi dane analiz poza TestGEN — to nie decyzja zwykłego użytkownika."""
    _override(app, _db(), role="user")

    resp = await client.post(BASE, json={"url": URL, "secret": SECRET, "events": ["gap.detected"]})

    assert resp.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_loguje_operacje(app, client):
    _override(app, _db())

    with patch("app.api.routes.webhooks.log_action", AsyncMock()) as audit:
        resp = await client.post(
            BASE, json={"url": URL, "secret": SECRET, "events": ["export.ready"]}
        )

    assert resp.status_code == 201
    assert audit.await_args.kwargs["action"] == "webhook.created"
    app.dependency_overrides.clear()


# ── lista (AC6) ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lista_zawiera_katalog_zdarzen(app, client):
    """Frontend nie musi powielać listy typów zdarzeń."""
    db = _db()
    tenant_id, user = _override(app, db)
    db.execute.return_value = _scalars([_webhook(tenant_id, user.id)])

    resp = await client.get(BASE)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert set(body["available_events"]) == {
        "analysis.completed",
        "security.finding",
        "gap.detected",
        "export.ready",
        "subscription.changed",
    }
    assert "secret_encrypted" not in body["items"][0]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lista_pokazuje_status_ostatniej_dostawy(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    db.execute.return_value = _scalars(
        [
            _webhook(
                tenant_id,
                user.id,
                last_delivery_status=DeliveryStatus.FAILED,
                last_delivery_at=datetime.now(UTC),
            )
        ]
    )

    resp = await client.get(BASE)

    assert resp.json()["items"][0]["last_delivery_status"] == "failed"
    app.dependency_overrides.clear()


# ── aktualizacja i usunięcie ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_zmienia_zdarzenia_bez_podawania_sekretu(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    webhook = _webhook(tenant_id, user.id, secret_encrypted="stary")
    db.execute.return_value = _scalar(webhook)

    with patch("app.api.routes.webhooks.log_action", AsyncMock()):
        resp = await client.put(
            f"{BASE}/{webhook.id}", json={"events": ["security.finding"], "is_active": False}
        )

    assert resp.status_code == 200
    assert resp.json()["events"] == ["security.finding"]
    assert resp.json()["is_active"] is False
    assert webhook.secret_encrypted == "stary"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_nieznanego_webhooka_to_404(app, client):
    db = _db()
    _override(app, db)
    db.execute.return_value = _scalar(None)

    resp = await client.put(f"{BASE}/{uuid.uuid4()}", json={"is_active": False})

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_zwraca_204(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    webhook = _webhook(tenant_id, user.id)
    db.execute.return_value = _scalar(webhook)

    with patch("app.api.routes.webhooks.log_action", AsyncMock()) as audit:
        resp = await client.delete(f"{BASE}/{webhook.id}")

    assert resp.status_code == 204
    db.delete.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "webhook.deleted"
    app.dependency_overrides.clear()


# ── test ping (AC1) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ping_zwraca_wynik_proby(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    webhook = _webhook(tenant_id, user.id)
    db.execute.return_value = _scalar(webhook)

    with patch(
        "app.services.integrations.webhook_service.WebhookService.test_webhook",
        AsyncMock(return_value={"success": True, "status_code": 200, "message": "Endpoint odpowiedział poprawnie"}),
    ):
        resp = await client.post(f"{BASE}/{webhook.id}/test")

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["status_code"] == 200
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ping_zglasza_niepowodzenie(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    webhook = _webhook(tenant_id, user.id)
    db.execute.return_value = _scalar(webhook)

    with patch(
        "app.services.integrations.webhook_service.WebhookService.test_webhook",
        AsyncMock(return_value={"success": False, "status_code": None, "message": "Przekroczono limit 10 s"}),
    ):
        resp = await client.post(f"{BASE}/{webhook.id}/test")

    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "limit" in resp.json()["message"]
    app.dependency_overrides.clear()


# ── historia dostaw (AC5) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_historia_dostaw_zwraca_proby(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    webhook = _webhook(tenant_id, user.id)
    deliveries = [
        WebhookDelivery(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            webhook_id=webhook.id,
            event_type="analysis.completed",
            payload={"event_type": "analysis.completed"},
            attempt_number=3,
            status=DeliveryStatus.FAILED,
            response_status=503,
            response_body="Service Unavailable",
            created_at=datetime.now(UTC),
        )
    ]
    db.execute.side_effect = [_scalar(webhook), _scalars(deliveries)]

    resp = await client.get(f"{BASE}/{webhook.id}/deliveries")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["status"] == "failed"
    assert item["attempt_number"] == 3
    assert item["response_status"] == 503
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_historia_cudzego_webhooka_to_404(app, client):
    db = _db()
    _override(app, db)
    db.execute.return_value = _scalar(None)

    resp = await client.get(f"{BASE}/{uuid.uuid4()}/deliveries")

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_historia_przyjmuje_filtry(app, client):
    db = _db()
    tenant_id, user = _override(app, db)
    webhook = _webhook(tenant_id, user.id)
    db.execute.side_effect = [_scalar(webhook), _scalars([])]

    resp = await client.get(
        f"{BASE}/{webhook.id}/deliveries",
        params={"status": "failed", "event_type": "gap.detected", "limit": 25},
    )

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    app.dependency_overrides.clear()
