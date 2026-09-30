"""Project management service — CRUD, audit, soft delete.

HOTFIX (izolacja tenantów, 2026-09-15): RLS jest nieskuteczne przy roli DB
z BYPASSRLS/SUPERUSER, więc zapytania dostają JAWNY filtr ``tenant_id``
z ``db.info["tenant_scope"]`` (ustawiany w get_current_user / set_rls_context).
RLS pozostaje jako druga warstwa, gdy rola będzie pozbawiona bypassu.
Projekty są unlimited w każdym planie (Story 7.1 — macierz 2026-08-28).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.models.project import Project, ProjectStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.services.admin.audit_service import log_action

_SORTABLE_FIELDS: dict[str, Any] = {
    "name": Project.name,
    "created_at": Project.created_at,
    "updated_at": Project.updated_at,
    "status": Project.status,
}


def _tenant_scope(db: AsyncSession) -> uuid.UUID | None:
    """Jawny scope tenanta z kontekstu żądania (db.info) — None = bez filtra."""
    scope = db.info.get("tenant_scope")
    return uuid.UUID(scope) if scope else None


def _require_write_role(actor: User, is_admin: bool = False, tenant_role: str = "user") -> None:
    if not is_admin and tenant_role != "owner":
        raise ForbiddenError("Requires role: owner or admin")


async def _get_active_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    """Fetch a project that is not soft-deleted.

    HOTFIX: jawny filtr tenant_id z kontekstu żądania (RLS nieskuteczne
    przy BYPASSRLS) — obcy identyfikator zwraca 404, nie wyciek danych.
    """
    stmt = select(Project).where(Project.id == project_id, Project.is_deleted.is_(False))
    scope = _tenant_scope(db)
    if scope is not None:
        stmt = stmt.where(Project.tenant_id == scope)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found")
    return project


async def _check_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Validate tenant exists (tenant scope is enforced by RLS).

    Projekty są unlimited w każdym planie (macierz zatwierdzona 2026-08-28,
    Story 7.1) — naturalne ograniczenie przez storage, nie licznik projektów.
    Plan-based project quota (dawniej Basic = 10) zostało usunięte.
    """
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise NotFoundError("Tenant not found")


async def create_project(
    db: AsyncSession,
    actor: User,
    name: str,
    description: str | None = None,
    language_hint: str | None = None,
    ip_address: str | None = None,
    tenant_id: uuid.UUID | None = None,
) -> Project:
    """Create a new project for the actor's tenant. All roles allowed."""
    tid = tenant_id or getattr(actor, "_tenant_id", None)
    if not tid:
        raise ValidationError("No tenant context available")
    await _check_tenant(db, tid)

    # Conflict detection — rely on unique constraint but short-circuit with friendly error
    existing_stmt = select(Project).where(
        Project.tenant_id == tid,
        Project.name == name,
        Project.is_deleted.is_(False),
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise ConflictError(f"Project with name '{name}' already exists")

    project = Project(
        tenant_id=tid,
        name=name,
        description=description,
        language_hint=language_hint,
        status=ProjectStatus.CREATED,
    )
    db.add(project)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"Project with name '{name}' already exists") from None

    await log_action(
        db,
        tenant_id=tid,
        user_id=actor.id,
        action="project.created",
        resource_type="project",
        resource_id=project.id,
        changes={"name": name, "language_hint": language_hint},
        ip_address=ip_address,
    )

    return project


async def list_projects(
    db: AsyncSession,
    actor: User,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    language: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Project], int]:
    """List projects for the actor's tenant with pagination/filters/sorting."""
    if sort_by not in _SORTABLE_FIELDS:
        raise ValidationError(f"Invalid sort_by '{sort_by}'. Allowed: {', '.join(_SORTABLE_FIELDS)}")
    if sort_order not in ("asc", "desc"):
        raise ValidationError("sort_order must be 'asc' or 'desc'")

    stmt = select(Project).where(Project.is_deleted.is_(False))

    # HOTFIX: jawny filtr tenant_id (RLS nieskuteczne przy BYPASSRLS)
    scope = _tenant_scope(db)
    if scope is not None:
        stmt = stmt.where(Project.tenant_id == scope)

    if status is not None:
        valid_statuses = {s.value for s in ProjectStatus}
        if status not in valid_statuses:
            raise ValidationError(
                f"Invalid status filter '{status}'. Valid values: {', '.join(sorted(valid_statuses))}"
            )
        stmt = stmt.where(Project.status == status)
    if language is not None:
        stmt = stmt.where(Project.language_hint == language)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    order_col = _SORTABLE_FIELDS[sort_by]
    stmt = stmt.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    projects = list(result.scalars().all())
    return projects, total


async def get_project(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
) -> Project:
    """Get a single project by id. Tenant scope enforced by RLS."""
    return await _get_active_project(db, project_id)


async def update_project(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
    language_hint: str | None = None,
    ip_address: str | None = None,
) -> Project:
    """Update project fields. Requires Owner or Admin role."""
    _require_write_role(actor, tenant_role=getattr(actor, "_tenant_role", "user"))

    project = await _get_active_project(db, project_id)

    changes: dict[str, Any] = {}

    if name is not None and name != project.name:
        # Detect name conflict within tenant (excluding current project)
        conflict_stmt = select(Project).where(
            Project.tenant_id == project.tenant_id,
            Project.name == name,
            Project.id != project.id,
            Project.is_deleted.is_(False),
        )
        conflict_result = await db.execute(conflict_stmt)
        if conflict_result.scalar_one_or_none() is not None:
            raise ConflictError(f"Project with name '{name}' already exists")
        changes["name"] = {"old": project.name, "new": name}
        project.name = name

    if description is not None and description != project.description:
        changes["description"] = {"old": project.description, "new": description}
        project.description = description

    if language_hint is not None and language_hint != project.language_hint:
        changes["language_hint"] = {"old": project.language_hint, "new": language_hint}
        project.language_hint = language_hint

    if changes:
        await log_action(
            db,
            tenant_id=project.tenant_id,
            user_id=actor.id,
            action="project.updated",
            resource_type="project",
            resource_id=project.id,
            changes=changes,
            ip_address=ip_address,
        )

    return project


async def delete_project(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    ip_address: str | None = None,
) -> None:
    """Soft delete a project. Requires Owner or Admin role."""
    _require_write_role(actor, tenant_role=getattr(actor, "_tenant_role", "user"))

    project = await _get_active_project(db, project_id)

    project.is_deleted = True
    project.deleted_at = datetime.now(UTC)

    await log_action(
        db,
        tenant_id=project.tenant_id,
        user_id=actor.id,
        action="project.deleted",
        resource_type="project",
        resource_id=project.id,
        ip_address=ip_address,
    )
