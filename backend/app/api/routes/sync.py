"""Dwukierunkowa synchronizacja z TMS — Epic 8, Story 8.11.

Osobny moduł od ``integrations_tms.py``, który odpowiada za konfigurację
połączenia i jednorazowy eksport. Tu chodzi o cykl: kierunek, odstęp,
zdrowie i konflikty.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_tenant
from app.models.sync_conflict import ConflictResolution, SyncConflict
from app.models.user import User
from app.schemas.sync import (
    ConflictResolveRequest,
    SyncConfigRequest,
    SyncConflictListResponse,
    SyncConflictResponse,
    SyncRunResponse,
    SyncStatusResponse,
)
from app.services.admin.audit_service import log_action
from app.services.export import sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations-sync"])
conflicts_router = APIRouter(prefix="/sync", tags=["integrations-sync"])


async def _pending_conflicts(
    db: AsyncSession, sync_state_id: uuid.UUID, tenant_id: uuid.UUID
) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(SyncConflict)
                .where(
                    SyncConflict.sync_state_id == sync_state_id,
                    SyncConflict.tenant_id == tenant_id,
                    SyncConflict.resolution == ConflictResolution.PENDING,
                )
            )
        ).scalar_one()
    )


@router.put(
    "/{integration_id}/sync/config",
    response_model=SyncStatusResponse,
    summary="Skonfiguruj synchronizację dwukierunkową",
    description=(
        "**Konfiguracja synchronizacji (Story 8.11).**\n\n"
        "Ustala kierunek (`push`, `pull`, `bidirectional`), odstęp między "
        "przebiegami i sposób rozstrzygania konfliktów. Odstęp krótszy niż "
        "5 minut jest odrzucany — TestRail i Jira dławią tempo żądań, więc "
        "pełny przebieg i tak trwa dłużej.\n\n"
        "Konfiguracja nie uruchamia synchronizacji; do tego służy `/activate`."
    ),
    responses={
        404: {"description": "Integracja nie istnieje."},
        422: {"description": "Dostawca nie wspiera synchronizacji albo odstęp za krótki."},
    },
)
async def configure_sync_route(
    integration_id: uuid.UUID,
    body: SyncConfigRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    """Tworzy albo nadpisuje konfigurację synchronizacji (AC1)."""
    state = await sync_service.configure_sync(
        db,
        integration_id,
        tenant_id,
        direction=body.direction,
        interval_minutes=body.interval_minutes,
        conflict_strategy=body.conflict_strategy,
    )
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="sync.configured",
        resource_type="sync_state",
        resource_id=state.id,
        changes={
            "direction": body.direction.value,
            "interval_minutes": body.interval_minutes,
            "conflict_strategy": body.conflict_strategy.value,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(state)
    pending = await _pending_conflicts(db, state.id, tenant_id)
    return SyncStatusResponse(**sync_service.sync_status_view(state, pending))


@router.get(
    "/{integration_id}/sync/status",
    response_model=SyncStatusResponse,
    summary="Stan synchronizacji",
    description=(
        "**Stan synchronizacji (Story 8.11, AC5).**\n\n"
        "Zwraca kierunek, odstęp, czas ostatniego przebiegu, jego wynik, "
        "liczbę przypadków objętych ostatnim udanym przebiegiem, liczbę "
        "nierozstrzygniętych konfliktów i zdrowie (`active` albo `degraded` "
        "po trzech nieudanych próbach z rzędu)."
    ),
)
async def get_sync_status_route(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    state = await sync_service.get_sync_state(db, integration_id, tenant_id)
    pending = await _pending_conflicts(db, state.id, tenant_id)
    return SyncStatusResponse(**sync_service.sync_status_view(state, pending))


@router.post(
    "/{integration_id}/sync/activate",
    response_model=SyncStatusResponse,
    summary="Włącz synchronizację",
    description=(
        "Włącza cykliczne przebiegi. Licznik nieudanych prób jest zerowany, "
        "więc synchronizacja włączona po naprawie awarii nie wraca od razu "
        "do stanu `degraded`."
    ),
)
async def activate_sync_route(
    integration_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    state = await sync_service.set_active(db, integration_id, tenant_id, True)
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="sync.activated",
        resource_type="sync_state",
        resource_id=state.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(state)
    pending = await _pending_conflicts(db, state.id, tenant_id)
    return SyncStatusResponse(**sync_service.sync_status_view(state, pending))


@router.post(
    "/{integration_id}/sync/deactivate",
    response_model=SyncStatusResponse,
    summary="Wyłącz synchronizację",
    description="Zatrzymuje cykliczne przebiegi. Konfiguracja i konflikty zostają.",
)
async def deactivate_sync_route(
    integration_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    state = await sync_service.set_active(db, integration_id, tenant_id, False)
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="sync.deactivated",
        resource_type="sync_state",
        resource_id=state.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(state)
    pending = await _pending_conflicts(db, state.id, tenant_id)
    return SyncStatusResponse(**sync_service.sync_status_view(state, pending))


@router.post(
    "/{integration_id}/sync/run",
    response_model=SyncRunResponse,
    status_code=202,
    summary="Uruchom synchronizację teraz",
    description=(
        "**Ręczne wyzwolenie przebiegu (Story 8.11, AC5).**\n\n"
        "Nie czeka na odstęp z konfiguracji. Przebieg idzie w tle, bo rozmowa "
        "z TMS-em przy setce przypadków trwa minuty — postęp śledzi się przez "
        "`/api/v1/tasks/{task_id}`."
    ),
    responses={404: {"description": "Synchronizacja nie jest skonfigurowana."}},
)
async def run_sync_now_route(
    integration_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncRunResponse:
    from app.workers.tasks.sync_tasks import run_sync

    state = await sync_service.get_sync_state(db, integration_id, tenant_id)
    result = run_sync.delay(str(state.id), str(tenant_id))
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="sync.run_requested",
        resource_type="sync_state",
        resource_id=state.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return SyncRunResponse(
        sync_state_id=state.id,
        task_id=result.id,
        status_url=f"/api/v1/tasks/{result.id}",
    )


@router.get(
    "/{integration_id}/sync/conflicts",
    response_model=SyncConflictListResponse,
    summary="Konflikty synchronizacji",
    description=(
        "**Log konfliktów (Story 8.11, AC4).**\n\n"
        "Każdy wiersz zawiera obie wersje przypadku — także wtedy, gdy "
        "strategia `last_write_wins` rozstrzygnęła konflikt automatycznie. "
        "Przegrana wersja jest jedynym śladem po nadpisanych danych."
    ),
)
async def list_conflicts_route(
    integration_id: uuid.UUID,
    resolution: ConflictResolution | None = Query(
        None, description="Filtr po rozstrzygnięciu; domyślnie wszystkie"
    ),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncConflictListResponse:
    state = await sync_service.get_sync_state(db, integration_id, tenant_id)

    conditions = [
        SyncConflict.sync_state_id == state.id,
        SyncConflict.tenant_id == tenant_id,
    ]
    if resolution is not None:
        conditions.append(SyncConflict.resolution == resolution)

    total = int(
        (
            await db.execute(select(func.count()).select_from(SyncConflict).where(*conditions))
        ).scalar_one()
    )
    rows = (
        (
            await db.execute(
                select(SyncConflict)
                .where(*conditions)
                .order_by(SyncConflict.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return SyncConflictListResponse(
        items=[SyncConflictResponse.model_validate(row) for row in rows],
        total=total,
    )


@conflicts_router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=SyncConflictResponse,
    summary="Rozstrzygnij konflikt ręcznie",
    description=(
        "**Ręczne rozstrzygnięcie (Story 8.11, AC4).**\n\n"
        "`tms_wins` wnosi zapamiętaną wersję TMS-a do przypadku w TestGEN. "
        "`testgen_wins` nie zmienia niczego lokalnie — wersja TestGEN już tam "
        "jest i trafi do TMS-a przy najbliższym przebiegu w kierunku push. "
        "Konflikt już rozstrzygnięty nie daje się rozstrzygnąć powtórnie."
    ),
    responses={
        404: {"description": "Konflikt nie istnieje."},
        422: {"description": "Konflikt został już rozstrzygnięty."},
    },
)
async def resolve_conflict_route(
    conflict_id: uuid.UUID,
    body: ConflictResolveRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncConflictResponse:
    conflict = await sync_service.resolve_conflict(
        db, conflict_id, tenant_id, body.resolution, current_user.id
    )
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="sync.conflict_resolved",
        resource_type="sync_conflict",
        resource_id=conflict.id,
        changes={"resolution": body.resolution.value},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(conflict)
    return SyncConflictResponse.model_validate(conflict)
