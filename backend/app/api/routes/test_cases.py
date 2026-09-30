"""Test case management API routes - Story 1.31

CRUD operations for test cases with filtering, pagination, and execution tracking.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_tenant
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, set_pagination_headers
from app.models.analysis_result import AnalysisResult
from app.models.audit_log import AuditLog
from app.models.test_case import (
    TestCase,
    TestCaseExecution,
    TestCaseStatus,
    TestFramework,
    TestPriority,
    TestType,
)
from app.models.user import User
from app.schemas.test_case import (
    BulkActionResponse,
    StatusCounts,
    TestCaseBulkDeleteRequest,
    TestCaseBulkUpdateRequest,
    TestCaseCreate,
    TestCaseExecutionResponse,
    TestCaseHistoryEntry,
    TestCaseHistoryResponse,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseUpdate,
)
from app.schemas.tms_export import TmsExportRequest
from app.services.admin.audit_service import log_action
from app.services.export import (
    generic_json_service,
    testrail_csv_service,
    xray_xml_service,
)
from app.services.export.tms_common import slugify, test_case_row

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-cases", tags=["test-cases"])

# Pola edytowalne przez PUT — używane też do audytu zmian (Story 6.5, AC7)
_UPDATABLE_FIELDS: list[tuple[str, str]] = [
    ("title", "title"),
    ("description", "description"),
    ("priority", "priority"),
    ("type", "type"),
    ("framework", "framework"),
    ("test_code", "test_code"),
    ("imports", "imports"),
    ("setup_code", "setup_code"),
    ("teardown_code", "teardown_code"),
    ("preconditions", "preconditions"),
    ("steps", "steps"),
    ("expected_result", "expected_result"),
    ("test_data", "test_data"),
    ("status", "status"),
    ("tags", "tags"),
    ("metadata", "meta"),
]


def _jsonable(value) -> str | None:
    """Serializuje wartość pola do JSON-owalnego stringa na potrzeby audytu."""
    if value is None:
        return None
    if hasattr(value, "value"):  # Enum
        return str(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


@router.post("", status_code=201, response_model=TestCaseResponse)
async def create_test_case_route(
    body: TestCaseCreate,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new test case. All authenticated roles allowed."""
    test_case = TestCase(
        analysis_result_id=body.analysis_result_id,
        source_file_id=body.source_file_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        type=body.type,
        framework=body.framework,
        language=body.language,
        generation_engine=body.generation_engine,
        source_function=body.source_function,
        source_class=body.source_class,
        source_endpoint=body.source_endpoint,
        test_code=body.test_code,
        imports=body.imports,
        setup_code=body.setup_code,
        teardown_code=body.teardown_code,
        preconditions=body.preconditions,
        steps=body.steps,
        expected_result=body.expected_result,
        test_data=body.test_data,
        scenario_description=body.scenario_description,
        scenario_rationale=body.scenario_rationale,
        edge_case_description=body.edge_case_description,
        confidence_score=body.confidence_score,
        tags=body.tags,
        meta=body.metadata,
        tenant_id=tenant_id,
    )

    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)

    response.headers["Location"] = f"/api/v1/test-cases/{test_case.id}"
    return test_case


