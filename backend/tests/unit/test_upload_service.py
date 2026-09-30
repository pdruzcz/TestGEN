"""Unit tests for the source file upload service (Story 1.6)."""

import io
import uuid
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import NotFoundError, QuotaExceededError
from app.models.project import ProjectStatus
from app.models.source_file import FileCategory
from app.models.tenant import PlanType
from app.models.user_tenant import TenantRole
from app.services.project import upload_service
from app.services.project.upload_service import (
    ALLOWED_EXTENSIONS,
    categorize_file,
    is_allowed_extension,
    max_file_size_bytes_for,
    upload_files,
)


def _build_upload(filename: str, payload: bytes, content_type: str = "text/x-python") -> UploadFile:
    headers = Headers({"content-type": content_type})
    return UploadFile(
        filename=filename,
        file=io.BytesIO(payload),
        size=len(payload),
        headers=headers,
    )


def _exec_scalar_one_or_none(value):
    return MagicMock(scalar_one_or_none=MagicMock(return_value=value))


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.info = {}  # HOTFIX izolacji: serwisy czytają tenant_scope z db.info
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def mock_billing_quota(monkeypatch):
    """Story 7.8: upload woła QuotaService (storage) — mock, by nie dokładać
    zapytań DB do sekwencji ``side_effect`` w testach uploadu."""
    svc = MagicMock()
    svc.enforce_quota = AsyncMock()
    svc.increment_usage = AsyncMock()
    monkeypatch.setattr("app.services.billing.quota_service.QuotaService", MagicMock(return_value=svc))
    return svc


@pytest.fixture()
def tenant_freemium():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = PlanType.BASIC
    return tenant


@pytest.fixture()
def tenant_premium():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = PlanType.PROFESSIONAL
    return tenant


@pytest.fixture()
def actor(tenant_freemium):
    actor = MagicMock()
    actor.id = uuid.uuid4()
    actor.tenant_id = tenant_freemium.id
    actor.role = TenantRole.USER
    return actor


@pytest.fixture()
def project(tenant_freemium):
    project = MagicMock()
    project.id = uuid.uuid4()
    project.tenant_id = tenant_freemium.id
    project.is_deleted = False
    project.status = ProjectStatus.CREATED
    return project


class TestAllowedExtension:
    def test_accepts_python(self):
        assert is_allowed_extension("module.py")

    def test_accepts_tar_gz(self):
        assert is_allowed_extension("bundle.tar.gz")

    def test_rejects_exe(self):
        assert not is_allowed_extension("malware.exe")

    def test_accepts_pdf(self):
        # PDF is intentionally allowed (Epic 2 documentation files).
        assert is_allowed_extension("spec.pdf")

    def test_rejects_unknown(self):
        assert not is_allowed_extension("README")


class TestMaxFileSize:
    def test_freemium_plan_default(self):
        assert max_file_size_bytes_for(PlanType.FREEMIUM) == 100 * 1024 * 1024

    def test_paid_plans_default(self):
        # Basic i Premium (płatne) — wyższy cap; model 3-planowy 7.1/2b.3
        assert max_file_size_bytes_for(PlanType.BASIC) == 500 * 1024 * 1024
        assert max_file_size_bytes_for(PlanType.PREMIUM) == 500 * 1024 * 1024


