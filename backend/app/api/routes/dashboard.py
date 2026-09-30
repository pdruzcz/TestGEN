"""Dashboard routes — Epic 6, Story 6.1.

Endpoints for main dashboard: aggregated summary + activity feed (audit logs).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.dashboard import (
    AuditLogListResponse,
    DashboardSummaryResponse,
)
from app.services.dashboard_service import get_summary, list_audit_logs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _tenant_of(current_user: User) -> uuid.UUID:
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="No tenant context")
    return tenant_id


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    description=(
        "**Dashboard główny — zagregowane podsumowanie (Story 6.1).**\n\n"
        "Zwraca w jednej odpowiedzi:\n"
        "- listę projektów z compliance % (najnowszy snapshot), liczbą testów, ostatnią analizą\n"
        "- 4 karty statystyk: liczba projektów, analiz w tym miesiącu, avg compliance, aktywni użytkownicy\n"
        "- widget użycia planu (tylko dla Owner/Admin; `null` dla Member)\n\n"
        "Aktywność (activity feed) pobierana osobnym endpointem `/dashboard/audit-logs` "
        "z pollingiem co 30s."
    ),
)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Aggregated dashboard summary."""
    tid = _tenant_of(current_user)
    return await get_summary(db, tid, current_user)


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    description=(
        "**Activity feed — ostatnie logi audytu (Story 6.1).**\n\n"
        "Zwraca listę wpisów z `audit_logs` dla bieżącego tenanta. Używane "
        "przez frontend z pollingiem co 30s (rxjs `interval(30000)`).\n\n"
        "Limit domyślnie 20, max 50."
    ),
)
async def get_dashboard_audit_logs(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Activity feed (audit logs)."""
    tid = _tenant_of(current_user)
    return await list_audit_logs(db, tid, limit=limit)
