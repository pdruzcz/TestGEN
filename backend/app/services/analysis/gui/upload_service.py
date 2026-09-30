"""GUI screenshot upload service — Story 3.8, AC1-AC2.

Validates uploaded screenshots (PNG/JPEG/BMP/TIFF/WebP, max 20MB), stores the
image bytes in MinIO under ``{tenant_id}/{project_id}/gui/{uuid}_{filename}`` and
records a ``gui_screenshots`` row per accepted file. Tenant isolation is enforced
by Postgres RLS. Mirrors the UML upload service.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import QuotaExceededError
from app.core.storage import upload_file
from app.models.gui_screenshot import GUIAnalysisStatus, GUIScreenshot
from app.models.user import User
from app.services.admin.audit_service import log_action
from app.services.project.upload_service import get_active_project

logger = logging.getLogger(__name__)

GUI_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
)
GUI_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/bmp", "image/tiff", "image/webp"}
)

# Screenshots can be large; cap at 20MB regardless of plan.
GUI_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
_READ_CHUNK = 64 * 1024


@dataclass
class GUIFileAcceptance:
    screenshot: GUIScreenshot | None
    filename: str
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None


@dataclass
class GUIUploadOutcome:
    accepted: list[GUIFileAcceptance]
    rejected: list[GUIFileAcceptance]


def _extension_for(filename: str) -> str:
    lower = filename.lower()
    idx = lower.rfind(".")
    return lower[idx:] if idx != -1 else ""


def is_gui_extension(filename: str) -> bool:
    return _extension_for(filename) in GUI_ALLOWED_EXTENSIONS


async def _read_and_store(
    file: UploadFile,
    *,
    bucket: str,
    storage_key: str,
    max_bytes: int,
) -> int | None:
    """Stream the upload to MinIO, returning the byte size or ``None`` if oversized."""
    total = 0
    with SpooledTemporaryFile(max_size=10 * 1024 * 1024) as tmp:
        while True:
            chunk = await file.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return None
            tmp.write(chunk)
        tmp.seek(0)
        await asyncio.to_thread(upload_file, bucket, storage_key, tmp, total, file.content_type)
    return total


async def upload_screenshots(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    files: list[UploadFile],
    ip_address: str | None = None,
) -> GUIUploadOutcome:
    """Validate and store GUI screenshots; create a ``gui_screenshots`` row per accepted file."""
    project = await get_active_project(db, project_id)
    settings = get_settings()
    bucket = settings.minio_bucket_name

    accepted: list[GUIFileAcceptance] = []
    rejected: list[GUIFileAcceptance] = []

    if not files:
        return GUIUploadOutcome(accepted=accepted, rejected=rejected)

    for file in files:
        declared = getattr(file, "size", None)
        if declared is not None and declared > GUI_MAX_FILE_SIZE_BYTES:
            raise QuotaExceededError(
                f"File size limit ({GUI_MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB) exceeded for screenshots"
            )

    # Continue the screen sequence from whatever already exists for the project.
    seq_stmt = select(func.coalesce(func.max(GUIScreenshot.screen_sequence), 0)).where(
        GUIScreenshot.project_id == project.id
    )
    next_sequence = ((await db.execute(seq_stmt)).scalar() or 0) + 1

    for file in files:
        filename = file.filename or "unnamed"
        if not is_gui_extension(filename):
            rejected.append(
                GUIFileAcceptance(
                    screenshot=None,
                    filename=filename,
                    status="rejected",
                    rejection_reason=(
                        "Nieobsługiwany format obrazu. Dozwolone: "
                        + ", ".join(sorted(GUI_ALLOWED_EXTENSIONS))
                    ),
                )
            )
            continue

        storage_key = f"{project.tenant_id}/{project.id}/gui/{uuid.uuid4()}_{filename}"
        size = await _read_and_store(
            file, bucket=bucket, storage_key=storage_key, max_bytes=GUI_MAX_FILE_SIZE_BYTES
        )
        if size is None:
            raise QuotaExceededError(
                f"File size limit ({GUI_MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB) exceeded for screenshots"
            )

        screenshot = GUIScreenshot(
            tenant_id=project.tenant_id,
            project_id=project.id,
            filename=filename,
            storage_key=storage_key,
            screen_sequence=next_sequence,
            status=GUIAnalysisStatus.PENDING,
            file_size=size,
            mime_type=file.content_type,
        )
        db.add(screenshot)
        await db.flush()
        next_sequence += 1

        await log_action(
            db,
            tenant_id=project.tenant_id,
            user_id=actor.id,
            action="gui_screenshot.uploaded",
            resource_type="gui_screenshot",
            resource_id=screenshot.id,
            changes={"filename": filename, "size_bytes": size, "project_id": str(project.id)},
            ip_address=ip_address,
        )

        accepted.append(
            GUIFileAcceptance(screenshot=screenshot, filename=filename, status="accepted")
        )

    return GUIUploadOutcome(accepted=accepted, rejected=rejected)


async def list_screenshots(
    db: AsyncSession,
    project_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[GUIScreenshot], int]:
    """Paginated list of a project's GUI screenshots."""
    await get_active_project(db, project_id)

    base_stmt = select(GUIScreenshot).where(GUIScreenshot.project_id == project_id)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        base_stmt.order_by(GUIScreenshot.screen_sequence.asc(), GUIScreenshot.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_screenshot(
    db: AsyncSession, project_id: uuid.UUID, screenshot_id: uuid.UUID
) -> GUIScreenshot | None:
    """Fetch a single screenshot scoped to the project (RLS enforces tenant)."""
    result = await db.execute(
        select(GUIScreenshot).where(
            GUIScreenshot.id == screenshot_id, GUIScreenshot.project_id == project_id
        )
    )
    return result.scalar_one_or_none()


async def get_analysis_result(db: AsyncSession, screenshot_id: uuid.UUID):
    """Return the analysis result + its components for a screenshot, if present."""
    from sqlalchemy.orm import selectinload

    from app.models.gui_screenshot import GUIAnalysisResult

    result = await db.execute(
        select(GUIAnalysisResult)
        .where(GUIAnalysisResult.screenshot_id == screenshot_id)
        .options(selectinload(GUIAnalysisResult.components))
        .order_by(GUIAnalysisResult.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
