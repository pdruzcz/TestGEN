"""Source file upload service.

Validates uploads per plan-based file-size limits and accepted extensions,
stores payloads in MinIO, and records metadata in the ``source_files`` table.
Tenant isolation is enforced by Postgres RLS — the service never filters on
``tenant_id`` manually except for belt-and-braces checks against soft-deleted
projects.
"""

import asyncio
import hashlib
import io
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from tempfile import SpooledTemporaryFile

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, QuotaExceededError
from app.core.storage import download_file_bytes, upload_file
from app.models.project import Project, ProjectStatus
from app.models.source_file import DocumentFormat, FileCategory, FileProcessingStatus, SourceFile
from app.models.tenant import PlanType, Tenant
from app.models.user import User
from app.services.admin.audit_service import log_action
from app.services.project.archive_extractor import ArchiveExtractor

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Code files
        ".py",
        ".java",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".cs",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".go",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        # Archive files
        ".zip",
        ".tar.gz",
        ".tgz",
        # Config / data files (Story 1.6-zakańczenie) — e.g. composer.json
        ".json",
        # Epic 2: Documentation files
        ".pdf",
        ".docx",
        ".md",
        ".markdown",
        ".html",
        ".htm",
        ".txt",
    }
)

# Archives are expanded into child SourceFiles at upload time
# (Story 1.6-zakańczenie) — they never reach the AST pipeline as blobs.
ARCHIVE_EXTENSIONS: frozenset[str] = frozenset({".zip", ".tar.gz", ".tgz"})

# Project data / config files — available to autodetection, not AST-parsed
# (CODE) and not sent to the E2 documentation parser (DOCUMENTATION).
DATA_EXTENSIONS: frozenset[str] = frozenset({".json"})

# Read file in 64 KiB chunks — large enough for throughput, small enough to
# keep memory use bounded when hashing many uploads concurrently.
_READ_CHUNK = 64 * 1024


@dataclass
class FileAcceptance:
    """Represents the outcome of validating + storing a single uploaded file."""

    source_file: SourceFile | None
    filename: str
    file_size: int
    mime_type: str | None
    sha256_hash: str | None
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None


@dataclass
class UploadOutcome:
    accepted: list[FileAcceptance]
    rejected: list[FileAcceptance]


def _extension_for(filename: str) -> str:
    lower = filename.lower()
    # Multi-dot archive extensions take precedence over single-dot matches.
    for multi in (".tar.gz", ".tgz"):
        if lower.endswith(multi):
            return multi
    idx = lower.rfind(".")
    return lower[idx:] if idx != -1 else ""


def is_allowed_extension(filename: str) -> bool:
    return _extension_for(filename) in ALLOWED_EXTENSIONS


def _ext_to_doc_format(ext: str) -> DocumentFormat | None:
    """Convert file extension to DocumentFormat enum."""
    mapping = {
        ".pdf": DocumentFormat.PDF,
        ".docx": DocumentFormat.DOCX,
        ".md": DocumentFormat.MARKDOWN,
        ".markdown": DocumentFormat.MARKDOWN,
        ".html": DocumentFormat.HTML,
        ".htm": DocumentFormat.HTML,
        ".txt": DocumentFormat.TXT,
    }
    return mapping.get(ext)


def categorize_file(filename: str) -> tuple[FileCategory, DocumentFormat | None]:
    """Classify a file by its extension into category and document format.

    Shared between upload_service and git_service so both paths assign
    ``file_category`` and ``doc_format`` consistently.
    """
    ext = _extension_for(filename)
    doc_exts = {".pdf", ".docx", ".md", ".markdown", ".html", ".htm", ".txt"}
    if ext in doc_exts:
        return FileCategory.DOCUMENTATION, _ext_to_doc_format(ext)
    if ext in DATA_EXTENSIONS:
        return FileCategory.DATA, None
    return FileCategory.CODE, None


def max_file_size_bytes_for(plan: PlanType) -> int:
    """Rozmiar pojedynczego pliku per plan (model 3-planowy, 7.1/2b.3).

    Freemium = stary darmowy cap (100 MB), plany płatne (Basic/Premium) =
    wyższy cap (500 MB). Nazwy ustawień ``*_basic``/``*_professional``
    pozostają (kompatybilność env) — semantyka: darmowy/płatny.
    """
    settings = get_settings()
    if plan == PlanType.FREEMIUM:
        return settings.max_file_size_basic_mb * 1024 * 1024
    return settings.max_file_size_professional_mb * 1024 * 1024


