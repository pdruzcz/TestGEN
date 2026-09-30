"""Security scan routes — Epic 4, Story 4.1.

Project-scoped endpoints to launch security scans (SAST and, in later stories,
taint/dependency/config/DAST), list scans, poll a scan's status with a severity
breakdown, and list findings with filters. Scans run asynchronously on the
``security`` Celery queue.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.models.security_finding import (
    ScanType,
    SecurityFinding,
    SecurityScan,
    Severity,
)
from app.models.user import User
from app.schemas.security import (
    BatchPatchRequest,
    BatchPatchResponse,
    ConflictReportResponse,
    FindingStatusUpdateRequest,
    PatchPreviewResponse,
    PatchRequest,
    PatchResponse,
    PoCRequest,
    PoCResponse,
    RecommendationRequest,
    RecommendationResponse,
    RepairStep,
    SecurityDashboardResponse,
    SecurityFindingListResponse,
    SecurityFindingResponse,
    SecurityReportResponse,
    SecurityReportSummary,
    SecurityScanListResponse,
    SecurityScanRequest,
    SecurityScanResponse,
    SecurityScanStatusResponse,
    SeverityCounts,
)
from app.services.billing.feature_gating import require_feature
from app.services.security_scan.finding_aggregator import FindingAggregator
from app.services.security_scan.patch_generator import ConflictReport, PatchGenerator, PatchResult
from app.services.security_scan.poc_generator import PoCGenerator
from app.services.security_scan.recommendation_engine import RecommendationEngine
from app.services.security_scan.risk_engine import RiskEngine
from app.workers.tasks.security_tasks import (
    run_config_scan,
    run_dast_scan,
    run_dependency_scan,
    run_sast,
    run_taint_analysis,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["security"])


def _tenant_of(current_user: User) -> uuid.UUID:
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    return tenant_id


@router.post(
    "/{project_id}/security-scan",
    status_code=202,
    response_model=SecurityScanResponse,
    dependencies=[Depends(require_feature("security"))],
)
async def start_security_scan(
    project_id: uuid.UUID,
    payload: SecurityScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityScanResponse:
    """Create a scan record and dispatch the async scan task (AC1)."""
    tenant_id = _tenant_of(current_user)
    engine_mode = get_settings().engine_mode.value

    if payload.scan_type.value == ScanType.DAST.value and not payload.target_url:
        raise HTTPException(status_code=422, detail="target_url jest wymagany dla skanu DAST")

    scan = SecurityScan(
        project_id=project_id,
        tenant_id=tenant_id,
        scan_type=ScanType(payload.scan_type.value),
        engine_mode=engine_mode,
        target_url=payload.target_url,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    task_id: str | None = None
    if payload.scan_type.value == ScanType.SAST.value:
        result = run_sast.delay(str(scan.id), str(project_id), str(tenant_id), engine_mode)
        task_id = result.id
        scan.task_id = task_id
        await db.commit()
    elif payload.scan_type.value == ScanType.TAINT.value:
        result = run_taint_analysis.delay(str(scan.id), str(project_id), str(tenant_id), engine_mode)
        task_id = result.id
        scan.task_id = task_id
        await db.commit()
    elif payload.scan_type.value == ScanType.DEPENDENCY.value:
        result = run_dependency_scan.delay(str(scan.id), str(project_id), str(tenant_id))
        task_id = result.id
        scan.task_id = task_id
        await db.commit()
    elif payload.scan_type.value == ScanType.CONFIG.value:
        result = run_config_scan.delay(str(scan.id), str(project_id), str(tenant_id), engine_mode)
        task_id = result.id
        scan.task_id = task_id
        await db.commit()
    elif payload.scan_type.value == ScanType.DAST.value:
        auth_config = payload.auth_config.model_dump() if payload.auth_config else None
        result = run_dast_scan.delay(str(scan.id), str(project_id), str(tenant_id), payload.target_url, auth_config)
        task_id = result.id
        scan.task_id = task_id
        await db.commit()
    else:
        # Other scan types land in later Epic 4 stories; record the scan as queued.
        logger.info("Scan type %s requested but not yet dispatched", payload.scan_type)

    return SecurityScanResponse(
        scan_id=scan.id,
        task_id=task_id,
        status=scan.status.value,
        created_at=scan.created_at,
    )


@router.get(
    "/{project_id}/security-scans",
    response_model=SecurityScanListResponse,
)
async def list_security_scans(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityScanListResponse:
    """List the project's scans, most recent first (AC1)."""
    result = await db.execute(
        select(SecurityScan).where(SecurityScan.project_id == project_id).order_by(SecurityScan.created_at.desc())
    )
    scans = result.scalars().all()
    return SecurityScanListResponse(
        scans=[
            SecurityScanStatusResponse(
                scan_id=s.id,
                scan_type=s.scan_type.value,
                engine_mode=s.engine_mode,
                status=s.status.value,
                findings_count=s.findings_count,
                started_at=s.started_at,
                completed_at=s.completed_at,
                error_message=s.error_message,
            )
            for s in scans
        ],
        total=len(scans),
    )


