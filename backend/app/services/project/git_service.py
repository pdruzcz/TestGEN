"""Git repository connector.

Performs a shallow clone over HTTPS into a temporary directory, indexes the
files with allowed extensions, uploads the payloads to MinIO and records
``source_files`` metadata. Tokens (if provided) are injected into the clone
URL and **never** logged; stderr from git is scrubbed before being surfaced
to users.

The service is kept backend-only and synchronous from the caller's point of
view — subprocess work is awaited via ``asyncio.create_subprocess_exec``.
"""

import asyncio
import hashlib
import io
import logging
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.storage import upload_file
from app.models.project import Project, ProjectStatus
from app.models.source_file import FileProcessingStatus, SourceFile
from app.models.user import User
from app.schemas.source_file import ALLOWED_GIT_HOSTS
from app.services.admin.audit_service import log_action
from app.services.project.upload_service import (
    ALLOWED_EXTENSIONS,
    ARCHIVE_EXTENSIONS,
    _archive_extractor_from_settings,
    _extension_for,
    _persist_file_bytes,
    categorize_file,
    get_active_project,
)

logger = logging.getLogger(__name__)

# Sanitize embedded tokens (HTTP basic-auth form) before echoing git output.
_TOKEN_IN_URL = re.compile(r"https://[^/\s@]+@")
_MAX_TRACKED_SIZE = 5 * 1024 * 1024  # skip monster files from a clone (5MB hard cap)


@dataclass
class GitConnectOutcome:
    files_indexed: int
    duplicates_skipped: int
    message: str


def _validate_git_url(repo_url: str, extra_allowed_hosts: set[str] | None = None) -> None:
    """Dopuszcza wyłącznie HTTPS i znane hosty.

    ``extra_allowed_hosts`` obsługuje self-hosted GitLaba (Story 8.2): host
    instancji jest znany dopiero z konfiguracji integracji, więc nie da się
    go trzymać w stałej whiteliście.
    """
    if not repo_url.startswith("https://"):
        raise ValidationError("Only HTTPS repository URLs are supported")
    host = urlparse(repo_url).hostname
    allowed = ALLOWED_GIT_HOSTS | (extra_allowed_hosts or set())
    if host not in allowed:
        raise ValidationError("Unsupported Git provider. Allowed: " + ", ".join(sorted(allowed)))


def _sanitize_git_output(message: str) -> str:
    return _TOKEN_IN_URL.sub("https://***@", message)


def _build_clone_url(repo_url: str, auth_token: str | None, auth_scheme: str | None = None) -> str:
    """Wstrzykuje token do URL klonowania w formie wymaganej przez hosta.

    ``auth_scheme`` podaje wywołujący, gdy hosta nie da się rozpoznać po
    domenie — tak jest przy self-hosted GitLabie (Story 8.2), który również
    wymaga prefiksu ``oauth2:``.
    """
    if not auth_token:
        return repo_url
    host = urlparse(repo_url).hostname or ""
    if auth_scheme:
        user_info = f"{auth_scheme}:{auth_token}"
    # Bitbucket app passwords require x-token-auth:<token>@
    elif host == "bitbucket.org":
        user_info = f"x-token-auth:{auth_token}"
    # GitLab personal access tokens work with oauth2:<token>@
    elif host == "gitlab.com":
        user_info = f"oauth2:{auth_token}"
    else:
        user_info = auth_token
    return repo_url.replace("https://", f"https://{user_info}@", 1)


async def shallow_clone(
    repo_url: str,
    branch: str,
    auth_token: str | None,
    auth_scheme: str | None = None,
) -> str:
    """Clone ``repo_url`` (shallow, single branch) into a fresh temp directory.

    Returns the absolute path of the temporary directory. Callers are
    responsible for cleaning it up; ``connect_repo`` does that inside a
    ``try/finally``.
    """
    settings = get_settings()
    tmp_dir = tempfile.mkdtemp(prefix="testgen-clone-")
    clone_url = _build_clone_url(repo_url, auth_token, auth_scheme)
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--branch",
            branch,
            clone_url,
            tmp_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.git_clone_timeout_seconds)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValidationError(f"Git clone timed out after {settings.git_clone_timeout_seconds}s") from exc

        if proc.returncode != 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            reason = _sanitize_git_output(stderr.decode(errors="replace").strip())
            raise ValidationError(f"Git clone failed: {reason or 'unknown error'}")
    except ValidationError:
        raise
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValidationError(f"Git clone error: {_sanitize_git_output(str(exc))}") from exc
    return tmp_dir


