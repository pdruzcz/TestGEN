"""Document analysis routes for Epic 2.

Provides REST API endpoints for document analysis status and retrieval
of extracted requirements, glossary, inconsistencies, gap analysis,
traceability, and test generation results.

NOTE: Document upload is handled by ``projects.py`` route
``POST /{project_id}/upload-documents``.  The dead ``upload_document``
route that was previously here has been removed — it created SourceFile
records with non-existent model fields (``language``, ``uploaded_by_id``,
``file_type``, ``metadata``).
"""

import logging
import os
import tempfile
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db, get_tenant
from app.core.exceptions import NotFoundError
from app.models.analysis_result import AnalysisResult, AnalysisStatus, EngineMode
from app.models.source_file import SourceFile
from app.models.user import User
from app.schemas.document import (
    DocumentStructure,
)
from app.services.analysis.comparison_report import (
    generate_comparison_report,
)
from app.services.analysis.document import (
    extract_requirements,
    preprocess_document,
)
from app.services.analysis.document.classifier import (
    DocumentClassifier,
    classify_document_async,
)
from app.services.analysis.document.glossary_extractor import (
    TERM_TYPES,
    TerminologyMapper,
)
from app.services.analysis.document.glossary_extractor import (
    from_result_data as glossary_from_result_data,
)
from app.services.analysis.document.inconsistency_detector import (
    from_result_data as inconsistencies_from_result_data,
)
from app.services.analysis.document.requirement_extractor import (
    convert_to_schema,
    from_result_data,
)
from app.services.analysis.gap_analyzer import (
    from_result_data as gap_analysis_from_result_data,
)
from app.services.billing.feature_gating import require_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Pydantic models for requests/responses ────────────────────────────────


class AnalysisStatusResponse(BaseModel):
    """Status of document analysis."""

    document_id: uuid.UUID
    status: str  # 'uploaded', 'processing', 'ready', 'failed'
    progress: float
    available_results: list[str]
    error: str | None = None


class ClassificationResponse(BaseModel):
    """Document classification result (Story 2.3)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "a1b2c3d4-0000-0000-0000-000000000001",
                    "doc_type": "specyfikacja_wymagań",
                    "confidence": 100.0,
                    "source": "native",
                    "reasoning": "Dokument pasuje do typu 'specyfikacja_wymagań'. Tytuł pasuje do wzorca.",
                    "native_confidence": 100.0,
                    "llm_confidence": None,
                }
            ]
        }
    )

    document_id: uuid.UUID
    doc_type: str
    confidence: float
    source: str
    reasoning: str | None = None
    native_confidence: float | None = None
    llm_confidence: float | None = None


class RequirementResponse(BaseModel):
    """A single persisted requirement with its workflow status (Story 2.4/2.5)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "a1b2c3d4-0000-0000-0000-000000000001",
                    "req_id": "WYM-001",
                    "text": "System musi umożliwiać logowanie za pomocą adresu email i hasła.",
                    "type": "functional",
                    "priority": "critical",
                    "source_section_id": "wymagania-funkcjonalne-1",
                    "source_section_title": "Wymagania funkcjonalne",
                    "confidence": 100.0,
                    "extraction_method": "native",
                    "status": "extracted",
                    "source": "native",
                    "reasoning": None,
                }
            ]
        }
    )

    document_id: uuid.UUID
    # Nazwa pliku dokumentu źródłowego — wypełniana w widokach projektowych
    # (agregacja wielu dokumentów); per-dokument ma filename w nagłówku listy.
    document_filename: str | None = None
    req_id: str
    text: str
    type: str  # 'functional' or 'non-functional'
    priority: str | None = None
    source_section_id: str
    source_section_title: str | None = None
    confidence: float
    extraction_method: str
    status: str = "extracted"
    # Extraction origin (Story 2.5): native|llm. Independent of ``status``.
    source: str = "native"
    # Optional LLM justification (Story 2.5).
    reasoning: str | None = None


class RequirementListResponse(BaseModel):
    """List of persisted requirements for a document (Story 2.4)."""

    document_id: uuid.UUID
    filename: str
    mode: str = "native"
    total: int
    requirements: list[RequirementResponse]


class ProjectRequirementsResponse(BaseModel):
    """Agregacja wymagań ze wszystkich dokumentów projektu (widok projektu)."""

    project_id: uuid.UUID
    total: int
    documents: int
    requirements: list[RequirementResponse]


