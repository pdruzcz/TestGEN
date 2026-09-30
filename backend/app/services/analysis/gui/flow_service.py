"""Persistence + loading helpers for reconstructed GUI user flows — Story 3.9.

Bridges the pure-Python :class:`GUIFlowReconstructor` with the database: loads
analysed screenshots into :class:`ScreenAnalysis` objects and persists a
:class:`FlowReconstructionResult` as a ``UserFlow`` (``source_type=gui``) plus
its ordered ``FlowStep`` rows. Tenant scope is enforced by Postgres RLS.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gui_screenshot import GUIAnalysisResult, GUIComponent, GUIScreenshot
from app.models.user_flow import FlowSourceType, FlowStatus, FlowStep, UserFlow
from app.services.analysis.gui.flow_reconstructor import (
    FlowReconstructionResult,
    ScreenAnalysis,
)
from app.services.analysis.gui.models import BBox, DetectedComponent


def _component_from_row(row: GUIComponent) -> DetectedComponent:
    bbox_data = row.bbox or {}
    bbox = BBox(
        x=bbox_data.get("x", 0),
        y=bbox_data.get("y", 0),
        width=bbox_data.get("width", 0),
        height=bbox_data.get("height", 0),
    )
    return DetectedComponent(
        component_type=row.component_type,
        bbox=bbox,
        confidence=row.confidence,
        label=row.label,
        attributes=row.attributes or {},
    )


async def load_screen_analyses(
    db: AsyncSession, project_id: uuid.UUID, screenshot_ids: list[uuid.UUID] | None = None
) -> tuple[list[ScreenAnalysis], list[str]]:
    """Load analysed screenshots of a project into reconstructor inputs.

    When ``screenshot_ids`` is given, only those screenshots are loaded (in their
    stored ``screen_sequence`` order). Screenshots without a completed analysis
    are skipped with a warning.
    """
    warnings: list[str] = []

    stmt = (
        select(GUIScreenshot)
        .where(GUIScreenshot.project_id == project_id)
        .options(selectinload(GUIScreenshot.analysis_result).selectinload(GUIAnalysisResult.components))
        .order_by(GUIScreenshot.screen_sequence)
    )
    if screenshot_ids:
        stmt = stmt.where(GUIScreenshot.id.in_(screenshot_ids))

    rows = (await db.execute(stmt)).scalars().all()

    screens: list[ScreenAnalysis] = []
    for row in rows:
        analysis = row.analysis_result
        if analysis is None:
            warnings.append(f"Pominięto ekran {row.filename}: brak wyniku analizy.")
            continue
        components = [_component_from_row(c) for c in analysis.components]
        screens.append(
            ScreenAnalysis(
                screenshot_id=str(row.id),
                sequence=row.screen_sequence,
                components=components,
                image=None,
            )
        )
    return screens, warnings


async def persist_gui_flow(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
    result: FlowReconstructionResult,
) -> UserFlow:
    """Persist a reconstructed GUI flow as a ``UserFlow`` + ``FlowStep`` rows."""
    steps_payload = [
        {
            "sequence": step.sequence,
            "action": step.action,
            "action_type": step.action_type,
            "target_element": step.target_element,
            "confidence": step.confidence,
            "source_screenshot_id": step.source_screenshot_id,
            "next_screenshot_id": step.next_screenshot_id,
        }
        for step in result.steps
    ]

    flow = UserFlow(
        project_id=project_id,
        tenant_id=tenant_id,
        source_type=FlowSourceType.GUI,
        source_ids=result.source_screenshot_ids,
        name=result.name,
        steps=steps_payload,
        status=FlowStatus.DRAFT,
        warnings=result.warnings or None,
    )
    db.add(flow)
    await db.flush()

    for step in result.steps:
        db.add(
            FlowStep(
                flow_id=flow.id,
                sequence=step.sequence,
                action=step.action,
                target_element=step.target_element,
                source_screenshot_id=uuid.UUID(step.source_screenshot_id),
                source="native",
                # GUI flows have no UML include/extend/decision semantics, but the
                # inferred action_type + confidence are useful downstream metadata
                # (Story 3-11-domknięcie, AC1 — relation_type/branch_label absent).
                meta={
                    "action_type": step.action_type,
                    "confidence": step.confidence,
                    "next_screenshot_id": step.next_screenshot_id,
                },
            )
        )
    await db.flush()
    return flow
