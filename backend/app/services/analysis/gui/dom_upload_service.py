"""GUI DOM/HTML source upload service — Story 1.51-zakańczenie (FR69/FR18), Part A2.

Accepts HTML views/templates (``.html``/``.htm``) — and an optional axe-core
``a11y.json`` dump — as a **GUI source** (sibling of screenshots, FR18). Each
HTML file is stored in MinIO under ``{tenant_id}/{project_id}/gui-dom/`` and
recorded as a ``source_files`` row with ``file_category='gui_dom'`` so origin-
based routing (A1) keeps it out of the E2 documentation parser: ``.html`` routed
as *documentation* still goes to ``HTMLParser``; ``.html`` analysed as GUI enters
*only* through this channel.

The ``a11y.json`` is an auxiliary artifact: stored in MinIO and surfaced to the
analysis task via its ``storage_key`` (no ``source_files`` row) so the parser can
merge semantic ``role``/``name``. Mirrors :mod:`app.services.analysis.gui.upload_service`.
"""

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass
from io import BytesIO

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import upload_file
from app.models.source_file import FileCategory, FileProcessingStatus, SourceFile
from app.models.user import User
from app.services.admin.audit_service import log_action
from app.services.project.upload_service import get_active_project

logger = logging.getLogger(__name__)

DOM_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".html", ".htm"})
A11Y_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".json"})
DOM_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # HTML/a11y are small text payloads
_READ_CHUNK = 64 * 1024


@dataclass
class DOMSourceAcceptance:
    source_file: SourceFile | None
    filename: str
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None


@dataclass
class DOMUploadOutcome:
    accepted: list[DOMSourceAcceptance]
    rejected: list[DOMSourceAcceptance]
    a11y_storage_key: str | None = None


def _extension_for(filename: str) -> str:
    lower = filename.lower()
    idx = lower.rfind(".")
    return lower[idx:] if idx != -1 else ""


def is_dom_extension(filename: str) -> bool:
    return _extension_for(filename) in DOM_ALLOWED_EXTENSIONS


async def _read_bytes(file: UploadFile, *, max_bytes: int) -> bytes | None:
    """Read an upload fully into memory; return ``None`` if it exceeds ``max_bytes``."""
    total = bytearray()
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        total.extend(chunk)
        if len(total) > max_bytes:
            return None
    return bytes(total)


async def _store_source(
    content: bytes,
    *,
    bucket: str,
    storage_key: str,
    content_type: str | None,
) -> tuple[int, str]:
    """Upload bytes to MinIO; return ``(size, sha256_hex)``."""
    await asyncio.to_thread(upload_file, bucket, storage_key, BytesIO(content), len(content), content_type)
    return len(content), hashlib.sha256(content).hexdigest()


