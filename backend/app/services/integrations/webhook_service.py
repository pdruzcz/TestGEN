"""Webhooki wychodzące — podpisywanie, dostarczanie, CRUD (Story 8.7).

Payload podpisujemy HMAC-SHA256 nad **dokładnie tymi bajtami**, które lecą
w ciele żądania. Serializację robimy raz i wysyłamy ten sam ``bytes``:
ponowne ``json.dumps`` mogłoby zmienić kolejność kluczy albo separatory
i odbiorca policzyłby inny podpis niż my.

Pojedyncza próba dostarczenia niczego nie ponawia — ponowieniami steruje
zadanie Celery (``workers/tasks/webhook_tasks.py``), bo stan między próbami
musi przetrwać restart workera.
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_token, encrypt_token
from app.core.exceptions import NotFoundError, ValidationError
from app.models.outbound_webhook import (
    DeliveryStatus,
    OutboundWebhook,
    WebhookDelivery,
    WebhookEventType,
)

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-TestGEN-Signature"
EVENT_HEADER = "X-TestGEN-Event"
DELIVERY_HEADER = "X-TestGEN-Delivery"

DELIVERY_TIMEOUT_SECONDS = 10.0
MIN_SECRET_LENGTH = 16
MAX_URL_LENGTH = 2048
_MAX_RESPONSE_BODY = 1024

# Odstępy ponowień w sekundach (AC4): 1 min, 5 min, 30 min.
RETRY_DELAYS_SECONDS: tuple[int, ...] = (60, 300, 1800)
MAX_ATTEMPTS = len(RETRY_DELAYS_SECONDS) + 1  # pierwsza próba + trzy ponowienia

ALLOWED_EVENTS = frozenset(e.value for e in WebhookEventType)


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """``sha256={hex}`` — ten sam format, którego używają GitHub i GitLab."""
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def serialize_payload(payload: dict[str, Any]) -> bytes:
    """Kanoniczna serializacja — podpis liczymy nad tym, co realnie wysyłamy."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def build_payload(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Składa ciało zdarzenia: typ, znacznik czasu i dane modułu (AC2).

    Pola specyficzne dla zdarzenia wchodzą płasko, żeby odbiorca nie musiał
    schodzić o poziom niżej; ``event_type`` i ``timestamp`` są zawsze.
    """
    body = {
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    body.update({k: v for k, v in data.items() if k not in ("event_type", "timestamp")})
    return body


def validate_url(url: str) -> str:
    """Wymusza HTTPS — payload niesie dane klienta, a podpis nie szyfruje treści."""
    candidate = (url or "").strip()
    if not candidate:
        raise ValidationError("Adres webhooka jest wymagany")
    if len(candidate) > MAX_URL_LENGTH:
        raise ValidationError(f"Adres webhooka może mieć maksymalnie {MAX_URL_LENGTH} znaków")
    if not candidate.startswith("https://"):
        raise ValidationError("Adres webhooka musi zaczynać się od https://")
    return candidate


def validate_secret(secret: str) -> str:
    secret = (secret or "").strip()
    if len(secret) < MIN_SECRET_LENGTH:
        raise ValidationError(f"Sekret musi mieć co najmniej {MIN_SECRET_LENGTH} znaków")
    return secret


def validate_events(events: list[str]) -> list[str]:
    if not events:
        raise ValidationError("Wybierz co najmniej jeden typ zdarzenia")
    unknown = [e for e in events if e not in ALLOWED_EVENTS]
    if unknown:
        raise ValidationError(f"Nieznane typy zdarzeń: {', '.join(sorted(unknown))}")
    # Kolejność bez znaczenia, duplikaty szkodzą — normalizujemy.
    return sorted(set(events))


class WebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def create_webhook(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        url: str,
        secret: str,
        events: list[str],
        description: str | None = None,
    ) -> OutboundWebhook:
        webhook = OutboundWebhook(
            tenant_id=tenant_id,
            user_id=user_id,
            url=validate_url(url),
            secret_encrypted=encrypt_token(validate_secret(secret), tenant_id),
            events=validate_events(events),
            description=(description or "").strip() or None,
            is_active=True,
        )
        self.db.add(webhook)
        await self.db.flush()
        return webhook

    async def list_webhooks(self, tenant_id: uuid.UUID) -> list[OutboundWebhook]:
        result = await self.db.execute(
            select(OutboundWebhook)
            .where(OutboundWebhook.tenant_id == tenant_id)
            .order_by(OutboundWebhook.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_webhook(self, webhook_id: uuid.UUID, tenant_id: uuid.UUID) -> OutboundWebhook:
        result = await self.db.execute(
            select(OutboundWebhook).where(
                OutboundWebhook.id == webhook_id,
                OutboundWebhook.tenant_id == tenant_id,
            )
        )
        webhook = result.scalar_one_or_none()
        if webhook is None:
            raise NotFoundError("Webhook nie został znaleziony")
        return webhook

    async def update_webhook(
        self,
        webhook_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        url: str | None = None,
        secret: str | None = None,
        events: list[str] | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> OutboundWebhook:
        """Aktualizuje webhook; pominięte pola zostają bez zmian.

        Pusty sekret oznacza „nie zmieniaj" — klient nie musi go znać, żeby
        zmienić adres albo listę zdarzeń.
        """
        webhook = await self.get_webhook(webhook_id, tenant_id)
        if url is not None:
            webhook.url = validate_url(url)
        if secret:
            webhook.secret_encrypted = encrypt_token(validate_secret(secret), tenant_id)
        if events is not None:
            webhook.events = validate_events(events)
        if description is not None:
            webhook.description = description.strip() or None
        if is_active is not None:
            webhook.is_active = is_active
        await self.db.flush()
        return webhook

    async def delete_webhook(self, webhook_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        webhook = await self.get_webhook(webhook_id, tenant_id)
        await self.db.delete(webhook)
        await self.db.flush()

    # ── dostarczanie ────────────────────────────────────────────────────────

    def secret_of(self, webhook: OutboundWebhook) -> str:
        return decrypt_token(webhook.secret_encrypted, webhook.tenant_id)

    async def send_now(
        self,
        webhook: OutboundWebhook,
        payload: dict[str, Any],
        delivery_id: uuid.UUID | None = None,
    ) -> tuple[int | None, str, str | None]:
        """Jedno żądanie POST. Zwraca ``(status_http, ciało, błąd)``.

        Nie rzuca przy błędzie sieci — wywołujący zapisuje wynik próby, a
        decyzję o ponowieniu podejmuje zadanie Celery.
        """
        body = serialize_payload(payload)
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign_payload(body, self.secret_of(webhook)),
            EVENT_HEADER: str(payload.get("event_type", "")),
            # Klucz idempotencji — odbiorca rozpozna po nim powtórzoną dostawę.
            DELIVERY_HEADER: str(delivery_id or uuid.uuid4()),
            "User-Agent": "TestGEN-Webhook/1.0",
        }
        try:
            async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_SECONDS) as client:
                response = await client.post(webhook.url, content=body, headers=headers)
        except httpx.TimeoutException:
            return None, "", f"Przekroczono limit {int(DELIVERY_TIMEOUT_SECONDS)} s"
        except httpx.HTTPError as exc:
            return None, "", f"Błąd połączenia: {exc}"

        return response.status_code, response.text[:_MAX_RESPONSE_BODY], None

    async def test_webhook(self, webhook_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any]:
        """Wysyła testowy ping i zwraca wynik bez zapisywania dostawy (AC1).

        Ping nie trafia do historii: to sprawdzenie konfiguracji, nie
        zdarzenie biznesowe — inaczej zaśmiecałby listę dostaw.
        """
        webhook = await self.get_webhook(webhook_id, tenant_id)
        payload = build_payload(
            "ping",
            {"message": "Testowa dostawa z TestGEN", "webhook_id": str(webhook.id)},
        )
        status_code, body, error = await self.send_now(webhook, payload)

        if error:
            return {"success": False, "status_code": None, "message": error}
        success = 200 <= (status_code or 0) < 300
        return {
            "success": success,
            "status_code": status_code,
            "message": (
                "Endpoint odpowiedział poprawnie"
                if success
                else f"Endpoint odpowiedział kodem {status_code}"
            ),
            "response_body": body[:500] or None,
        }

    async def list_deliveries(
        self,
        webhook_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        limit: int = 100,
        status: str | None = None,
        event_type: str | None = None,
    ) -> list[WebhookDelivery]:
        """Historia dostaw webhooka, najnowsze pierwsze (AC5)."""
        await self.get_webhook(webhook_id, tenant_id)  # 404 dla cudzego webhooka

        stmt = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.tenant_id == tenant_id,
            )
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(WebhookDelivery.status == DeliveryStatus(status))
        if event_type:
            stmt = stmt.where(WebhookDelivery.event_type == event_type)

        return list((await self.db.execute(stmt)).scalars().all())


def next_retry_delay(attempt_number: int) -> int | None:
    """Odstęp przed kolejną próbą albo ``None``, gdy limit wyczerpany (AC4).

    ``attempt_number`` to numer próby, która właśnie się nie powiodła.
    """
    if attempt_number < 1 or attempt_number > len(RETRY_DELAYS_SECONDS):
        return None
    return RETRY_DELAYS_SECONDS[attempt_number - 1]
