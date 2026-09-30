"""Audit logging service."""

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    changes: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=changes,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry


def _apply_filters(
    stmt: Select,
    tenant_id: uuid.UUID | None,
    action: str | None,
    user_id: uuid.UUID | None,
    resource_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select:
    """Wspólne filtry dla listowania i zliczania wpisów (Story 6.15, AC6)."""
    if tenant_id:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    return stmt


async def query_logs(
    db: AsyncSession,
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    limit = min(limit, 200)  # upper bound to prevent data dump
    if offset > 10000:
        logger.warning("query_logs offset %d exceeds cap of 10000, truncating", offset)
    offset = min(offset, 10000)  # prevent expensive scans on large tables
    stmt = _apply_filters(
        select(AuditLog), tenant_id, action, user_id, resource_type, date_from, date_to
    ).order_by(AuditLog.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_logs(
    db: AsyncSession,
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    """Liczba wpisów spełniających te same filtry co ``query_logs`` (paginacja)."""
    stmt = _apply_filters(
        select(func.count()).select_from(AuditLog),
        tenant_id,
        action,
        user_id,
        resource_type,
        date_from,
        date_to,
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def list_actions(db: AsyncSession) -> list[str]:
    """Unikalne nazwy akcji — zasila filtr typu zdarzenia w panelu admina."""
    result = await db.execute(select(AuditLog.action).distinct())
    return sorted(result.scalars().all())