def _iter_source_files(repo_dir: Path):
    """Yield ``(abs_path, relative_path)`` for every supported file under ``repo_dir``.

    Skips the ``.git`` directory and any path with a disallowed extension.
    """
    for root, dirs, files in os.walk(repo_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        for name in files:
            abs_path = Path(root) / name
            rel_path = abs_path.relative_to(repo_dir).as_posix()
            if _extension_for(name) not in ALLOWED_EXTENSIONS:
                continue
            yield abs_path, rel_path


async def _extract_repo_archive(
    db: AsyncSession,
    project: Project,
    archive_abs: Path,
    archive_rel: str,
) -> tuple[int, int]:
    """Extract one archive found in a clone into child SourceFiles.

    Story 1.6-zakańczenie — archives committed to a repo are unpacked and their
    contents indexed (archive-relative paths preserved in ``original_path`` so
    config files like ``composer.json`` still land where FrameworkDetector
    looks for them), instead of storing one opaque blob no parser consumes.

    Returns ``(stored, duplicates_skipped)``. A zip-bomb or oversized archive
    is skipped with a warning — the rest of the repo is still indexed.
    """
    stored = 0
    duplicates = 0
    with tempfile.TemporaryDirectory(prefix="testgen-repo-archive-") as target_dir:
        try:
            rel_paths = _archive_extractor_from_settings().extract(
                str(archive_abs), target_dir, allowed_extensions=ALLOWED_EXTENSIONS
            )
        except ValueError as exc:
            logger.warning("Skipping archive %s from repo: %s", archive_rel, exc)
            return 0, 0
        for rel in rel_paths:
            try:
                data = (Path(target_dir) / rel).read_bytes()
            except OSError:
                logger.warning("Could not read %s from archive %s", rel, archive_rel)
                continue
            source_file = await _persist_file_bytes(
                db,
                project,
                filename=os.path.basename(rel.replace("\\", "/")),
                original_path=rel,
                data=data,
                mime_type="application/octet-stream",
            )
            if source_file is None:
                duplicates += 1
            else:
                stored += 1
    return stored, duplicates


async def connect_repo(
    db: AsyncSession,
    actor: User,
    project_id: uuid.UUID,
    repo_url: str,
    branch: str = "main",
    auth_token: str | None = None,
    ip_address: str | None = None,
    extra_allowed_hosts: set[str] | None = None,
    auth_scheme: str | None = None,
) -> GitConnectOutcome:
    """Clone ``repo_url`` and register every supported file as a ``SourceFile``."""
    _validate_git_url(repo_url, extra_allowed_hosts)
    project = await get_active_project(db, project_id)

    settings = get_settings()
    bucket = settings.minio_bucket_name

    tmp_dir = await shallow_clone(repo_url, branch, auth_token, auth_scheme)
    files_indexed = 0
    duplicates_skipped = 0
    try:
        repo_dir = Path(tmp_dir)
        for abs_path, rel_path in _iter_source_files(repo_dir):
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            if size > _MAX_TRACKED_SIZE:
                logger.info("Skipping %s (%d bytes) — exceeds per-file cap", rel_path, size)
                continue

            if _extension_for(abs_path.name) in ARCHIVE_EXTENSIONS:
                # Story 1.6-zakańczenie — unpack archives instead of indexing
                # them as opaque blobs; contents flow into the normal pipeline.
                stored, duplicates = await _extract_repo_archive(db, project, abs_path, rel_path)
                files_indexed += stored
                duplicates_skipped += duplicates
                continue

            data = abs_path.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()

            # Duplicate detection — skip if same hash already in project.
            existing = await db.execute(
                select(SourceFile).where(
                    SourceFile.project_id == project.id,
                    SourceFile.sha256_hash == sha256,
                    SourceFile.is_cleaned_up.is_(False),
                )
            )
            if existing.scalar_one_or_none():
                duplicates_skipped += 1
                continue

            storage_key = f"{project.tenant_id}/{project.id}/{uuid.uuid4()}_{abs_path.name}"
            await asyncio.to_thread(
                upload_file,
                bucket,
                storage_key,
                io.BytesIO(data),
                size,
                "application/octet-stream",
            )

            # Categorize file using shared logic with upload_service.
            file_category, doc_format = categorize_file(abs_path.name)

            source_file = SourceFile(
                tenant_id=project.tenant_id,
                project_id=project.id,
                filename=abs_path.name,
                original_path=rel_path,
                storage_key=storage_key,
                file_size=size,
                mime_type="application/octet-stream",
                sha256_hash=sha256,
                file_category=file_category,
                doc_format=doc_format,
                processing_status=FileProcessingStatus.UPLOADED,
            )
            db.add(source_file)
            await db.flush()
            files_indexed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if files_indexed and project.status == ProjectStatus.CREATED:
        project.status = ProjectStatus.ACTIVE

    await log_action(
        db,
        tenant_id=project.tenant_id,
        user_id=actor.id,
        action="source_file.repo_connected",
        resource_type="project",
        resource_id=project.id,
        changes={
            "repo_url": repo_url,
            "branch": branch,
            "files_indexed": files_indexed,
        },
        ip_address=ip_address,
    )

    return GitConnectOutcome(
        files_indexed=files_indexed,
        duplicates_skipped=duplicates_skipped,
        message=(
            f"Repository connected. {files_indexed} files indexed."
            + (f" {duplicates_skipped} duplicates skipped." if duplicates_skipped else "")
        ),
    )