@router.get(
    "/{project_id}/security-scans/{scan_id}",
    response_model=SecurityScanStatusResponse,
)
async def get_security_scan(
    project_id: uuid.UUID,
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityScanStatusResponse:
    """Return a scan's status plus a per-severity findings breakdown (AC1, AC3)."""
    scan = await db.get(SecurityScan, scan_id)
    if scan is None or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Skan nie został znaleziony")

    counts_result = await db.execute(
        select(SecurityFinding.severity, func.count())
        .where(SecurityFinding.scan_id == scan_id)
        .group_by(SecurityFinding.severity)
    )
    counts = SeverityCounts()
    for severity, count in counts_result.all():
        key = severity.value if isinstance(severity, Severity) else str(severity)
        if hasattr(counts, key):
            setattr(counts, key, count)

    return SecurityScanStatusResponse(
        scan_id=scan.id,
        scan_type=scan.scan_type.value,
        engine_mode=scan.engine_mode,
        status=scan.status.value,
        findings_count=scan.findings_count,
        severity_counts=counts,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        error_message=scan.error_message,
    )


@router.get(
    "/{project_id}/security-findings",
    response_model=SecurityFindingListResponse,
)
async def list_security_findings(
    project_id: uuid.UUID,
    scan_id: uuid.UUID | None = Query(None),
    severity: str | None = Query(None, pattern="^(critical|high|medium|low|info)$"),
    scan_type: str | None = Query(None, pattern="^(sast|taint|dependency|config|dast)$"),
    status: str | None = Query(None, pattern="^(open|acknowledged|fixed|false_positive)$"),
    vulnerability_type: str | None = Query(None),
    file_path: str | None = Query(None),
    cwe_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityFindingListResponse:
    """List findings for a project with optional filters (AC3)."""
    conditions = [SecurityFinding.project_id == project_id]
    if scan_id is not None:
        conditions.append(SecurityFinding.scan_id == scan_id)
    if severity is not None:
        conditions.append(SecurityFinding.severity == Severity(severity))
    if scan_type is not None:
        conditions.append(SecurityFinding.scan_type == ScanType(scan_type))
    if vulnerability_type is not None:
        conditions.append(SecurityFinding.vulnerability_type == vulnerability_type)
    if cwe_id is not None:
        conditions.append(SecurityFinding.cwe_id == cwe_id)
    if file_path is not None:
        conditions.append(SecurityFinding.file_path.ilike(f"%{file_path}%"))
    if status is not None:
        from app.models.security_finding import FindingStatus

        conditions.append(SecurityFinding.status == FindingStatus(status))

    total_result = await db.execute(select(func.count()).select_from(SecurityFinding).where(*conditions))
    total = total_result.scalar_one()

    result = await db.execute(
        select(SecurityFinding)
        .where(*conditions)
        .order_by(SecurityFinding.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    findings = result.scalars().all()

    return SecurityFindingListResponse(
        findings=[SecurityFindingResponse.model_validate(f) for f in findings],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}/security-scans/{scan_id}/sbom")
async def get_scan_sbom(
    project_id: uuid.UUID,
    scan_id: uuid.UUID,
    sbom_format: str = Query("cyclonedx", pattern="^(cyclonedx|spdx)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the generated SBOM for a dependency scan (Story 4.4)."""
    scan = await db.get(SecurityScan, scan_id)
    if scan is None or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Skan nie został znaleziony")
    if scan.scan_type.value != ScanType.DEPENDENCY.value:
        raise HTTPException(status_code=400, detail="SBOM dostępny tylko dla skanów zależności")
    if not scan.scan_metadata or sbom_format not in scan.scan_metadata:
        raise HTTPException(status_code=404, detail="SBOM nie został wygenerowany")
    return scan.scan_metadata[sbom_format]


@router.get(
    "/{project_id}/security-report",
    response_model=SecurityReportResponse,
)
async def get_security_report(
    project_id: uuid.UUID,
    scan_id: list[uuid.UUID] | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityReportResponse:
    """Return the aggregated, deduplicated, correlated security report (AC2)."""
    aggregator = FindingAggregator(db)
    result = await aggregator.aggregate(project_id, scan_id or [], db)
    return SecurityReportResponse(
        summary=SecurityReportSummary(**result.summary),
        findings=[SecurityFindingResponse.model_validate(f) for f in result.findings],
        dedup_count=result.dedup_count,
        correlation_count=len(result.correlations),
    )


@router.get(
    "/{project_id}/security-dashboard",
    response_model=SecurityDashboardResponse,
)
async def get_security_dashboard(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityDashboardResponse:
    """Return the risk dashboard: CVSS distribution, top 10 and repair sequence (AC3)."""
    engine = RiskEngine(db)
    assessment = await engine.calculate_risk(project_id, db)
    return SecurityDashboardResponse(
        cvss_distribution=assessment.cvss_distribution,
        top_10_findings=[SecurityFindingResponse.model_validate(f) for f in assessment.top_10],
        repair_sequence=[
            RepairStep(
                finding_id=f.id,
                vulnerability_type=f.vulnerability_type,
                severity=f.severity.value,
                cvss_score=f.cvss_score,
                effort=f.effort,
                priority=f.priority,
            )
            for f in assessment.prioritized_findings
        ],
        total_findings=len(assessment.prioritized_findings),
    )


@router.post(
    "/{project_id}/security-findings/{finding_id}/recommendation",
    response_model=RecommendationResponse,
    dependencies=[Depends(require_feature("security_recommendations"))],
)
async def generate_finding_recommendation(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: RecommendationRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    """Generate a remediation recommendation (problem/risk/fix/diff) for a finding (AC1-AC4)."""
    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    engine_mode = get_settings().engine_mode.value
    engine = RecommendationEngine()
    recommendation = await engine.generate_recommendation(
        finding, source_code=finding.code_snippet, engine_mode=engine_mode
    )
    return RecommendationResponse(
        finding_id=finding.id,
        problem_description=recommendation.problem_description,
        risk_description=recommendation.risk_description,
        fix_description=recommendation.fix_description,
        fixed_code_snippet=recommendation.fixed_code_snippet,
        diff=recommendation.diff,
        language=recommendation.language,
        engine_source=recommendation.engine_source,
    )


@router.post(
    "/{project_id}/security-findings/{finding_id}/generate-poc",
    response_model=PoCResponse,
    dependencies=[Depends(require_feature("security"))],
)
async def generate_finding_poc(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: PoCRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PoCResponse:
    """Generate a safe, non-destructive PoC for an injection finding (AC1-AC4)."""
    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    engine_mode = get_settings().engine_mode.value
    poc = await PoCGenerator().generate_poc(finding, engine_mode=engine_mode, source_code=finding.code_snippet)
    if poc is None:
        raise HTTPException(
            status_code=422,
            detail="Generowanie PoC nie jest wspierane dla tego typu podatności",
        )

    finding.poc_payload = poc.payload
    finding.poc_steps = {"steps": poc.reproduction_steps}
    finding.poc_expected_effect = poc.expected_effect
    await db.commit()

    return PoCResponse(
        finding_id=finding.id,
        payload=poc.payload,
        reproduction_steps=poc.reproduction_steps,
        expected_effect=poc.expected_effect,
        severity=poc.severity,
        is_safe=poc.is_safe,
        disclaimer=poc.disclaimer,
        engine_source=poc.engine_source,
    )


@router.get(
    "/{project_id}/security-findings/{finding_id}/poc",
    response_model=PoCResponse,
)
async def get_finding_poc(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PoCResponse:
    """Return a previously generated PoC for a finding (AC1, AC4)."""
    from app.services.security_scan.poc_generator import DISCLAIMER

    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")
    if not finding.poc_payload:
        raise HTTPException(status_code=404, detail="PoC nie został jeszcze wygenerowany")

    steps = (finding.poc_steps or {}).get("steps", []) if finding.poc_steps else []
    return PoCResponse(
        finding_id=finding.id,
        payload=finding.poc_payload,
        reproduction_steps=steps,
        expected_effect=finding.poc_expected_effect or "",
        severity=finding.severity.value if finding.severity else "medium",
        is_safe=True,
        disclaimer=DISCLAIMER,
        engine_source="native",
    )


def _conflict_to_response(conflict: ConflictReport) -> ConflictReportResponse:
    return ConflictReportResponse(
        patch_a_id=uuid.UUID(conflict.patch_a_id),
        patch_b_id=uuid.UUID(conflict.patch_b_id),
        overlapping_lines=conflict.overlapping_lines,
        severity=conflict.severity,
    )


def _patch_to_response(result: PatchResult) -> PatchResponse:
    return PatchResponse(
        finding_id=uuid.UUID(result.finding_id),
        file_path=result.file_path,
        patch_content=result.patch_content,
        patch_filename=result.patch_filename,
        is_valid=result.is_valid,
        conflicts=[_conflict_to_response(c) for c in result.conflicts],
    )


def _persist_patch(finding: SecurityFinding, result: PatchResult) -> None:
    """Store the generated patch inline in finding_metadata (derived data, no migration)."""
    metadata = dict(finding.finding_metadata or {})
    metadata["patch"] = {
        "patch_content": result.patch_content,
        "patch_filename": result.patch_filename,
        "is_valid": result.is_valid,
    }
    finding.finding_metadata = metadata


@router.post(
    "/{project_id}/security-findings/{finding_id}/generate-patch",
    response_model=PatchResponse,
    dependencies=[Depends(require_feature("security"))],
)
async def generate_finding_patch(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: PatchRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatchResponse:
    """Generate a git-apply-ready unified-diff patch for a finding (AC1, AC2)."""
    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    engine_mode = get_settings().engine_mode.value
    engine = RecommendationEngine()
    recommendation = await engine.generate_recommendation(
        finding, source_code=finding.code_snippet, engine_mode=engine_mode
    )
    result = await PatchGenerator(engine).generate_patch(finding, recommendation, finding.code_snippet or "")
    if not result.patch_content:
        raise HTTPException(
            status_code=422,
            detail="Nie udało się wygenerować patcha — brak różnicy między kodem podatnym a naprawionym",
        )

    _persist_patch(finding, result)
    await db.commit()
    return _patch_to_response(result)


@router.get(
    "/{project_id}/security-findings/{finding_id}/patch",
    response_model=PatchResponse,
)
async def get_finding_patch(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatchResponse:
    """Return a previously generated patch for a finding (AC2)."""
    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    stored = (finding.finding_metadata or {}).get("patch")
    if not stored:
        raise HTTPException(status_code=404, detail="Patch nie został jeszcze wygenerowany")
    return PatchResponse(
        finding_id=finding.id,
        file_path=finding.file_path or "code",
        patch_content=stored["patch_content"],
        patch_filename=stored["patch_filename"],
        is_valid=stored.get("is_valid", False),
    )


@router.get(
    "/{project_id}/security-findings/{finding_id}/patch/preview",
    response_model=PatchPreviewResponse,
)
async def preview_finding_patch(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatchPreviewResponse:
    """Preview before/after code and the diff without persisting (AC2)."""
    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    engine_mode = get_settings().engine_mode.value
    engine = RecommendationEngine()
    recommendation = await engine.generate_recommendation(
        finding, source_code=finding.code_snippet, engine_mode=engine_mode
    )
    result = await PatchGenerator(engine).generate_patch(finding, recommendation, finding.code_snippet or "")
    return PatchPreviewResponse(
        finding_id=finding.id,
        file_path=finding.file_path or "code",
        patch_content=result.patch_content,
        original_code=finding.code_snippet or "",
        fixed_code=recommendation.fixed_code_snippet,
        is_valid=result.is_valid,
    )


@router.get("/{project_id}/security-findings/{finding_id}/patch/download")
async def download_finding_patch(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the stored patch as a ``.patch`` file applicable via ``git apply`` (AC2)."""
    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    stored = (finding.finding_metadata or {}).get("patch")
    if not stored:
        raise HTTPException(status_code=404, detail="Patch nie został jeszcze wygenerowany")
    filename = stored["patch_filename"]
    return Response(
        content=stored["patch_content"],
        media_type="text/x-patch",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{project_id}/security-patches/batch",
    response_model=BatchPatchResponse,
    dependencies=[Depends(require_feature("security"))],
)
async def generate_batch_patches(
    project_id: uuid.UUID,
    payload: BatchPatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchPatchResponse:
    """Generate one patch per finding and report same-file conflicts (AC3)."""
    conditions = [SecurityFinding.project_id == project_id]
    if payload.finding_ids:
        conditions.append(SecurityFinding.id.in_(payload.finding_ids))
    result = await db.execute(select(SecurityFinding).where(*conditions))
    findings = list(result.scalars().all())
    if not findings:
        raise HTTPException(status_code=404, detail="Brak podatności do wygenerowania patchy")

    patches = await PatchGenerator().generate_batch_patches(findings, db, engine_mode=get_settings().engine_mode.value)
    by_id = {str(f.id): f for f in findings}
    conflicts: list[ConflictReportResponse] = []
    seen: set[tuple[str, str]] = set()
    for patch in patches:
        finding = by_id.get(patch.finding_id)
        if finding is not None and patch.patch_content:
            _persist_patch(finding, patch)
        for conflict in patch.conflicts:
            key = tuple(sorted((conflict.patch_a_id, conflict.patch_b_id)))
            if key not in seen:
                seen.add(key)
                conflicts.append(_conflict_to_response(conflict))
    await db.commit()

    return BatchPatchResponse(
        patches=[_patch_to_response(p) for p in patches],
        conflicts=conflicts,
        total=len(patches),
    )


@router.get(
    "/{project_id}/security-patches/conflicts",
    response_model=list[ConflictReportResponse],
)
async def list_patch_conflicts(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConflictReportResponse]:
    """List potential merge conflicts between findings in the same file (AC3)."""
    result = await db.execute(select(SecurityFinding).where(SecurityFinding.project_id == project_id))
    findings = list(result.scalars().all())
    conflicts = PatchGenerator()._detect_conflicts(findings)
    return [_conflict_to_response(c) for c in conflicts]


@router.patch(
    "/{project_id}/security-findings/{finding_id}/status",
    response_model=SecurityFindingResponse,
)
async def update_finding_status(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: FindingStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityFindingResponse:
    """Change a finding's triage status (acknowledge / false_positive / fixed)."""
    from app.models.security_finding import FindingStatus

    finding = await db.get(SecurityFinding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Podatność nie została znaleziona")

    finding.status = FindingStatus(payload.status.value)
    await db.commit()
    await db.refresh(finding)
    return SecurityFindingResponse.model_validate(finding)