class TestUploadFiles:
    @patch("app.services.project.upload_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.upload_file")
    async def test_happy_path_accepts_python_file(self, mock_minio, mock_log, mock_db, actor, project, tenant_freemium):
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),  # project fetch
                _exec_scalar_one_or_none(tenant_freemium),  # tenant fetch
                _exec_scalar_one_or_none(None),  # duplicate detection (no match)
            ]
        )

        file = _build_upload("service.py", b"print('hi')\n")
        outcome = await upload_files(mock_db, actor=actor, project_id=project.id, files=[file])

        assert len(outcome.accepted) == 1
        assert not outcome.rejected
        mock_minio.assert_called_once()
        mock_log.assert_awaited_once()
        accepted = outcome.accepted[0]
        assert accepted.filename == "service.py"
        assert accepted.status == "accepted"
        # AC6 — first accepted upload promotes project CREATED → ACTIVE.
        assert project.status == ProjectStatus.ACTIVE

    @patch("app.services.project.upload_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.upload_file")
    async def test_rejects_unsupported_extension(self, mock_minio, mock_log, mock_db, actor, project, tenant_freemium):
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(tenant_freemium),
                _exec_scalar_one_or_none(None),  # duplicate detection on the accepted file
            ]
        )

        good = _build_upload("ok.py", b"print('hi')\n")
        bad = _build_upload("bad.exe", b"MZ...", content_type="application/octet-stream")
        outcome = await upload_files(mock_db, actor=actor, project_id=project.id, files=[good, bad])

        assert len(outcome.accepted) == 1
        assert len(outcome.rejected) == 1
        assert outcome.rejected[0].status == "rejected"
        assert "Unsupported" in (outcome.rejected[0].rejection_reason or "")
        mock_minio.assert_called_once()  # only good file uploaded

    @patch("app.services.project.upload_service.upload_file")
    async def test_declared_size_over_limit_raises_429(
        self, mock_minio, mock_db, actor, project, tenant_freemium, monkeypatch
    ):
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(tenant_freemium),
            ]
        )

        # Shrink the Basic limit to keep the test fast.
        monkeypatch.setattr(upload_service, "max_file_size_bytes_for", lambda plan: 1024)

        oversized = _build_upload("big.py", b"x" * 2048)
        with pytest.raises(QuotaExceededError) as exc:
            await upload_files(mock_db, actor=actor, project_id=project.id, files=[oversized])
        assert "Basic" in exc.value.detail
        mock_minio.assert_not_called()

    @patch("app.services.project.upload_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.upload_file")
    async def test_streamed_size_over_limit_raises_429(
        self, mock_minio, mock_log, mock_db, actor, project, tenant_freemium, monkeypatch
    ):
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(tenant_freemium),
            ]
        )
        monkeypatch.setattr(upload_service, "max_file_size_bytes_for", lambda plan: 1024)

        # Bypass the declared-size short-circuit by zeroing it out.
        oversized = _build_upload("streamed.py", b"x" * 2048)
        oversized.size = None  # type: ignore[assignment]

        with pytest.raises(QuotaExceededError):
            await upload_files(mock_db, actor=actor, project_id=project.id, files=[oversized])

    async def test_missing_project_raises_404(self, mock_db, actor):
        mock_db.execute = AsyncMock(side_effect=[_exec_scalar_one_or_none(None)])
        with pytest.raises(NotFoundError):
            await upload_files(mock_db, actor=actor, project_id=uuid.uuid4(), files=[])

    async def test_missing_tenant_raises_404(self, mock_db, actor, project):
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(None),  # tenant missing
            ]
        )
        with pytest.raises(NotFoundError):
            await upload_files(mock_db, actor=actor, project_id=project.id, files=[])

    def test_allowed_extensions_snapshot(self):
        # Guard against accidental deletions from the allow-list.
        for ext in (".py", ".java", ".ts", ".zip", ".tar.gz"):
            assert ext in ALLOWED_EXTENSIONS


