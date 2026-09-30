"""GUI screenshot upload + analysis routes — Epic 3, Story 3.8."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.core.pagination import PaginationParams, set_pagination_headers
from app.models.user import User
from app.models.user_flow import FlowSourceType, UserFlow
from app.models.visual_regression import VisualRegressionResult
from app.schemas.gui import (
    BoundingBox,
    ComponentDeltaOut,
    DOMUploadItem,
    DOMUploadResponse,
    GUIAnalysisListResponse,
    GUIAnalysisResponse,
    GUIAnalysisSummary,
    GUIAnalyzeRequest,
    GUIAnalyzeTaskResponse,
    GUIComponentOut,
    GUIFlowReconstructionRequest,
    GUIFlowReconstructionTaskResponse,
    GUIScreenshotListResponse,
    GUIScreenshotOut,
    GUIUploadItem,
    GUIUploadResponse,
    LayoutNode,
    OCRTextBlock,
    VisualRegressionListItem,
    VisualRegressionListResponse,
    VisualRegressionRequest,
    VisualRegressionResponse,
)
from app.schemas.user_flow import FlowStepOut, UserFlowListResponse, UserFlowOut
from app.services.analysis.gui.comparison_service import list_comparisons, run_comparison
from app.services.analysis.gui.dom_upload_service import list_dom_analyses, upload_dom_sources
from app.services.analysis.gui.upload_service import (
    get_analysis_result,
    get_screenshot,
    list_screenshots,
    upload_screenshots,
)
from app.services.billing.feature_gating import require_feature
from app.services.test_generation.visual_regression_codegen import generate_visual_regression_code
from app.workers.tasks.analysis_tasks import (
    analyze_dom_source,
    analyze_gui_screenshot,
    reconstruct_gui_flows,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["gui"])


@router.post(
    "/{project_id}/gui/upload",
    status_code=202,
    response_model=GUIUploadResponse,
    dependencies=[Depends(require_feature("gui"))],
)
async def upload_gui_route(
    project_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(..., description="One or more GUI screenshot files"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GUIUploadResponse:
    """Upload GUI screenshots. Analysis is dispatched asynchronously per file."""
    outcome = await upload_screenshots(
        db,
        actor=current_user,
        project_id=project_id,
        files=files,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    accepted: list[GUIUploadItem] = []
    for item in outcome.accepted:
        screenshot = item.screenshot
        task_id: str | None = None
        if screenshot is not None:
            await db.refresh(screenshot)
            result = analyze_gui_screenshot.delay(str(screenshot.id), str(screenshot.tenant_id))
            task_id = result.id
        accepted.append(
            GUIUploadItem(
                screenshot_id=screenshot.id if screenshot else None,
                filename=item.filename,
                status=item.status,
                task_id=task_id,
            )
        )

    rejected = [
        GUIUploadItem(
            screenshot_id=None,
            filename=item.filename,
            status=item.status,
            rejection_reason=item.rejection_reason,
        )
        for item in outcome.rejected
    ]

    return GUIUploadResponse(
        project_id=project_id,
        accepted=accepted,
        rejected=rejected,
        total_accepted=len(accepted),
        total_rejected=len(rejected),
    )


@router.get(
    "/{project_id}/gui",
    response_model=GUIScreenshotListResponse,
)
async def list_gui_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GUIScreenshotListResponse:
    """Paginated list of a project's GUI screenshots."""
    screenshots, total = await list_screenshots(
        db,
        project_id=project_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)
    return GUIScreenshotListResponse(
        screenshots=[GUIScreenshotOut.model_validate(s) for s in screenshots],
        total=total,
    )


