"""Visual-regression comparison service — Epic 3, Story 3.10.

Bridges the pure-Python :class:`VisualRegressionEngine` with the database and
MinIO: loads two analysed screenshots (baseline + comparison) with their
detected components, decodes their images (when imaging deps are available),
runs the comparison, uploads the annotated diff-image and persists a
:class:`VisualRegressionResult`. Tenant scope is enforced by Postgres RLS.

Per AC-1 the comparison runs synchronously inside the request. Heavy imaging
dependencies are optional: when missing, the image bytes decode to ``None`` and
the engine produces a semantic-only result (no pixel diff, no diff-image).
"""

import asyncio
import io
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.storage import download_file_bytes, upload_file
from app.models.gui_screenshot import GUIAnalysisResult, GUIScreenshot
from app.models.visual_regression import VisualRegressionResult
from app.services.analysis.gui.flow_service import _component_from_row
from app.services.analysis.gui.models import DetectedComponent
from app.services.analysis.gui.orchestrator import decode_image
from app.services.analysis.gui.visual_regression import (
    VisualComparisonResult,
    VisualRegressionEngine,
)

logger = logging.getLogger(__name__)


async def _load_screenshot(
    db: AsyncSession, project_id: uuid.UUID, screenshot_id: uuid.UUID
) -> GUIScreenshot | None:
    stmt = (
        select(GUIScreenshot)
        .where(
            GUIScreenshot.id == screenshot_id,
            GUIScreenshot.project_id == project_id,
        )
        .options(
            selectinload(GUIScreenshot.analysis_result).selectinload(GUIAnalysisResult.components)
        )
    )
    return (await db.execute(stmt)).scalars().first()


def _components_of(screenshot: GUIScreenshot) -> list[DetectedComponent]:
    analysis = screenshot.analysis_result
    if analysis is None:
        return []
    return [_component_from_row(c) for c in analysis.components]


async def _decode_screenshot_image(screenshot: GUIScreenshot) -> object | None:
    """Download + decode a screenshot image, returning ``None`` on any failure."""
    try:
        data = await asyncio.to_thread(
            download_file_bytes, get_settings().minio_bucket_name, screenshot.storage_key
        )
    except Exception as exc:  # pragma: no cover - network/storage dependent
        logger.warning("Nie udało się pobrać obrazu %s: %s", screenshot.id, exc)
        return None
    image, _size, _warning = decode_image(data)
    return image


async def run_comparison(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
    baseline_id: uuid.UUID,
    comparison_id: uuid.UUID,
    pixel_threshold: float = 0.02,
) -> tuple[VisualRegressionResult | None, VisualComparisonResult | None, str | None]:
    """Run + persist a visual comparison.

    Returns ``(record, engine_result, error)``. ``error`` is a Polish message
    when a screenshot is missing; otherwise ``None`` and ``record`` is the
    persisted :class:`VisualRegressionResult`.
    """
    baseline = await _load_screenshot(db, project_id, baseline_id)
    comparison = await _load_screenshot(db, project_id, comparison_id)
    if baseline is None:
        return None, None, "Nie znaleziono screenshotu baseline."
    if comparison is None:
        return None, None, "Nie znaleziono screenshotu porównawczego."

    baseline_image = await _decode_screenshot_image(baseline)
    comparison_image = await _decode_screenshot_image(comparison)

    engine = VisualRegressionEngine(pixel_threshold=pixel_threshold)
    result = engine.compare(
        baseline_image,
        comparison_image,
        _components_of(baseline),
        _components_of(comparison),
    )

    diff_image_key: str | None = None
    if result.diff_image is not None:
        diff_image_key = f"{tenant_id}/{project_id}/diff/{baseline_id}_{comparison_id}.png"
        try:
            buffer = io.BytesIO(result.diff_image)
            await asyncio.to_thread(
                upload_file,
                get_settings().minio_bucket_name,
                diff_image_key,
                buffer,
                len(result.diff_image),
                "image/png",
            )
        except Exception as exc:  # pragma: no cover - storage dependent
            logger.warning("Nie udało się zapisać obrazu różnicy: %s", exc)
            result.warnings.append("Nie udało się zapisać obrazu różnicy do magazynu.")
            diff_image_key = None

    semantic_payload = result.semantic_diff_payload()
    record = VisualRegressionResult(
        project_id=project_id,
        tenant_id=tenant_id,
        baseline_screenshot_id=baseline_id,
        comparison_screenshot_id=comparison_id,
        pixel_diff_percentage=result.pixel_diff_percentage,
        semantic_diff=semantic_payload,
        changes=semantic_payload,
        diff_image_key=diff_image_key,
        status=result.status,
        warnings=result.warnings or None,
    )
    db.add(record)
    await db.flush()
    return record, result, None


async def list_comparisons(
    db: AsyncSession, project_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[VisualRegressionResult], int]:
    """Return a paginated list of stored comparisons for a project, newest first."""
    base_stmt = select(VisualRegressionResult).where(
        VisualRegressionResult.project_id == project_id
    )
    total = (
        await db.execute(select(func.count()).select_from(base_stmt.subquery()))
    ).scalar() or 0
    stmt = (
        base_stmt.order_by(VisualRegressionResult.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, total
