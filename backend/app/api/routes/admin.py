"""Trasy panelu administracyjnego — Epic 6, Story 6.15.

Udostępnia administratorowi platformy przegląd tenantów (AC4, AC5), log audytu
z filtrami i paginacją (AC6) oraz globalną konfigurację (AC7).  Wszystkie trasy
wymagają roli ``admin``.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NIL_UUID
from app.core.dependencies import get_db, require_role
from app.core.exceptions import NotFoundError
from app.models.payment import WebhookEvent
from app.models.user import User
from app.schemas.admin import (
    AuditLogEntryResponse,
    AuditLogListResponse,
    PlatformConfigResponse,
    TenantListResponse,
    TenantProjectListResponse,
    TenantProjectResponse,
    TenantSummaryResponse,
    UpdatePlatformConfigRequest,
)
from app.services.admin.audit_service import count_logs, list_actions, log_action, query_logs
from app.services.admin.config_service import get_config, update_config
from app.services.admin.tenant_service import get_tenant_details, list_tenant_projects, list_tenants
from app.services.billing.webhook_processor import WebhookProcessor

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tenants", response_model=TenantListResponse)
async def admin_list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TenantListResponse:
    """Lista tenantów z liczbą użytkowników, projektów i zajętością storage."""
    tenants, total = await list_tenants(db, page=page, page_size=page_size, search=search)
    return TenantListResponse(
        tenants=[TenantSummaryResponse(**tenant) for tenant in tenants],
        total=total,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantSummaryResponse)
async def admin_get_tenant(
    tenant_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TenantSummaryResponse:
    """Szczegóły tenanta na potrzeby widoku cross-tenant."""
    return TenantSummaryResponse(**await get_tenant_details(db, tenant_id))


@router.get("/tenants/{tenant_id}/projects", response_model=TenantProjectListResponse)
async def admin_list_tenant_projects(
    tenant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TenantProjectListResponse:
    """Projekty wybranego tenanta — nawigacja z widoku cross-tenant."""
    projects, total = await list_tenant_projects(db, tenant_id, page=page, page_size=page_size)
    return TenantProjectListResponse(
        projects=[TenantProjectResponse(**project) for project in projects],
        total=total,
    )


@router.get("/audit-logs/actions", response_model=list[str])
async def admin_list_audit_actions(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Unikalne typy akcji — zasila filtr w panelu."""
    return await list_actions(db)


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def admin_list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    tenant_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=100),
    resource_type: str | None = Query(None, max_length=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Log audytu z filtrami po dacie, użytkowniku i typie akcji."""
    filters = {
        "tenant_id": tenant_id,
        "action": action,
        "user_id": user_id,
        "resource_type": resource_type,
        "date_from": date_from,
        "date_to": date_to,
    }
    logs = await query_logs(db, limit=page_size, offset=(page - 1) * page_size, **filters)
    total = await count_logs(db, **filters)
    return AuditLogListResponse(
        logs=[AuditLogEntryResponse.model_validate(entry, from_attributes=True) for entry in logs],
        total=total,
    )


@router.get("/config", response_model=PlatformConfigResponse)
async def admin_get_config(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> PlatformConfigResponse:
    """Konfiguracja platformy: limity, LLM, tryb serwisowy, flagi funkcji."""
    return PlatformConfigResponse(**await get_config(db))


@router.put("/config", response_model=PlatformConfigResponse)
async def admin_update_config(
    body: UpdatePlatformConfigRequest,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> PlatformConfigResponse:
    """Zapisuje częściową zmianę konfiguracji i rejestruje ją w logu audytu."""
    config = await update_config(
        db,
        admin=current_user,
        sections=body.sections(),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return PlatformConfigResponse(**config)


@router.post(
    "/billing/webhooks/{event_uid}/replay",
    summary="Replay notyfikacji webhooka tpay (operacje)",
    description=(
        "**Story 7.3 (AC7).** Ponowne przetworzenie zapisanego zdarzenia "
        "webhook (``WebhookEvent.raw``) tym samym pipeline'em — z pominiętą "
        "walidacją podpisu (dane z audytu). Idempotentne biznesowo (zdarzenie "
        "`processed` nie wywoła efektów ponownie). Zdarzenia odrzucone "
        "walidacją (`rejected_*`) nie podlegają replayowi → 409. "
        "Wymaga roli **admin**; operacja trafia do logu audytu."
    ),
)
async def admin_replay_webhook(
    event_uid: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Replay po rozjeździe stanu (np. po awarii) — AC7."""
    result = await db.execute(select(WebhookEvent).where(WebhookEvent.event_uid == event_uid))
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundError("Webhook event not found")

    status_before = str(event.processing_status)
    _ok, status_after = await WebhookProcessor(db).replay_event(event)
    await db.commit()

    # AC7: operacja logowana w audycie admina (kto, kiedy, jaki event).
    await log_action(
        db,
        tenant_id=uuid.UUID(NIL_UUID),
        user_id=current_user.id,
        action="billing.webhook_replayed",
        resource_type="webhook_event",
        resource_id=event.id,
        changes={
            "event_uid": event_uid,
            "processing_status_before": status_before,
            "processing_status_after": status_after,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"event_uid": event_uid, "replayed": True, "processing_status": status_after}