@router.post(
    "/{project_id}/gui/analyze",
    status_code=202,
    response_model=GUIAnalyzeTaskResponse,
    dependencies=[Depends(require_feature("gui"))],
)
async def analyze_gui_route(
    project_id: uuid.UUID,
    payload: GUIAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GUIAnalyzeTaskResponse:
    """Force (re)analysis of a specific screenshot. Dispatches the Celery task."""
    screenshot = await get_screenshot(db, project_id, payload.screenshot_id)
    if screenshot is None:
        raise HTTPException(status_code=404, detail="GUI screenshot not found")

    result = analyze_gui_screenshot.delay(str(screenshot.id), str(screenshot.tenant_id))
    return GUIAnalyzeTaskResponse(
        screenshot_id=screenshot.id,
        task_id=result.id,
        status="pending",
    )


@router.post(
    "/{project_id}/gui/flows",
    status_code=202,
    response_model=GUIFlowReconstructionTaskResponse,
    dependencies=[Depends(require_feature("gui"))],
)
async def reconstruct_gui_flows_route(
    project_id: uuid.UUID,
    payload: GUIFlowReconstructionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GUIFlowReconstructionTaskResponse:
    """Dispatch reconstruction of a GUI user flow from a screenshot sequence (Story 3.9)."""
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")

    screenshot_ids = [str(s) for s in payload.screenshot_ids] if payload.screenshot_ids else None
    result = reconstruct_gui_flows.delay(
        str(project_id),
        str(tenant_id),
        screenshot_ids,
        get_settings().engine_mode.value,
    )
    return GUIFlowReconstructionTaskResponse(task_id=result.id, status="pending")


def _flow_to_out(flow: UserFlow) -> UserFlowOut:
    return UserFlowOut(
        id=flow.id,
        name=flow.name,
        source_type=flow.source_type,
        source_ids=flow.source_ids,
        steps=[FlowStepOut.model_validate(s) for s in flow.flow_steps],
        status=flow.status,
        warnings=flow.warnings,
        created_at=flow.created_at,
    )


@router.get(
    "/{project_id}/gui/flows",
    response_model=UserFlowListResponse,
)
async def list_gui_flows_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFlowListResponse:
    """Paginated list of GUI-reconstructed user flows for a project (Story 3.9)."""
    base_stmt = select(UserFlow).where(
        UserFlow.project_id == project_id,
        UserFlow.source_type == FlowSourceType.GUI,
    )
    total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar() or 0
    stmt = (
        base_stmt.options(selectinload(UserFlow.flow_steps))
        .order_by(UserFlow.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    flows = (await db.execute(stmt)).scalars().all()
    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)
    return UserFlowListResponse(flows=[_flow_to_out(f) for f in flows], total=total)


@router.post(
    "/{project_id}/gui/compare",
    response_model=VisualRegressionResponse,
    dependencies=[Depends(require_feature("gui"))],
)
async def compare_gui_route(
    project_id: uuid.UUID,
    payload: VisualRegressionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VisualRegressionResponse:
    """Compare two GUI screenshots synchronously and persist the result (Story 3.10)."""
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")

    record, result, error = await run_comparison(
        db,
        project_id=project_id,
        tenant_id=tenant_id,
        baseline_id=payload.baseline_screenshot_id,
        comparison_id=payload.comparison_screenshot_id,
        pixel_threshold=payload.pixel_threshold,
    )
    if error is not None or record is None or result is None:
        raise HTTPException(status_code=404, detail=error or "Porównanie nie powiodło się.")

    test_code: str | None = None
    if payload.generate_test_code:
        test_code = generate_visual_regression_code(
            result,
            framework=payload.test_framework,
            baseline_name=str(payload.baseline_screenshot_id),
            threshold=payload.pixel_threshold,
        )

    await db.commit()

    diff_image_url = (
        f"/api/v1/projects/{project_id}/gui/comparisons/{record.id}/diff" if record.diff_image_key else None
    )
    return VisualRegressionResponse(
        id=record.id,
        baseline_screenshot_id=payload.baseline_screenshot_id,
        comparison_screenshot_id=payload.comparison_screenshot_id,
        pixel_diff_percentage=record.pixel_diff_percentage,
        status=record.status.value,
        semantic_diff=[ComponentDeltaOut(**d) for d in result.semantic_diff_payload()],
        diff_image_url=diff_image_url,
        test_code=test_code,
        warnings=result.warnings,
        created_at=record.created_at,
    )


@router.get(
    "/{project_id}/gui/comparisons",
    response_model=VisualRegressionListResponse,
)
async def list_gui_comparisons_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VisualRegressionListResponse:
    """Paginated list of stored visual-regression comparisons for a project (Story 3.10)."""
    rows, total = await list_comparisons(db, project_id, pagination.page, pagination.page_size)
    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)
    return VisualRegressionListResponse(
        items=[
            VisualRegressionListItem(
                id=r.id,
                baseline_screenshot_id=r.baseline_screenshot_id,
                comparison_screenshot_id=r.comparison_screenshot_id,
                pixel_diff_percentage=r.pixel_diff_percentage,
                status=r.status.value,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{project_id}/gui/comparisons/{comparison_id}/diff")
async def get_comparison_diff_route(
    project_id: uuid.UUID,
    comparison_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream the stored annotated diff-image of a comparison (Story 3.10)."""
    record = (
        (
            await db.execute(
                select(VisualRegressionResult).where(
                    VisualRegressionResult.id == comparison_id,
                    VisualRegressionResult.project_id == project_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if record is None or not record.diff_image_key:
        raise HTTPException(status_code=404, detail="Brak obrazu różnicy dla tego porównania.")

    import asyncio as _asyncio

    from app.core.config import get_settings
    from app.core.storage import download_file_bytes

    data = await _asyncio.to_thread(download_file_bytes, get_settings().minio_bucket_name, record.diff_image_key)
    return Response(content=data, media_type="image/png")


def _bbox_to_schema(data: dict | None) -> BoundingBox | None:
    if not data:
        return None
    return BoundingBox(
        x=data.get("x", 0),
        y=data.get("y", 0),
        width=data.get("width", 0),
        height=data.get("height", 0),
    )


def _layout_to_schema(data: dict | None) -> LayoutNode | None:
    if not data:
        return None
    return LayoutNode(
        type=data.get("type", "unknown"),
        label=data.get("label"),
        bbox=_bbox_to_schema(data.get("bbox")),
        children=[c for c in (_layout_to_schema(child) for child in data.get("children", [])) if c],
    )


@router.get(
    "/{project_id}/gui/{screenshot_id}/result",
    response_model=GUIAnalysisResponse,
)
async def get_gui_result_route(
    project_id: uuid.UUID,
    screenshot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GUIAnalysisResponse:
    """Screenshot analysis result: OCR text blocks, components and layout tree."""
    screenshot = await get_screenshot(db, project_id, screenshot_id)
    if screenshot is None:
        raise HTTPException(status_code=404, detail="GUI screenshot not found")

    analysis = await get_analysis_result(db, screenshot_id)
    if analysis is None:
        return GUIAnalysisResponse(
            screenshot_id=screenshot_id,
            status=screenshot.status,
        )

    text_blocks = [
        OCRTextBlock(
            text=tb.get("text", ""),
            bbox=_bbox_to_schema(tb.get("bbox")) or BoundingBox(x=0, y=0, width=0, height=0),
            confidence=tb.get("confidence", 0.0),
        )
        for tb in (analysis.ocr_text_blocks or [])
    ]
    components = [
        GUIComponentOut(
            id=comp.id,
            component_type=comp.component_type,
            label=comp.label,
            bbox=_bbox_to_schema(comp.bbox),
            confidence=comp.confidence,
            attributes=comp.attributes,
        )
        for comp in analysis.components
    ]

    return GUIAnalysisResponse(
        screenshot_id=screenshot_id,
        status=screenshot.status,
        ocr_text_blocks=text_blocks,
        components=components,
        layout_tree=_layout_to_schema(analysis.layout_tree),
        warnings=analysis.warnings or [],
        processing_time_ms=analysis.processing_time_ms,
    )


@router.post(
    "/{project_id}/gui/dom/upload",
    status_code=202,
    response_model=DOMUploadResponse,
    dependencies=[Depends(require_feature("gui"))],
)
async def upload_gui_dom_route(
    project_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(..., description="Jeden lub więcej plików HTML/DOM jako źródło GUI (.html/.htm)"),
    a11y: UploadFile | None = File(None, description="Opcjonalny zrzut axe-core a11y.json"),
    version_label: str | None = Form(None, description="Opcjonalny tag before/after, np. 'przed refaktoryzacją'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DOMUploadResponse:
    """Upload HTML/DOM as a GUI source (sibling of screenshots) — Story 1.51-zakańczenie A2.

    Origin-based routing: HTML entering here is analysed as GUI structure and
    feeds self-healing with real locator attributes. HTML routed as documentation
    still goes to the E2 ``HTMLParser``; HTML in a code bundle stays code.
    """
    outcome = await upload_dom_sources(
        db,
        actor=current_user,
        project_id=project_id,
        html_files=files,
        a11y_file=a11y,
        version_label=version_label,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    accepted: list[DOMUploadItem] = []
    for item in outcome.accepted:
        source = item.source_file
        task_id: str | None = None
        if source is not None:
            await db.refresh(source)
            result = analyze_dom_source.delay(
                str(source.id),
                str(source.tenant_id),
                outcome.a11y_storage_key,
                version_label,
            )
            task_id = result.id
        accepted.append(
            DOMUploadItem(
                dom_source_id=source.id if source else None,
                filename=item.filename,
                status=item.status,
                task_id=task_id,
            )
        )

    rejected = [
        DOMUploadItem(
            dom_source_id=None,
            filename=item.filename,
            status=item.status,
            rejection_reason=item.rejection_reason,
        )
        for item in outcome.rejected
    ]

    return DOMUploadResponse(
        project_id=project_id,
        accepted=accepted,
        rejected=rejected,
        a11y_accepted=outcome.a11y_storage_key is not None,
        total_accepted=len(accepted),
        total_rejected=len(rejected),
    )


@router.get(
    "/{project_id}/gui/analyses",
    response_model=GUIAnalysisListResponse,
)
async def list_gui_analyses_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GUIAnalysisListResponse:
    """Paginated GUI analysis history (screenshot + DOM) — Story 1.51-zakańczenie B1.

    Powers the healing launcher's before/after version selectors (Part B2).
    """
    analyses, total = await list_dom_analyses(db, project_id, page=pagination.page, page_size=pagination.page_size)
    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)
    return GUIAnalysisListResponse(
        analyses=[GUIAnalysisSummary(**a) for a in analyses],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
