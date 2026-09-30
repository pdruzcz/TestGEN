"""Tests for base mixins: UUIDMixin, TenantMixin, TimestampMixin."""

import uuid

from sqlalchemy import inspect

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class _UUIDOnly(Base, UUIDMixin):
    __tablename__ = "_test_uuid_only"


class _WithTenant(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "_test_with_tenant"


class TestUUIDMixin:
    def test_id_column_is_uuid(self):
        mapper = inspect(_UUIDOnly)
        col = mapper.columns["id"]
        assert col.type.python_type is uuid.UUID

    def test_id_is_primary_key(self):
        mapper = inspect(_UUIDOnly)
        col = mapper.columns["id"]
        assert col.primary_key

    def test_id_default_is_uuid4(self):
        mapper = inspect(_UUIDOnly)
        col = mapper.columns["id"]
        assert col.default is not None
        generated = col.default.arg({})
        assert isinstance(generated, uuid.UUID)
        assert generated.version == 4

    def test_id_uses_native_postgresql_uuid(self):
        mapper = inspect(_UUIDOnly)
        col = mapper.columns["id"]
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID

        assert isinstance(col.type, PG_UUID)


class TestTenantMixin:
    def test_tenant_id_column_exists(self):
        mapper = inspect(_WithTenant)
        assert "tenant_id" in mapper.columns

    def test_tenant_id_is_uuid(self):
        mapper = inspect(_WithTenant)
        col = mapper.columns["tenant_id"]
        assert col.type.python_type is uuid.UUID

    def test_tenant_id_has_fk_to_tenants(self):
        mapper = inspect(_WithTenant)
        col = mapper.columns["tenant_id"]
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert "tenants.id" in str(fks[0].target_fullname)

    def test_tenant_id_is_indexed(self):
        indexes = _WithTenant.__table__.indexes
        indexed_cols = {c.name for idx in indexes for c in idx.columns}
        assert "tenant_id" in indexed_cols


class TestTimestampMixin:
    def test_created_at_column_exists(self):
        mapper = inspect(_WithTenant)
        assert "created_at" in mapper.columns

    def test_updated_at_column_exists(self):
        mapper = inspect(_WithTenant)
        assert "updated_at" in mapper.columns

    def test_created_at_has_server_default(self):
        mapper = inspect(_WithTenant)
        col = mapper.columns["created_at"]
        assert col.server_default is not None

    def test_updated_at_is_nullable(self):
        mapper = inspect(_WithTenant)
        col = mapper.columns["updated_at"]
        assert col.nullable

    def test_created_at_is_datetime_with_timezone(self):
        mapper = inspect(_WithTenant)
        col = mapper.columns["created_at"]
        assert col.type.timezone


class TestNamingConvention:
    def test_index_convention(self):
        assert Base.metadata.naming_convention["ix"] == "ix_%(column_0_label)s"

    def test_unique_convention(self):
        assert Base.metadata.naming_convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"

    def test_fk_convention(self):
        assert "fk_" in Base.metadata.naming_convention["fk"]

    def test_pk_convention(self):
        assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
