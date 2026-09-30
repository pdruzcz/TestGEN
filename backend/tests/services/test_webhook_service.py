"""Testy serwisu webhooków wychodzących — Story 8.7 (AC1, AC3, AC4; Task 7.1).

Nacisk na podpis: odbiorca policzy HMAC nad bajtami, które faktycznie
dostanie, więc test musi sprawdzać, że podpisujemy dokładnie to samo,
co wysyłamy — nie „równoważny" JSON.
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.outbound_webhook import DeliveryStatus, OutboundWebhook
from app.services.integrations.webhook_service import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    MAX_ATTEMPTS,
    RETRY_DELAYS_SECONDS,
    SIGNATURE_HEADER,
    WebhookService,
    build_payload,
    next_retry_delay,
    serialize_payload,
    sign_payload,
    validate_events,
    validate_secret,
    validate_url,
)

SECRET = "s" * 32
TENANT = uuid.uuid4()
URL = "https://klient.example.com/hook"


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _webhook(**overrides) -> OutboundWebhook:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "user_id": uuid.uuid4(),
        "url": URL,
        "secret_encrypted": "enc",
        "events": ["analysis.completed"],
        "is_active": True,
    }
    defaults.update(overrides)
    return OutboundWebhook(**defaults)


def _patch_transport(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    original = httpx.AsyncClient

    def _factory(*args, **kwargs):
        def _handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        kwargs["transport"] = httpx.MockTransport(_handle)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return seen


# ── podpis (AC3) ─────────────────────────────────────────────────────────────


def test_podpis_ma_format_sha256():
    signature = sign_payload(b'{"a":1}', SECRET)

    assert signature.startswith("sha256=")
    assert len(signature) == len("sha256=") + 64


def test_podpis_zgadza_sie_z_niezaleznym_obliczeniem():
    """Odbiorca liczy go tak samo — to jest cały kontrakt weryfikacji."""
    body = b'{"event_type":"analysis.completed"}'
    expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    assert sign_payload(body, SECRET) == f"sha256={expected}"


def test_inny_sekret_daje_inny_podpis():
    body = b'{"a":1}'
    assert sign_payload(body, SECRET) != sign_payload(body, "i" * 32)


def test_zmiana_jednego_bajtu_zmienia_podpis():
    assert sign_payload(b'{"a":1}', SECRET) != sign_payload(b'{"a":2}', SECRET)


def test_serializacja_jest_deterministyczna():
    """Podpis liczymy nad bajtami wysyłanymi — kolejność kluczy musi być stała."""
    first = serialize_payload({"b": 2, "a": 1})
    second = serialize_payload({"a": 1, "b": 2})

    assert first == second
    assert json.loads(first) == {"a": 1, "b": 2}


def test_serializacja_zachowuje_znaki_narodowe():
    body = serialize_payload({"opis": "zażółć gęślą jaźń"})
    assert "zażółć" in body.decode("utf-8")


# ── payload (AC2) ────────────────────────────────────────────────────────────


def test_payload_ma_typ_i_znacznik_czasu():
    payload = build_payload("analysis.completed", {"project_id": "p1"})

    assert payload["event_type"] == "analysis.completed"
    assert payload["timestamp"].endswith("+00:00")
    assert payload["project_id"] == "p1"


def test_dane_modulu_nie_nadpisuja_pol_systemowych():
    """Moduł nie może podmienić typu zdarzenia ani znacznika czasu."""
    payload = build_payload(
        "security.finding", {"event_type": "podszywka", "timestamp": "kiedyś", "severity": "critical"}
    )

    assert payload["event_type"] == "security.finding"
    assert payload["timestamp"] != "kiedyś"
    assert payload["severity"] == "critical"


# ── walidacja konfiguracji (AC1) ─────────────────────────────────────────────


def test_url_musi_byc_https():
    assert validate_url(URL) == URL
    with pytest.raises(ValidationError, match="https"):
        validate_url("http://klient.example.com/hook")


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_pusty_url_odrzucony(bad):
    with pytest.raises(ValidationError):
        validate_url(bad)


def test_zbyt_dlugi_url_odrzucony():
    with pytest.raises(ValidationError, match="2048"):
        validate_url("https://x.pl/" + "a" * 2100)


def test_sekret_ma_minimalna_dlugosc():
    assert validate_secret(SECRET) == SECRET
    with pytest.raises(ValidationError, match="16"):
        validate_secret("krótki")


def test_lista_zdarzen_nie_moze_byc_pusta():
    with pytest.raises(ValidationError, match="co najmniej jeden"):
        validate_events([])


def test_nieznane_zdarzenie_odrzucone():
    with pytest.raises(ValidationError, match="Nieznane"):
        validate_events(["analysis.completed", "wymyslone.zdarzenie"])


def test_zdarzenia_sa_normalizowane():
    """Duplikaty szkodzą (podwójna dostawa), kolejność jest bez znaczenia."""
    assert validate_events(["gap.detected", "analysis.completed", "gap.detected"]) == [
        "analysis.completed",
        "gap.detected",
    ]


def test_wszystkie_piec_typow_jest_dozwolonych():
    events = [
        "analysis.completed",
        "security.finding",
        "gap.detected",
        "export.ready",
        "subscription.changed",
    ]
    assert validate_events(events) == sorted(events)


# ── CRUD ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_szyfruje_sekret_i_normalizuje_zdarzenia():
    db = _db()
    webhook = await WebhookService(db).create_webhook(
        tenant_id=TENANT,
        user_id=uuid.uuid4(),
        url=URL,
        secret=SECRET,
        events=["gap.detected", "analysis.completed"],
    )

    assert webhook.url == URL
    assert SECRET not in webhook.secret_encrypted
    assert webhook.events == ["analysis.completed", "gap.detected"]
    assert webhook.is_active is True
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_odrzuca_http():
    with pytest.raises(ValidationError):
        await WebhookService(_db()).create_webhook(
            tenant_id=TENANT,
            user_id=uuid.uuid4(),
            url="http://klient.example.com/hook",
            secret=SECRET,
            events=["analysis.completed"],
        )


@pytest.mark.asyncio
async def test_get_nieznanego_webhooka_to_404():
    db = _db()
    db.execute.return_value = _scalar(None)

    with pytest.raises(NotFoundError):
        await WebhookService(db).get_webhook(uuid.uuid4(), TENANT)


@pytest.mark.asyncio
async def test_update_bez_sekretu_go_nie_zmienia():
    """Zmiana adresu nie powinna wymagać ponownego podawania sekretu."""
    webhook = _webhook(secret_encrypted="stary-szyfrogram")
    db = _db()
    db.execute.return_value = _scalar(webhook)

    updated = await WebhookService(db).update_webhook(
        webhook.id, TENANT, url="https://nowy.example.com/hook"
    )

    assert updated.url == "https://nowy.example.com/hook"
    assert updated.secret_encrypted == "stary-szyfrogram"


@pytest.mark.asyncio
async def test_update_z_sekretem_go_wymienia():
    webhook = _webhook(secret_encrypted="stary-szyfrogram")
    db = _db()
    db.execute.return_value = _scalar(webhook)

    updated = await WebhookService(db).update_webhook(webhook.id, TENANT, secret="n" * 20)

    assert updated.secret_encrypted != "stary-szyfrogram"


@pytest.mark.asyncio
async def test_update_moze_wylaczyc_webhook():
    webhook = _webhook()
    db = _db()
    db.execute.return_value = _scalar(webhook)

    updated = await WebhookService(db).update_webhook(webhook.id, TENANT, is_active=False)

    assert updated.is_active is False


@pytest.mark.asyncio
async def test_lista_zwraca_webhooki_tenanta():
    webhooks = [_webhook(), _webhook()]
    db = _db()
    db.execute.return_value = _scalars(webhooks)

    assert await WebhookService(db).list_webhooks(TENANT) == webhooks


# ── dostarczanie ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_now_podpisuje_dokladnie_wysylane_bajty(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, text="ok"))
    service = WebhookService(_db())
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)
    payload = build_payload("analysis.completed", {"project_id": "p1"})
    delivery_id = uuid.uuid4()

    status_code, body, error = await service.send_now(_webhook(), payload, delivery_id)

    assert (status_code, body, error) == (200, "ok", None)
    request = seen[0]
    expected = hmac.new(SECRET.encode(), request.content, hashlib.sha256).hexdigest()
    assert request.headers[SIGNATURE_HEADER] == f"sha256={expected}"
    assert request.headers[EVENT_HEADER] == "analysis.completed"
    assert request.headers[DELIVERY_HEADER] == str(delivery_id)
    assert request.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_send_now_nie_rzuca_przy_timeoucie(monkeypatch):
    """Decyzję o ponowieniu podejmuje zadanie Celery, nie ta funkcja."""

    def _timeout(request):
        raise httpx.TimeoutException("za wolno")

    _patch_transport(monkeypatch, _timeout)
    service = WebhookService(_db())
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)

    status_code, _, error = await service.send_now(_webhook(), {"event_type": "x"})

    assert status_code is None
    assert "limit 10 s" in error


@pytest.mark.asyncio
async def test_send_now_nie_rzuca_przy_bledzie_sieci(monkeypatch):
    def _boom(request):
        raise httpx.ConnectError("DNS")

    _patch_transport(monkeypatch, _boom)
    service = WebhookService(_db())
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)

    status_code, _, error = await service.send_now(_webhook(), {"event_type": "x"})

    assert status_code is None
    assert "Błąd połączenia" in error


@pytest.mark.asyncio
async def test_send_now_przycina_cialo_odpowiedzi(monkeypatch):
    """Proxy potrafi oddać megabajt HTML-a — do diagnozy starczy 1 KB."""
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="x" * 5000))
    service = WebhookService(_db())
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)

    _, body, _ = await service.send_now(_webhook(), {"event_type": "x"})

    assert len(body) == 1024


# ── test ping (AC1) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ping_uznaje_2xx_za_sukces(monkeypatch):
    webhook = _webhook()
    db = _db()
    db.execute.return_value = _scalar(webhook)
    _patch_transport(monkeypatch, lambda r: httpx.Response(204))
    service = WebhookService(db)
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)

    result = await service.test_webhook(webhook.id, TENANT)

    assert result["success"] is True
    assert result["status_code"] == 204


@pytest.mark.asyncio
async def test_ping_zglasza_kod_bledu(monkeypatch):
    webhook = _webhook()
    db = _db()
    db.execute.return_value = _scalar(webhook)
    _patch_transport(monkeypatch, lambda r: httpx.Response(404, text="nie ma"))
    service = WebhookService(db)
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)

    result = await service.test_webhook(webhook.id, TENANT)

    assert result["success"] is False
    assert "404" in result["message"]


@pytest.mark.asyncio
async def test_ping_nie_zapisuje_dostawy(monkeypatch):
    """Ping to sprawdzenie konfiguracji — nie może zaśmiecać historii."""
    webhook = _webhook()
    db = _db()
    db.execute.return_value = _scalar(webhook)
    _patch_transport(monkeypatch, lambda r: httpx.Response(200))
    service = WebhookService(db)
    monkeypatch.setattr(service, "secret_of", lambda w: SECRET)

    await service.test_webhook(webhook.id, TENANT)

    db.add.assert_not_called()


# ── harmonogram ponowień (AC4) ───────────────────────────────────────────────


def test_odstepy_ponowien_to_minuta_piec_i_trzydziesci():
    assert RETRY_DELAYS_SECONDS == (60, 300, 1800)
    assert MAX_ATTEMPTS == 4  # pierwsza próba + trzy ponowienia


@pytest.mark.parametrize(("attempt", "delay"), [(1, 60), (2, 300), (3, 1800)])
def test_kolejne_proby_maja_rosnacy_odstep(attempt, delay):
    assert next_retry_delay(attempt) == delay


def test_po_trzech_ponowieniach_nie_ma_kolejnego_terminu():
    assert next_retry_delay(4) is None
    assert next_retry_delay(99) is None


def test_nieprawidlowy_numer_proby_nie_wywraca_harmonogramu():
    assert next_retry_delay(0) is None
    assert next_retry_delay(-1) is None


# ── historia dostaw (AC5) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_historia_odrzuca_cudzy_webhook():
    db = _db()
    db.execute.return_value = _scalar(None)

    with pytest.raises(NotFoundError):
        await WebhookService(db).list_deliveries(uuid.uuid4(), TENANT)


@pytest.mark.asyncio
async def test_historia_przyjmuje_filtr_statusu():
    webhook = _webhook()
    db = _db()
    db.execute.side_effect = [_scalar(webhook), _scalars([])]

    result = await WebhookService(db).list_deliveries(
        webhook.id, TENANT, status=DeliveryStatus.FAILED.value
    )

    assert result == []
