"""Unit tests for the git clone source connector (Story 1.6)."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.project import ProjectStatus
from app.models.user_tenant import TenantRole
from app.services.project.git_service import (
    _build_clone_url,
    _sanitize_git_output,
    _validate_git_url,
    connect_repo,
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


@pytest.fixture()
def actor():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.tenant_id = uuid.uuid4()
    a.role = TenantRole.USER
    return a


@pytest.fixture()
def project(actor):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.tenant_id = actor.tenant_id
    p.is_deleted = False
    p.status = ProjectStatus.CREATED
    return p


class TestValidateGitUrl:
    def test_accepts_github(self):
        _validate_git_url("https://github.com/org/repo.git")

    def test_accepts_gitlab(self):
        _validate_git_url("https://gitlab.com/group/repo")

    def test_accepts_bitbucket(self):
        _validate_git_url("https://bitbucket.org/team/repo")

    def test_rejects_http(self):
        with pytest.raises(ValidationError):
            _validate_git_url("http://github.com/org/repo.git")

    def test_rejects_ssh(self):
        with pytest.raises(ValidationError):
            _validate_git_url("git@github.com:org/repo.git")

    def test_rejects_unknown_host(self):
        with pytest.raises(ValidationError):
            _validate_git_url("https://evil.example.com/repo")


class TestSanitizeGitOutput:
    def test_masks_embedded_token(self):
        raw = "fatal: could not read from https://SECRET_TOKEN@github.com/org/repo"
        cleaned = _sanitize_git_output(raw)
        assert "SECRET_TOKEN" not in cleaned
        assert "https://***@github.com/org/repo" in cleaned

    def test_leaves_plain_url_alone(self):
        raw = "fatal: repository not found at https://github.com/org/repo"
        assert _sanitize_git_output(raw) == raw


class TestBuildCloneUrl:
    def test_no_token_returns_original(self):
        assert _build_clone_url("https://github.com/org/repo.git", None) == "https://github.com/org/repo.git"

    def test_injects_token(self):
        result = _build_clone_url("https://github.com/org/repo.git", "tk_123")
        assert result == "https://tk_123@github.com/org/repo.git"


class TestConnectRepo:
    @patch("app.services.project.git_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.git_service.upload_file")
    @patch("app.services.project.git_service._iter_source_files")
    @patch("app.services.project.git_service.shallow_clone", new_callable=AsyncMock)
    @patch("app.services.project.git_service.shutil.rmtree")
    async def test_happy_path_indexes_supported_files(
        self,
        mock_rmtree,
        mock_clone,
        mock_iter,
        mock_upload,
        mock_log,
        mock_db,
        actor,
        project,
        tmp_path,
    ):
        # project fetch + duplicate-detection query per indexed file (2 files).
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(None),  # app.py — no duplicate
                _exec_scalar_one_or_none(None),  # main.ts — no duplicate
            ]
        )

        # Prepare two files inside tmp_path for the clone walker.
        py_file = tmp_path / "app.py"
        py_file.write_bytes(b"print('hi')")
        ts_file = tmp_path / "main.ts"
        ts_file.write_bytes(b"export const x = 1;")

        mock_clone.return_value = str(tmp_path)
        mock_iter.return_value = iter(
            [
                (py_file, "app.py"),
                (ts_file, "main.ts"),
            ]
        )

        outcome = await connect_repo(
            mock_db,
            actor=actor,
            project_id=project.id,
            repo_url="https://github.com/org/repo.git",
            branch="main",
            auth_token=None,
        )

        assert outcome.files_indexed == 2
        assert mock_upload.call_count == 2
        mock_log.assert_awaited_once()
        assert project.status == ProjectStatus.ACTIVE
        mock_rmtree.assert_called_once_with(str(tmp_path), ignore_errors=True)

    @patch("app.services.project.git_service.log_action", new_callable=AsyncMock)
    @patch("app.services.project.upload_service.upload_file")
    @patch("app.services.project.git_service.upload_file")
    @patch("app.services.project.git_service._iter_source_files")
    @patch("app.services.project.git_service.shallow_clone", new_callable=AsyncMock)
    @patch("app.services.project.git_service.shutil.rmtree")
    async def test_archive_in_repo_is_extracted_not_indexed_as_blob(
        self,
        mock_rmtree,
        mock_clone,
        mock_iter,
        mock_git_upload,
        mock_upload_service_upload,
        mock_log,
        mock_db,
        actor,
        project,
        tmp_path,
    ):
        """Story 1.6-zakańczenie — a .zip committed in a repo is unpacked and its
        contents indexed (with archive-relative original_path), instead of
        being stored as one opaque blob no parser can consume."""
        import zipfile as zipfile_mod

        from app.models.source_file import FileCategory

        zip_path = tmp_path / "project.zip"
        with zipfile_mod.ZipFile(zip_path, "w") as zf:
            zf.writestr("src/index.php", "<?php echo 1;")
            zf.writestr("composer.json", '{"require-dev": {"phpunit/phpunit": "^10"}}')

        mock_clone.return_value = str(tmp_path)
        mock_iter.return_value = iter([(zip_path, "project.zip")])

        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(None),  # dup on src/index.php
                _exec_scalar_one_or_none(None),  # dup on composer.json
            ]
        )

        outcome = await connect_repo(
            mock_db,
            actor=actor,
            project_id=project.id,
            repo_url="https://github.com/org/repo.git",
            branch="main",
            auth_token=None,
        )

        # The two extracted files are indexed; the zip blob itself is not.
        assert outcome.files_indexed == 2
        assert mock_git_upload.call_count == 0
        assert mock_upload_service_upload.call_count == 2
        assert project.status == ProjectStatus.ACTIVE

        added = {c.args[0].filename: c.args[0] for c in mock_db.add.call_args_list}
        assert added["index.php"].file_category == FileCategory.CODE
        assert added["composer.json"].file_category == FileCategory.DATA
        assert added["index.php"].original_path == "src/index.php"
        assert added["composer.json"].original_path == "composer.json"

    async def test_invalid_url_raises_before_db(self, mock_db, actor, project):
        with pytest.raises(ValidationError):
            await connect_repo(
                mock_db,
                actor=actor,
                project_id=project.id,
                repo_url="http://insecure.example/repo",
                branch="main",
            )

    async def test_missing_project_raises_404(self, mock_db, actor):
        mock_db.execute = AsyncMock(side_effect=[_exec_scalar_one_or_none(None)])
        with pytest.raises(NotFoundError):
            await connect_repo(
                mock_db,
                actor=actor,
                project_id=uuid.uuid4(),
                repo_url="https://github.com/org/repo.git",
                branch="main",
            )

    @patch("app.services.project.git_service.shallow_clone", new_callable=AsyncMock)
    async def test_clone_failure_bubbles_validation_error(self, mock_clone, mock_db, actor, project):
        mock_db.execute = AsyncMock(side_effect=[_exec_scalar_one_or_none(project)])
        mock_clone.side_effect = ValidationError("Git clone failed: not found")

        with pytest.raises(ValidationError):
            await connect_repo(
                mock_db,
                actor=actor,
                project_id=project.id,
                repo_url="https://github.com/org/repo.git",
                branch="main",
            )


class TestIterSourceFiles:
    def test_skips_dotgit_and_disallowed(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_bytes(b"ref")
        (tmp_path / "a.py").write_bytes(b"x")
        (tmp_path / "bin.exe").write_bytes(b"x")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.ts").write_bytes(b"x")

        from app.services.project.git_service import _iter_source_files

        found = sorted(rel for _, rel in _iter_source_files(Path(tmp_path)))
        assert found == ["a.py", "sub/b.ts"]