@router.get("", response_model=TestCaseListResponse)
async def list_test_cases_route(
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    project_id: uuid.UUID | None = Query(
        None,
        description=("Filter by project (via analysis_result.project_id) — bez tego endpoint listuje cały tenant"),
    ),
    analysis_result_id: uuid.UUID | None = Query(None, description="Filter by analysis result"),
    source_file_id: uuid.UUID | None = Query(None, description="Filter by source file"),
    test_type: TestType | None = Query(None, description="Filter by test type", alias="type"),
    status: TestCaseStatus | None = Query(None, description="Filter by status"),
    framework: TestFramework | None = Query(None, description="Filter by framework"),
    priority: TestPriority | None = Query(None, description="Filter by priority"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc|desc"),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List test cases for the current user's tenant. Paginated."""
    query = select(TestCase).where(TestCase.tenant_id == tenant_id)
    # Warunki filtrów współdzielone między listę a liczniki statusów —
    # inaczej status_counts (header listy) liczyłyby cały tenant podczas
    # gdy lista jest przefiltrowana po projekcie.
    count_filters = [TestCase.tenant_id == tenant_id]

    # Apply filters
    if project_id:
        # TestCase nie ma bezpośredniego project_id — relacja prowadzi przez
        # AnalysisResult (test_cases.analysis_result_id → analysis_results.project_id).
        query = query.join(AnalysisResult, TestCase.analysis_result_id == AnalysisResult.id).where(
            AnalysisResult.project_id == project_id
        )
        count_filters.append(
            TestCase.analysis_result_id.in_(select(AnalysisResult.id).where(AnalysisResult.project_id == project_id))
        )
    if analysis_result_id:
        query = query.where(TestCase.analysis_result_id == analysis_result_id)
        count_filters.append(TestCase.analysis_result_id == analysis_result_id)
    if source_file_id:
        query = query.where(TestCase.source_file_id == source_file_id)
        count_filters.append(TestCase.source_file_id == source_file_id)
    if test_type:
        query = query.where(TestCase.type == test_type)
        count_filters.append(TestCase.type == test_type)
    if status:
        query = query.where(TestCase.status == status)
        count_filters.append(TestCase.status == status)
    if framework:
        query = query.where(TestCase.framework == framework)
        count_filters.append(TestCase.framework == framework)
    if priority:
        query = query.where(TestCase.priority == priority)
        count_filters.append(TestCase.priority == priority)

    # Apply sorting
    sort_column = getattr(TestCase, sort_by, TestCase.created_at)
    query = query.order_by(sort_column.desc()) if sort_order.lower() == "desc" else query.order_by(sort_column.asc())

    # Count total + aggregate per status (single query with GROUP BY)
    count_query = select(TestCase.status, func.count(TestCase.id)).where(*count_filters).group_by(TestCase.status)
    count_result = (await db.execute(count_query)).all()
    status_map: dict[str, int] = {row[0]: row[1] for row in count_result}
    total = sum(status_map.values())

    status_counts = StatusCounts(
        ready=status_map.get("READY", 0),
        passed=status_map.get("PASSED", 0),
        failed=status_map.get("FAILED", 0),
        skipped=status_map.get("SKIPPED", 0),
        draft=status_map.get("DRAFT", 0),
        disabled=status_map.get("DISABLED", 0),
    )

    # Apply pagination
    result = await db.execute(query.offset((pagination.page - 1) * pagination.page_size).limit(pagination.page_size))
    test_cases = result.scalars().all()

    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)

    return TestCaseListResponse(
        test_cases=[TestCaseResponse.model_validate(tc) for tc in test_cases],
        total=total,
        status_counts=status_counts,
    )


@router.get("/{test_case_id}", response_model=TestCaseResponse)
async def get_test_case_route(
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a single test case by id."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    return test_case


@router.put("/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case_route(
    test_case_id: uuid.UUID,
    body: TestCaseUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update test case fields. Sets is_edited=True."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    # Update provided fields + collect before/after for audit (Story 6.5, AC7)
    changes: dict[str, dict[str, str | None]] = {}
    for schema_field, model_field in _UPDATABLE_FIELDS:
        new_value = getattr(body, schema_field)
        if new_value is None:
            continue
        old_value = getattr(test_case, model_field)
        if old_value == new_value:
            continue
        changes[schema_field] = {
            "before": _jsonable(old_value),
            "after": _jsonable(new_value),
        }
        setattr(test_case, model_field, new_value)

    # Mark as edited
    test_case.is_edited = True

    if changes:
        await log_action(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            action="test_case.update",
            resource_type="test_case",
            resource_id=test_case_id,
            changes=changes,
        )

    await db.commit()
    await db.refresh(test_case)
    return test_case


@router.delete("/{test_case_id}", status_code=204)
async def delete_test_case_route(
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a test case."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    await db.delete(test_case)
    await db.commit()


@router.patch("/{test_case_id}/status", response_model=TestCaseResponse)
async def update_test_case_status_route(
    test_case_id: uuid.UUID,
    status: TestCaseStatus = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update test case status (draft, ready, passed, failed, etc.)."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    old_status = test_case.status
    test_case.status = status
    if _jsonable(old_status) != _jsonable(status):
        await log_action(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            action="test_case.status",
            resource_type="test_case",
            resource_id=test_case_id,
            changes={"status": {"before": _jsonable(old_status), "after": _jsonable(status)}},
        )
    await db.commit()
    await db.refresh(test_case)
    return test_case


@router.post("/{test_case_id}/execute", status_code=202)
async def execute_test_case_route(
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Trigger test case execution. Returns 202 with task_id."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    # TODO: Integrate with test execution worker
    # task = execute_test_case.delay(str(test_case_id))
    # return {"task_id": task.id, "status": "pending", "status_url": f"/api/v1/tasks/{task.id}"}

    return {"message": "Test execution not yet implemented"}


@router.get("/{test_case_id}/executions", response_model=list[TestCaseExecutionResponse])
async def list_test_case_executions_route(
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get execution history for a test case."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    exec_result = await db.execute(
        select(TestCaseExecution)
        .where(TestCaseExecution.test_case_id == test_case_id)
        .order_by(TestCaseExecution.executed_at.desc())
        .limit(50)
    )
    executions = exec_result.scalars().all()

    return [TestCaseExecutionResponse.model_validate(e) for e in executions]


@router.post("/{test_case_id}/review", response_model=TestCaseResponse)
async def review_test_case_route(
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Mark test case as reviewed by current user."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise NotFoundError("Test case not found")

    test_case.reviewed_at = datetime.utcnow()
    test_case.reviewed_by = current_user.id
    await db.commit()
    await db.refresh(test_case)
    return test_case


@router.post("/bulk-update", response_model=BulkActionResponse)
async def bulk_update_test_cases_route(
    body: TestCaseBulkUpdateRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Zbiorcza zmiana statusu/priorytetu test case'ów (Story 6.5, AC5)."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id.in_(body.ids),
            TestCase.tenant_id == tenant_id,
        )
    )
    test_cases = result.scalars().all()

    affected = 0
    for test_case in test_cases:
        changes: dict[str, dict[str, str | None]] = {}
        if body.status is not None and test_case.status != body.status:
            changes["status"] = {
                "before": _jsonable(test_case.status),
                "after": _jsonable(body.status),
            }
            test_case.status = body.status
        if body.priority is not None and test_case.priority != body.priority:
            changes["priority"] = {
                "before": _jsonable(test_case.priority),
                "after": _jsonable(body.priority),
            }
            test_case.priority = body.priority
        if changes:
            await log_action(
                db,
                tenant_id=tenant_id,
                user_id=current_user.id,
                action="test_case.bulk_update",
                resource_type="test_case",
                resource_id=test_case.id,
                changes=changes,
            )
            affected += 1

    await db.commit()
    return BulkActionResponse(affected=affected)


@router.post("/bulk-delete", response_model=BulkActionResponse)
async def bulk_delete_test_cases_route(
    body: TestCaseBulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Zbiorcze usuwanie test case'ów (Story 6.5, AC5)."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id.in_(body.ids),
            TestCase.tenant_id == tenant_id,
        )
    )
    test_cases = result.scalars().all()

    for test_case in test_cases:
        await log_action(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            action="test_case.bulk_delete",
            resource_type="test_case",
            resource_id=test_case.id,
            changes={"title": {"before": test_case.title, "after": None}},
        )
        await db.delete(test_case)

    affected = len(test_cases)
    await db.commit()
    return BulkActionResponse(affected=affected)


# --- Eksport do TMS (Story 6.8, FR46) ---------------------------------------

_TMS_RENDERERS = {
    "testrail": testrail_csv_service.render,
    "xray": xray_xml_service.render,
    "json": generic_json_service.render,
}
_TMS_CONTENT_TYPES = {
    "testrail": "text/csv; charset=utf-8",
    "xray": "application/xml; charset=utf-8",
    "json": "application/json; charset=utf-8",
}
_TMS_EXTENSIONS = {"testrail": "csv", "xray": "xml", "json": "json"}


@router.post("/export")
async def export_test_cases_to_tms_route(
    body: TmsExportRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Eksport test case'ów do formatu TMS: TestRail CSV / Xray XML / JSON.

    AC6 — puste `ids` = wszystkie test case'y tenanta; w przeciwnym razie
    eksportowane są tylko wskazane (zaznaczone/przefiltrowane) rekordy.
    AC7 — nazwa pliku: `testgen_{projekt}_{data}_{format}.{ext}` w nagłówku
    Content-Disposition. Generowanie synchroniczne (małe pliki).
    """
    query = select(TestCase).where(TestCase.tenant_id == tenant_id)
    if body.ids:
        query = query.where(TestCase.id.in_(body.ids))
    result = await db.execute(query.order_by(TestCase.created_at.asc()))
    test_cases = result.scalars().all()

    project_slug = "projekt"
    if body.project_id:
        from app.models.project import Project

        project_result = await db.execute(
            select(Project).where(
                Project.id == body.project_id,
                Project.tenant_id == tenant_id,
            )
        )
        project = project_result.scalar_one_or_none()
        if project:
            project_slug = slugify(project.name)

    rows = [test_case_row(tc) for tc in test_cases]
    content = _TMS_RENDERERS[body.format](rows, body.field_mapping)

    date_part = datetime.utcnow().date().isoformat()
    filename = f"testgen_{project_slug}_{date_part}_{body.format}.{_TMS_EXTENSIONS[body.format]}"
    return Response(
        content=content,
        media_type=_TMS_CONTENT_TYPES[body.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{test_case_id}/history", response_model=TestCaseHistoryResponse)
async def get_test_case_history_route(
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Historia zmian test case'a z audit logu (Story 6.5, AC7)."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id,
            TestCase.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Test case not found")

    log_result = await db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.resource_type == "test_case",
            AuditLog.resource_id == test_case_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    rows = log_result.all()

    entries: list[TestCaseHistoryEntry] = []
    for audit_log, author_email in rows:
        details = audit_log.details or {}
        if not details:
            entries.append(
                TestCaseHistoryEntry(
                    changed_at=audit_log.created_at,
                    author=author_email,
                    action=audit_log.action,
                    field="-",
                )
            )
            continue
        for field, change in details.items():
            before = change.get("before") if isinstance(change, dict) else None
            after = change.get("after") if isinstance(change, dict) else _jsonable(change)
            entries.append(
                TestCaseHistoryEntry(
                    changed_at=audit_log.created_at,
                    author=author_email,
                    action=audit_log.action,
                    field=field,
                    old_value=before,
                    new_value=after,
                )
            )

    return TestCaseHistoryResponse(entries=entries, total=len(entries))
