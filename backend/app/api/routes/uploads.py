"""Source file upload + Git connect + delete routes (Story 1.6 + Story 2.1)."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, set_pagination_headers
from app.core.storage import delete_file
from app.models.source_file import SourceFile
from app.models.user import User
from app.schemas.source_file import (
    ConnectRepoRequest,
    ConnectRepoResponse,
    FileInfo,
    SourceFileListResponse,
    SourceFileResponse,
    UploadResponse,
)
from app.services.project.git_service import connect_repo
from app.services.project.upload_service import (
    get_active_project,
    list_project_files,
    upload_files,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["uploads"])


@router.post(
    "/{project_id}/upload",
    status_code=201,
    response_model=UploadResponse,
)
async def upload_source_files_route(
    project_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(..., description="One or more source files"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Upload source files. AC8: all authenticated roles allowed."""
    outcome = await upload_files(
        db,
        actor=current_user,
        project_id=project_id,
        files=files,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    accepted = [
        FileInfo(
            id=item.source_file.id if item.source_file else None,
            filename=item.filename,
            file_size=item.file_size,
            mime_type=item.mime_type,
            sha256_hash=item.sha256_hash,
            status=item.status,
        )
        for item in outcome.accepted
    ]
    rejected = [
        FileInfo(
            id=None,
            filename=item.filename,
            file_size=item.file_size,
            mime_type=item.mime_type,
            sha256_hash=item.sha256_hash,
            status=item.status,
            rejection_reason=item.rejection_reason,
        )
        for item in outcome.rejected
    ]
    return UploadResponse(
        project_id=project_id,
        accepted_files=accepted,
        rejected_files=rejected,
        total_accepted=len(accepted),
        total_rejected=len(rejected),
    )


@router.post(
    "/{project_id}/connect-repo",
    status_code=201,
    response_model=ConnectRepoResponse,
)
async def connect_repo_route(
    project_id: uuid.UUID,
    body: ConnectRepoRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectRepoResponse:
    """Clone an HTTPS git repo and register its source files."""
    outcome = await connect_repo(
        db,
        actor=current_user,
        project_id=project_id,
        repo_url=body.repo_url,
        branch=body.branch,
        auth_token=body.auth_token,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return ConnectRepoResponse(
        project_id=project_id,
        repo_url=body.repo_url,
        branch=body.branch,
        files_indexed=outcome.files_indexed,
        duplicates_skipped=outcome.duplicates_skipped,
        message=outcome.message,
    )


@router.get(
    "/{project_id}/files",
    response_model=SourceFileListResponse,
)
async def list_source_files_route(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SourceFileListResponse:
    """Paginated list of the project's uploaded source files."""
    files, total = await list_project_files(
        db,
        project_id=project_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    base_url = str(request.url.remove_query_params(["page", "page_size"])).rstrip("?")
    set_pagination_headers(response, total, pagination, base_url)

    return SourceFileListResponse(
        files=[SourceFileResponse.model_validate(f) for f in files],
        total=total,
    )


@router.delete(
    "/{project_id}/files/{file_id}",
    status_code=204,
)
async def delete_source_file_route(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a source file: mark as cleaned up and remove from MinIO.

    Requires Owner or Admin role.  Uses the existing ``is_cleaned_up`` flag
    so the file is ignored by queries but remains auditable.
    """
    await get_active_project(db, project_id)

    result = await db.execute(
        select(SourceFile).where(
            SourceFile.id == file_id,
            SourceFile.project_id == project_id,
            SourceFile.is_cleaned_up.is_(False),
        )
    )
    sf = result.scalar_one_or_none()
    if not sf:
        raise NotFoundError("Source file not found")

    # Remove from MinIO
    settings = get_settings()
    await asyncio.to_thread(delete_file, settings.minio_bucket_name, sf.storage_key)

    # Soft delete
    sf.is_cleaned_up = True
    await db.commit()
