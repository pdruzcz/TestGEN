"""Project management API routes — CRUD with RBAC, pagination, filters, preprocessing."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, set_pagination_headers
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.models.source_file import SourceFile
from app.models.user import User
from app.schemas.preprocessing import (
    PreprocessingReportResponse,
    SourceFileUpdate,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.source_file import SourceFileResponse
from app.services.project.preprocessing_service import PreprocessingService
from app.services.project.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from app.services.project.upload_service import get_active_project, upload_files
from app.workers.tasks.preprocessing_tasks import preprocessing_detect_language

logger = logging.getLogger(__name__)

# ── Agregacje analiz dokumentacji per projekt ──────────────────────────────
from app.api.routes.documents import (  # noqa: E402
    ProjectGlossaryResponse,
    ProjectInconsistenciesResponse,
    ProjectRequirementsResponse,
    _glossary_term_response,
    _inconsistency_response,
    _requirement_response,
)
from app.services.analysis.document.glossary_extractor import (  # noqa: E402
    from_result_data as glossary_from_result_data,
)
from app.services.analysis.document.inconsistency_detector import (  # noqa: E402
    from_result_data as inconsistencies_from_result_data,
)
from app.services.analysis.document.requirement_extractor import (  # noqa: E402
    from_result_data as requirements_from_result_data,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectResponse)
async def create_project_route(
    body: ProjectCreate,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project. All authenticated roles allowed."""
    project = await create_project(
        db,
        actor=current_user,
        name=body.name,
        description=body.description,
        language_hint=body.language_hint,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)

    response.headers["Location"] = f"/api/v1/projects/{project.id}"
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects_route(
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    status: str | None = Query(None, description="Filter by status"),
    language: str | None = Query(None, description="Filter by language_hint"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc|desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects for the current user's tenant. Paginated."""
    projects, total = await list_projects(
        db,
        actor=current_user,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
        language=language,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single project by id."""
    project = await get_project(db, actor=current_user, project_id=project_id)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project_route(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update project fields. Requires Owner or Admin role."""
    project = await update_project(
        db,
        actor=current_user,
        project_id=project_id,
        name=body.name,
        description=body.description,
        language_hint=body.language_hint,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project_route(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a project. Requires Owner or Admin role."""
    await delete_project(
        db,
        actor=current_user,
        project_id=project_id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()


# --- Preprocessing endpoints (Story 1.7) ---


@router.post("/{project_id}/preprocess", status_code=202)
async def preprocess_project_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger async preprocessing for a project. Returns 202 with task_id."""
    await get_active_project(db, project_id)

    task = preprocessing_detect_language.delay(str(project_id), str(current_user._tenant_id))
    return {"task_id": task.id, "status": "pending", "status_url": f"/api/v1/tasks/{task.id}"}


@router.get("/{project_id}/preprocessing-report", response_model=PreprocessingReportResponse)
async def get_preprocessing_report_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return cached preprocessing report for a project."""
    service = PreprocessingService()
    report = await service.get_cached_report(project_id)
    if report is None:
        raise NotFoundError("Preprocessing report not found. Run POST /preprocess first.")
    return PreprocessingReportResponse(
        project_id=report.project_id,
        languages=[{"language": ls.language, "count": ls.count, "loc": ls.loc} for ls in report.languages],
        detected_frameworks=report.detected_frameworks,
        total_loc=report.total_loc,
        unknown_files=[{"filename": uf.filename, "file_id": uf.file_id} for uf in report.unknown_files],
    )


@router.patch("/{project_id}/source-files/{file_id}", response_model=SourceFileResponse)
async def patch_source_file_route(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    body: SourceFileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually classify a source file's language/framework."""
    result = await db.execute(
        select(SourceFile).where(
            SourceFile.id == file_id,
            SourceFile.project_id == project_id,
            SourceFile.is_cleaned_up.is_(False),
        )
    )
    sf = result.scalar_one_or_none()
    if not sf:
        raise NotFoundError("Source file not found")

    if body.detected_language is not None:
        sf.detected_language = body.detected_language
        sf.requires_manual_classification = False
    if body.detected_framework is not None:
        sf.detected_framework = body.detected_framework

    await db.commit()
    await db.refresh(sf)
    return sf


# --- Epic 2: Documentation upload endpoints ---


@router.post("/{project_id}/upload-documents", status_code=202)
async def upload_documents_route(
    project_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(..., description="Documentation files (PDF, DOCX, MD, HTML, TXT)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload documentation files (PDF, DOCX, MD, HTML, TXT) to a project.

    Returns 202 Accepted with task_id for async parsing.
    """
    # Reuse existing upload service — validates extensions, stores to MinIO,
    # creates SourceFile records, logs audit, transitions project to ACTIVE.
    outcome = await upload_files(
        db,
        actor=current_user,
        project_id=project_id,
        files=files,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    if not outcome.accepted:
        raise NotFoundError("No valid documentation files provided.")

    # Trigger Celery parsing task for each accepted documentation file
    from app.services.task_progress_service import TaskProgressService
    from app.workers.tasks.document_tasks import parse_document_task

    progress_svc = TaskProgressService()
    task_ids: list[str] = []
    for item in outcome.accepted:
        if item.source_file and item.source_file.doc_format:
            task = parse_document_task.delay(
                str(item.source_file.id),
                str(current_user._tenant_id),
            )
            progress_svc.init_task(task.id, str(current_user._tenant_id))
            task_ids.append(task.id)

    primary_task_id = task_ids[0] if task_ids else ""

    return {
        "task_id": primary_task_id,
        "status": "pending",
        "status_url": f"/api/v1/tasks/{primary_task_id}" if primary_task_id else "",
        "message": f"Parsing {len(task_ids)} document(s)...",
    }


@router.get("/{project_id}/documents", response_model=list[SourceFileResponse])
async def list_documents_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documentation files for a project."""
    await get_active_project(db, project_id)

    result = await db.execute(
        select(SourceFile)
        .where(
            SourceFile.project_id == project_id,
            SourceFile.file_category == "documentation",
            SourceFile.is_cleaned_up.is_(False),
        )
        .order_by(SourceFile.created_at.desc())
    )
    documents = result.scalars().all()

    # Enrich with the latest completed classification per file (Story 2.3, AC7)
    # so the document card can show the type chip without an extra round-trip.
    classification_by_file: dict[uuid.UUID, dict] = {}
    if documents:
        file_ids = [doc.id for doc in documents]
        cls_result = await db.execute(
            select(AnalysisResult)
            .where(
                AnalysisResult.source_file_id.in_(file_ids),
                AnalysisResult.module == "classification",
                AnalysisResult.status == AnalysisStatus.COMPLETED,
            )
            .order_by(AnalysisResult.created_at.desc())
        )
        for ar in cls_result.scalars().all():
            # setdefault: rows are ordered newest-first, so keep the latest
            classification_by_file.setdefault(ar.source_file_id, ar.result_data or {})

    responses: list[SourceFileResponse] = []
    for doc in documents:
        resp = SourceFileResponse.model_validate(doc)
        cls = classification_by_file.get(doc.id)
        if cls:
            resp.doc_type = cls.get("doc_type")
            resp.classification_confidence = cls.get("confidence")
            resp.classification_justification = cls.get("reasoning")
        responses.append(resp)
    return responses


@router.get("/{project_id}/documents/{document_id}", response_model=SourceFileResponse)
async def get_document_route(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single documentation file by id."""
    await get_active_project(db, project_id)

    result = await db.execute(
        select(SourceFile).where(
            SourceFile.id == document_id,
            SourceFile.project_id == project_id,
            SourceFile.file_category == "documentation",
            SourceFile.is_cleaned_up.is_(False),
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    return SourceFileResponse.model_validate(document)


async def _project_module_results(
    db: AsyncSession, project_id: uuid.UUID, module: str
) -> list[tuple[AnalysisResult, SourceFile]]:
    """Ukończone AnalysisResult ``module`` dla dokumentacji projektu (+plik)."""
    rows = (
        await db.execute(
            select(AnalysisResult, SourceFile)
            .join(SourceFile, AnalysisResult.source_file_id == SourceFile.id)
            .where(
                SourceFile.project_id == project_id,
                SourceFile.file_category == "documentation",
                SourceFile.is_cleaned_up.is_(False),
                AnalysisResult.module == module,
                AnalysisResult.status == AnalysisStatus.COMPLETED,
            )
            .order_by(SourceFile.created_at.desc())
        )
    ).all()
    return list(rows)


@router.get("/{project_id}/requirements", response_model=ProjectRequirementsResponse)
async def get_project_requirements_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectRequirementsResponse:
    """Wymagania ze WSZYSTKICH dokumentów projektu (widok nawigacji projektu).

    Każdy element niesie ``document_id``/``document_filename`` — UI pokazuje
    dokument źródłowy. Wejście przez konkretny dokument używa per-document
    ``GET /documents/{id}/requirements``.
    """
    await get_active_project(db, project_id)
    items: list = []
    documents: set[uuid.UUID] = set()
    for ar, sf in await _project_module_results(db, project_id, "requirements"):
        for it in requirements_from_result_data(ar.result_data):
            resp = _requirement_response(sf.id, it)
            resp.document_filename = sf.filename
            items.append(resp)
        documents.add(sf.id)
    return ProjectRequirementsResponse(
        project_id=project_id,
        total=len(items),
        documents=len(documents),
        requirements=items,
    )


@router.get("/{project_id}/glossary", response_model=ProjectGlossaryResponse)
async def get_project_glossary_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectGlossaryResponse:
    """Terminy glosariusza ze wszystkich dokumentów projektu (z dokumentem źródłowym)."""
    await get_active_project(db, project_id)
    items: list = []
    documents: set[uuid.UUID] = set()
    for ar, sf in await _project_module_results(db, project_id, "glossary"):
        for it in glossary_from_result_data(ar.result_data):
            resp = _glossary_term_response(sf.id, it)
            resp.document_filename = sf.filename
            items.append(resp)
        documents.add(sf.id)
    return ProjectGlossaryResponse(
        project_id=project_id,
        total=len(items),
        documents=len(documents),
        terms=items,
    )


@router.get("/{project_id}/inconsistencies", response_model=ProjectInconsistenciesResponse)
async def get_project_inconsistencies_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectInconsistenciesResponse:
    """Niespójności ze wszystkich dokumentów projektu (z dokumentem źródłowym)."""
    await get_active_project(db, project_id)
    items: list = []
    documents: set[uuid.UUID] = set()
    for ar, sf in await _project_module_results(db, project_id, "inconsistencies"):
        for it in inconsistencies_from_result_data(ar.result_data):
            resp = _inconsistency_response(sf.id, it)
            resp.document_filename = sf.filename
            items.append(resp)
        documents.add(sf.id)
    return ProjectInconsistenciesResponse(
        project_id=project_id,
        total=len(items),
        documents=len(documents),
        inconsistencies=items,
    )