async def upload_dom_sources(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    html_files: list[UploadFile],
    a11y_file: UploadFile | None = None,
    version_label: str | None = None,
    ip_address: str | None = None,
) -> DOMUploadOutcome:
    """Validate and store HTML/DOM GUI sources; one ``source_files`` row per accepted file."""
    project = await get_active_project(db, project_id)
    settings = get_settings()
    bucket = settings.minio_bucket_name

    accepted: list[DOMSourceAcceptance] = []
    rejected: list[DOMSourceAcceptance] = []

    a11y_storage_key: str | None = None
    if a11y_file is not None:
        a11y_name = a11y_file.filename or "a11y.json"
        if _extension_for(a11y_name) not in A11Y_ALLOWED_EXTENSIONS:
            rejected.append(
                DOMSourceAcceptance(
                    source_file=None,
                    filename=a11y_name,
                    status="rejected",
                    rejection_reason="Plik a11y musi być w formacie JSON.",
                )
            )
        else:
            a11y_bytes = await _read_bytes(a11y_file, max_bytes=DOM_MAX_FILE_SIZE_BYTES)
            if a11y_bytes is None:
                rejected.append(
                    DOMSourceAcceptance(
                        source_file=None,
                        filename=a11y_name,
                        status="rejected",
                        rejection_reason=(f"Plik a11y przekracza limit {DOM_MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."),
                    )
                )
            else:
                a11y_storage_key = f"{project.tenant_id}/{project.id}/gui-dom/{uuid.uuid4()}_{a11y_name}"
                await _store_source(
                    a11y_bytes,
                    bucket=bucket,
                    storage_key=a11y_storage_key,
                    content_type=a11y_file.content_type,
                )

    for file in html_files:
        filename = file.filename or "unnamed"
        if not is_dom_extension(filename):
            rejected.append(
                DOMSourceAcceptance(
                    source_file=None,
                    filename=filename,
                    status="rejected",
                    rejection_reason=(
                        "Nieobsługiwany format źródła GUI. Dozwolone: " + ", ".join(sorted(DOM_ALLOWED_EXTENSIONS))
                    ),
                )
            )
            continue

        content = await _read_bytes(file, max_bytes=DOM_MAX_FILE_SIZE_BYTES)
        if content is None:
            rejected.append(
                DOMSourceAcceptance(
                    source_file=None,
                    filename=filename,
                    status="rejected",
                    rejection_reason=(f"Plik przekracza limit {DOM_MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."),
                )
            )
            continue

        storage_key = f"{project.tenant_id}/{project.id}/gui-dom/{uuid.uuid4()}_{filename}"
        size, sha256 = await _store_source(
            content, bucket=bucket, storage_key=storage_key, content_type=file.content_type
        )

        source = SourceFile(
            tenant_id=project.tenant_id,
            project_id=project.id,
            filename=filename,
            storage_key=storage_key,
            file_size=size,
            mime_type=file.content_type,
            sha256_hash=sha256,
            file_category=FileCategory.GUI_DOM,
            processing_status=FileProcessingStatus.UPLOADED,
        )
        db.add(source)
        await db.flush()

        await log_action(
            db,
            tenant_id=project.tenant_id,
            user_id=actor.id,
            action="gui_dom_source.uploaded",
            resource_type="source_file",
            resource_id=source.id,
            changes={
                "filename": filename,
                "size_bytes": size,
                "project_id": str(project.id),
                "version_label": version_label,
            },
            ip_address=ip_address,
        )

        accepted.append(DOMSourceAcceptance(source_file=source, filename=filename, status="accepted"))

    return DOMUploadOutcome(accepted=accepted, rejected=rejected, a11y_storage_key=a11y_storage_key)


async def list_dom_analyses(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Paginated list of a project's GUI analyses (screenshot + DOM), newest first.

    A project's analyses are reached via either the screenshot or the DOM source
    file, so both paths are joined (``GUIAnalysisResult`` itself has no
    ``project_id``/``tenant_id`` — isolation is enforced transitively through the
    RLS on ``gui_screenshots`` / ``source_files``). Returns one row per analysis
    with a derived ``source_label`` and a correlated ``component_count``.
    """
    from sqlalchemy import func, select

    from app.models.gui_screenshot import GUIAnalysisResult, GUIComponent, GUIScreenshot
    from app.models.source_file import SourceFile

    await get_active_project(db, project_id)

    gar = GUIAnalysisResult.__table__
    gs = GUIScreenshot.__table__.alias("gs")
    sf = SourceFile.__table__.alias("sf")
    gc = GUIComponent.__table__.alias("gc")

    project_expr = func.coalesce(gs.c.project_id, sf.c.project_id)
    base = (
        gar.outerjoin(gs, gar.c.screenshot_id == gs.c.id)
        .outerjoin(sf, gar.c.source_file_id == sf.c.id)
        .where(project_expr == project_id)
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    comp_count = (
        select(func.count())
        .select_from(gc)
        .where(gc.c.analysis_id == gar.c.id)
        .scalar_subquery()
        .label("component_count")
    )
    stmt = (
        select(
            gar.c.id.label("id"),
            gar.c.source_type.label("source_type"),
            gar.c.created_at.label("created_at"),
            gar.c.version_label.label("version_label"),
            func.coalesce(gs.c.filename, sf.c.filename).label("source_label"),
            gs.c.screen_sequence.label("screen_sequence"),
            comp_count,
        )
        .select_from(base)
        .order_by(gar.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    analyses = [
        {
            "id": r.id,
            "source_type": r.source_type,
            "created_at": r.created_at,
            "version_label": r.version_label,
            "source_label": r.source_label,
            "screen_sequence": r.screen_sequence,
            "component_count": r.component_count,
        }
        for r in rows
    ]
    return analyses, total
