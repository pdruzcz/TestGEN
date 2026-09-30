"""Traceability matrix routes — Epic 3, Story 3.15.

Exposes the project-scoped traceability matrix (UML/GUI source element → user
flow → Gherkin "test" → coverage), its coverage summary, an async rebuild
trigger, and a multi-format export. CSV and JSON are produced natively; XLSX and
PDF require optional libraries (openpyxl / reportlab) and degrade gracefully with
HTTP 501 when those are not installed.
"""

import csv
import io
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.traceability import (
    TraceabilityBuildResponse,
    TraceabilityEntryOut,
    TraceabilityMatrixOut,
)
from app.services.analysis.traceability_service import TraceabilityService
from app.workers.tasks.analysis_tasks import build_traceability_matrix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["traceability"])

_EXPORT_COLUMNS = [
    "source_type",
    "source_element_type",
    "source_element_name",
    "coverage_status",
    "linked_flow_id",
    "linked_gherkin_id",
    "test_case_id",
    "code_reference",
    "code_framework",
]


@router.get(
    "/{project_id}/traceability",
    response_model=TraceabilityMatrixOut,
)
async def get_traceability_matrix(
    project_id: uuid.UUID,
    source_type: str | None = Query(None, pattern="^(uml|gui)$"),
    coverage_status: str | None = Query(None, pattern="^(covered|partial|uncovered)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceabilityMatrixOut:
    """Paginated, filterable traceability matrix plus a coverage summary (AC-1, AC-3)."""
    service = TraceabilityService(db)
    rows, total = await service.get_matrix(
        project_id,
        source_type=source_type,
        coverage_status=coverage_status,
        page=page,
        page_size=page_size,
    )
    summary = await service.get_summary(project_id)
    return TraceabilityMatrixOut(
        elements=[TraceabilityEntryOut.model_validate(r) for r in rows],
        summary=summary,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{project_id}/traceability/build",
    status_code=202,
    response_model=TraceabilityBuildResponse,
)
async def build_traceability_matrix_route(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> TraceabilityBuildResponse:
    """Trigger an asynchronous (re)build of the traceability matrix (AC-5)."""
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")

    result = build_traceability_matrix.delay(str(project_id), str(tenant_id))
    return TraceabilityBuildResponse(task_id=result.id, status="pending")


@router.get("/{project_id}/traceability/export")
async def export_traceability_matrix(
    project_id: uuid.UUID,
    export_format: str = Query("csv", alias="format", pattern="^(csv|xlsx|json|pdf)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export the full traceability matrix in the requested format (AC-6).

    CSV/JSON are native; XLSX/PDF require optional libs and return 501 if absent.
    """
    service = TraceabilityService(db)
    rows, _ = await service.get_matrix(project_id, page=1, page_size=100_000)
    records = [r.to_dict() for r in rows]
    stem = f"traceability_{project_id}"

    if export_format == "csv":
        buffer = io.StringIO()
        buffer.write("\ufeff")  # UTF-8 BOM for Excel
        writer = csv.DictWriter(
            buffer, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore", delimiter=";"
        )
        writer.writeheader()
        for rec in records:
            writer.writerow({col: rec.get(col, "") for col in _EXPORT_COLUMNS})
        data = buffer.getvalue().encode("utf-8")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'},
        )

    if export_format == "json":
        data = json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{stem}.json"'},
        )

    if export_format == "xlsx":
        data = _build_xlsx(records)
        if data is None:
            raise HTTPException(
                status_code=501,
                detail="Eksport XLSX wymaga biblioteki openpyxl, która nie jest zainstalowana.",
            )
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{stem}.xlsx"'},
        )

    # pdf
    data = _build_pdf(records)
    if data is None:
        raise HTTPException(
            status_code=501,
            detail="Eksport PDF wymaga biblioteki reportlab, która nie jest zainstalowana.",
        )
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
    )


def _build_xlsx(records: list[dict]) -> bytes | None:
    """Render the matrix to XLSX bytes, or ``None`` if openpyxl is unavailable."""
    try:
        from openpyxl import Workbook
    except ImportError:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Traceability"
    ws.append(_EXPORT_COLUMNS)
    for rec in records:
        ws.append([str(rec.get(col, "") or "") for col in _EXPORT_COLUMNS])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _build_pdf(records: list[dict]) -> bytes | None:
    """Render the matrix to a PDF table, or ``None`` if reportlab is unavailable."""
    try:
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.platypus import SimpleDocTemplate, Table
    except ImportError:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    table_data = [_EXPORT_COLUMNS]
    for rec in records:
        table_data.append([str(rec.get(col, "") or "") for col in _EXPORT_COLUMNS])
    doc.build([Table(table_data)])
    return buffer.getvalue()
