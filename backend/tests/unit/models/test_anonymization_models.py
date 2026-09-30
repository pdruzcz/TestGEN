"""Tests for the AnonymizationMap model — Story 1.54."""

from sqlalchemy import inspect

from app.models.anonymization_map import AnonymizationMap
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin


class TestAnonymizationMapModel:
    def test_inherits_mixins(self):
        assert issubclass(AnonymizationMap, UUIDMixin)
        assert issubclass(AnonymizationMap, TenantMixin)
        assert issubclass(AnonymizationMap, TimestampMixin)

    def test_tablename(self):
        assert AnonymizationMap.__tablename__ == "anonymization_maps"

    def test_has_project_id_fk(self):
        mapper = inspect(AnonymizationMap)
        col = mapper.columns["project_id"]
        fks = list(col.foreign_keys)
        assert any("projects.id" in str(fk.target_fullname) for fk in fks)

    def test_analysis_id_nullable_fk(self):
        mapper = inspect(AnonymizationMap)
        col = mapper.columns["analysis_id"]
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert any("analysis_results.id" in str(fk.target_fullname) for fk in fks)

    def test_has_encrypted_map_bytes(self):
        mapper = inspect(AnonymizationMap)
        assert "encrypted_map" in mapper.columns

    def test_has_count_columns(self):
        mapper = inspect(AnonymizationMap)
        assert "token_count" in mapper.columns
        assert "secret_count" in mapper.columns

    def test_has_expires_at(self):
        mapper = inspect(AnonymizationMap)
        assert "expires_at" in mapper.columns

    def test_registered_in_get_all_models(self):
        from app.models import get_all_models

        assert AnonymizationMap in get_all_models()
