"""Analysis routes — pipeline orchestration and LLM file analysis."""

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db, get_tenant
from app.core.exceptions import NotFoundError, ValidationError
from app.core.storage import get_minio_client
from app.models.project import Project
from app.models.source_file import SourceFile
from app.models.tenant import Tenant
from app.models.uml_diagram import UMLDiagram
from app.models.usage import CounterType
from app.models.user import User
from app.schemas.analysis import AnalysisResponse, LLMError
from app.schemas.task_schemas import AnalysisAcceptedResponse, AnalysisRequest
from app.services.analysis.llm_service import analyze_file_content
from app.services.billing.quota_service import QuotaService as BillingQuotaService
from app.services.quota_service import QuotaService
from app.services.task_progress_service import TaskProgressService
from app.workers.pipeline import run_pipeline
from app.workers.tasks.analysis_tasks import analyze_cross_diagrams

# Moduły wymagające plików źródłowych kodu (pipeline AST → analiza → testy).
_CODE_MODULES = frozenset({"code_analysis", "test_generation"})

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["analysis"])


# ── DEMO-001: Single-file LLM analysis (existing) ──────────────────────────


@router.post(
    "/{project_id}/files/{file_id}/analyze",
    response_model=AnalysisResponse,
)
async def analyze_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    result = await db.execute(
        select(SourceFile).where(
            SourceFile.id == file_id,
            SourceFile.project_id == project_id,
            SourceFile.is_cleaned_up == False,  # noqa: E712
        )
    )
    source_file = result.scalar_one_or_none()
    if not source_file:
        raise NotFoundError("File not found or already cleaned up")

    settings = get_settings()
    client = get_minio_client()
    response = client.get_object(settings.minio_bucket_name, source_file.storage_key)
    try:
        content = response.read().decode("utf-8", errors="replace")
    finally:
        response.close()
        response.release_conn()

    try:
        analysis = await analyze_file_content(source_file.filename, content)
    except Exception as exc:
        logger.error("LLM analysis failed: %s", exc)
        raise LLMError(detail=f"LLM analysis failed: {exc}") from exc

    return AnalysisResponse(
        analysis=analysis,
        file_id=file_id,
        project_id=project_id,
    )


# ── Story 1.10: Pipeline analysis trigger ───────────────────────────────────


@router.post(
    "/{project_id}/analyze",
    response_model=AnalysisAcceptedResponse,
    status_code=202,
)
async def start_analysis(
    project_id: uuid.UUID,
    body: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> AnalysisAcceptedResponse:
    # Verify project exists and belongs to tenant (RLS-enforced)
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundError("Project not found")

    # Brama modułowa: każdy wybrany moduł wymaga swoich artefaktów.
    # Pipeline AST jest kodocentryczny — bez modułów kodowych wystarczy UML.
    modules = set(body.modules) if body.modules else {"code_analysis"}
    needs_code = bool(modules & _CODE_MODULES)
    needs_uml = "uml_analysis" in modules

    if needs_code:
        file_count = await db.scalar(
            select(func.count()).where(
                SourceFile.project_id == project_id,
                SourceFile.is_cleaned_up == False,  # noqa: E712
            )
        )
        if not file_count:
            raise ValidationError("Project has no source files uploaded")

    if needs_uml:
        diagram_count = await db.scalar(select(func.count()).where(UMLDiagram.project_id == project_id))
        if not diagram_count:
            raise ValidationError("Project has no UML diagrams uploaded")

    # Story 7.8 (AC1): limity z subscription_plans.features — 429 z body
    # ``limit_reached`` gdy licznik analiz lub liczba plików ponad plan.
    billing_quota = BillingQuotaService(db)
    await billing_quota.enforce_quota(tenant_id, CounterType.ANALYSES)
    if needs_code:
        await billing_quota.enforce_quota(tenant_id, CounterType.FILES_PER_ANALYSIS, increment=int(file_count or 0))

    # Quota check + reserve (atomic — eliminates TOCTOU race condition)
    tenant = await db.get(Tenant, tenant_id)
    quota_svc = QuotaService()
    quota_svc.check_and_reserve(tenant_id, plan=tenant.plan)

    # Dispatch Celery task — engine_mode from user request or server config
    effective_engine_mode = (body.engine_mode or get_settings().engine_mode).value
    if needs_code:
        task = run_pipeline.delay(
            tenant_id=str(tenant_id),
            project_id=str(project_id),
            engine_mode=effective_engine_mode,
            modules=body.modules,
            # Story 1.56 (AC3): jawny .value — Celery/JSON nie musi znać enuma
            test_framework=body.test_framework.value if body.test_framework else None,
            llm_model=body.llm_model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        # Moduł UML przy pełnym pipeline: odpal cross-diagram równolegle
        # (wynik na ekranie „User flows", task kodowy pozostaje głównym).
        if needs_uml:
            analyze_cross_diagrams.delay(str(project_id), str(tenant_id), None, effective_engine_mode)
    else:
        # UML-only: zamiast pipeline'u kodu (który by się wywalił na kroku
        # AST bez plików) dispatchujemy cross-diagram analysis — ten sam task,
        # co przycisk „Analizuj user flows" na ekranie UML.
        task = analyze_cross_diagrams.delay(str(project_id), str(tenant_id), None, effective_engine_mode)

    # Init progress tracking in Redis
    progress_svc = TaskProgressService()
    progress_svc.init_task(task.id, str(tenant_id))

    # Story 7.8 (AC3): licznik ``analyses`` w usage_counters po udanym dispatchu
    # (atomowy UPDATE; commit robi dependency get_db).
    await billing_quota.increment_usage(tenant_id, CounterType.ANALYSES)

    return AnalysisAcceptedResponse(
        task_id=task.id,
        status="pending",
        status_url=f"/api/v1/tasks/{task.id}",
    )
