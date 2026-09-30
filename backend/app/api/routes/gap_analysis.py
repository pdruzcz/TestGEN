"""Functional gap analysis routes — Epic 5, Story 5.1.

Project-scoped endpoints to launch gap analysis (async), list findings with
filters and pagination, and get a summary.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.code_error import CodeError, ErrorCategory
from app.models.compliance_snapshot import ComplianceSnapshot
from app.models.gap_finding import GapFinding, GapType
from app.models.project import Project
from app.models.recommendation import Recommendation, RecommendationPriority
from app.models.user import User
from app.schemas.gap import (
    CodeErrorResponse,
    CodeErrorScanRequest,
    CodeErrorScanResponse,
    CodeErrorsListResponse,
    CodeErrorStatusUpdateRequest,
    CodeErrorSummary,
    ComparisonResponse,
    ComplianceScoreResponse,
    ComplianceSnapshotResponse,
    FindingDiffResponse,
    FunctionScoreResponse,
    GapAnalysisRequest,
    GapAnalysisSummary,
    GapAnalysisTriggerResponse,
    GapFindingResponse,
    GapFindingsListResponse,
    ModuleScoreResponse,
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationResponse,
    RecommendationsListResponse,
    RecommendationSummary,
    SkeletonGenerateRequest,
    SkeletonResponse,
    SnapshotCreateRequest,
    SnapshotDiffResponse,
    TrendPointResponse,
    TrendResponse,
)
from app.services.billing.feature_gating import require_feature
from app.services.gap_analysis.compliance_engine import ComplianceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["gap-analysis"])


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
    "/{project_id}/gap-analysis",
    response_model=GapAnalysisTriggerResponse,
    status_code=202,
    dependencies=[Depends(require_feature("code_doc_consistency"))],
    description=(
        "**Uruchom analizę luk funkcjonalnych (Epic 5, FR38).**\n\n"
        "Asynchronicznie porównuje wymagania z dokumentacji z bytami kodu "
        "przy użyciu 3 algorytmów fuzzy matching (Levenshtein, Jaro-Winkler, "
        "TF-IDF cosine). Klasyfikuje wynik w 4 typy luk (missing/different/"
        "extra/inconsistent).\n\n"
        "Tryb `engine_mode`:\n"
        "- `native` (domyślnie) — deterministyczny, offline\n"
        "- `llm` — semantyczna analiza przez LLMGateway\n"
        "- `hybrid` — łączy native + LLM, najwyższy recall\n\n"
        "Wymaga uprzedniego uruchomienia analizy dokumentu (requirements) i "
        "skanowania kodu (logic_structures). Zwraca `task_id` do śledzenia "
        "w `/tasks/{task_id}`."
    ),
    responses={
        202: {
            "description": "Analiza zaplanowana — zwraca task_id do śledzenia.",
            "content": {
                "application/json": {
                    "example": {"task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "status": "pending"},
                },
            },
        },
        404: {"description": "Projekt nie znaleziony lub brak dostępu w tenant."},
        403: {"description": "Brak kontekstu tenant."},
    },
)
async def start_gap_analysis(
    project_id: uuid.UUID,
    body: GapAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GapAnalysisTriggerResponse:
    """Launch asynchronous gap analysis for the project."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    from app.workers.tasks.gap_tasks import run_gap_analysis

    task = run_gap_analysis.delay(
        str(project_id),
        [str(d) for d in body.document_ids] if body.document_ids else [],
        str(tid),
        body.engine_mode,
    )
    return GapAnalysisTriggerResponse(task_id=task.id, status="pending")