@dataclass
class ArchiveExtractionOutcome:
    """Outcome of expanding one uploaded archive into child SourceFiles."""

    accepted: list[FileAcceptance]
    rejected: list[FileAcceptance]


def _archive_extractor_from_settings() -> ArchiveExtractor:
    """Build an ArchiveExtractor honouring the configured zip-bomb caps."""
    settings = get_settings()
    return ArchiveExtractor(
        max_archive_size_mb=settings.archive_max_compressed_mb,
        max_extracted_total_mb=settings.archive_max_extracted_mb,
        max_file_count=settings.archive_max_file_count,
    )


async def _persist_file_bytes(
    db: AsyncSession,
    project: Project,
    *,
    filename: str,
    original_path: str | None,
    data: bytes,
    mime_type: str | None,
) -> SourceFile | None:
    """Hash, dedupe-check and store one payload as a SourceFile.

    Returns ``None`` when an identical (sha256) active file already exists in
    the project — the partial unique index on ``(project_id, sha256_hash)``
    forbids duplicates, so callers skip instead of inserting.
    """
    sha256 = hashlib.sha256(data).hexdigest()

    existing = await db.execute(
        select(SourceFile).where(
            SourceFile.project_id == project.id,
            SourceFile.sha256_hash == sha256,
            SourceFile.is_cleaned_up.is_(False),
        )
    )
    if existing.scalar_one_or_none():
        return None

    settings = get_settings()
    bucket = settings.minio_bucket_name
    storage_key = f"{project.tenant_id}/{project.id}/{uuid.uuid4()}_{filename}"
    await asyncio.to_thread(
        upload_file,
        bucket,
        storage_key,
        io.BytesIO(data),
        len(data),
        mime_type,
    )

    file_category, doc_format = categorize_file(filename)
    source_file = SourceFile(
        tenant_id=project.tenant_id,
        project_id=project.id,
        filename=filename,
        original_path=original_path,
        storage_key=storage_key,
        file_size=len(data),
        mime_type=mime_type,
        sha256_hash=sha256,
        file_category=file_category,
        doc_format=doc_format,
        processing_status=FileProcessingStatus.UPLOADED,
    )
    db.add(source_file)
    await db.flush()
    return source_file


async def _extract_and_register_archive(
    db: AsyncSession,
    actor: User,
    project: Project,
    archive_sf: SourceFile,
    *,
    ip_address: str | None = None,
) -> ArchiveExtractionOutcome:
    """Download ``archive_sf`` from MinIO, extract it, register child SourceFiles.

    Children keep their archive-relative path in ``original_path`` so the
    AST/preprocessing pipeline sees the real project structure. Disallowed
    extensions inside the archive are skipped with a warning (the rest of the
    archive is still analysed); a zip-bomb — decompressed size or file count
    over the configured caps — rejects the archive itself.
    """
    settings = get_settings()
    accepted: list[FileAcceptance] = []
    rejected: list[FileAcceptance] = []

    try:
        archive_data = await asyncio.to_thread(
            download_file_bytes,
            settings.minio_bucket_name,
            archive_sf.storage_key,
        )
    except Exception:
        # Storage hiccup — keep the archive as an accepted (unexpanded) blob
        # rather than failing the whole upload.
        logger.exception("Archive download failed for %s; skipping extraction", archive_sf.storage_key)
        return ArchiveExtractionOutcome(accepted=accepted, rejected=rejected)

    suffix = _extension_for(archive_sf.filename) or ".zip"
    with tempfile.TemporaryDirectory(prefix="testgen-archive-") as workdir:
        archive_path = os.path.join(workdir, f"archive{suffix}")
        with open(archive_path, "wb") as f:
            f.write(archive_data)

        target_dir = os.path.join(workdir, "extracted")
        try:
            rel_paths = _archive_extractor_from_settings().extract(
                archive_path,
                target_dir,
                allowed_extensions=ALLOWED_EXTENSIONS,
            )
        except ValueError as exc:
            logger.warning("Rejecting archive %s: %s", archive_sf.filename, exc)
            archive_sf.processing_status = FileProcessingStatus.FAILED
            archive_sf.error_message = str(exc)[:1000]
            rejected.append(
                FileAcceptance(
                    source_file=archive_sf,
                    filename=archive_sf.filename,
                    file_size=archive_sf.file_size,
                    mime_type=archive_sf.mime_type,
                    sha256_hash=archive_sf.sha256_hash,
                    status="rejected",
                    rejection_reason=f"Archive extraction failed: {exc}",
                )
            )
            return ArchiveExtractionOutcome(accepted=accepted, rejected=rejected)

        for rel in rel_paths:
            try:
                file_data = (Path(target_dir) / rel).read_bytes()
            except OSError:
                logger.warning("Could not read extracted file %s", rel)
                continue

            child = await _persist_file_bytes(
                db,
                project,
                filename=os.path.basename(rel.replace("\\", "/")),
                original_path=rel,
                data=file_data,
                mime_type="application/octet-stream",
            )
            if child is None:
                continue  # duplicate content — unique index forbids re-inserting

            await log_action(
                db,
                tenant_id=project.tenant_id,
                user_id=actor.id,
                action="source_file.extracted_from_archive",
                resource_type="source_file",
                resource_id=child.id,
                changes={
                    "filename": child.filename,
                    "archive": archive_sf.filename,
                    "path": rel,
                },
                ip_address=ip_address,
            )
            accepted.append(
                FileAcceptance(
                    source_file=child,
                    filename=child.filename,
                    file_size=child.file_size,
                    mime_type=child.mime_type,
                    sha256_hash=child.sha256_hash,
                    status="accepted",
                )
            )

    return ArchiveExtractionOutcome(accepted=accepted, rejected=rejected)


