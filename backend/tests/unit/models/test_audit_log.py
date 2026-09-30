"""Tests for AuditLog model."""

from sqlalchemy import inspect

from app.models.audit_log import AuditLog
from app.models.base import UUIDMixin


class TestAuditLogModel:
    def test_inherits_uuid_mixin(self):
        assert issubclass(AuditLog, UUIDMixin)

    def test_tablename(self):
        assert AuditLog.__tablename__ == "audit_logs"

    def test_has_tenant_id_column(self):
        mapper = inspect(AuditLog)
        assert "tenant_id" in mapper.columns

    def test_tenant_id_is_nullable(self):
        mapper = inspect(AuditLog)
        col = mapper.columns["tenant_id"]
        assert col.nullable

    def test_has_user_id_column(self):
        mapper = inspect(AuditLog)
        assert "user_id" in mapper.columns

    def test_user_id_is_nullable(self):
        mapper = inspect(AuditLog)
        col = mapper.columns["user_id"]
        assert col.nullable

    def test_has_action_column(self):
        mapper = inspect(AuditLog)
        assert "action" in mapper.columns

    def test_has_resource_type_column(self):
        mapper = inspect(AuditLog)
        assert "resource_type" in mapper.columns

    def test_has_resource_id_column(self):
        mapper = inspect(AuditLog)
        assert "resource_id" in mapper.columns

    def test_has_details_column(self):
        mapper = inspect(AuditLog)
        assert "details" in mapper.columns

    def test_has_ip_address_column(self):
        mapper = inspect(AuditLog)
        assert "ip_address" in mapper.columns

    def test_has_created_at_column(self):
        mapper = inspect(AuditLog)
        assert "created_at" in mapper.columns
