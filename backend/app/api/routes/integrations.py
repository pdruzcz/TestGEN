"""Integration routes — Epic 5, Stories 5.8/5.9.

Project-scoped endpoints to configure external integrations (Jira / Azure
DevOps), test the connection, and sync gap findings / recommendations as
issues.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.integrations_tms import get_jira_tms_config, get_testrail_config
from app.core.dependencies import get_current_user, get_db
from app.core.encryption import encrypt
from app.core.exceptions import ValidationError
from app.models.analysis_result import AnalysisResult
from app.models.integration import (
    IntegrationConfig,
    IntegrationProvider,
    IntegrationSyncLog,
    SyncStatus,
)
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.export import TmsExportAcceptedResponse, TmsExportRequest
from app.schemas.integration import (
    CicdGenerateRequest,
    CicdGenerateResponse,
    CicdSummaryResponse,
    CicdTemplateInfo,
    CicdTemplateListResponse,
    IntegrationConfigRequest,
    IntegrationConfigResponse,
    IntegrationSyncRequest,
    IntegrationSyncResponse,
    IntegrationTestResponse,
    SyncLogResponse,
    SyncResultResponse,
)
from app.services.integrations import cicd_generator
from app.services.integrations.findings_query import collect_project_outcome
from app.services.integrations.status_check_builder import (
    build_status_description,
    normalize_threshold,
)
from app.services.task_progress_service import TaskProgressService
from app.workers.tasks.export_tasks import export_to_jira_tms, export_to_testrail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["integrations"])


def _tenant_of(current_user: User) -> uuid.UUID:
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="No tenant context")
    return tenant_id


async def _verify_project_access(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/{project_id}/integrations/configure",
    response_model=IntegrationConfigResponse,
    description=(
        "**Konfiguruj integrację z trackerem (Stories 5.8/5.9).**\n\n"
        "Tworzy lub aktualizuje konfigurację integracji dla projektu. "
        "Poświadczenia (email + api_token) są szyfrowane Fernet i persystowane "
        "w `encrypted_credentials`.\n\n"
        "Dostawcy:\n"
        "- `jira` — Atlassian Jira Cloud (REST API v3)\n"
        "- `azure_devops` — Microsoft Azure DevOps (Work Items API)\n\n"
        "Dla ADO: `organization` + `project` są wymagane w settings."
    ),
    responses={
        200: {"description": "Konfiguracja zapisana."},
        404: {"description": "Projekt nie znaleziony lub brak dostępu."},
    },
)
async def configure_integration(
    project_id: uuid.UUID,
    body: IntegrationConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigResponse:
    """Create or update integration configuration for the project."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    # Check if config already exists for this provider
    existing = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.provider == body.provider,
                IntegrationConfig.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()

    credentials = encrypt(f"{body.email}:{body.api_token}")
    settings: dict = {
        "project_key": body.project_key,
        "issue_type": body.issue_type,
    }
    if body.organization:
        settings["organization"] = body.organization
    if body.project:
        settings["project"] = body.project

    if existing:
        existing.base_url = body.base_url
        existing.encrypted_credentials = credentials
        existing.settings = settings
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return IntegrationConfigResponse.model_validate(existing)

    config = IntegrationConfig(
        tenant_id=tid,
        project_id=project_id,
        provider=IntegrationProvider(body.provider),
        base_url=body.base_url,
        encrypted_credentials=credentials,
        settings=settings,
        is_active=True,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return IntegrationConfigResponse.model_validate(config)


@router.get(
    "/{project_id}/integrations/config",
    response_model=IntegrationConfigResponse | None,
)
async def get_integration_config(
    project_id: uuid.UUID,
    provider: str = Query("jira"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationConfigResponse | None:
    """Get integration configuration for a provider."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    config = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.provider == provider,
                IntegrationConfig.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()

    if config is None:
        return None
    return IntegrationConfigResponse.model_validate(config)


@router.post(
    "/{project_id}/integrations/test",
    response_model=IntegrationTestResponse,
    description=(
        "**Test połączenia z trackerem.**\n\n"
        "Wywołuje endpoint `/serverinfo` (Jira) lub `/_apis/projects/{project}` "
        "(ADO) aby zweryfikować poświadczenia i dostęp do organizacji.\n\n"
        "Nie tworzy zasobów — bezpieczny test."
    ),
)
async def test_integration(
    project_id: uuid.UUID,
    provider: str = Query("jira"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationTestResponse:
    """Test connection to the external tool."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    config = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.provider == provider,
                IntegrationConfig.tenant_id == tid,
                IntegrationConfig.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if config is None:
        return IntegrationTestResponse(
            connected=False,
            message="No active integration configured for this provider",
        )

    if config.provider == IntegrationProvider.JIRA:
        from app.services.integrations.jira_service import JiraService

        try:
            svc = JiraService(config)
            ok = svc.test_connection()
            return IntegrationTestResponse(
                connected=ok,
                message="Connection successful" if ok else "Connection failed — check credentials",
            )
        except Exception as e:
            return IntegrationTestResponse(connected=False, message=str(e))

    if config.provider == IntegrationProvider.AZURE_DEVOPS:
        from app.services.integrations.azure_devops_service import AzureDevOpsService

        try:
            svc = AzureDevOpsService(config)
            ok = svc.test_connection()
            return IntegrationTestResponse(
                connected=ok,
                message="Connection successful" if ok else "Connection failed — check PAT and organization",
            )
        except Exception as e:
            return IntegrationTestResponse(connected=False, message=str(e))

    return IntegrationTestResponse(
        connected=False,
        message=f"Provider '{provider}' not yet supported",
    )


@router.post(
    "/{project_id}/integrations/sync",
    response_model=SyncResultResponse,
    description=(
        "**Synchronizuj findings/recommendations do trackera (FR42).**\n\n"
        "Tworzy issue (Jira) lub work item (ADO) dla każdego elementu z "
        "`body.item_ids`. Pomija duplikaty (na podstawie `external_ids` w logu "
        "sync) chyba że `body.force=true`.\n\n"
        "Mapowanie pól:\n"
        "- Severity `critical` → Jira Priority `Highest` / ADO Priority 1\n"
        "- Severity `warning` → `High` / 2\n"
        "- Severity `info` → `Medium` / 3\n"
        "- Gap type → Labels / Tags (`testgen`, `gap-analysis`, `{type}`)\n"
        "- Requirement ID → Description\n\n"
        "Statusy sync w `IntegrationSyncLog`: pending → running → success / "
        "partial / failed."
    ),
    responses={
        200: {
            "description": "Sync ukończony",
            "content": {
                "application/json": {
                    "example": {
                        "sync_log_id": "...",
                        "total": 12,
                        "synced": 10,
                        "failed": 2,
                        "status": "partial",
                    },
                },
            },
        },
        404: {"description": "Brak aktywnej integracji dla providera."},
        422: {"description": "Nieznany provider."},
    },
)
async def sync_to_integration(
    project_id: uuid.UUID,
    body: IntegrationSyncRequest,
    provider: str = Query("jira"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResultResponse:
    """Sync gap findings or recommendations to external tool as issues."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    config = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.provider == provider,
                IntegrationConfig.tenant_id == tid,
                IntegrationConfig.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active {provider} integration configured",
        )

    if config.provider == IntegrationProvider.JIRA:
        from app.services.integrations.jira_service import JiraService

        svc = JiraService(config)
    elif config.provider == IntegrationProvider.AZURE_DEVOPS:
        from app.services.integrations.azure_devops_service import AzureDevOpsService

        svc = AzureDevOpsService(config)
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Provider '{provider}' not yet supported",
        )

    if body.sync_type == "gap_findings":
        from app.models.gap_finding import GapFinding

        findings = list(
            (
                await db.execute(
                    select(GapFinding).where(
                        GapFinding.project_id == project_id,
                        GapFinding.tenant_id == tid,
                    )
                )
            ).scalars().all()
        )
        result = svc.sync_from_gap_findings(findings)
    elif body.sync_type == "recommendations":
        from app.models.recommendation import Recommendation

        recs = list(
            (
                await db.execute(
                    select(Recommendation).where(
                        Recommendation.project_id == project_id,
                        Recommendation.tenant_id == tid,
                    )
                )
            ).scalars().all()
        )
        result = svc.sync_from_recommendations(recs)
    else:
        raise HTTPException(status_code=422, detail="Invalid sync_type")

    # Log the sync
    log = IntegrationSyncLog(
        tenant_id=tid,
        integration_config_id=config.id,
        project_id=project_id,
        sync_type=body.sync_type,
        status=SyncStatus.SUCCESS if not result.errors else SyncStatus.PARTIAL,
        items_total=result.total,
        items_synced=result.synced,
        errors={"items": result.errors} if result.errors else None,
    )
    db.add(log)
    await db.commit()

    return SyncResultResponse(
        total=result.total,
        synced=result.synced,
        errors=result.errors,
    )


@router.get(
    "/{project_id}/integrations/logs",
    response_model=list[SyncLogResponse],
)
async def list_sync_logs(
    project_id: uuid.UUID,
    provider: str = Query("jira"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SyncLogResponse]:
    """List sync logs for the project's integration."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    config = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.provider == provider,
                IntegrationConfig.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()

    if config is None:
        return []

    logs = (
        await db.execute(
            select(IntegrationSyncLog)
            .where(IntegrationSyncLog.integration_config_id == config.id)
            .order_by(IntegrationSyncLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    return [SyncLogResponse.model_validate(l) for l in logs]


# ── Epic 8, Story 8.4: generator konfiguracji CI/CD ─────────────────────────


@router.get(
    "/{project_id}/ci-cd/templates",
    response_model=CicdTemplateListResponse,
    description=(
        "**Katalog platform CI/CD (Story 8.4).**\n\n"
        "Zwraca dostępne platformy wraz z nazwą pliku docelowego i instrukcją "
        "dodania klucza API, a także dopuszczalne wartości parametrów."
    ),
)
async def list_cicd_templates(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CicdTemplateListResponse:
    """Platformy i dopuszczalne parametry generatora (AC5/AC6)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    return CicdTemplateListResponse(
        platforms=[CicdTemplateInfo(**p) for p in cicd_generator.list_platforms()],
        available_modules=list(cicd_generator.ANALYSIS_MODULES),
        available_engine_modes=list(cicd_generator.ENGINE_MODES),
        available_thresholds=list(cicd_generator.SEVERITY_THRESHOLDS),
        api_key_variable=cicd_generator.API_KEY_VARIABLE,
    )


@router.post(
    "/{project_id}/ci-cd/generate",
    response_model=CicdGenerateResponse,
    description=(
        "**Generowanie konfiguracji CI/CD (Story 8.4).**\n\n"
        "Zwraca gotową zawartość pliku dla wybranej platformy. Konfiguracja "
        "uwierzytelnia się kluczem API (Story 8.6) i przerywa build, gdy "
        "analiza znajdzie problem co najmniej tak poważny jak wybrany próg."
    ),
)
async def generate_cicd_config(
    project_id: uuid.UUID,
    body: CicdGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CicdGenerateResponse:
    """Renderuje plik konfiguracyjny dla wskazanej platformy (AC1-AC4, AC6)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    params = cicd_generator.CicdParams(
        project_id=str(project_id),
        platform=body.platform,
        severity_threshold=body.severity_threshold,
        modules=list(body.modules),
        engine_mode=body.engine_mode,
        timeout_minutes=body.timeout_minutes,
    )
    return CicdGenerateResponse(**cicd_generator.generate(params))


@router.get(
    "/{project_id}/ci-cd/summary",
    response_model=CicdSummaryResponse,
    description=(
        "**Werdykt bramki CI/CD (Story 8.4).**\n\n"
        "Endpoint wołany przez wygenerowany pipeline po zakończeniu analizy. "
        "Zlicza otwarte znaleziska i zwraca `should_fail` — logika progu "
        "zostaje po stronie serwera, więc pipeline i status check na PR "
        "(Story 8.3) zawsze zgadzają się co do werdyktu."
    ),
)
async def get_cicd_summary(
    project_id: uuid.UUID,
    threshold: str = Query("critical", description="Próg blokujący: critical, high lub medium"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CicdSummaryResponse:
    """Podsumowanie znalezisk i decyzja o przerwaniu builda (AC1-AC4)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    normalized = normalize_threshold(threshold)
    outcome = await collect_project_outcome(db, tid, project_id)
    state, description = build_status_description(outcome, normalized)

    return CicdSummaryResponse(
        project_id=project_id,
        threshold=normalized,
        counts=outcome.counts,
        total=outcome.total,
        blocking=outcome.count_at_or_above(normalized),
        should_fail=state == "failure",
        state=state,
        description=description,
    )


# ── Epic 8, Story 8.8: eksport przypadków testowych do TestRail ─────────────


@router.post(
    "/{project_id}/export/testrail",
    response_model=TmsExportAcceptedResponse,
    status_code=202,
    summary="Eksportuj przypadki testowe do TestRail",
    description=(
        "**Eksport do TestRail (Story 8.8).**\n\n"
        "Uruchamia eksport w tle i zwraca identyfikator zadania. Eksport idzie "
        "asynchronicznie, bo TestRail dławi tempo żądań — setka przypadków to "
        "minuty pracy.\n\n"
        "Przypadki już wyeksportowane (rozpoznane po polu `custom_testgen_id`) "
        "są aktualizowane, a nie duplikowane. Pusta lista `test_case_ids` "
        "oznacza wszystkie przypadki projektu."
    ),
    responses={
        202: {"description": "Eksport przyjęty; postęp pod `status_url`."},
        404: {"description": "Projekt nie istnieje albo brak konfiguracji TestRail."},
    },
)
async def export_test_cases_to_testrail(
    project_id: uuid.UUID,
    body: TmsExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TmsExportAcceptedResponse:
    """Kolejkuje eksport przypadków testowych do TestRaila (AC2/AC3)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    config = await get_testrail_config(db, project_id, tid)

    # Liczba przypadków w podsumowaniu: przy pustej liście liczymy wszystkie,
    # żeby użytkownik od razu wiedział, na co się pisze.
    # TestCase nie ma ``project_id`` — wiąże się z projektem przez AnalysisResult.
    count_stmt = select(func.count()).select_from(TestCase).where(
        TestCase.tenant_id == tid,
        TestCase.analysis_result_id.in_(
            select(AnalysisResult.id).where(AnalysisResult.project_id == project_id)
        ),
    )
    if body.test_case_ids:
        count_stmt = count_stmt.where(TestCase.id.in_(body.test_case_ids))
    total = int(await db.scalar(count_stmt) or 0)

    task = export_to_testrail.delay(
        tenant_id=str(tid),
        project_id=str(project_id),
        integration_config_id=str(config.id),
        test_case_ids=[str(i) for i in body.test_case_ids],
    )
    TaskProgressService().init_task(task.id, str(tid))

    return TmsExportAcceptedResponse(
        task_id=task.id,
        status="pending",
        status_url=f"/api/v1/tasks/{task.id}",
        test_cases=total,
    )


# ── Epic 8, Story 8.9: eksport do Jira Xray i Zephyr Scale ─────────────────


async def _dispatch_jira_export(
    project_id: uuid.UUID,
    body: TmsExportRequest,
    current_user: User,
    db: AsyncSession,
    provider: str,
) -> TmsExportAcceptedResponse:
    """Wspólna ścieżka dla obu wtyczek — różni je tylko nazwa dostawcy."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    config = await get_jira_tms_config(db, project_id, tid)

    if config.provider.value != provider:
        raise ValidationError(
            f"Projekt jest skonfigurowany dla wtyczki „{config.provider.value}”. "
            "Zmień konfigurację albo użyj eksportu zgodnego z nią."
        )

    count_stmt = select(func.count()).select_from(TestCase).where(
        TestCase.tenant_id == tid,
        TestCase.analysis_result_id.in_(
            select(AnalysisResult.id).where(AnalysisResult.project_id == project_id)
        ),
    )
    if body.test_case_ids:
        count_stmt = count_stmt.where(TestCase.id.in_(body.test_case_ids))
    total = int(await db.scalar(count_stmt) or 0)

    task = export_to_jira_tms.delay(
        tenant_id=str(tid),
        project_id=str(project_id),
        integration_config_id=str(config.id),
        test_case_ids=[str(i) for i in body.test_case_ids],
        provider=provider,
    )
    TaskProgressService().init_task(task.id, str(tid))

    return TmsExportAcceptedResponse(
        task_id=task.id,
        status="pending",
        status_url=f"/api/v1/tasks/{task.id}",
        test_cases=total,
    )


@router.post(
    "/{project_id}/export/xray",
    response_model=TmsExportAcceptedResponse,
    status_code=202,
    summary="Eksportuj przypadki testowe do Jira Xray",
    description=(
        "**Eksport do Xraya (Story 8.9).**\n\n"
        "Uruchamia eksport w tle. Testy już wyeksportowane (rozpoznane po "
        "etykiecie `testgen-{id}`) są aktualizowane, a nie duplikowane. "
        "Pusta lista `test_case_ids` oznacza wszystkie przypadki projektu."
    ),
    responses={
        202: {"description": "Eksport przyjęty; postęp pod `status_url`."},
        404: {"description": "Projekt nie istnieje albo brak konfiguracji Jira."},
        422: {"description": "Projekt jest skonfigurowany dla innej wtyczki."},
    },
)
async def export_test_cases_to_xray(
    project_id: uuid.UUID,
    body: TmsExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TmsExportAcceptedResponse:
    """Kolejkuje eksport przypadków do Jiry przez Xraya (AC2/AC4)."""
    return await _dispatch_jira_export(project_id, body, current_user, db, "xray")


@router.post(
    "/{project_id}/export/zephyr",
    response_model=TmsExportAcceptedResponse,
    status_code=202,
    summary="Eksportuj przypadki testowe do Zephyr Scale",
    description=(
        "**Eksport do Zephyr Scale (Story 8.9).**\n\n"
        "Uruchamia eksport w tle. Testy już wyeksportowane (rozpoznane po polu "
        "własnym `testgen_id`) są aktualizowane, a nie duplikowane. Foldery "
        "powstają automatycznie, per moduł."
    ),
    responses={
        202: {"description": "Eksport przyjęty; postęp pod `status_url`."},
        404: {"description": "Projekt nie istnieje albo brak konfiguracji Jira."},
        422: {"description": "Projekt jest skonfigurowany dla innej wtyczki."},
    },
)
async def export_test_cases_to_zephyr(
    project_id: uuid.UUID,
    body: TmsExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TmsExportAcceptedResponse:
    """Kolejkuje eksport przypadków do Jiry przez Zephyr Scale (AC3/AC4)."""
    return await _dispatch_jira_export(project_id, body, current_user, db, "zephyr")