@router.get(
    "/{project_id}/gap-findings",
    response_model=GapFindingsListResponse,
    description=(
        "**Lista znalezisk luk (Epic 5, FR39).**\n\n"
        "Paginowana lista z filtrami:\n"
        "- `gap_type` — missing | different | extra | inconsistent\n"
        "- `severity` — info | warning | critical\n"
        "- `min_score` — 0.0-100.0\n"
        "- `match_method` — lev | jw | sem | combined | hybrid | llm\n\n"
        "Wynik zawiera podsumowanie (`summary`) wyliczone dla całego projektu, "
        "nie tylko bieżącej strony."
    ),
)
async def list_gap_findings(
    project_id: uuid.UUID,
    gap_type: str | None = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=100.0),
    severity: str | None = Query(None),
    match_method: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GapFindingsListResponse:
    """List gap findings with filters and pagination."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    query = select(GapFinding).where(
        GapFinding.project_id == project_id,
        GapFinding.tenant_id == tid,
    )

    if gap_type:
        try:
            gt = GapType(gap_type)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid gap_type: {gap_type}") from None
        query = query.where(GapFinding.gap_type == gt)

    if min_score > 0:
        query = query.where(GapFinding.match_score >= min_score)

    if severity:
        query = query.where(GapFinding.severity == severity)

    if match_method:
        query = query.where(GapFinding.match_method == match_method)

    # Total count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginated results
    offset = (page - 1) * size
    items_q = query.order_by(GapFinding.match_score.desc()).offset(offset).limit(size)
    results = (await db.execute(items_q)).scalars().all()

    findings = [GapFindingResponse.model_validate(f) for f in results]

    # Build summary (over all findings, not just current page)
    summary = await _build_summary(db, project_id, tid)

    return GapFindingsListResponse(
        findings=findings,
        total=total,
        page=page,
        size=size,
        summary=summary,
    )


@router.get(
    "/{project_id}/gap-analysis/summary",
    response_model=GapAnalysisSummary,
    description=(
        "**Podsumowanie analizy luk.**\n\n"
        "Zwraca łączną liczbę wymagań, bytów kodu, liczebności per typ luki, "
        "średni score dopasowania i procent pokrycia (coverage %)."
    ),
)
async def get_gap_analysis_summary(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GapAnalysisSummary:
    """Get summary of gap analysis for the project."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    return await _build_summary(db, project_id, tid)


@router.get(
    "/{project_id}/gap-findings/by-type",
)
async def list_gap_findings_grouped(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List gap findings grouped by gap_type with counts and percentages."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    base_query = select(GapFinding).where(
        GapFinding.project_id == project_id,
        GapFinding.tenant_id == tid,
    )
    all_results = (await db.execute(base_query)).scalars().all()

    types = ["missing", "different", "extra", "inconsistent"]
    total = len(all_results)
    grouped: dict[str, dict] = {}
    for t in types:
        items = [f for f in all_results if f.gap_type.value == t]
        count = len(items)
        grouped[t] = {
            "count": count,
            "percentage": round(count / total * 100.0, 1) if total > 0 else 0.0,
            "findings": [GapFindingResponse.model_validate(f) for f in items],
        }

    return {"total": total, "grouped": grouped}


async def _build_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> GapAnalysisSummary:
    """Build aggregate summary from gap_findings table."""
    base_query = select(GapFinding).where(
        GapFinding.project_id == project_id,
        GapFinding.tenant_id == tenant_id,
    )

    all_results = (await db.execute(base_query)).scalars().all()

    missing = sum(1 for f in all_results if f.gap_type == GapType.MISSING)
    different = sum(1 for f in all_results if f.gap_type == GapType.DIFFERENT)
    extra = sum(1 for f in all_results if f.gap_type == GapType.EXTRA)
    inconsistent = sum(1 for f in all_results if f.gap_type == GapType.INCONSISTENT)

    scores = [f.match_score for f in all_results if f.match_score > 0]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    # Requirements that have matches = those that are NOT missing
    matched_reqs = different  # different means there IS a match, just divergent
    total_requirements = missing + matched_reqs
    coverage = (matched_reqs / total_requirements * 100.0) if total_requirements > 0 else 0.0

    return GapAnalysisSummary(
        total_requirements=total_requirements,
        total_code_entities=extra,
        missing_count=missing,
        different_count=different,
        extra_count=extra,
        inconsistent_count=inconsistent,
        avg_match_score=round(avg_score, 1),
        coverage_percentage=round(coverage, 1),
    )


# ── Compliance endpoints (Story 5.3) ─────────────────────────────────────────