class RequirementUpdateRequest(BaseModel):
    """Mutation body for editing a requirement (Story 2.4).

    ``text`` updates the requirement description; ``status`` sets an explicit
    workflow status; otherwise an edit marks the element ``edited``.
    """

    status: str | None = None
    text: str | None = None
    priority: str | None = None


class CodeMappingResponse(BaseModel):
    """A code-entity mapping for a glossary term (Story 2.6, AC2)."""

    name: str
    type: str  # function | method | class | module
    similarity: float
    is_confirmed: bool = False


class GlossaryTermResponse(BaseModel):
    """A single persisted glossary term with code mappings (Story 2.6)."""

    document_id: uuid.UUID
    document_filename: str | None = None
    term: str
    definition: str | None = None
    occurrences_count: int = 0
    term_type: str = "business"  # domain | technical | business | acronym
    source_sections: list[dict[str, Any]] = Field(default_factory=list)
    is_verified: bool = False
    code_mappings: list[CodeMappingResponse] = Field(default_factory=list)


class GlossaryListResponse(BaseModel):
    """List of persisted glossary terms for a document (Story 2.6)."""

    document_id: uuid.UUID
    filename: str
    total: int
    terms: list[GlossaryTermResponse]


class ProjectGlossaryResponse(BaseModel):
    """Agregacja terminów glosariusza ze wszystkich dokumentów projektu."""

    project_id: uuid.UUID
    total: int
    documents: int
    terms: list[GlossaryTermResponse]


class GlossaryTermUpdateRequest(BaseModel):
    """Mutation body for editing a glossary term (Story 2.6, AC4).

    ``confirmed_mapping_ids`` flips ``code_mappings[].is_confirmed`` for the
    named entities (absent names are unconfirmed).
    """

    definition: str | None = None
    term_type: str | None = None
    is_verified: bool | None = None
    confirmed_mapping_ids: list[str] | None = None


class InconsistencyResponse(BaseModel):
    """A single persisted inconsistency with its workflow status (Story 2.7)."""

    document_id: uuid.UUID
    document_filename: str | None = None
    inconsistency_id: str
    type: str  # contradiction | terminology | missing_reference | duplicate
    severity: str  # critical | high | medium | low
    description: str
    affected_requirements: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    source_section_id: str | None = None
    status: str = "open"  # open | accepted | false_positive | fixed


class InconsistencyListResponse(BaseModel):
    """List of persisted inconsistencies for a document (Story 2.7)."""

    document_id: uuid.UUID
    filename: str
    total: int
    inconsistencies: list[InconsistencyResponse]


class ProjectInconsistenciesResponse(BaseModel):
    """Agregacja niespójności ze wszystkich dokumentów projektu."""

    project_id: uuid.UUID
    total: int
    documents: int
    inconsistencies: list[InconsistencyResponse]


class InconsistencyStatusUpdateRequest(BaseModel):
    """Mutation body for the inconsistency workflow status (Story 2.7, AC4).

    ``status`` is the only mutable field; Pydantic rejects anything outside the
    allowed set with a 422.
    """

    status: Literal["open", "accepted", "false_positive", "fixed"]


# ── Document analysis status ─────────────────────────────────────────────


