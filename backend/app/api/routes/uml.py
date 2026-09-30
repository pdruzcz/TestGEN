"""UML diagram upload + listing routes (Story 3.1)."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.core.pagination import PaginationParams, set_pagination_headers
from app.models.uml_diagram import DiagramType
from app.models.user import User
from app.schemas.uml import (
    DiagramCodeComparisonResponse,
    UMLDiagramDetailResponse,
    UMLDiagramListResponse,
    UMLDiagramResponse,
    UMLParseRequest,
    UMLParseResponse,
    UMLParseTaskResponse,
    UMLUploadItem,
    UMLUploadResponse,
)
from app.schemas.user_flow import (
    CrossAnalysisRequest,
    CrossAnalysisTaskResponse,
    FlowStepOut,
    UserFlowListResponse,
    UserFlowOut,
)
from app.services.analysis.uml.class_code_comparator import (
    DiagramCodeComparator,
    class_model_from_columns,
)
from app.services.analysis.uml.code_structure_provider import (
    LogicStructuresCodeProvider,
)
from app.services.analysis.uml.upload_service import (
    get_parsed_model,
    get_uml_diagram,
    list_uml_diagrams,
    upload_uml,
)
from app.services.analysis.uml.user_flow_repository import UserFlowRepository
from app.services.billing.feature_gating import require_feature
from app.workers.tasks.analysis_tasks import analyze_cross_diagrams
from app.workers.tasks.uml_tasks import parse_uml_diagram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["uml"])


@router.post(
    "/{project_id}/uml/upload",
    status_code=202,
    response_model=UMLUploadResponse,
    dependencies=[Depends(require_feature("uml"))],
)
async def upload_uml_route(
    project_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(..., description="One or more UML diagram files"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMLUploadResponse:
    """Upload UML diagrams (XMI / PlantUML). Async parsing is dispatched per file."""
    outcome = await upload_uml(
        db,
        actor=current_user,
        project_id=project_id,
        files=files,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    accepted: list[UMLUploadItem] = []
    for item in outcome.accepted:
        diagram = item.diagram
        task_id: str | None = None
        if diagram is not None:
            await db.refresh(diagram)
            result = parse_uml_diagram.delay(str(diagram.id), str(diagram.tenant_id))
            task_id = result.id
        accepted.append(
            UMLUploadItem(
                diagram_id=diagram.id if diagram else None,
                filename=item.filename,
                format=item.format,
                status=item.status,
                task_id=task_id,
            )
        )

    rejected = [
        UMLUploadItem(
            diagram_id=None,
            filename=item.filename,
            format=item.format,
            status=item.status,
            rejection_reason=item.rejection_reason,
        )
        for item in outcome.rejected
    ]

    return UMLUploadResponse(
        project_id=project_id,
        accepted=accepted,
        rejected=rejected,
        total_accepted=len(accepted),
        total_rejected=len(rejected),
    )


@router.post(
    "/{project_id}/uml/parse",
    status_code=202,
    response_model=UMLParseTaskResponse,
    dependencies=[Depends(require_feature("uml"))],
)
async def parse_uml_route(
    project_id: uuid.UUID,
    payload: UMLParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMLParseTaskResponse:
    """Force (re)parsing of a specific diagram. Dispatches the Celery task."""
    diagram = await get_uml_diagram(db, project_id, payload.diagram_id)
    if diagram is None:
        raise HTTPException(status_code=404, detail="UML diagram not found")

    result = parse_uml_diagram.delay(str(diagram.id), str(diagram.tenant_id))
    return UMLParseTaskResponse(
        diagram_id=diagram.id,
        task_id=result.id,
        status="parsing",
    )


@router.get(
    "/{project_id}/uml",
    response_model=UMLDiagramListResponse,
)
async def list_uml_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMLDiagramListResponse:
    """Paginated list of the project's UML diagrams."""
    diagrams, total = await list_uml_diagrams(
        db,
        project_id=project_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)

    return UMLDiagramListResponse(
        diagrams=[UMLDiagramResponse.model_validate(d) for d in diagrams],
        total=total,
    )


