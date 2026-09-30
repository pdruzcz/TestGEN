"""Gherkin/BDD feature generation + listing routes — Epic 3, Story 3.11."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.gherkin import (
    GherkinFeatureListItem,
    GherkinFeatureListResponse,
    GherkinFeatureOut,
    GherkinGenerateRequest,
    GherkinGenerateTaskResponse,
    GherkinScenarioOut,
)
from app.services.billing.feature_gating import require_feature
from app.services.test_generation.gherkin_service import get_feature, list_features
from app.workers.tasks.analysis_tasks import generate_gherkin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["gherkin"])


def _feature_to_out(feature) -> GherkinFeatureOut:
    return GherkinFeatureOut(
        id=feature.id,
        feature_name=feature.feature_name,
        feature_description=feature.feature_description,
        source_flow_id=feature.source_flow_id,
        scenarios=[GherkinScenarioOut(**s) for s in (feature.scenarios or [])],
        raw_feature=feature.raw_feature or "",
        engine_mode=feature.engine_mode,
        validation_warnings=feature.validation_warnings or [],
        status=feature.status,
        created_at=feature.created_at,
    )


@router.post(
    "/{project_id}/gherkin/generate",
    status_code=202,
    response_model=GherkinGenerateTaskResponse,
    # Gherkin powstaje z przepływów UML/GUI — obie rodziny modułów gated
    # na tym samym progu (basic, seed 7.1), więc próg „uml" jest reprezentatywny.
    dependencies=[Depends(require_feature("uml"))],
)
async def generate_gherkin_route(
    project_id: uuid.UUID,
    payload: GherkinGenerateRequest,
    current_user: User = Depends(get_current_user),
) -> GherkinGenerateTaskResponse:
    """Launch asynchronous Gherkin generation from user flows (AC-1, AC-8)."""
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.flow_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przepływu.")

    result = generate_gherkin.delay(
        str(project_id),
        str(tenant_id),
        [str(f) for f in payload.flow_ids],
        get_settings().engine_mode.value,
        payload.feature_name,
    )
    return GherkinGenerateTaskResponse(task_id=result.id, status="pending")


@router.get(
    "/{project_id}/gherkin",
    response_model=GherkinFeatureListResponse,
)
async def list_gherkin_route(
    project_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GherkinFeatureListResponse:
    """Paginated list of generated Gherkin features for the project (AC-8)."""
    features, total = await list_features(db, project_id, page=page, page_size=page_size)
    return GherkinFeatureListResponse(
        features=[GherkinFeatureListItem.model_validate(f) for f in features],
        total=total,
    )


@router.get("/{project_id}/gherkin/{feature_id}")
async def get_gherkin_route(
    project_id: uuid.UUID,
    feature_id: uuid.UUID,
    output_format: str = Query("json", alias="format", pattern="^(json|raw)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gherkin feature details; ``format=raw`` returns the plain ``.feature`` text (AC-8)."""
    feature = await get_feature(db, project_id, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Gherkin feature not found")

    if output_format == "raw":
        return PlainTextResponse(feature.raw_feature or "")
    return _feature_to_out(feature)
