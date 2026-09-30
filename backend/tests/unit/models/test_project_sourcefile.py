"""Tests for Project and SourceFile models."""

import uuid

from sqlalchemy import inspect

from app.models.base import TenantMixin, TimestampMixin, UUIDMixin
from app.models.project import Project, ProjectStatus
from app.models.source_file import SourceFile


class TestProjectModel:
    def test_inherits_mixins(self):
        assert issubclass(Project, UUIDMixin)
        assert issubclass(Project, TenantMixin)
        assert issubclass(Project, TimestampMixin)

    def test_tablename(self):
        assert Project.__tablename__ == "projects"

    def test_has_name_column(self):
        mapper = inspect(Project)
        assert "name" in mapper.columns

    def test_has_description_column(self):
        mapper = inspect(Project)
        assert "description" in mapper.columns

    def test_has_language_column(self):
        mapper = inspect(Project)
        assert "language" in mapper.columns

    def test_has_framework_column(self):
        mapper = inspect(Project)
        assert "framework" in mapper.columns

    def test_has_status_column(self):
        mapper = inspect(Project)
        assert "status" in mapper.columns

    def test_status_enum_values(self):
        assert ProjectStatus.CREATED.value == "created"
        assert ProjectStatus.ACTIVE.value == "active"
        assert ProjectStatus.ANALYZING.value == "analyzing"
        assert ProjectStatus.COMPLETED.value == "completed"
        assert ProjectStatus.ARCHIVED.value == "archived"


class TestSourceFileModel:
    def test_inherits_mixins(self):
        assert issubclass(SourceFile, UUIDMixin)
        assert issubclass(SourceFile, TenantMixin)
        assert issubclass(SourceFile, TimestampMixin)

    def test_tablename(self):
        assert SourceFile.__tablename__ == "source_files"

    def test_has_filename_column(self):
        mapper = inspect(SourceFile)
        assert "filename" in mapper.columns

    def test_has_project_id_fk(self):
        mapper = inspect(SourceFile)
        col = mapper.columns["project_id"]
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert "projects.id" in str(fks[0].target_fullname)

    def test_has_detected_language_column(self):
        mapper = inspect(SourceFile)
        assert "detected_language" in mapper.columns

    def test_has_detected_framework_column(self):
        mapper = inspect(SourceFile)
        assert "detected_framework" in mapper.columns

    def test_has_file_size_column(self):
        mapper = inspect(SourceFile)
        assert "file_size" in mapper.columns

    def test_has_sha256_hash_column(self):
        mapper = inspect(SourceFile)
        assert "sha256_hash" in mapper.columns

    def test_repr(self):
        sf = SourceFile(id=uuid.uuid4(), filename="test.py", file_size=100, is_cleaned_up=False)
        r = repr(sf)
        assert "SourceFile" in r
