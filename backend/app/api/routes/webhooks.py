"""Webhooki wychodzące TestGEN — Epic 8, Story 8.7.

Nie mylić z ``webhooks_tpay`` (prefiks ``/billing/webhooks``), który przyjmuje
notyfikacje od operatora płatności. Tu chodzi o ruch w drugą stronę: to my
powiadamiamy systemy klienta.

Zarządzanie wymaga sesji właściciela firmy — webhook wynosi dane analiz poza
TestGEN, więc decyzja o jego założeniu nie należy do zwykłego użytkownika.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_tenant, require_role, require_session
from app.models.user import User
from app.schemas.webhook import (
    CreateWebhookRequest,
    TestWebhookResponse,
    UpdateWebhookRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookListResponse,
    WebhookResponse,
)
from app.services.admin.audit_service import log_action
from app.services.integrations.webhook_service import WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks-outbound"])


def _to_response(webhook) -> WebhookResponse:
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        description=webhook.description,
        events=list(webhook.events or []),
        is_active=webhook.is_active,
        last_delivery_at=webhook.last_delivery_at,
        last_delivery_status=(
            webhook.last_delivery_status.value if webhook.last_delivery_status else None
        ),
        created_at=webhook.created_at,
    )


def _delivery_response(delivery) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=delivery.id,
        webhook_id=delivery.webhook_id,
        event_type=delivery.event_type,
        status=delivery.status.value,
        attempt_number=delivery.attempt_number,
        response_status=delivery.response_status,
        response_body=delivery.response_body,
        error_message=delivery.error_message,
        delivered_at=delivery.delivered_at,
        next_retry_at=delivery.next_retry_at,
        created_at=delivery.created_at,
    )


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: CreateWebhookRequest,
    request: Request,
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Tworzy webhook i zapisuje sekret w postaci zaszyfrowanej (AC1)."""
    service = WebhookService(db)
    webhook = await service.create_webhook(
        tenant_id=tenant_id,
        user_id=current_user.id,
        url=body.url,
        secret=body.secret,
        events=list(body.events),
        description=body.description,
    )
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="webhook.created",
        resource_type="outbound_webhook",
        resource_id=webhook.id,
        changes={"url": webhook.url, "events": webhook.events},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(webhook)
    return _to_response(webhook)


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> WebhookListResponse:
    """Webhooki firmy wraz z katalogiem dostępnych zdarzeń (AC6)."""
    webhooks = await WebhookService(db).list_webhooks(tenant_id)
    items = [_to_response(w) for w in webhooks]
    return WebhookListResponse(items=items, total=len(items))


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: uuid.UUID,
    body: UpdateWebhookRequest,
    request: Request,
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Zmienia adres, sekret, listę zdarzeń lub aktywność (AC6)."""
    service = WebhookService(db)
    webhook = await service.update_webhook(
        webhook_id,
        tenant_id,
        url=body.url,
        secret=body.secret,
        events=list(body.events) if body.events is not None else None,
        description=body.description,
        is_active=body.is_active,
    )
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="webhook.updated",
        resource_type="outbound_webhook",
        resource_id=webhook.id,
        changes={
            "url": webhook.url,
            "events": webhook.events,
            "is_active": webhook.is_active,
            "secret_changed": bool(body.secret),
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(webhook)
    return _to_response(webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Usuwa webhook wraz z historią dostaw (kaskada w bazie)."""
    service = WebhookService(db)
    webhook = await service.get_webhook(webhook_id, tenant_id)
    url = webhook.url
    await service.delete_webhook(webhook_id, tenant_id)
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="webhook.deleted",
        resource_type="outbound_webhook",
        resource_id=webhook_id,
        changes={"url": url},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{webhook_id}/test", response_model=TestWebhookResponse)
async def test_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> TestWebhookResponse:
    """Wysyła testowy ping pod adres webhooka (AC1).

    Wynik nie trafia do historii dostaw — to sprawdzenie konfiguracji,
    nie zdarzenie biznesowe.
    """
    result = await WebhookService(db).test_webhook(webhook_id, tenant_id)
    return TestWebhookResponse(**result)


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def list_deliveries(
    webhook_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=200),
    delivery_status: str | None = Query(None, alias="status"),
    event_type: str | None = Query(None),
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryListResponse:
    """Historia dostaw z filtrami po statusie i typie zdarzenia (AC5)."""
    deliveries = await WebhookService(db).list_deliveries(
        webhook_id,
        tenant_id,
        limit=limit,
        status=delivery_status,
        event_type=event_type,
    )
    items = [_delivery_response(d) for d in deliveries]
    return WebhookDeliveryListResponse(items=items, total=len(items))