@router.get("/{document_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """Get the current status of document analysis."""
    source_file = await db.get(SourceFile, document_id)
    if not source_file:
        raise NotFoundError("Document not found")

    # Map file processing status to analysis status
    file_status = source_file.processing_status.value

    # Check what analysis results are available
    available_results: list[str] = []
    progress = 0.0

    if file_status in ("ready", "uploaded"):
        # Check for completed analysis modules in AnalysisResult
        analysis_results = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.status == AnalysisStatus.COMPLETED,
            )
        )
        for ar in analysis_results.scalars().all():
            available_results.append(ar.module)
            if ar.module == "document_preprocessing":
                progress += 15
            elif ar.module == "classification":
                progress += 10
            elif ar.module == "requirements":
                progress += 25
            elif ar.module == "glossary" or ar.module == "inconsistencies":
                progress += 15
            elif ar.module == "gap_analysis":
                progress += 10
            elif ar.module == "traceability" or ar.module == "test_generation":
                progress += 5

    error = source_file.error_message if file_status == "failed" else None

    return AnalysisStatusResponse(
        document_id=document_id,
        status=file_status,
        progress=min(progress, 100.0),
        available_results=available_results,
        error=error,
    )


# ── Document re-parse (on-demand re-analysis) ──────────────────────────────


@router.post("/{document_id}/reparse", status_code=202, dependencies=[Depends(require_feature("documentation"))])
async def reparse_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Re-run document parsing (sections / requirements / glossary) on demand.

    Resets the file to ``PROCESSING``, clears any prior error and dispatches
    the existing ``parse_document_task``. No quota is consumed — document
    parsing is free, unlike ``POST /projects/{id}/analyze`` which analyses
    source code and is quota-gated. Returns 202 + ``task_id`` so the client
    can poll status exactly like after upload.
    """
    from app.models.source_file import FileCategory, FileProcessingStatus
    from app.services.task_progress_service import TaskProgressService
    from app.workers.tasks.document_tasks import parse_document_task

    source_file = await db.get(SourceFile, document_id)
    if not source_file or source_file.file_category != FileCategory.DOCUMENTATION or source_file.is_cleaned_up:
        raise NotFoundError("Document not found")

    source_file.processing_status = FileProcessingStatus.PROCESSING
    source_file.error_message = None
    await db.commit()

    task = parse_document_task.delay(str(document_id), str(tenant_id))
    TaskProgressService().init_task(task.id, str(tenant_id))

    return {
        "task_id": task.id,
        "status": "pending",
        "status_url": f"/api/v1/tasks/{task.id}",
    }


# ── Analysis results retrieval ─────────────────────────────────────────────


@router.get("/{document_id}/analysis")
async def get_document_analysis(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get complete analysis results for a document."""
    source_file = await db.get(SourceFile, document_id)
    if not source_file:
        raise NotFoundError("Document not found")

    # Check if preprocessing is complete via AnalysisResult
    prep_result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "document_preprocessing",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    if not prep_result.scalar_one_or_none():
        raise HTTPException(
            status_code=202,
            detail="Analysis not yet complete. Check status endpoint.",
        )

    # Load document structure from storage or cache
    doc = _load_document_structure(source_file, db)

    # Get analysis results based on mode
    engine_mode = get_settings().engine_mode.value
    results: dict[str, Any] = {
        "document_id": document_id,
        "filename": source_file.filename,
        "mode": engine_mode,
        "classification": None,
        "requirements": None,
        "glossary": None,
        "inconsistencies": None,
        "gap_analysis": None,
        "traceability": None,
        "test_generation": None,
    }

    # Check for completed analysis results
    ar_query = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    completed_modules = {ar.module for ar in ar_query.scalars().all()}

    # Classification
    if "classification" in completed_modules:
        class_result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.module == "classification",
            )
        )
        class_ar = class_result.scalar_one_or_none()
        if class_ar:
            results["classification"] = class_ar.result_data

    # Requirements
    if "requirements" in completed_modules:
        results["requirements"] = [
            convert_to_schema(r) | {"extraction_method": engine_mode} for r in extract_requirements(doc)
        ]

    # Glossary (read from persistence — Story 2.6 closure)
    if "glossary" in completed_modules:
        glos_result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.module == "glossary",
            )
        )
        glos_ar = glos_result.scalar_one_or_none()
        if glos_ar:
            results["glossary"] = glossary_from_result_data(glos_ar.result_data)

    # Inconsistencies (read from persistence — Story 2.7 closure)
    if "inconsistencies" in completed_modules:
        inc_result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.module == "inconsistencies",
            )
        )
        inc_ar = inc_result.scalar_one_or_none()
        if inc_ar:
            results["inconsistencies"] = inconsistencies_from_result_data(inc_ar.result_data)

    # Gap analysis (read from persistence — Story 2.8 closure)
    if "gap_analysis" in completed_modules:
        gap_result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.module == "gap_analysis",
            )
        )
        gap_ar = gap_result.scalar_one_or_none()
        if gap_ar:
            results["gap_analysis"] = gap_analysis_from_result_data(gap_ar.result_data)

    # Fallback to an all-zero summary when detection has not persisted anything
    # yet (keeps the ``gap_analysis`` key present for clients expecting it).
    if results["gap_analysis"] is None:
        results["gap_analysis"] = gap_analysis_from_result_data(None)

    # Traceability (read from persistence — Story 2.9 closure)
    if "traceability" in completed_modules:
        trace_result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.module == "traceability",
            )
        )
        trace_ar = trace_result.scalar_one_or_none()
        if trace_ar:
            # result_data is stored directly in the flat frontend shape, so it
            # is returned as-is (no summary/items deserializer needed).
            results["traceability"] = trace_ar.result_data

    # Fallback to an all-zero flat summary when traceability has not persisted
    # anything yet (keeps the ``traceability`` key present for clients).
    if results["traceability"] is None:
        results["traceability"] = {
            "document_name": source_file.filename,
            "total_requirements": 0,
            "full_coverage": 0,
            "partial_coverage": 0,
            "no_coverage": 0,
            "coverage_percentage": 0.0,
            "entries": [],
        }

    # Test generation (read from persistence — Story 2.10 closure)
    if "test_generation" in completed_modules:
        tg_result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document_id,
                AnalysisResult.module == "test_generation",
            )
        )
        tg_ar = tg_result.scalar_one_or_none()
        if tg_ar:
            # result_data is stored directly in the flat frontend shape, so it
            # is returned as-is (no deserializer needed).
            results["test_generation"] = tg_ar.result_data

    # Fallback to an all-zero flat summary when test generation has not
    # persisted anything yet (keeps the ``test_generation`` key present).
    if results["test_generation"] is None:
        results["test_generation"] = {
            "document_name": source_file.filename,
            "total_requirements": 0,
            "generated_tests": 0,
            "coverage_percentage": 0.0,
            "tests": [],
        }

    return results


# ── Document requirements (native extraction) — Story 2.4 closure ───────────


async def _get_requirements_result(
    document_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[SourceFile, AnalysisResult]:
    """Return the SourceFile and its completed requirements AnalysisResult.

    Raises ``NotFoundError`` (404) when the document is missing,
    ``HTTPException(202)`` when preprocessing is not finished, and
    ``HTTPException(202)`` when requirements extraction is not yet available.
    """
    source_file, _ = await _get_preprocessing_artifacts(document_id, db)

    req_result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "requirements",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    req_ar = req_result.scalar_one_or_none()
    if not req_ar:
        raise HTTPException(
            status_code=202,
            detail="Wymagania jeszcze niedostępne.",
        )
    return source_file, req_ar


def _requirement_response(document_id: uuid.UUID, item: dict[str, Any]) -> RequirementResponse:
    """Build a RequirementResponse from a persisted result_data element."""
    return RequirementResponse(
        document_id=document_id,
        req_id=item.get("req_id", ""),
        text=item.get("text", ""),
        type=item.get("type", "functional"),
        priority=item.get("priority"),
        source_section_id=item.get("source_section_id", ""),
        source_section_title=item.get("source_section_title"),
        confidence=float(item.get("confidence") or 0.0),
        extraction_method=item.get("extraction_method", "native"),
        status=item.get("status", "extracted"),
        source=item.get("source", "native"),
        reasoning=item.get("reasoning"),
    )


@router.get("/{document_id}/requirements", response_model=RequirementListResponse)
async def get_requirements(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequirementListResponse:
    """Get persisted requirements for a document (AC2).

    Reads the requirements persisted by the parsing task from
    ``AnalysisResult.result_data["requirements"]``. 404 when the document is
    missing, 202 when requirements are not yet available, 200 with the list and
    workflow statuses otherwise.
    """
    source_file, req_ar = await _get_requirements_result(document_id, db)
    items = from_result_data(req_ar.result_data)
    return RequirementListResponse(
        document_id=document_id,
        filename=source_file.filename,
        mode=req_ar.engine_mode.value if req_ar.engine_mode else "native",
        total=len(items),
        requirements=[_requirement_response(document_id, it) for it in items],
    )


@router.post("/{document_id}/requirements/{req_id}/accept", response_model=RequirementResponse)
async def accept_requirement(
    document_id: uuid.UUID,
    req_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequirementResponse:
    """Accept a requirement — sets its workflow status to ``accepted`` (AC3)."""
    return await _set_requirement_status(document_id, req_id, "accepted", db)


@router.post("/{document_id}/requirements/{req_id}/reject", response_model=RequirementResponse)
async def reject_requirement(
    document_id: uuid.UUID,
    req_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequirementResponse:
    """Reject a requirement — sets its workflow status to ``rejected`` (AC3)."""
    return await _set_requirement_status(document_id, req_id, "rejected", db)


@router.put("/{document_id}/requirements/{req_id}", response_model=RequirementResponse)
async def update_requirement(
    document_id: uuid.UUID,
    req_id: str,
    body: RequirementUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequirementResponse:
    """Edit a requirement — mutates text/priority and sets status (AC3).

    An explicit ``status`` (``accepted``/``rejected``/``extracted``/``edited``)
    wins; otherwise any text/priority change marks the element ``edited``.
    """
    _, req_ar = await _get_requirements_result(document_id, db)
    items = from_result_data(req_ar.result_data)

    for item in items:
        if item.get("req_id") != req_id:
            continue

        changed = False
        if body.priority is not None:
            item["priority"] = body.priority
            changed = True
        if body.text is not None:
            item["text"] = body.text
            changed = True

        if body.status in {"accepted", "rejected", "extracted", "edited"}:
            item["status"] = body.status
        elif changed:
            item["status"] = "edited"

        req_ar.result_data = {"requirements": items}
        await db.commit()
        return _requirement_response(document_id, item)

    raise NotFoundError(f"Wymaganie {req_id} nie istnieje")


async def _set_requirement_status(
    document_id: uuid.UUID,
    req_id: str,
    status: str,
    db: AsyncSession,
) -> RequirementResponse:
    """Set a single requirement's workflow status and persist it (AC3)."""
    _, req_ar = await _get_requirements_result(document_id, db)
    items = from_result_data(req_ar.result_data)

    for item in items:
        if item.get("req_id") == req_id:
            item["status"] = status
            req_ar.result_data = {"requirements": items}
            await db.commit()
            return _requirement_response(document_id, item)

    raise NotFoundError(f"Wymaganie {req_id} nie istnieje")


# ── Document glossary (native extraction) — Story 2.6 closure ──────────────


async def _get_glossary_result(
    document_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[SourceFile, AnalysisResult]:
    """Return the SourceFile and its completed glossary AnalysisResult.

    Raises ``NotFoundError`` (404) when the document is missing,
    ``HTTPException(202)`` when preprocessing is not finished, and
    ``HTTPException(202)`` when glossary extraction is not yet available.
    """
    source_file, _ = await _get_preprocessing_artifacts(document_id, db)

    glos_result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "glossary",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    glos_ar = glos_result.scalar_one_or_none()
    if not glos_ar:
        raise HTTPException(status_code=202, detail="Glosariusz jeszcze niedostępny.")
    return source_file, glos_ar


def _glossary_term_response(document_id: uuid.UUID, item: dict[str, Any]) -> GlossaryTermResponse:
    """Build a GlossaryTermResponse from a persisted result_data element."""
    return GlossaryTermResponse(
        document_id=document_id,
        term=item.get("term", ""),
        definition=item.get("definition"),
        occurrences_count=int(item.get("occurrences_count") or 0),
        term_type=item.get("term_type", "business"),
        source_sections=list(item.get("source_sections") or []),
        is_verified=bool(item.get("is_verified")),
        code_mappings=[
            CodeMappingResponse(
                name=mapping.get("name", ""),
                type=mapping.get("type", "function"),
                similarity=float(mapping.get("similarity") or 0.0),
                is_confirmed=bool(mapping.get("is_confirmed")),
            )
            for mapping in (item.get("code_mappings") or [])
        ],
    )


@router.get("/{document_id}/glossary", response_model=GlossaryListResponse)
async def get_glossary(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryListResponse:
    """Get persisted glossary terms for a document (AC4).

    Reads ``AnalysisResult.result_data["terms"]``. 404 when the document is
    missing, 202 when glossary is not yet available, 200 with the list otherwise.
    """
    source_file, glos_ar = await _get_glossary_result(document_id, db)
    items = glossary_from_result_data(glos_ar.result_data)
    return GlossaryListResponse(
        document_id=document_id,
        filename=source_file.filename,
        total=len(items),
        terms=[_glossary_term_response(document_id, it) for it in items],
    )


@router.put("/{document_id}/glossary/{term}", response_model=GlossaryTermResponse)
async def update_glossary_term(
    document_id: uuid.UUID,
    term: str,
    body: GlossaryTermUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryTermResponse:
    """Edit a glossary term — mutates definition/term_type/is_verified and
    confirms code mappings (AC4). Term match is case-insensitive."""
    _, glos_ar = await _get_glossary_result(document_id, db)
    items = glossary_from_result_data(glos_ar.result_data)

    for item in items:
        if item.get("term", "").lower() != term.lower():
            continue

        changed = False
        if body.definition is not None:
            item["definition"] = body.definition
            changed = True
        if body.term_type in TERM_TYPES:
            item["term_type"] = body.term_type
            changed = True
        if body.is_verified is not None:
            item["is_verified"] = body.is_verified
            changed = True
        if body.confirmed_mapping_ids is not None:
            confirmed = set(body.confirmed_mapping_ids)
            for mapping in item.get("code_mappings") or []:
                mapping["is_confirmed"] = mapping.get("name") in confirmed
            changed = True

        if changed:
            glos_ar.result_data = {"terms": items}
            await db.commit()
        return _glossary_term_response(document_id, item)

    raise NotFoundError(f"Termin {term} nie istnieje")


@router.post(
    "/{document_id}/glossary/map-to-code",
    response_model=GlossaryListResponse,
    dependencies=[Depends(require_feature("documentation"))],
)
async def map_glossary_to_code(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryListResponse:
    """Rebuild code mappings for every term against the project's code analysis
    (AC4, AC2). Sync in v1 (small term sets); persists ``code_mappings`` into
    result_data and returns the updated list."""
    source_file, glos_ar = await _get_glossary_result(document_id, db)
    items = glossary_from_result_data(glos_ar.result_data)

    mappings = await TerminologyMapper().map_to_code(items, source_file.project_id, db)
    for item in items:
        item["code_mappings"] = mappings.get(item.get("term", ""), [])

    glos_ar.result_data = {"terms": items}
    await db.commit()

    return GlossaryListResponse(
        document_id=document_id,
        filename=source_file.filename,
        total=len(items),
        terms=[_glossary_term_response(document_id, it) for it in items],
    )


# ── Document inconsistencies (native detection) — Story 2.7 closure ─────────


async def _get_inconsistencies_result(
    document_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[SourceFile, AnalysisResult]:
    """Return the SourceFile and its completed inconsistencies AnalysisResult.

    Raises ``NotFoundError`` (404) when the document is missing,
    ``HTTPException(202)`` when preprocessing is not finished, and
    ``HTTPException(202)`` when inconsistency detection is not yet available.
    """
    source_file, _ = await _get_preprocessing_artifacts(document_id, db)

    inc_result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "inconsistencies",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    inc_ar = inc_result.scalar_one_or_none()
    if not inc_ar:
        raise HTTPException(status_code=202, detail="Niespójności jeszcze niedostępne.")
    return source_file, inc_ar


def _inconsistency_response(document_id: uuid.UUID, item: dict[str, Any]) -> InconsistencyResponse:
    """Build an InconsistencyResponse from a persisted result_data element."""
    return InconsistencyResponse(
        document_id=document_id,
        inconsistency_id=item.get("inconsistency_id", ""),
        type=item.get("type", ""),
        severity=item.get("severity", "medium"),
        description=item.get("description", ""),
        affected_requirements=list(item.get("affected_requirements") or []),
        suggestion=item.get("suggestion"),
        source_section_id=item.get("source_section_id"),
        status=item.get("status", "open"),
    )


@router.get("/{document_id}/inconsistencies", response_model=InconsistencyListResponse)
async def get_inconsistencies(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InconsistencyListResponse:
    """Get persisted inconsistencies for a document (AC3).

    Reads ``AnalysisResult.result_data["items"]``. 404 when the document is
    missing, 202 when inconsistencies are not yet available, 200 with the list
    and workflow statuses otherwise.
    """
    source_file, inc_ar = await _get_inconsistencies_result(document_id, db)
    items = inconsistencies_from_result_data(inc_ar.result_data)
    return InconsistencyListResponse(
        document_id=document_id,
        filename=source_file.filename,
        total=len(items),
        inconsistencies=[_inconsistency_response(document_id, it) for it in items],
    )


@router.put(
    "/{document_id}/inconsistencies/{inconsistency_id}",
    response_model=InconsistencyResponse,
)
async def update_inconsistency_status(
    document_id: uuid.UUID,
    inconsistency_id: str,
    body: InconsistencyStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InconsistencyResponse:
    """Update an inconsistency's workflow status (AC4) — mutates ``status``
    (open/accepted/false_positive/fixed) in ``result_data`` and persists it."""
    _, inc_ar = await _get_inconsistencies_result(document_id, db)
    items = inconsistencies_from_result_data(inc_ar.result_data)

    for item in items:
        if item.get("inconsistency_id") != inconsistency_id:
            continue

        item["status"] = body.status
        inc_ar.result_data = {"items": items}
        await db.commit()
        return _inconsistency_response(document_id, item)

    raise NotFoundError(f"Niespójność {inconsistency_id} nie istnieje")


# ── Document sections (preprocessing) — Story 2.2 ──────────────────────────


async def _get_preprocessing_artifacts(document_id: uuid.UUID, db: AsyncSession) -> tuple[SourceFile, AnalysisResult]:
    """Return the SourceFile and its completed preprocessing AnalysisResult.

    Raises ``NotFoundError`` (404) when the document is missing and
    ``HTTPException(202)`` when preprocessing has not finished — mirroring the
    contract of ``get_document_analysis``.
    """
    source_file = await db.get(SourceFile, document_id)
    if not source_file:
        raise NotFoundError("Document not found")

    prep_result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "document_preprocessing",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    prep_ar = prep_result.scalar_one_or_none()
    if not prep_ar:
        raise HTTPException(
            status_code=202,
            detail="Analiza nieukończona — sprawdź endpoint /status.",
        )
    return source_file, prep_ar


def _preprocessing_sections(prep_ar: AnalysisResult) -> list[dict]:
    """Flat section list persisted by the preprocessing task (AC1).

    ``position``/``section_type``/``page_number`` default to sane values for
    AnalysisResults created before those fields were serialized (AC3 backfill).
    """
    data = prep_ar.result_data or {}
    flat: list[dict] = data.get("sections", []) or []
    for index, section in enumerate(flat):
        section.setdefault("position", index)
        section.setdefault("section_type", "unclassified")
        section.setdefault("page_number", None)
        section.setdefault("children", [])
    return flat


def _build_section_tree(flat: list[dict]) -> list[dict]:
    """Reconstruct a parent-child tree from the flat serialized section list."""
    by_id = {s["section_id"]: {**s, "children": []} for s in flat}
    roots: list[dict] = []
    for section in by_id.values():
        parent_id = section.get("parent_section_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(section)
        else:
            roots.append(section)
    return roots


@router.get("/{document_id}/sections")
async def get_document_sections(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get document sections reconstructed as a tree (AC1).

    Reads the sections persisted by the preprocessing task in
    ``AnalysisResult.result_data["sections"]`` and rebuilds the parent-child
    hierarchy from ``parent_section_id``.
    """
    source_file, prep_ar = await _get_preprocessing_artifacts(document_id, db)
    flat = _preprocessing_sections(prep_ar)
    tree = _build_section_tree(flat)

    return {
        "document_id": document_id,
        "filename": source_file.filename,
        "total": len(tree),
        "sections": tree,
    }


@router.get("/{document_id}/sections/{section_id}")
async def get_document_section(
    document_id: uuid.UUID,
    section_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single section by ID with its content (AC2). 404 if not found."""
    _, prep_ar = await _get_preprocessing_artifacts(document_id, db)
    flat = _preprocessing_sections(prep_ar)

    for section in flat:
        if section.get("section_id") == section_id:
            return {
                "document_id": document_id,
                "section": section,
            }

    raise NotFoundError(f"Sekcja {section_id} nie istnieje")


# ── Document classification — Story 2.3 closure ────────────────────────────


def _classification_response(document_id: uuid.UUID, data: dict[str, Any]) -> ClassificationResponse:
    """Build a ClassificationResponse from a persisted ``result_data`` dict."""
    return ClassificationResponse(
        document_id=document_id,
        doc_type=data.get("doc_type", "inny"),
        confidence=float(data.get("confidence") or 0.0),
        source=data.get("source", "native"),
        reasoning=data.get("reasoning"),
        native_confidence=data.get("native_confidence"),
        llm_confidence=data.get("llm_confidence"),
    )


@router.post(
    "/{document_id}/classify",
    response_model=ClassificationResponse,
    dependencies=[Depends(require_feature("documentation"))],
)
async def classify_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> ClassificationResponse:
    """Classify a document by the global ``engine_mode`` (AC1).

    No request body — the engine mode comes from ``Settings`` only. The result
    is upserted into ``AnalysisResult(module="classification")``.
    """
    source_file = await db.get(SourceFile, document_id)
    if not source_file:
        raise NotFoundError("Document not found")

    engine_mode = get_settings().engine_mode.value
    doc = _load_document_structure(source_file, db)
    classification = await classify_document_async(doc, engine_mode, tenant_id=tenant_id)

    result_data: dict[str, Any] = {
        "doc_type": classification.doc_type.value,
        "confidence": classification.confidence,
        "source": classification.source.value,
        "reasoning": classification.reasoning,
        "native_confidence": classification.native_confidence,
        "llm_confidence": classification.llm_confidence,
    }
    try:
        # best-effort: enrich with raw native scores for debugging/hybrid merge
        result_data["all_scores"] = DocumentClassifier()._native_scores(doc)
    except Exception:
        logger.debug("all_scores unavailable for %s", document_id, exc_info=True)

    existing = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "classification",
        )
    )
    cls_ar = existing.scalar_one_or_none()
    if cls_ar:
        cls_ar.result_data = result_data
        cls_ar.status = AnalysisStatus.COMPLETED
        cls_ar.engine_mode = EngineMode(engine_mode)
    else:
        db.add(
            AnalysisResult(
                tenant_id=tenant_id,
                project_id=source_file.project_id,
                source_file_id=document_id,
                engine_mode=EngineMode(engine_mode),
                module="classification",
                status=AnalysisStatus.COMPLETED,
                result_data=result_data,
            )
        )
    await db.commit()
    return _classification_response(document_id, result_data)


@router.get("/{document_id}/classification", response_model=ClassificationResponse)
async def get_document_classification(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassificationResponse:
    """Get the persisted document classification (AC1).

    404 when the document is missing, 202 when preprocessing or classification
    is not yet available, 200 with the classification otherwise.
    """
    await _get_preprocessing_artifacts(document_id, db)  # raises 404 / 202

    cls_result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.source_file_id == document_id,
            AnalysisResult.module == "classification",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    cls_ar = cls_result.scalar_one_or_none()
    if not cls_ar:
        raise HTTPException(status_code=202, detail="Klasyfikacja jeszcze niedostępna.")
    return _classification_response(document_id, cls_ar.result_data or {})


@router.post("/{document_id}/compare")
async def compare_analysis_modes(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Compare native vs LLM analysis results.

    The comparison is an analytical feature (native-vs-LLM coverage delta),
    independent of the configured ``engine_mode``. Requirement extraction is
    native-only today (LLM extraction is unimplemented), so both sides return
    identical results until LLM extraction lands.
    """
    source_file = await db.get(SourceFile, document_id)
    if not source_file:
        raise NotFoundError("Document not found")

    doc = _load_document_structure(source_file, db)

    # Get results for both modes (extraction is native-only today)
    native_reqs = [convert_to_schema(r) for r in extract_requirements(doc)]
    llm_reqs = [convert_to_schema(r) for r in extract_requirements(doc)]

    # Generate comparison report
    report = generate_comparison_report(
        doc,
        {"requirements": native_reqs},
        {"requirements": llm_reqs},
    )

    return {
        "document_id": document_id,
        "mode_a": "native",
        "mode_b": "llm",
        "report": report,
    }


# ── Helper functions ────────────────────────────────────────────────────────


def _load_document_structure(source_file: SourceFile, db: AsyncSession) -> DocumentStructure:
    """Load document structure from storage or AnalysisResult cache."""
    from app.core.config import get_settings
    from app.core.storage import get_minio_client
    from app.services.analysis.document import get_document_parser

    # Try to load from AnalysisResult cache first
    # (synchronous check — the caller should handle the async part)
    settings = get_settings()
    client = get_minio_client()

    try:
        response = client.get_object(settings.minio_bucket_name, source_file.storage_key)
        content = response.read()
        response.close()
        response.release_conn()
    except Exception as exc:
        logger.error("Failed to load document from MinIO: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load document") from exc

    # Parse document based on file type
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_file.filename)[1]) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parser = get_document_parser(tmp_path)
        parsed = parser.parse()
        doc = preprocess_document(parsed)
        return doc
    finally:
        os.unlink(tmp_path)