async def get_active_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    """Fetch a project; raise 404 if missing/deleted/**obcy tenant**.

    HOTFIX (izolacja tenantów, 2026-09-15): jawny filtr ``tenant_id`` z
    ``db.info["tenant_scope"]`` — choke-point wszystkich uploadów i list plików
    (RLS nieskuteczne przy roli DB z BYPASSRLS/SUPERUSER). NIL/admin i
    przepływy systemowe (webhooki, taski z set_rls_context) — bez filtra.
    """
    from app.services.project.project_service import _tenant_scope

    stmt = select(Project).where(
        Project.id == project_id,
        Project.is_deleted.is_(False),
    )
    scope = _tenant_scope(db)
    if scope is not None:
        stmt = stmt.where(Project.tenant_id == scope)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found")
    return project


async def _fetch_tenant_plan(db: AsyncSession, tenant_id: uuid.UUID) -> PlanType:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError("Tenant not found")
    return tenant.plan


async def _hash_and_store_file(
    file: UploadFile,
    *,
    bucket: str,
    storage_key: str,
    max_bytes: int,
) -> tuple[int, str] | tuple[None, str]:
    """Read ``file`` once, hashing bytes and spooling to upload.

    Returns ``(file_size, sha256_hex)`` on success, or ``(None, reason)`` if the
    max size was exceeded. Files under 10 MiB stay in memory; larger payloads
    spill to a temp file to bound RAM usage.
    """
    sha = hashlib.sha256()
    total = 0

    with SpooledTemporaryFile(max_size=10 * 1024 * 1024) as tmp:
        while True:
            chunk = await file.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return None, "max_size_exceeded"
            sha.update(chunk)
            tmp.write(chunk)

        tmp.seek(0)
        await asyncio.to_thread(
            upload_file,
            bucket,
            storage_key,
            tmp,
            total,
            file.content_type,
        )

    return total, sha.hexdigest()


