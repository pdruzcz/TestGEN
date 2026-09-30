"""Tests for Tenant model."""

from sqlalchemy import inspect

from app.models.base import TimestampMixin, UUIDMixin
from app.models.tenant import PlanType, Tenant


class TestTenantModel:
    def test_inherits_uuid_mixin(self):
        assert issubclass(Tenant, UUIDMixin)

    def test_inherits_timestamp_mixin(self):
        assert issubclass(Tenant, TimestampMixin)

    def test_tablename(self):
        assert Tenant.__tablename__ == "tenants"

    def test_has_name_column(self):
        mapper = inspect(Tenant)
        assert "name" in mapper.columns

    def test_has_slug_column(self):
        mapper = inspect(Tenant)
        assert "slug" in mapper.columns

    def test_slug_is_unique(self):
        mapper = inspect(Tenant)
        col = mapper.columns["slug"]
        assert col.unique

    def test_slug_is_indexed(self):
        indexes = Tenant.__table__.indexes
        indexed_cols = {c.name for idx in indexes for c in idx.columns}
        assert "slug" in indexed_cols

    def test_has_settings_column(self):
        mapper = inspect(Tenant)
        assert "settings" in mapper.columns

    def test_settings_is_nullable(self):
        mapper = inspect(Tenant)
        col = mapper.columns["settings"]
        assert col.nullable

    def test_has_is_active_column(self):
        mapper = inspect(Tenant)
        assert "is_active" in mapper.columns

    def test_has_plan_column(self):
        mapper = inspect(Tenant)
        assert "plan" in mapper.columns


class TestPlanType:
    """Model 3-planowy (7.1/CR#2): freemium | basic | premium."""

    def test_has_freemium_plan(self):
        assert PlanType.FREEMIUM.value == "freemium"

    def test_has_basic_plan(self):
        assert PlanType.BASIC.value == "basic"

    def test_has_premium_plan(self):
        assert PlanType.PREMIUM.value == "premium"

    def test_all_plans(self):
        assert set(PlanType) == {PlanType.FREEMIUM, PlanType.BASIC, PlanType.PREMIUM}
