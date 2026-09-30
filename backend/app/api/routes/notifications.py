"""Powiadomienia in-app — Story 7.11 (AC3).

Odczyt własnych powiadomień (dzwonek w navbarze): lista z paginacją,
licznik nieprzeczytanych (polling FE co 30 s), oznaczanie przeczytanymi.
Scope: ``user_id`` = zalogowany użytkownik (+ RLS tenant z JWT).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_notification_service
from app.models.user import User
from app.schemas.notifications import (
    MarkAllReadOut,
    NotificationListOut,
    NotificationOut,
    UnreadCountOut,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListOut:
    """Lista powiadomień użytkownika — najnowsze pierwsze (AC3)."""
    items, total = await service.get_notifications(current_user.id, page=page, size=size)
    return NotificationListOut(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> UnreadCountOut:
    """Liczba nieprzeczytanych — badge dzwonka (AC3; polling co 30 s)."""
    count = await service.get_unread_count(current_user.id)
    return UnreadCountOut(count=count)


@router.post("/read-all", response_model=MarkAllReadOut)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> MarkAllReadOut:
    """„Oznacz wszystkie jako przeczytane" (AC3)."""
    updated = await service.mark_all_as_read(current_user.id)
    await db.commit()
    return MarkAllReadOut(updated=updated)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_as_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationOut:
    """Oznacz pojedyncze jako przeczytane (AC3) — 404 przy cudzym."""
    notification = await service.mark_as_read(notification_id, current_user.id)
    await db.commit()
    return NotificationOut.model_validate(notification)
