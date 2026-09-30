"""Rozsyłanie zdarzeń do webhooków klienta — Epic 8, Story 8.7 (AC2).

Emiter jest celowo „cichy": moduł biznesowy woła go po zakończeniu swojej
pracy i nie sprawdza wyniku. Nieudana dostawa webhooka nie może wywrócić
analizy ani skanu bezpieczeństwa — to powiadomienie, nie część transakcji.

Sama wysyłka idzie przez Celery; tutaj powstają wyłącznie wiersze
``webhook_deliveries`` w stanie ``pending``. Dzięki temu zdarzenie nie
ginie, gdy worker padnie między zapisem a dostawą — zamiatacz ponowień
podejmie je z bazy.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbound_webhook import (
    DeliveryStatus,
    OutboundWebhook,
    WebhookDelivery,
)
from app.services.integrations.webhook_service import build_payload

logger = logging.getLogger(__name__)


async def _subscribers(
    db: AsyncSession, tenant_id: uuid.UUID, event_type: str
) -> list[OutboundWebhook]:
    """Aktywne webhooki tenanta subskrybujące dany typ zdarzenia."""
    result = await db.execute(
        select(OutboundWebhook).where(
            OutboundWebhook.tenant_id == tenant_id,
            OutboundWebhook.is_active.is_(True),
        )
    )
    # Dopasowanie w Pythonie: webhooków per tenant są jednostki, a zapytanie
    # z operatorem ANY po tablicy wiązałoby nas z dialektem Postgresa.
    # ``subscribes_to`` sprawdza jednocześnie aktywność i subskrypcję, więc
    # warunek jest jeden i ten sam niezależnie od tego, co odsiał SQL.
    return [w for w in result.scalars().all() if w.subscribes_to(event_type)]


async def emit_event(
    db: AsyncSession,
    event_type: str,
    tenant_id: uuid.UUID,
    data: dict[str, Any],
    *,
    dispatch: bool = True,
) -> list[WebhookDelivery]:
    """Tworzy dostawy dla subskrybentów zdarzenia i kolejkuje je (AC2).

    Zwraca utworzone wiersze; pustą listę, gdy nikt nie subskrybuje — to
    normalny przypadek, nie błąd.
    """
    try:
        webhooks = await _subscribers(db, tenant_id, event_type)
    except Exception:  # emiter nie może wywrócić modułu, który go zawołał
        logger.warning("Nie udało się odczytać webhooków dla %s", event_type, exc_info=True)
        return []

    if not webhooks:
        return []

    payload = build_payload(event_type, data)
    deliveries: list[WebhookDelivery] = []
    for webhook in webhooks:
        delivery = WebhookDelivery(
            tenant_id=tenant_id,
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload,
            attempt_number=1,
            status=DeliveryStatus.PENDING,
        )
        db.add(delivery)
        deliveries.append(delivery)

    await db.flush()

    if dispatch:
        for delivery in deliveries:
            _dispatch(delivery.id)

    return deliveries


def _dispatch(delivery_id: uuid.UUID) -> None:
    """Kolejkuje dostawę; import w środku rozcina cykl workers↔services."""
    try:
        from app.workers.tasks.webhook_tasks import deliver_webhook

        deliver_webhook.delay(str(delivery_id))
    except Exception:  # broker niedostępny — zamiatacz podejmie z bazy
        logger.warning("Nie udało się zakolejkować dostawy %s", delivery_id, exc_info=True)


async def emit_event_standalone(
    event_type: str,
    tenant_id: uuid.UUID,
    data: dict[str, Any],
) -> int:
    """Wariant dla miejsc bez otwartej sesji (zadania Celery).

    Otwiera własną sesję, ustawia kontekst RLS tenanta i commituje — zdarzenie
    musi być trwałe niezależnie od transakcji, w której powstało.
    """
    from sqlalchemy import text

    from app.core.database import task_session

    try:
        async with task_session() as session:
            await session.execute(
                text(f"SET LOCAL app.current_tenant = '{uuid.UUID(str(tenant_id))}'")
            )
            deliveries = await emit_event(session, event_type, tenant_id, data, dispatch=False)
            await session.commit()
            ids = [d.id for d in deliveries]
        for delivery_id in ids:  # dispatch po commicie — worker musi zobaczyć wiersz
            _dispatch(delivery_id)
        return len(ids)
    except Exception:
        logger.warning("Emisja zdarzenia %s nie powiodła się", event_type, exc_info=True)
        return 0
