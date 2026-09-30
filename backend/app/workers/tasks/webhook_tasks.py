"""Dostarczanie webhooków wychodzących — Epic 8, Story 8.7 (AC4).

Ponowienia prowadzimy przez Celery, a nie przez retry w httpx: stan między
próbami (numer próby, kod odpowiedzi, termin kolejnej) musi przetrwać
restart workera, więc mieszka w ``webhook_deliveries``.

Dwa mechanizmy, celowo nakładające się:

* zadanie samo planuje kolejną próbę (``apply_async(countdown=...)``) —
  szybka ścieżka,
* zamiatacz z beat co minutę podejmuje dostawy z zaległym ``next_retry_at`` —
  siatka bezpieczeństwa na zgubione wiadomości i restarty brokera.

Podwójne podjęcie tej samej dostawy jest nieszkodliwe: zamiatacz bierze
tylko te z terminem w przeszłości i od razu go czyści.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Ile dostaw bierze jeden przebieg zamiatacza — limit chroni przed zalaniem
# kolejki po dłuższej awarii endpointu klienta.
_SWEEP_BATCH = 200


async def _deliver_impl(delivery_id: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.outbound_webhook import DeliveryStatus, OutboundWebhook, WebhookDelivery
    from app.services.integrations.webhook_service import (
        MAX_ATTEMPTS,
        WebhookService,
        next_retry_delay,
    )

    did = uuid.UUID(delivery_id)

    async with task_session() as session:
        await session.execute(
            text("SET LOCAL app.current_tenant = '00000000-0000-0000-0000-000000000000'")
        )
        delivery = await session.get(WebhookDelivery, did)
        if delivery is None:
            logger.warning("Dostawa %s nie istnieje — pomijam", delivery_id)
            return {"status": "missing"}
        if delivery.status == DeliveryStatus.DELIVERED:
            return {"status": "already_delivered"}

        webhook = await session.get(OutboundWebhook, delivery.webhook_id)
        if webhook is None or not webhook.is_active:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = "Webhook został usunięty lub wyłączony"
            delivery.next_retry_at = None
            await session.commit()
            return {"status": "skipped"}

        tid = delivery.tenant_id
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        service = WebhookService(session)
        status_code, body, error = await service.send_now(webhook, delivery.payload, delivery.id)

        delivery.response_status = status_code
        delivery.response_body = body or None
        delivery.error_message = error
        now = datetime.now(UTC)

        if status_code is not None and 200 <= status_code < 300:
            delivery.status = DeliveryStatus.DELIVERED
            delivery.delivered_at = now
            delivery.next_retry_at = None
            webhook.last_delivery_at = now
            webhook.last_delivery_status = DeliveryStatus.DELIVERED
            await session.commit()
            return {"status": "delivered", "attempt": delivery.attempt_number}

        delay = next_retry_delay(delivery.attempt_number)
        if delay is None or delivery.attempt_number >= MAX_ATTEMPTS:
            delivery.status = DeliveryStatus.FAILED
            delivery.next_retry_at = None
            webhook.last_delivery_at = now
            webhook.last_delivery_status = DeliveryStatus.FAILED
            await session.commit()
            await _log_exhausted(tid, webhook, delivery)
            return {"status": "failed", "attempts": delivery.attempt_number}

        # Kolejna próba: numer rośnie już teraz, żeby zamiatacz nie policzył
        # tej samej próby dwa razy.
        delivery.attempt_number += 1
        delivery.status = DeliveryStatus.PENDING
        delivery.next_retry_at = now + timedelta(seconds=delay)
        await session.commit()

        deliver_webhook.apply_async(args=[delivery_id], countdown=delay)
        return {"status": "retry_scheduled", "attempt": delivery.attempt_number, "delay": delay}


async def _log_exhausted(tenant_id, webhook, delivery) -> None:
    """Wyczerpanie prób zostawia ślad w audycie (AC4)."""
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.admin.audit_service import log_action

    try:
        async with task_session() as session:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            await log_action(
                session,
                tenant_id=tenant_id,
                user_id=None,
                action="webhook.delivery_failed",
                resource_type="outbound_webhook",
                resource_id=webhook.id,
                changes={
                    "url": webhook.url,
                    "event_type": delivery.event_type,
                    "attempts": delivery.attempt_number,
                    "response_status": delivery.response_status,
                    "error": delivery.error_message,
                },
            )
            await session.commit()
    except Exception:
        logger.warning("Nie udało się zapisać audytu nieudanej dostawy", exc_info=True)


async def _sweep_impl() -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.models.outbound_webhook import DeliveryStatus, WebhookDelivery

    now = datetime.now(UTC)
    async with task_session() as session:
        await session.execute(
            text("SET LOCAL app.current_tenant = '00000000-0000-0000-0000-000000000000'")
        )
        result = await session.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == DeliveryStatus.PENDING,
                WebhookDelivery.next_retry_at.is_not(None),
                WebhookDelivery.next_retry_at <= now,
            )
            .order_by(WebhookDelivery.next_retry_at)
            .limit(_SWEEP_BATCH)
        )
        pending = list(result.scalars().all())
        for delivery in pending:
            # Czyścimy termin od razu — gdyby zadanie z countdown jednak
            # dotarło, nie podjęłoby tej dostawy po raz drugi.
            delivery.next_retry_at = None
        await session.commit()
        ids = [str(d.id) for d in pending]

    for delivery_id in ids:
        deliver_webhook.delay(delivery_id)

    return {"requeued": len(ids)}


@celery_app.task(
    bind=True,
    name="webhooks.deliver",
    queue="webhooks",
    max_retries=0,  # ponowienia prowadzimy sami, ze stanem w bazie
)
def deliver_webhook(self, delivery_id: str) -> dict:
    """Jedna próba dostarczenia; przy niepowodzeniu planuje kolejną (AC4)."""
    try:
        return asyncio.run(_deliver_impl(delivery_id))
    except Exception as exc:
        logger.error("Dostarczanie webhooka %s przerwane: %s", delivery_id, exc)
        raise


@celery_app.task(
    name="webhooks.retry_pending",
    queue="webhooks",
)
def retry_pending_webhook_deliveries() -> dict:
    """Zamiatacz: podejmuje dostawy z zaległym terminem ponowienia (AC4)."""
    return asyncio.run(_sweep_impl())