def _flow_to_out(flow) -> UserFlowOut:
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
    "/{project_id}/uml/flows",
    response_model=UserFlowListResponse,
)
async def list_flows_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFlowListResponse:
    """Paginated list of user flows reconstructed for the project (Story 3.7)."""
    repo = UserFlowRepository(db)
    flows, total = await repo.get_by_project(project_id, page=pagination.page, page_size=pagination.page_size)
    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)
    return UserFlowListResponse(flows=[_flow_to_out(f) for f in flows], total=total)


@router.get(
    "/{project_id}/uml/flows/{flow_id}",
    response_model=UserFlowOut,
)
async def get_flow_route(
    project_id: uuid.UUID,
    flow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFlowOut:
    """User flow details with its ordered steps (Story 3.7)."""
    repo = UserFlowRepository(db)
    flow = await repo.get_by_id(project_id, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="User flow not found")
    return _flow_to_out(flow)


@router.get(
    "/{project_id}/uml/{diagram_id}",
    response_model=UMLDiagramDetailResponse,
)
async def get_uml_route(
    project_id: uuid.UUID,
    diagram_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMLDiagramDetailResponse:
    """Diagram details plus the parsed structural model (if available)."""
    diagram = await get_uml_diagram(db, project_id, diagram_id)
    if diagram is None:
        raise HTTPException(status_code=404, detail="UML diagram not found")

    parsed = await get_parsed_model(db, diagram_id)
    parsed_response = None
    if parsed is not None:
        parsed_response = UMLParseResponse(
            diagram_id=diagram_id,
            diagram_type=parsed.model_type,
            participants=parsed.participants,
            elements=parsed.elements,
            relationships=parsed.relationships,
            fragments=parsed.fragments,
            flows=parsed.flows,
            source=parsed.source,
            confidence=parsed.confidence,
        )

    return UMLDiagramDetailResponse(
        diagram=UMLDiagramResponse.model_validate(diagram),
        parsed_model=parsed_response,
    )


@router.post(
    "/{project_id}/uml/{diagram_id}/compare-code",
    response_model=DiagramCodeComparisonResponse,
    dependencies=[Depends(require_feature("uml"))],
)
async def compare_code_route(
    project_id: uuid.UUID,
    diagram_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiagramCodeComparisonResponse:
    """Compare a parsed class diagram with the project's source code (Story 3.4).

    Code structure comes from the project's ``logic_structures`` (Epic 1 AST
    analysis) via ``LogicStructuresCodeProvider``. When the project has no code
    analysis yet, the provider yields an empty structure and every diagram class
    is reported as ``diagram_only``.
    """
    diagram = await get_uml_diagram(db, project_id, diagram_id)
    if diagram is None:
        raise HTTPException(status_code=404, detail="UML diagram not found")

    parsed = await get_parsed_model(db, diagram_id)
    if parsed is None or parsed.model_type != DiagramType.CLASS:
        raise HTTPException(status_code=400, detail="Diagram nie jest sparsowanym diagramem klas")

    class_model = class_model_from_columns(parsed.elements, parsed.relationships, parsed.fragments)
    code_provider = LogicStructuresCodeProvider(db)
    await code_provider.load(project_id)
    comparison = DiagramCodeComparator().compare(class_model, code_provider, project_id)
    return DiagramCodeComparisonResponse(
        diagram_id=diagram_id,
        matching_classes=[m.model_dump() for m in comparison.matching_classes],
        diagram_only_classes=comparison.diagram_only_classes,
        code_only_classes=comparison.code_only_classes,
        discrepancies=[d.model_dump() for d in comparison.discrepancies],
    )


@router.post(
    "/{project_id}/uml/analyze",
    status_code=202,
    response_model=CrossAnalysisTaskResponse,
    dependencies=[Depends(require_feature("uml"))],
)
async def analyze_cross_diagrams_route(
    project_id: uuid.UUID,
    payload: CrossAnalysisRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CrossAnalysisTaskResponse:
    """Launch asynchronous cross-diagram analysis (Story 3.7). Returns a task id."""
    payload = payload or CrossAnalysisRequest()
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")

    diagram_ids = [str(d) for d in payload.diagram_ids] if payload.diagram_ids else None
    result = analyze_cross_diagrams.delay(
        str(project_id),
        str(tenant_id),
        diagram_ids,
        get_settings().engine_mode.value,
    )
    return CrossAnalysisTaskResponse(task_id=result.id, status="pending")