async def upload_files(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    files: list[UploadFile],
    ip_address: str | None = None,
) -> UploadOutcome:
    """Validate and upload source files to MinIO.

    Per AC2 the file size limit is per-plan; per AC5 unsupported extensions are
    rejected individually while valid files continue. A successful first upload
    transitions the project from ``CREATED`` to ``ACTIVE`` (AC6).
    """
    project = await get_active_project(db, project_id)
    plan = await _fetch_tenant_plan(db, project.tenant_id)
    max_bytes = max_file_size_bytes_for(plan)
    settings = get_settings()
    bucket = settings.minio_bucket_name

    accepted: list[FileAcceptance] = []
    rejected: list[FileAcceptance] = []

    if not files:
        return UploadOutcome(accepted=accepted, rejected=rejected)

    # AC2 must return 429 regardless of extension — evaluate size before touching storage.
    # Do a quick pre-check if the client supplied ``size`` via multipart header.
    for file in files:
        declared_size = getattr(file, "size", None)
        if declared_size is not None and declared_size > max_bytes:
            raise QuotaExceededError(
                f"File size limit ({max_bytes // (1024 * 1024)}MB) exceeded for {plan.value.capitalize()} plan"
            )

    for file in files:
        filename = file.filename or "unnamed"

        if not is_allowed_extension(filename):
            rejected.append(
                FileAcceptance(
                    source_file=None,
                    filename=filename,
                    file_size=0,
                    mime_type=file.content_type,
                    sha256_hash=None,
                    status="rejected",
                    rejection_reason=("Unsupported file extension. Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS))),
                )
            )
            continue

        storage_key = f"{project.tenant_id}/{project.id}/{uuid.uuid4()}_{filename}"

        size_or_none, hash_or_reason = await _hash_and_store_file(
            file,
            bucket=bucket,
            storage_key=storage_key,
            max_bytes=max_bytes,
        )

        if size_or_none is None:
            # Over-limit streamed content: translate to 429 per AC2.
            raise QuotaExceededError(
                f"File size limit ({max_bytes // (1024 * 1024)}MB) exceeded for {plan.value.capitalize()} plan"
            )

        # Story 7.8 (AC1/AC3): kumulatywny limit storage per plan — 429 z body
        # ``limit_reached`` gdy suma zajętości + nowy plik ponad features.storage_bytes.
        from app.models.usage import CounterType
        from app.services.billing.quota_service import QuotaService as BillingQuotaService

        billing_quota = BillingQuotaService(db)
        await billing_quota.enforce_quota(project.tenant_id, CounterType.STORAGE_BYTES, increment=size_or_none)

        # Duplicate detection — reject if same hash already exists in project.
        existing = await db.execute(
            select(SourceFile).where(
                SourceFile.project_id == project_id,
                SourceFile.sha256_hash == hash_or_reason,
                SourceFile.is_cleaned_up.is_(False),
            )
        )
        if existing.scalar_one_or_none():
            rejected.append(
                FileAcceptance(
                    source_file=None,
                    filename=filename,
                    file_size=size_or_none,
                    mime_type=file.content_type,
                    sha256_hash=hash_or_reason,
                    status="rejected",
                    rejection_reason="duplicate",
                )
            )
            continue

        # Determine file category and format (shared with git_service).
        file_category, doc_format = categorize_file(filename)

        source_file = SourceFile(
            tenant_id=project.tenant_id,
            project_id=project.id,
            filename=filename,
            storage_key=storage_key,
            file_size=size_or_none,
            mime_type=file.content_type,
            sha256_hash=hash_or_reason,
            file_category=file_category,
            doc_format=doc_format,
            processing_status=FileProcessingStatus.UPLOADED,
        )
        db.add(source_file)
        await db.flush()

        await log_action(
            db,
            tenant_id=project.tenant_id,
            user_id=actor.id,
            action="source_file.uploaded",
            resource_type="source_file",
            resource_id=source_file.id,
            changes={
                "filename": filename,
                "size_bytes": size_or_none,
                "project_id": str(project.id),
            },
            ip_address=ip_address,
        )

        # Story 7.8 (AC3): inkrementacja licznika storage po udanym zapisie.
        await billing_quota.increment_usage(project.tenant_id, CounterType.STORAGE_BYTES, value=size_or_none)

        archive_acceptance = FileAcceptance(
            source_file=source_file,
            filename=filename,
            file_size=size_or_none,
            mime_type=file.content_type,
            sha256_hash=hash_or_reason,
            status="accepted",
        )

        # Story 1.6-zakańczenie — archives are expanded into individual child
        # SourceFiles so the AST/preprocessing pipeline can consume their
        # contents; a zip-bomb/oversized archive is rejected outright.
        if _extension_for(filename) in ARCHIVE_EXTENSIONS:
            extraction = await _extract_and_register_archive(db, actor, project, source_file, ip_address=ip_address)
            if extraction.rejected:
                rejected.extend(extraction.rejected)
            else:
                accepted.append(archive_acceptance)
                accepted.extend(extraction.accepted)
        else:
            accepted.append(archive_acceptance)

    # AC6 — first successful upload promotes the project to ACTIVE.
    if accepted and project.status == ProjectStatus.CREATED:
        project.status = ProjectStatus.ACTIVE

    return UploadOutcome(accepted=accepted, rejected=rejected)


async def list_project_files(
    db: AsyncSession,
    project_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SourceFile], int]:
    """Return a paginated list of the project's (non-cleaned-up) source files."""
    # Validates RLS tenant ownership and soft-delete.
    await get_active_project(db, project_id)

    from sqlalchemy import func

    base_stmt = select(SourceFile).where(
        SourceFile.project_id == project_id,
        SourceFile.is_cleaned_up.is_(False),
    )
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base_stmt.order_by(SourceFile.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total
