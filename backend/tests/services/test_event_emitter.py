"""Testy emitera zdarzeń — Story 8.7 (AC2; Task 7.2).

Emiter ma dwie własności, na których wszystko stoi: trafia wyłącznie do
subskrybentów danego zdarzenia i nigdy nie wywraca modułu, który go zawołał.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.outbound_webhook import DeliveryStatus, OutboundWebhook
from app.services.integrations.event_emitter import emit_event

TENANT = uuid.uuid4()


def _db(webhooks: list) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = webhooks
    db.execute = AsyncMock(return_value=result)
    return db


def _webhook(events: list[str], *, is_active: bool = True) -> OutboundWebhook:
    return OutboundWebhook(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        user_id=uuid.uuid4(),
        url="https://klient.example.com/hook",
        secret_encrypted="enc",
        events=events,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_tworzy_dostawe_dla_subskrybenta():
    webhook = _webhook(["analysis.completed"])
    db = _db([webhook])

    with patch("app.services.integrations.event_emitter._dispatch") as dispatch:
        deliveries = await emit_event(db, "analysis.completed", TENANT, {"project_id": "p1"})

    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.webhook_id == webhook.id
    assert delivery.event_type == "analysis.completed"
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempt_number == 1
    assert delivery.payload["project_id"] == "p1"
    dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_pomija_webhooki_bez_subskrypcji_zdarzenia():
    db = _db([_webhook(["gap.detected"]), _webhook(["export.ready"])])

    with patch("app.services.integrations.event_emitter._dispatch") as dispatch:
        deliveries = await emit_event(db, "analysis.completed", TENANT, {})

    assert deliveries == []
    dispatch.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_pomija_webhooki_wylaczone():
    db = _db([_webhook(["analysis.completed"], is_active=False)])

    with patch("app.services.integrations.event_emitter._dispatch"):
        assert await emit_event(db, "analysis.completed", TENANT, {}) == []


@pytest.mark.asyncio
async def test_kilku_subskrybentow_dostaje_osobne_dostawy():
    """Każdy endpoint ma własny wiersz — historia prób jest per odbiorca."""
    db = _db([_webhook(["security.finding"]), _webhook(["security.finding", "gap.detected"])])

    with patch("app.services.integrations.event_emitter._dispatch") as dispatch:
        deliveries = await emit_event(db, "security.finding", TENANT, {"severity": "critical"})

    assert len(deliveries) == 2
    assert len({d.webhook_id for d in deliveries}) == 2
    assert dispatch.call_count == 2


@pytest.mark.asyncio
async def test_wszystkie_dostawy_niosa_ten_sam_payload():
    db = _db([_webhook(["gap.detected"]), _webhook(["gap.detected"])])

    with patch("app.services.integrations.event_emitter._dispatch"):
        deliveries = await emit_event(db, "gap.detected", TENANT, {"gap_id": "g1"})

    assert deliveries[0].payload == deliveries[1].payload


@pytest.mark.asyncio
async def test_bez_dispatchu_nie_kolejkuje():
    """Wariant dla emisji w cudzej transakcji — kolejkujemy dopiero po commicie."""
    db = _db([_webhook(["export.ready"])])

    with patch("app.services.integrations.event_emitter._dispatch") as dispatch:
        deliveries = await emit_event(db, "export.ready", TENANT, {}, dispatch=False)

    assert len(deliveries) == 1
    dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_blad_odczytu_webhookow_nie_wywraca_wolajacego():
    """Moduł biznesowy skończył pracę — emiter nie może jej unieważnić."""
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("baza padła"))

    assert await emit_event(db, "analysis.completed", TENANT, {}) == []


@pytest.mark.asyncio
async def test_awaria_brokera_nie_wywraca_emisji():
    """Wiersz w bazie zostaje — zamiatacz podejmie dostawę później."""
    db = _db([_webhook(["analysis.completed"])])

    with patch(
        "app.workers.tasks.webhook_tasks.deliver_webhook.delay",
        side_effect=RuntimeError("RabbitMQ padł"),
    ):
        deliveries = await emit_event(db, "analysis.completed", TENANT, {})

    assert len(deliveries) == 1


@pytest.mark.parametrize(
    "event_type",
    [
        "analysis.completed",
        "security.finding",
        "gap.detected",
        "export.ready",
        "subscription.changed",
    ],
)
@pytest.mark.asyncio
async def test_wszystkie_piec_typow_przechodzi_przez_emiter(event_type):
    db = _db([_webhook([event_type])])

    with patch("app.services.integrations.event_emitter._dispatch"):
        deliveries = await emit_event(db, event_type, TENANT, {})

    assert deliveries[0].event_type == event_type
    assert deliveries[0].payload["event_type"] == event_type
