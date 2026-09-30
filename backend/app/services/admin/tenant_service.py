"""Przegląd tenantów dla panelu administracyjnego (Story 6.15, AC4, AC5).

Metryki (liczba użytkowników, zajętość storage, liczba projektów) liczone są
zbiorczo dla całej strony wyników, aby uniknąć zapytań N+1.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.models.source_file import SourceFile
from app.models.tenant import Tenant
from app.models.user_tenant import UserTenant

MAX_PAGE_SIZE = 100


def _summary(tenant: Tenant, user_count: int, storage_bytes: int, project_count: int) -> dict[str, Any]:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan.value if hasattr(tenant.plan, "value") else str(tenant.plan),
        "is_active": tenant.is_active,
        "created_at": tenant.created_at,
        "user_count": user_count,
        "storage_bytes": storage_bytes,
        "project_count": project_count,
    }


async def list_tenants(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Zwraca stronę tenantów z metrykami oraz łączną liczbę tenantów."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    base = select(Tenant)
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(Tenant.name.ilike(pattern) | Tenant.slug.ilike(pattern))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    result = await db.execute(
        base.order_by(Tenant.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    tenants = list(result.scalars().all())
    if not tenants:
        return [], total

    ids = [tenant.id for tenant in tenants]

    users_rows = await db.execute(
        select(UserTenant.tenant_id, func.count())
        .where(UserTenant.tenant_id.in_(ids))
        .group_by(UserTenant.tenant_id)
    )
    user_counts = dict(users_rows.all())

    storage_rows = await db.execute(
        select(SourceFile.tenant_id, func.coalesce(func.sum(SourceFile.file_size), 0))
        .where(SourceFile.tenant_id.in_(ids), SourceFile.is_cleaned_up.is_(False))
        .group_by(SourceFile.tenant_id)
    )
    storage = dict(storage_rows.all())

    project_rows = await db.execute(
        select(Project.tenant_id, func.count()).where(Project.tenant_id.in_(ids)).group_by(Project.tenant_id)
    )
    project_counts = dict(project_rows.all())

    return [
        _summary(
            tenant,
            int(user_counts.get(tenant.id, 0)),
            int(storage.get(tenant.id, 0)),
            int(project_counts.get(tenant.id, 0)),
        )
        for tenant in tenants
    ], total


async def get_tenant_details(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    """Szczegóły pojedynczego tenanta wraz z metrykami."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Nie znaleziono tenanta")

    user_count = (
        await db.execute(select(func.count()).select_from(UserTenant).where(UserTenant.tenant_id == tenant_id))
    ).scalar() or 0
    storage_bytes = (
        await db.execute(
            select(func.coalesce(func.sum(SourceFile.file_size), 0)).where(
                SourceFile.tenant_id == tenant_id,
                SourceFile.is_cleaned_up.is_(False),
            )
        )
    ).scalar() or 0
    project_count = (
        await db.execute(select(func.count()).select_from(Project).where(Project.tenant_id == tenant_id))
    ).scalar() or 0

    return _summary(tenant, int(user_count), int(storage_bytes), int(project_count))


async def list_tenant_projects(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Projekty wybranego tenanta — nawigacja cross-tenant (AC5)."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    base = select(Project).where(Project.tenant_id == tenant_id, Project.is_deleted.is_(False))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    result = await db.execute(
        base.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    projects = [
        {
            "id": project.id,
            "name": project.name,
            "status": project.status.value if hasattr(project.status, "value") else str(project.status),
            "created_at": project.created_at,
        }
        for project in result.scalars().all()
    ]
    return projects, total
