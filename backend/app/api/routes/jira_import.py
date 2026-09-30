"""Import wymagań z Jiry — Epic 8, Story 8.12.

Osobny moduł od ``integrations.py``, mimo że story mówi o jego rozbudowie:
tamten plik ma już ponad pół tysiąca linii i obsługuje trackery, CI/CD oraz
eksport TMS. Import to trzeci, niezależny temat.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_tenant
from app.core.encryption import decrypt
from app.core.exceptions import NotFoundError, ValidationError
from app.models.integration import IntegrationConfig, IntegrationProvider
from app.models.jira_import import SUPPORTED_ISSUE_TYPES, JiraImport, JiraImportStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.jira_import import (
    JiraImportAcceptedResponse,
    JiraImportRequest,
    JiraImportStatusResponse,
    JiraProjectListResponse,
    JiraProjectOption,
)
from app.services.admin.audit_service import log_action
from app.services.integrations.jira_service import JiraImportClient, JiraImportError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["integrations-jira-import"])


async def _jira_integration(
    db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID
) -> IntegrationConfig:
    """Aktywna integracja z Jirą dla projektu; 404, gdy jej nie ma."""
    config = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.tenant_id == tenant_id,
                IntegrationConfig.provider == IntegrationProvider.JIRA,
                IntegrationConfig.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if config is None:
        raise NotFoundError("Integracja z Jirą nie jest skonfigurowana dla tego projektu")
    return config


async def _verify_project(db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID) -> Project:
    project = (
        await db.execute(
            select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Projekt nie został znaleziony")
    return project


def _client(config: IntegrationConfig) -> JiraImportClient:
    email, _, token = decrypt(config.encrypted_credentials).partition(":")
    return JiraImportClient(config.base_url, email, token)


@router.get(
    "/projects/{project_id}/import/jira/projects",
    response_model=JiraProjectListResponse,
    summary="Projekty Jiry dostępne do importu",
    description=(
        "**Lista projektów Jiry (Story 8.12, AC5).**\n\n"
        "Zwraca projekty widoczne dla konta z konfiguracji integracji — to z nich "
        "wybiera się źródło importu. Lista pochodzi wprost z Jiry, więc odzwierciedla "
        "uprawnienia tego konta, a nie wszystko, co w instancji istnieje."
    ),
    responses={404: {"description": "Integracja z Jirą nie jest skonfigurowana."}},
)
async def list_jira_projects(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> JiraProjectListResponse:
    await _verify_project(db, project_id, tenant_id)
    config = await _jira_integration(db, project_id, tenant_id)

    try:
        items = await _client(config).list_projects()
    except JiraImportError as exc:
        raise ValidationError(str(exc)) from exc

    return JiraProjectListResponse(
        items=[JiraProjectOption(**item) for item in items],
        total=len(items),
    )


@router.post(
    "/projects/{project_id}/import/jira",
    response_model=JiraImportAcceptedResponse,
    status_code=202,
    summary="Zaimportuj wymagania z Jiry",
    description=(
        "**Import wymagań (Story 8.12, AC1-AC4).**\n\n"
        "Pobiera historyjki, epiki, błędy i podzadania wskazanego projektu Jiry, "
        "przekłada je na wymagania TestGEN i zapisuje razem z załącznikami.\n\n"
        "Kolejny import jest **przyrostowy**: pyta o zgłoszenia zmienione po ostatnim "
        "udanym przebiegu i aktualizuje istniejące wymagania zamiast je dublować. "
        "`full_reimport` pomija ten znacznik i pobiera wszystko.\n\n"
        "Import idzie w tle — postęp pod `/api/v1/tasks/{task_id}`."
    ),
    responses={
        202: {"description": "Import przyjęty; postęp pod `status_url`."},
        404: {"description": "Projekt nie istnieje albo brak integracji z Jirą."},
        422: {"description": "Nieobsługiwany typ zgłoszenia."},
    },
)
async def start_jira_import(
    project_id: uuid.UUID,
    body: JiraImportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> JiraImportAcceptedResponse:
    from app.workers.tasks.jira_import_tasks import import_from_jira_task

    await _verify_project(db, project_id, tenant_id)
    config = await _jira_integration(db, project_id, tenant_id)

    unsupported = [t for t in body.issue_types if t not in SUPPORTED_ISSUE_TYPES]
    if unsupported:
        raise ValidationError(
            "Nieobsługiwane typy zgłoszeń: "
            + ", ".join(unsupported)
            + ". Dozwolone: "
            + ", ".join(SUPPORTED_ISSUE_TYPES)
        )

    record = (
        await db.execute(
            select(JiraImport).where(
                JiraImport.project_id == project_id,
                JiraImport.tenant_id == tenant_id,
                JiraImport.jira_project_key == body.jira_project_key,
            )
        )
    ).scalar_one_or_none()

    if record is None:
        record = JiraImport(
            tenant_id=tenant_id,
            project_id=project_id,
            integration_id=config.id,
            jira_project_key=body.jira_project_key,
            issue_types=list(body.issue_types),
            status=JiraImportStatus.PENDING,
            total_imported=0,
            total_attachments=0,
            total_skipped=0,
        )
        db.add(record)
    else:
        record.integration_id = config.id
        record.issue_types = list(body.issue_types)
        record.status = JiraImportStatus.PENDING
        record.last_error = None

    if body.full_reimport:
        record.last_import_at = None
    elif body.updated_after is not None:
        record.last_import_at = body.updated_after

    await db.flush()
    result = import_from_jira_task.delay(str(record.id), str(tenant_id))

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.jira.import_requested",
        resource_type="jira_import",
        resource_id=record.id,
        changes={
            "jira_project_key": body.jira_project_key,
            "issue_types": list(body.issue_types),
            "full_reimport": body.full_reimport,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return JiraImportAcceptedResponse(
        import_id=record.id,
        task_id=result.id,
        status_url=f"/api/v1/tasks/{result.id}",
    )


@router.get(
    "/projects/{project_id}/import/jira/status",
    response_model=list[JiraImportStatusResponse],
    summary="Stan importów z Jiry",
    description=(
        "**Stan importu (Story 8.12, AC5).**\n\n"
        "Jeden wpis na projekt Jiry powiązany z tym projektem TestGEN: data "
        "ostatniego udanego importu, liczba wymagań i załączników oraz liczba "
        "zgłoszeń pominiętych wraz z powodem."
    ),
)
async def get_jira_import_status(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[JiraImportStatusResponse]:
    await _verify_project(db, project_id, tenant_id)

    rows = (
        (
            await db.execute(
                select(JiraImport)
                .where(
                    JiraImport.project_id == project_id,
                    JiraImport.tenant_id == tenant_id,
                )
                .order_by(JiraImport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [JiraImportStatusResponse.model_validate(row) for row in rows]
