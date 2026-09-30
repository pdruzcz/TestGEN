"""UML diagram upload service (Story 3.1).

Validates UML uploads (XMI / PlantUML), stores payloads in MinIO under
``{tenant_id}/{project_id}/uml/{uuid}_{filename}``, and records metadata in the
``uml_diagrams`` table. Tenant isolation is enforced by Postgres RLS.
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
from app.models.uml_diagram import UMLDiagram, UMLDiagramStatus, UMLFormat
from app.models.user import User
from app.services.admin.audit_service import log_action
from app.services.project.upload_service import (
    _fetch_tenant_plan,
    get_active_project,
    max_file_size_bytes_for,
)

logger = logging.getLogger(__name__)

UML_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Tier 1 — semantic/textual (Story 3.1).
        ".xmi",
        ".xml",
        ".puml",
        ".plantuml",
        # Tier 2 — visual (Story 3.1b): SVG, PDF, raster images.
        ".svg",
        ".pdf",
        ".png",
        ".jpeg",
        ".jpg",
    }
)
UML_MIME_TYPES: frozenset[str] = frozenset(
    {
        "text/xml",
        "application/xml",
        "text/plain",
        # Visual formats (Tier 2).
        "image/svg+xml",
        "application/pdf",
        "image/png",
        "image/jpeg",
    }
)
# Formats whose payload is binary — stored in MinIO and fetched at parse time,
# never utf-8-decoded into ``raw_content``.
UML_BINARY_FORMATS: frozenset[UMLFormat] = frozenset({UMLFormat.PDF, UMLFormat.RASTER})

_READ_CHUNK = 64 * 1024


@dataclass
class UMLFileAcceptance:
    diagram: UMLDiagram | None
    filename: str
    format: UMLFormat | None
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None


@dataclass
class UMLUploadOutcome:
    accepted: list[UMLFileAcceptance]
    rejected: list[UMLFileAcceptance]


def _extension_for(filename: str) -> str:
    lower = filename.lower()
    idx = lower.rfind(".")
    return lower[idx:] if idx != -1 else ""


def is_uml_extension(filename: str) -> bool:
    return _extension_for(filename) in UML_ALLOWED_EXTENSIONS


def detect_format_from_content(content: bytes) -> UMLFormat:
    """Sniff the UML format from file bytes (magic bytes + markers).

    Tier 2 binary formats are detected by magic bytes; SVG by its XML tag; the
    Tier 1 semantic formats by their usual markers.
    """
    head = content[:4096].lstrip()
    lowered = head.lower()
    # Tier 2 binary formats — magic bytes take priority (case-insensitive).
    if lowered.startswith(b"%pdf"):
        return UMLFormat.PDF
    if lowered.startswith(b"\x89png"):
        return UMLFormat.RASTER
    if head.startswith(b"\xff\xd8\xff"):
        return UMLFormat.RASTER
    # SVG (vector graphics XML) before the generic XML→XMI fallback.
    if b"<svg" in lowered:
        return UMLFormat.SVG
    # Tier 1 semantic formats.
    if b"@startuml" in lowered:
        return UMLFormat.PLANTUML
    if head.startswith(b"<?xml") or b"<xmi" in lowered or b"<xmi:xmi" in lowered:
        return UMLFormat.XMI
    return UMLFormat.XMI if head.startswith(b"<") else UMLFormat.PLANTUML


def detect_format(filename: str, content: bytes) -> UMLFormat:
    """Prefer extension, fall back to content sniffing for ambiguous .xml."""
    ext = _extension_for(filename)
    if ext in (".puml", ".plantuml"):
        return UMLFormat.PLANTUML
    if ext == ".xmi":
        return UMLFormat.XMI
    if ext == ".svg":
        return UMLFormat.SVG
    if ext == ".pdf":
        return UMLFormat.PDF
    if ext in (".png", ".jpeg", ".jpg"):
        return UMLFormat.RASTER
    # .xml is ambiguous → sniff content.
    return detect_format_from_content(content)


async def _read_and_store(
    file: UploadFile,
    *,
    bucket: str,
    storage_key: str,
    max_bytes: int,
) -> tuple[bytes, int] | None:
    """Read the upload once, returning ``(content, size)`` or ``None`` if oversized."""
    total = 0
    chunks: list[bytes] = []
    with SpooledTemporaryFile(max_size=10 * 1024 * 1024) as tmp:
        while True:
            chunk = await file.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return None
            chunks.append(chunk)
            tmp.write(chunk)
        tmp.seek(0)
        await asyncio.to_thread(upload_file, bucket, storage_key, tmp, total, file.content_type)
    return b"".join(chunks), total


async def upload_uml(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    files: list[UploadFile],
    ip_address: str | None = None,
) -> UMLUploadOutcome:
    """Validate and store UML diagrams; create a ``uml_diagrams`` row per accepted file."""
    project = await get_active_project(db, project_id)
    plan = await _fetch_tenant_plan(db, project.tenant_id)
    max_bytes = max_file_size_bytes_for(plan)
    settings = get_settings()
    bucket = settings.minio_bucket_name

    accepted: list[UMLFileAcceptance] = []
    rejected: list[UMLFileAcceptance] = []

    if not files:
        return UMLUploadOutcome(accepted=accepted, rejected=rejected)

    for file in files:
        declared = getattr(file, "size", None)
        if declared is not None and declared > max_bytes:
            raise QuotaExceededError(
                f"File size limit ({max_bytes // (1024 * 1024)}MB) exceeded for {plan.value.capitalize()} plan"
            )

    for file in files:
        filename = file.filename or "unnamed"
        if not is_uml_extension(filename):
            rejected.append(
                UMLFileAcceptance(
                    diagram=None,
                    filename=filename,
                    format=None,
                    status="rejected",
                    rejection_reason=(
                        "Nieobsługiwane rozszerzenie. Dozwolone: " + ", ".join(sorted(UML_ALLOWED_EXTENSIONS))
                    ),
                )
            )
            continue

        storage_key = f"{project.tenant_id}/{project.id}/uml/{uuid.uuid4()}_{filename}"
        stored = await _read_and_store(file, bucket=bucket, storage_key=storage_key, max_bytes=max_bytes)
        if stored is None:
            raise QuotaExceededError(
                f"File size limit ({max_bytes // (1024 * 1024)}MB) exceeded for {plan.value.capitalize()} plan"
            )
        content, size = stored
        fmt = detect_format(filename, content)

        if fmt in UML_BINARY_FORMATS:
            # PDF / raster payloads are binary — parsed from MinIO at parse time,
            # never utf-8-decoded into ``raw_content``.
            raw_text = None
        else:
            try:
                raw_text = content.decode("utf-8")
            except UnicodeDecodeError:
                raw_text = content.decode("utf-8", errors="replace")

        diagram = UMLDiagram(
            tenant_id=project.tenant_id,
            project_id=project.id,
            filename=filename,
            storage_key=storage_key,
            format=fmt,
            raw_content=raw_text,
            status=UMLDiagramStatus.PENDING,
            file_size=size,
            mime_type=file.content_type,
        )
        db.add(diagram)
        await db.flush()

        await log_action(
            db,
            tenant_id=project.tenant_id,
            user_id=actor.id,
            action="uml_diagram.uploaded",
            resource_type="uml_diagram",
            resource_id=diagram.id,
            changes={"filename": filename, "format": fmt.value, "size_bytes": size, "project_id": str(project.id)},
            ip_address=ip_address,
        )

        accepted.append(UMLFileAcceptance(diagram=diagram, filename=filename, format=fmt, status="accepted"))

    return UMLUploadOutcome(accepted=accepted, rejected=rejected)


async def list_uml_diagrams(
    db: AsyncSession,
    project_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[UMLDiagram], int]:
    """Paginated list of a project's UML diagrams."""
    await get_active_project(db, project_id)

    base_stmt = select(UMLDiagram).where(UMLDiagram.project_id == project_id)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base_stmt.order_by(UMLDiagram.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_uml_diagram(db: AsyncSession, project_id: uuid.UUID, diagram_id: uuid.UUID) -> UMLDiagram | None:
    """Fetch a single diagram scoped to the project (RLS enforces tenant)."""
    result = await db.execute(
        select(UMLDiagram).where(UMLDiagram.id == diagram_id, UMLDiagram.project_id == project_id)
    )
    return result.scalar_one_or_none()


async def get_parsed_model(db: AsyncSession, diagram_id: uuid.UUID):
    """Return the most recent parsed model for a diagram, if any."""
    from app.models.uml_diagram import ParsedUMLModel

    result = await db.execute(
        select(ParsedUMLModel)
        .where(ParsedUMLModel.diagram_id == diagram_id)
        .order_by(ParsedUMLModel.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
