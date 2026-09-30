"""Pipeline helpers — bridge between DB source files and analysis services.

Provides file retrieval from MinIO for the analysis pipeline steps.
Follows the same pattern as PreprocessingService._read_file_content().
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import download_file_bytes
from app.models.source_file import SourceFile

logger = logging.getLogger(__name__)

_MAX_CONTENT_BYTES = 1_048_576  # 1 MB — skip larger files


@dataclass
class SourceFileInfo:
    """Lightweight container for a source file ready for analysis."""

    file_path: str
    content: str
    language: str
    source_file_id: str
    file_size: int


def fetch_project_source_files(
    session: Session,
    project_id: str,
    tenant_id: str,
) -> tuple[list[SourceFileInfo], list[str]]:
    """Retrieve source files for a project from DB + MinIO.

    Returns (valid_files, warnings).
    Files > 1 MB or with unknown/None language are skipped.
    """
    settings = get_settings()
    warnings: list[str] = []

    result = session.execute(
        select(SourceFile).where(
            SourceFile.project_id == uuid.UUID(project_id),
            SourceFile.is_cleaned_up == False,  # noqa: E712
        )
    )
    source_files = result.scalars().all()

    if not source_files:
        warnings.append("No source files found for project")
        return [], warnings

    valid: list[SourceFileInfo] = []

    for sf in source_files:
        # Skip files without detected language
        lang = sf.detected_language
        if not lang or lang.lower() in ("unknown", "none"):
            warnings.append(f"Skipping {sf.filename}: unsupported language ({lang!r})")
            continue

        # Skip large files
        if sf.file_size and sf.file_size > _MAX_CONTENT_BYTES:
            warnings.append(f"Skipping {sf.filename}: too large ({sf.file_size} bytes)")
            continue

        # Download content from MinIO
        try:
            raw = download_file_bytes(settings.minio_bucket_name, sf.storage_key)
            content = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            warnings.append(f"Skipping {sf.filename}: download failed ({exc})")
            logger.warning("Failed to download %s: %s", sf.storage_key, exc)
            continue

        valid.append(
            SourceFileInfo(
                file_path=sf.original_path or sf.filename,
                content=content,
                language=lang,
                source_file_id=str(sf.id),
                file_size=sf.file_size or len(raw),
            )
        )

    logger.info(
        "project=%s — %d/%d files ready for analysis",
        project_id,
        len(valid),
        len(source_files),
    )
    return valid, warnings