def _make_zip_bytes(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestJsonAcceptance:
    """Story 1.6-zakańczenie — ``.json`` accepted as project DATA (item 1)."""

    def test_json_is_allowed_extension(self):
        assert is_allowed_extension("composer.json")

    def test_json_categorized_as_data_not_code_or_doc(self):
        category, doc_format = categorize_file("composer.json")
        assert category == FileCategory.DATA
        assert doc_format is None

    def test_code_file_still_categorized_as_code(self):
        # Regression guard: adding DATA must not reclassify code.
        assert categorize_file("service.py")[0] == FileCategory.CODE
        assert categorize_file("spec.md")[0] == FileCategory.DOCUMENTATION


class TestArchiveExtraction:
    """Story 1.6-zakańczenie — uploaded archives extracted into child SourceFiles (item 2)."""

    @patch("app.services.project.upload_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.download_file_bytes")
    @patch("app.services.project.upload_service.upload_file")
    async def test_zip_extracts_php_and_composer_json(
        self, mock_minio, mock_download, mock_log, mock_db, actor, project, tenant_freemium
    ):
        entries = {
            "src/index.php": "<?php echo 1;",
            "composer.json": '{"require-dev": {"phpunit/phpunit": "^10"}}',
        }
        zip_bytes = _make_zip_bytes(entries)
        mock_download.return_value = zip_bytes

        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),  # project fetch
                _exec_scalar_one_or_none(tenant_freemium),  # tenant fetch
                _exec_scalar_one_or_none(None),  # dup check on the zip itself
                _exec_scalar_one_or_none(None),  # dup check on index.php
                _exec_scalar_one_or_none(None),  # dup check on composer.json
            ]
        )

        file = _build_upload("project.zip", zip_bytes, "application/zip")
        outcome = await upload_files(mock_db, actor=actor, project_id=project.id, files=[file])

        # The zip + both extracted files are accepted.
        assert len(outcome.accepted) == 3
        assert not outcome.rejected

        by_name = {a.filename: a.source_file for a in outcome.accepted}
        assert by_name["index.php"].file_category == FileCategory.CODE
        assert by_name["composer.json"].file_category == FileCategory.DATA
        # Relative paths from the archive are preserved on original_path.
        assert by_name["index.php"].original_path == "src/index.php"
        assert by_name["composer.json"].original_path == "composer.json"

        # Archive payload downloaded once from MinIO for extraction.
        mock_download.assert_called_once()

    @patch("app.services.project.upload_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.download_file_bytes")
    @patch("app.services.project.upload_service.upload_file")
    async def test_zip_skips_disallowed_files_inside(
        self, mock_minio, mock_download, mock_log, mock_db, actor, project, tenant_freemium
    ):
        # .png is not in ALLOWED_EXTENSIONS but is not in the binary exclude set
        # either, so it exercises the allow-list filter inside the extractor.
        entries = {"src/index.php": "<?php echo 1;", "assets/logo.png": "PNG-bytes"}
        zip_bytes = _make_zip_bytes(entries)
        mock_download.return_value = zip_bytes

        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(tenant_freemium),
                _exec_scalar_one_or_none(None),  # dup on zip
                _exec_scalar_one_or_none(None),  # dup on index.php (png never extracted)
            ]
        )

        file = _build_upload("project.zip", zip_bytes, "application/zip")
        outcome = await upload_files(mock_db, actor=actor, project_id=project.id, files=[file])

        # The .png is skipped; the .php and the zip are accepted.
        assert {a.filename for a in outcome.accepted} == {"project.zip", "index.php"}
        assert not outcome.rejected

    @patch("app.services.project.upload_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.download_file_bytes")
    @patch("app.services.project.upload_service.upload_file")
    async def test_zip_bomb_is_rejected_not_hung(
        self, mock_minio, mock_download, mock_log, mock_db, actor, project, tenant_freemium, monkeypatch
    ):
        zip_bytes = _make_zip_bytes({"big.py": "x" * (10 * 1024)})
        mock_download.return_value = zip_bytes

        # Shrink the decompressed-size cap to 0 MiB so any content trips it.
        from app.services.project.archive_extractor import ArchiveExtractor

        monkeypatch.setattr(
            upload_service,
            "_archive_extractor_from_settings",
            lambda: ArchiveExtractor(max_extracted_total_mb=0),
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(tenant_freemium),
                _exec_scalar_one_or_none(None),  # dup on the zip
            ]
        )

        file = _build_upload("project.zip", zip_bytes, "application/zip")
        outcome = await upload_files(mock_db, actor=actor, project_id=project.id, files=[file])

        assert not outcome.accepted
        assert len(outcome.rejected) == 1
        reason = outcome.rejected[0].rejection_reason or ""
        assert "extraction" in reason.lower() or "decompressed" in reason.lower()
