"""Source file Pydantic schemas — upload, git-connect, list responses."""

import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

ALLOWED_GIT_HOSTS: set[str] = {"github.com", "gitlab.com", "bitbucket.org"}


class FileInfo(BaseModel):
    id: uuid.UUID | None = None
    filename: str
    file_size: int
    mime_type: str | None = None
    sha256_hash: str | None = None
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    project_id: uuid.UUID
    accepted_files: list[FileInfo]
    rejected_files: list[FileInfo]
    total_accepted: int
    total_rejected: int


class ConnectRepoRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=2000)
    branch: str = Field(default="main", min_length=1, max_length=255)
    auth_token: str | None = Field(default=None, max_length=500)

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError("Only HTTPS repository URLs are supported")
        host = urlparse(v).hostname
        if host not in ALLOWED_GIT_HOSTS:
            raise ValueError("Unsupported Git provider. Allowed: " + ", ".join(sorted(ALLOWED_GIT_HOSTS)))
        return v

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Branch name cannot be blank")
        return stripped


class ConnectRepoResponse(BaseModel):
    project_id: uuid.UUID
    repo_url: str
    branch: str
    files_indexed: int
    duplicates_skipped: int = 0
    message: str


class SourceFileResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    filename: str
    original_path: str | None = None
    file_size: int
    mime_type: str | None = None
    sha256_hash: str
    detected_language: str | None = None
    detected_framework: str | None = None
    requires_manual_classification: bool = False
    loc_count: int = 0
    is_cleaned_up: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Epic 2: Documentation support
    file_category: str | None = None
    doc_format: str | None = None
    page_count: int | None = None
    # Processing lifecycle — universal for all file categories
    processing_status: str = "uploaded"
    error_message: str | None = None
    # Epic 2.3: Document classification enrichment (list endpoint only).
    # Populated from AnalysisResult(module="classification"); null when absent.
    doc_type: str | None = None
    classification_confidence: float | None = None
    classification_justification: str | None = None

    model_config = {"from_attributes": True}


class SourceFileListResponse(BaseModel):
    files: list[SourceFileResponse]
    total: int
