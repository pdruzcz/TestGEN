"""Testy dostarczania i ponowień webhooków — Story 8.7 (AC4; Task 7.4).

Ponowienia to najdelikatniejsza część tej story: pomyłka albo gubi dostawę,
albo zalewa endpoint klienta powtórkami. Testy sprawdzają obie granice —
narastające odstępy i twardy koniec po wyczerpaniu prób.

Wzorzec mockowania sesji: test_integration_status_tasks.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.elements import TextClause

from app.models.outbound_webhook import DeliveryStatus, OutboundWebhook, WebhookDelivery

TENANT = uuid.uuid4()


def _session_ctx(session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _webhook(**overrides) -> OutboundWebhook:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "user_id": uuid.uuid4(),
        "url": "https://klient.example.com/hook",
        "secret_encrypted": "enc",
        "events": ["analysis.completed"],
        "is_active": True,
    }
    defaults.update(overrides)
    return OutboundWebhook(**defaults)


def _delivery(webhook, **overrides) -> WebhookDelivery:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "webhook_id": webhook.id,
        "event_type": "analysis.completed",
        "payload": {"event_type": "analysis.completed", "project_id": "p1"},
        "attempt_number": 1,
        "status": DeliveryStatus.PENDING,
    }
    defaults.update(overrides)
    return WebhookDelivery(**defaults)


def _session(delivery, webhook, pending: list | None = None) -> AsyncMock:
    session = AsyncMock()

    async def _get(model, _id):
        if model is WebhookDelivery:
            return delivery
        if model is OutboundWebhook:
            return webhook
        return None

    session.get = AsyncMock(side_effect=_get)

    async def _execute(statement, *args, **kwargs):
        result = MagicMock()
        if isinstance(statement, TextClause):
            return result
        result.scalars.return_value.all.return_value = pending or []
        return result

    session.execute = AsyncMock(side_effect=_execute)
    return session


async def _deliver(delivery, webhook, *, send_result):
    from app.workers.tasks import webhook_tasks

    session = _session(delivery, webhook)
    with patch("app.core.database.task_session", return_value=_session_ctx(session)), patch(
        "app.services.integrations.webhook_service.WebhookService.send_now",
        AsyncMock(return_value=send_result),
    ), patch(
        "app.workers.tasks.webhook_tasks.deliver_webhook.apply_async"
    ) as scheduled, patch(
        "app.workers.tasks.webhook_tasks._log_exhausted", AsyncMock()
    ) as audit:
        result = await webhook_tasks._deliver_impl(str(delivery.id))
    return result, scheduled, audit


# ── sukces ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_odpowiedz_2xx_oznacza_dostarczone():
    webhook = _webhook()
    delivery = _delivery(webhook)

    result, scheduled, _ = await _deliver(delivery, webhook, send_result=(200, "ok", None))

    assert result["status"] == "delivered"
    assert delivery.status == DeliveryStatus.DELIVERED
    assert delivery.delivered_at is not None
    assert delivery.next_retry_at is None
    assert webhook.last_delivery_status == DeliveryStatus.DELIVERED
    scheduled.assert_not_called()


@pytest.mark.parametrize("code", [200, 201, 202, 204, 299])
@pytest.mark.asyncio
async def test_cale_pasmo_2xx_uznajemy_za_sukces(code):
    webhook = _webhook()
    delivery = _delivery(webhook)

    result, _, _ = await _deliver(delivery, webhook, send_result=(code, "", None))

    assert result["status"] == "delivered"


@pytest.mark.asyncio
async def test_juz_dostarczona_nie_jest_wysylana_ponownie():
    """Zamiatacz i zadanie z countdown mogą podjąć tę samą dostawę."""
    from app.workers.tasks import webhook_tasks

    webhook = _webhook()
    delivery = _delivery(webhook, status=DeliveryStatus.DELIVERED)
    session = _session(delivery, webhook)

    send = AsyncMock()
    with patch("app.core.database.task_session", return_value=_session_ctx(session)), patch(
        "app.services.integrations.webhook_service.WebhookService.send_now", send
    ):
        result = await webhook_tasks._deliver_impl(str(delivery.id))

    assert result == {"status": "already_delivered"}
    send.assert_not_awaited()


# ── ponowienia (AC4) ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_piecsetka_planuje_ponowienie_za_minute():
    webhook = _webhook()
    delivery = _delivery(webhook)

    result, scheduled, _ = await _deliver(delivery, webhook, send_result=(503, "down", None))

    assert result == {"status": "retry_scheduled", "attempt": 2, "delay": 60}
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempt_number == 2
    assert delivery.next_retry_at > datetime.now(UTC)
    scheduled.assert_called_once()
    assert scheduled.call_args.kwargs["countdown"] == 60


@pytest.mark.parametrize(("attempt", "delay"), [(1, 60), (2, 300), (3, 1800)])
@pytest.mark.asyncio
async def test_odstepy_rosna_z_kazda_proba(attempt, delay):
    webhook = _webhook()
    delivery = _delivery(webhook, attempt_number=attempt)

    result, scheduled, _ = await _deliver(delivery, webhook, send_result=(500, "", None))

    assert result["delay"] == delay
    assert scheduled.call_args.kwargs["countdown"] == delay


@pytest.mark.asyncio
async def test_timeout_tez_uruchamia_ponowienie():
    webhook = _webhook()
    delivery = _delivery(webhook)

    result, _, _ = await _deliver(
        delivery, webhook, send_result=(None, "", "Przekroczono limit 10 s")
    )

    assert result["status"] == "retry_scheduled"
    assert delivery.error_message == "Przekroczono limit 10 s"


@pytest.mark.asyncio
async def test_po_czwartej_probie_dostawa_jest_nieudana():
    """Trzy ponowienia po pierwszej próbie — dalej nie próbujemy."""
    webhook = _webhook()
    delivery = _delivery(webhook, attempt_number=4)

    result, scheduled, audit = await _deliver(delivery, webhook, send_result=(500, "", None))

    assert result == {"status": "failed", "attempts": 4}
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.next_retry_at is None
    assert webhook.last_delivery_status == DeliveryStatus.FAILED
    scheduled.assert_not_called()
    audit.assert_awaited_once()  # ślad w audycie (AC4)


@pytest.mark.asyncio
async def test_kod_4xx_tez_prowadzi_do_ponowienia_a_potem_porazki():
    """Błąd po stronie odbiorcy bywa przejściowy (np. 429) — próbujemy dalej."""
    webhook = _webhook()
    delivery = _delivery(webhook, attempt_number=4)

    result, _, _ = await _deliver(delivery, webhook, send_result=(404, "brak", None))

    assert result["status"] == "failed"
    assert delivery.response_status == 404


# ── stany brzegowe ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nieistniejaca_dostawa_nie_wywraca_workera():
    from app.workers.tasks import webhook_tasks

    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=MagicMock())

    with patch("app.core.database.task_session", return_value=_session_ctx(session)):
        result = await webhook_tasks._deliver_impl(str(uuid.uuid4()))

    assert result == {"status": "missing"}


@pytest.mark.asyncio
async def test_wylaczony_webhook_konczy_dostawe_bez_wysylki():
    from app.workers.tasks import webhook_tasks

    webhook = _webhook(is_active=False)
    delivery = _delivery(webhook)
    session = _session(delivery, webhook)

    send = AsyncMock()
    with patch("app.core.database.task_session", return_value=_session_ctx(session)), patch(
        "app.services.integrations.webhook_service.WebhookService.send_now", send
    ):
        result = await webhook_tasks._deliver_impl(str(delivery.id))

    assert result == {"status": "skipped"}
    assert delivery.status == DeliveryStatus.FAILED
    assert "usunięty lub wyłączony" in delivery.error_message
    send.assert_not_awaited()


# ── zamiatacz (AC4) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zamiatacz_podejmuje_zalegle_dostawy():
    from app.workers.tasks import webhook_tasks

    webhook = _webhook()
    stale = [
        _delivery(webhook, next_retry_at=datetime.now(UTC) - timedelta(minutes=5)),
        _delivery(webhook, next_retry_at=datetime.now(UTC) - timedelta(minutes=1)),
    ]
    session = _session(None, webhook, pending=stale)

    with patch("app.core.database.task_session", return_value=_session_ctx(session)), patch(
        "app.workers.tasks.webhook_tasks.deliver_webhook.delay"
    ) as dispatch:
        result = await webhook_tasks._sweep_impl()

    assert result == {"requeued": 2}
    assert dispatch.call_count == 2
    # Termin wyczyszczony — spóźnione zadanie z countdown nie podejmie ich drugi raz
    assert all(d.next_retry_at is None for d in stale)


@pytest.mark.asyncio
async def test_zamiatacz_bez_zaleglosci_nic_nie_robi():
    from app.workers.tasks import webhook_tasks

    session = _session(None, _webhook(), pending=[])

    with patch("app.core.database.task_session", return_value=_session_ctx(session)), patch(
        "app.workers.tasks.webhook_tasks.deliver_webhook.delay"
    ) as dispatch:
        result = await webhook_tasks._sweep_impl()

    assert result == {"requeued": 0}
    dispatch.assert_not_called()


# ── konfiguracja Celery ──────────────────────────────────────────────────────


def test_zadania_ida_na_wlasna_kolejke():
    """Zablokowany endpoint klienta nie może wstrzymywać analiz."""
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert routes["webhooks.deliver"] == {"queue": "webhooks"}
    assert routes["webhooks.retry_pending"] == {"queue": "webhooks"}
    assert "webhooks" in [q.name for q in celery_app.conf.task_queues]


def test_zamiatacz_w_harmonogramie_co_minute():
    from celery.schedules import crontab

    from app.workers.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["webhooks-retry-pending-every-minute"]
    assert entry["task"] == "webhooks.retry_pending"
    assert entry["schedule"] == crontab(minute="*")


def test_celery_nie_ponawia_samo():
    """Ponowienia prowadzimy ze stanem w bazie — wbudowany retry by je dublował."""
    from app.workers.tasks.webhook_tasks import deliver_webhook

    assert deliver_webhook.max_retries == 0
