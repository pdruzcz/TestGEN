"""Persistence + orchestration for Gherkin features — Epic 3, Story 3.11.

Loads reconstructed :class:`UserFlow` objects, runs the deterministic native
generator (optionally enriched via the LLM Gateway) and persists the resulting
:class:`GherkinFeature` rows. Tenant isolation is enforced by Postgres RLS;
queries additionally scope by ``project_id``.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gherkin_feature import GherkinFeature, GherkinStatus
from app.models.user_flow import UserFlow
from app.services.test_generation.gherkin_generator import (
    enrich_with_llm,
    generate_native,
)


async def _load_flow(db: AsyncSession, project_id: uuid.UUID, flow_id: uuid.UUID) -> UserFlow | None:
    stmt = (
        select(UserFlow)
        .options(selectinload(UserFlow.flow_steps))
        .where(UserFlow.id == flow_id, UserFlow.project_id == project_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def generate_for_flow(
    db: AsyncSession,
    project_id: uuid.UUID,
    flow_id: uuid.UUID,
    engine_mode: str = "native",
    feature_name: str | None = None,
    llm_gateway=None,
    tenant_id=None,
) -> GherkinFeature | None:
    """Generate and persist a Gherkin feature from a single user flow.

    Returns the persisted :class:`GherkinFeature`, or ``None`` if the flow does
    not exist. The LLM enrichment (``llm``/``hybrid``) degrades gracefully to the
    native result with an appended Polish warning on any failure.
    """
    flow = await _load_flow(db, project_id, flow_id)
    if flow is None:
        return None

    feature_model, raw, warnings = generate_native([flow], feature_name)

    if engine_mode in ("llm", "hybrid") and llm_gateway is not None:
        raw, llm_warnings = await enrich_with_llm(feature_model, raw, llm_gateway, tenant_id=tenant_id)
        warnings = warnings + llm_warnings

    record = GherkinFeature(
        project_id=project_id,
        source_flow_id=flow.id,
        feature_name=feature_model.feature_name,
        feature_description=feature_model.feature_description,
        scenarios=[s.to_dict() for s in feature_model.scenarios],
        raw_feature=raw,
        engine_mode=engine_mode,
        validation_warnings=warnings,
        status=GherkinStatus.VALIDATED if not warnings else GherkinStatus.GENERATED,
    )
    db.add(record)
    await db.flush()
    return record


async def list_features(
    db: AsyncSession, project_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[GherkinFeature], int]:
    base_stmt = select(GherkinFeature).where(GherkinFeature.project_id == project_id)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        base_stmt.order_by(GherkinFeature.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_feature(
    db: AsyncSession, project_id: uuid.UUID, feature_id: uuid.UUID
) -> GherkinFeature | None:
    stmt = select(GherkinFeature).where(
        GherkinFeature.id == feature_id, GherkinFeature.project_id == project_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()