async def _get_all_findings(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[GapFinding]:
    """Fetch all gap findings for compliance computation."""
    query = select(GapFinding).where(
        GapFinding.project_id == project_id,
        GapFinding.tenant_id == tenant_id,
    )
    return list((await db.execute(query)).scalars().all())


@router.get(
    "/{project_id}/compliance",
    response_model=ComplianceScoreResponse,
    description=(
        "**Compliance score projektu (Epic 5, FR40).**\n\n"
        "Score 0-100, gdzie 100 = pełna zgodność z dokumentacją. "
        "Obliczane w locie z `gap_findings` na podstawie penalty weights:\n"
        "- missing+critical = 15, missing+warning = 8, missing+info = 3\n"
        "- different+critical = 10, different+warning = 5, different+info = 2\n"
        "- inconsistent = 10/5/2\n"
        "- extra = 5/3/1\n\n"
        "Wzór: `score = max(0, 100 - Σ penalties)`."
    ),
    responses={
        200: {
            "description": "Score projektu",
            "content": {
                "application/json": {
                    "example": {
                        "score": 62.0,
                        "total_findings": 18,
                        "breakdown": {"missing": 4, "different": 6, "extra": 7, "inconsistent": 1},
                    },
                },
            },
        },
    },
)
async def get_compliance_score(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplianceScoreResponse:
    """Get global project compliance score (0-100)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    findings = await _get_all_findings(db, project_id, tid)
    engine = ComplianceEngine()
    result = engine.calculate_project_score(findings)
    return ComplianceScoreResponse(
        score=result.score,
        total_findings=result.total_findings,
        breakdown=result.breakdown,
    )


@router.get(
    "/{project_id}/compliance/modules",
    response_model=list[ModuleScoreResponse],
    description=(
        "**Compliance score per moduł (plik).**\n\n"
        "Grupuje findings po `file_path` i wylicza score 0-100 per moduł. "
        "Sortowane rosnąco po liczbie findings (najgorsze pierwsze)."
    ),
)
async def get_compliance_modules(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ModuleScoreResponse]:
    """Get compliance scores grouped by module (file)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    findings = await _get_all_findings(db, project_id, tid)
    engine = ComplianceEngine()
    results = engine.calculate_module_scores(findings)
    return [
        ModuleScoreResponse(
            file_path=m.file_path,
            score=m.score,
            total_findings=m.total_findings,
            breakdown=m.breakdown,
        )
        for m in results
    ]


@router.get(
    "/{project_id}/compliance/functions",
    response_model=list[FunctionScoreResponse],
    description=(
        "**Compliance score per funkcja / byt kodu.**\n\n"
        "Grupuje findings po `code_entity_id` i wylicza score 0-100 per funkcja. "
        "Użyteczne do drill-down w module."
    ),
)
async def get_compliance_functions(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FunctionScoreResponse]:
    """Get compliance scores grouped by function/code entity."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    findings = await _get_all_findings(db, project_id, tid)
    engine = ComplianceEngine()
    results = engine.calculate_function_scores(findings)
    return [
        FunctionScoreResponse(
            code_entity_id=fn.code_entity_id,
            score=fn.score,
            total_findings=fn.total_findings,
            breakdown=fn.breakdown,
            file_path=fn.file_path,
            entity_name=fn.entity_name,
        )
        for fn in results
    ]


@router.post(
    "/{project_id}/compliance/export",
    dependencies=[Depends(require_feature("functional_gaps"))],
)
async def export_compliance_report(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export full compliance report as CSV string."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    findings = await _get_all_findings(db, project_id, tid)
    engine = ComplianceEngine()
    csv_data = engine.export_csv(findings)
    return {"csv": csv_data, "format": "text/csv"}


# ── Code error endpoints (Story 5.4) ─────────────────────────────────────────


@router.post(
    "/{project_id}/code-errors/scan",
    response_model=CodeErrorScanResponse,
    status_code=202,
    dependencies=[Depends(require_feature("functional_gaps"))],
)
async def start_code_error_scan(
    project_id: uuid.UUID,
    body: CodeErrorScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeErrorScanResponse:
    """Launch asynchronous code error detection for the project."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    from app.workers.tasks.code_error_tasks import run_code_error_detection

    task = run_code_error_detection.delay(
        str(project_id),
        str(tid),
        body.categories,
    )
    return CodeErrorScanResponse(task_id=task.id, status="pending")


@router.get(
    "/{project_id}/code-errors",
    response_model=CodeErrorsListResponse,
)
async def list_code_errors(
    project_id: uuid.UUID,
    category: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeErrorsListResponse:
    """List code errors with filters and pagination."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    query = select(CodeError).where(
        CodeError.project_id == project_id,
        CodeError.tenant_id == tid,
        CodeError.status != "false_positive",
    )

    if category:
        try:
            cat = ErrorCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid category: {category}",
            ) from None
        query = query.where(CodeError.category == cat)

    if severity:
        query = query.where(CodeError.severity == severity)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * size
    items_q = query.order_by(CodeError.created_at.desc()).offset(offset).limit(size)
    results = (await db.execute(items_q)).scalars().all()

    errors = [CodeErrorResponse.model_validate(e) for e in results]
    summary = await _build_code_error_summary(db, project_id, tid)

    return CodeErrorsListResponse(
        errors=errors,
        total=total,
        page=page,
        size=size,
        summary=summary,
    )


@router.get(
    "/{project_id}/code-errors/summary",
    response_model=CodeErrorSummary,
)
async def get_code_error_summary(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeErrorSummary:
    """Get summary of code errors for the project."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    return await _build_code_error_summary(db, project_id, tid)


@router.patch(
    "/{project_id}/code-errors/{error_id}/status",
    response_model=CodeErrorResponse,
)
async def update_code_error_status(
    project_id: uuid.UUID,
    error_id: uuid.UUID,
    payload: CodeErrorStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeErrorResponse:
    """Triage a code error (dismiss as false_positive — Story 5.10, AC4).

    Dismissed findings stay out of lists/summaries and are not re-detected
    on rescans of the same code state (stable fingerprint key).
    """
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    error = await db.get(CodeError, error_id)
    if error is None or error.project_id != project_id or error.tenant_id != tid:
        raise HTTPException(status_code=404, detail="Błąd kodu nie został znaleziony")

    error.status = payload.status
    await db.commit()
    await db.refresh(error)
    return CodeErrorResponse.model_validate(error)


async def _build_code_error_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> CodeErrorSummary:
    """Build aggregate summary from code_errors table (open findings only)."""
    base_query = select(CodeError).where(
        CodeError.project_id == project_id,
        CodeError.tenant_id == tenant_id,
        CodeError.status != "false_positive",
    )
    all_results = list((await db.execute(base_query)).scalars().all())

    by_category: dict[str, int] = {c.value: 0 for c in ErrorCategory}
    by_severity: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}

    for e in all_results:
        cat = e.category.value if isinstance(e.category, ErrorCategory) else str(e.category)
        by_category[cat] = by_category.get(cat, 0) + 1
        sev = e.severity or "warning"
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return CodeErrorSummary(
        total_errors=len(all_results),
        by_category=by_category,
        by_severity=by_severity,
    )


# ── Recommendation endpoints (Story 5.5) ─────────────────────────────────────


@router.post(
    "/{project_id}/recommendations/generate",
    response_model=RecommendationGenerateResponse,
    status_code=202,
    dependencies=[Depends(require_feature("functional_gaps"))],
    description=(
        "**Generuj rekomendacje naprawcze (Epic 5, FR42).**\n\n"
        "Uruchamia asynchroniczny task, który dla każdej luki w `gap_findings` "
        "produces actionable rekomendację z:\n"
        "- `priority` (P1 natychmiat → P4 niski)\n"
        "- `confidence` (0.0-1.0)\n"
        "- `effort_estimate` (S/M/L)\n"
        "- `suggested_action` (tekst)\n\n"
        "Źródła:\n"
        "- `native` — template-based, deterministyczne (confidence 0.7)\n"
        "- `llm` — semantyczne przez LLMGateway\n"
        "- `hybrid` — oba źródła połączone\n\n"
        "Mapowanie priorytetów: missing+critical=P1, different+critical=P1, "
        "inconsistent zawsze P1, missing+warning=P2, extra+info=P4."
    ),
)
async def generate_recommendations(
    project_id: uuid.UUID,
    body: RecommendationGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationGenerateResponse:
    """Generate recommendations from gap findings and code errors."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    from app.workers.tasks.recommendation_tasks import run_recommendation_generation

    task = run_recommendation_generation.delay(
        str(project_id),
        str(tid),
        body.sources,
    )
    return RecommendationGenerateResponse(task_id=task.id, status="pending")


@router.get(
    "/{project_id}/recommendations",
    response_model=RecommendationsListResponse,
    description=(
        "**Lista rekomendacji.**\n\n"
        "Paginowana lista z filtrami:\n"
        "- `priority` — P1 | P2 | P3 | P4\n"
        "- `source_type` — native | llm | hybrid\n"
        "- `min_confidence` — 0.0-1.0\n\n"
        "Każda rekomendacja ma `suggested_action`, `effort_estimate` "
        "(S/M/L) i powiązanie do `gap_finding_id`."
    ),
)
async def list_recommendations(
    project_id: uuid.UUID,
    priority: str | None = Query(None),
    source_type: str | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationsListResponse:
    """List recommendations with filters and pagination."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    query = select(Recommendation).where(
        Recommendation.project_id == project_id,
        Recommendation.tenant_id == tid,
    )

    if priority:
        try:
            pri = RecommendationPriority(priority)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid priority: {priority}",
            ) from None
        query = query.where(Recommendation.priority == pri)

    if source_type:
        query = query.where(Recommendation.source_type == source_type)

    if min_confidence > 0:
        query = query.where(Recommendation.confidence >= min_confidence)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * size
    items_q = query.order_by(Recommendation.created_at.desc()).offset(offset).limit(size)
    results = (await db.execute(items_q)).scalars().all()

    recs = [RecommendationResponse.model_validate(r) for r in results]
    summary = await _build_recommendation_summary(db, project_id, tid)

    return RecommendationsListResponse(
        recommendations=recs,
        total=total,
        page=page,
        size=size,
        summary=summary,
    )


@router.get(
    "/{project_id}/recommendations/summary",
    response_model=RecommendationSummary,
)
async def get_recommendation_summary(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationSummary:
    """Get summary of recommendations for the project."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    return await _build_recommendation_summary(db, project_id, tid)


async def _build_recommendation_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> RecommendationSummary:
    """Build aggregate summary from recommendations table."""
    base_query = select(Recommendation).where(
        Recommendation.project_id == project_id,
        Recommendation.tenant_id == tenant_id,
    )
    all_results = list((await db.execute(base_query)).scalars().all())

    by_priority: dict[str, int] = {p.value: 0 for p in RecommendationPriority}
    total_conf = 0.0
    low_conf = 0

    for r in all_results:
        pri = r.priority.value if isinstance(r.priority, RecommendationPriority) else str(r.priority)
        by_priority[pri] = by_priority.get(pri, 0) + 1
        total_conf += r.confidence
        if r.confidence < 0.5:
            low_conf += 1

    avg_conf = round(total_conf / len(all_results), 2) if all_results else 0.0

    return RecommendationSummary(
        total=len(all_results),
        by_priority=by_priority,
        avg_confidence=avg_conf,
        low_confidence_count=low_conf,
    )


# ── Skeleton endpoints (Story 5.6) ───────────────────────────────────────────


@router.post(
    "/{project_id}/gap-findings/{finding_id}/skeleton",
    response_model=SkeletonResponse,
    dependencies=[Depends(require_feature("functional_gaps"))],
    description=(
        "**Generuj skeleton kodu (Story 5.6).**\n\n"
        "Dostępne tylko dla findings typu `missing`. Produkuje plik źródłowy "
        "ze stub implementacji (`NotImplementedError` / `UnsupportedOperationException`).\n\n"
        "Obsługiwane języki: `python`, `typescript`, `java`, `csharp`.\n\n"
        "Skeleton jest walidowany tree-sitter — gwarancja poprawnej składni. "
        "Wynik jest persystowany na `finding.skeleton_code` + `skeleton_language`."
    ),
    responses={
        200: {
            "description": "Skeleton wygenerowany",
            "content": {
                "application/json": {
                    "example": {
                        "code": "def export_pdf_report(data):\n    raise NotImplementedError(...)",
                        "language": "python",
                        "file_name": "export_pdf_report.py",
                    },
                },
            },
        },
        422: {"description": "Finding nie jest typu missing, lub błąd składni."},
        404: {"description": "Finding nie znaleziony."},
    },
)
async def generate_skeleton(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: SkeletonGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SkeletonResponse:
    """Generate skeleton code for a missing-implementation gap finding."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    finding = (
        await db.execute(
            select(GapFinding).where(
                GapFinding.id == finding_id,
                GapFinding.project_id == project_id,
                GapFinding.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()

    if finding is None:
        raise HTTPException(status_code=404, detail="Gap finding not found")

    if finding.gap_type != GapType.MISSING:
        raise HTTPException(
            status_code=422,
            detail="Skeleton can only be generated for MISSING gaps",
        )

    from app.services.gap_analysis.skeleton_generator import SkeletonGenerator

    generator = SkeletonGenerator()
    result = generator.generate(finding, body.language)

    if result.error:
        raise HTTPException(status_code=422, detail=result.error)

    # Persist skeleton on the finding
    finding.skeleton_code = result.code
    finding.skeleton_language = result.language
    await db.commit()

    return SkeletonResponse(
        finding_id=finding_id,
        skeleton_code=result.code,
        language=result.language,
        function_name=result.function_name,
    )


@router.get(
    "/{project_id}/gap-findings/{finding_id}/skeleton",
    response_model=SkeletonResponse,
)
async def get_skeleton(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SkeletonResponse:
    """Retrieve previously generated skeleton code for a gap finding."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    finding = (
        await db.execute(
            select(GapFinding).where(
                GapFinding.id == finding_id,
                GapFinding.project_id == project_id,
                GapFinding.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()

    if finding is None:
        raise HTTPException(status_code=404, detail="Gap finding not found")

    if not finding.skeleton_code:
        raise HTTPException(
            status_code=404,
            detail="No skeleton generated for this finding yet",
        )

    return SkeletonResponse(
        finding_id=finding_id,
        skeleton_code=finding.skeleton_code,
        language=finding.skeleton_language or "python",
        function_name="",
    )


# ── Version comparison endpoints (Story 5.7) ─────────────────────────────────


@router.post(
    "/{project_id}/compliance/snapshot",
    response_model=ComplianceSnapshotResponse,
    status_code=201,
    dependencies=[Depends(require_feature("functional_gaps"))],
    description=(
        "**Utwórz snapshot compliance (Story 5.7).**\n\n"
        "Przechwytuje aktualny stan compliance (score + breakdown + counts) "
        "jako punkt w czasie. Snapshots pozwalają na porównanie wersji i trend."
    ),
)
async def create_compliance_snapshot(
    project_id: uuid.UUID,
    body: SnapshotCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplianceSnapshotResponse:
    """Capture current compliance state as a named snapshot."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    findings = await _get_all_findings(db, project_id, tid)
    engine = ComplianceEngine()
    score = engine.calculate_project_score(findings)
    summary = await _build_summary(db, project_id, tid)

    snapshot = ComplianceSnapshot(
        tenant_id=tid,
        project_id=project_id,
        score=score.score,
        total_findings=score.total_findings,
        missing_count=summary.missing_count,
        different_count=summary.different_count,
        extra_count=summary.extra_count,
        inconsistent_count=summary.inconsistent_count,
        avg_match_score=summary.avg_match_score,
        coverage_percentage=summary.coverage_percentage,
        label=body.label,
        notes=body.notes,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return ComplianceSnapshotResponse.model_validate(snapshot)


@router.get(
    "/{project_id}/compliance/snapshots",
    response_model=list[ComplianceSnapshotResponse],
)
async def list_compliance_snapshots(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ComplianceSnapshotResponse]:
    """List all compliance snapshots for the project, newest first."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    result = await db.execute(
        select(ComplianceSnapshot)
        .where(
            ComplianceSnapshot.project_id == project_id,
            ComplianceSnapshot.tenant_id == tid,
        )
        .order_by(ComplianceSnapshot.created_at.desc())
    )
    snapshots = result.scalalars().all()
    return [ComplianceSnapshotResponse.model_validate(s) for s in snapshots]


@router.get(
    "/{project_id}/compliance/compare",
    response_model=ComparisonResponse,
    description=(
        "**Porównanie dwóch snapshotów compliance (Story 5.7).**\n\n"
        "Parametry `v1` i `v2` to IDs snapshotów. Zwraca per-finding diff:\n"
        "- `fixed` — luki rozwiązane między wersjami\n"
        "- `new` — luki dodane od v1\n"
        "- `unchanged` — bez zmian\n"
        "- `worsened` — score się obniżył\n\n"
        "Plus delta compliance i trend."
    ),
)
async def compare_versions(
    project_id: uuid.UUID,
    v1: uuid.UUID = Query(..., description="First snapshot ID"),
    v2: uuid.UUID = Query(..., description="Second snapshot ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResponse:
    """Compare two compliance snapshots with per-finding diff."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    snap1 = (
        await db.execute(
            select(ComplianceSnapshot).where(
                ComplianceSnapshot.id == v1,
                ComplianceSnapshot.project_id == project_id,
                ComplianceSnapshot.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()
    snap2 = (
        await db.execute(
            select(ComplianceSnapshot).where(
                ComplianceSnapshot.id == v2,
                ComplianceSnapshot.project_id == project_id,
                ComplianceSnapshot.tenant_id == tid,
            )
        )
    ).scalar_one_or_none()

    if snap1 is None or snap2 is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    from app.services.gap_analysis.comparison_engine import ComparisonEngine

    engine = ComparisonEngine()

    # Fetch findings linked to each snapshot's analysis_id if available,
    # otherwise compare all current findings as-is.
    v1_findings: list[GapFinding] = []
    v2_findings: list[GapFinding] = []

    if snap1.analysis_id:
        v1_findings = list(
            (
                await db.execute(
                    select(GapFinding).where(
                        GapFinding.analysis_id == snap1.analysis_id,
                        GapFinding.tenant_id == tid,
                    )
                )
            )
            .scalars()
            .all()
        )
    if snap2.analysis_id:
        v2_findings = list(
            (
                await db.execute(
                    select(GapFinding).where(
                        GapFinding.analysis_id == snap2.analysis_id,
                        GapFinding.tenant_id == tid,
                    )
                )
            )
            .scalars()
            .all()
        )

    result = engine.compare(snap1, snap2, v1_findings, v2_findings)

    return ComparisonResponse(
        v1_snapshot=ComplianceSnapshotResponse.model_validate(snap1),
        v2_snapshot=ComplianceSnapshotResponse.model_validate(snap2),
        snapshot_diff=SnapshotDiffResponse(
            v1_score=result.snapshot_diff.v1_score,
            v2_score=result.snapshot_diff.v2_score,
            score_delta=result.snapshot_diff.score_delta,
            direction=result.snapshot_diff.direction,
            v1_total=result.snapshot_diff.v1_total,
            v2_total=result.snapshot_diff.v2_total,
            total_delta=result.snapshot_diff.total_delta,
            missing_delta=result.snapshot_diff.missing_delta,
            different_delta=result.snapshot_diff.different_delta,
            extra_delta=result.snapshot_diff.extra_delta,
            inconsistent_delta=result.snapshot_diff.inconsistent_delta,
            coverage_delta=result.snapshot_diff.coverage_delta,
            avg_match_score_delta=result.snapshot_diff.avg_match_score_delta,
        ),
        finding_diffs=[
            FindingDiffResponse(
                key=fd.key,
                status=fd.status,
                gap_type=fd.gap_type,
                v1_severity=fd.v1_severity,
                v2_severity=fd.v2_severity,
                v1_score=fd.v1_score,
                v2_score=fd.v2_score,
                requirement_text=fd.requirement_text,
            )
            for fd in result.finding_diffs
        ],
        summary=result.summary,
    )


@router.get(
    "/{project_id}/compliance/trend",
    response_model=TrendResponse,
)
async def get_compliance_trend(
    project_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrendResponse:
    """Get compliance trend data across snapshots (oldest to newest)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)

    result = await db.execute(
        select(ComplianceSnapshot)
        .where(
            ComplianceSnapshot.project_id == project_id,
            ComplianceSnapshot.tenant_id == tid,
        )
        .order_by(ComplianceSnapshot.created_at.asc())
        .limit(limit)
    )
    snapshots = list(result.scalars().all())

    from app.services.gap_analysis.comparison_engine import ComparisonEngine

    engine = ComparisonEngine()
    trend_data = engine.compute_trend(snapshots)
    return TrendResponse(points=[TrendPointResponse(**p) for p in trend_data])
