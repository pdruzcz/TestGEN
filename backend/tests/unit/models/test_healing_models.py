"""Tests for healing models: HealingReport, HealingItem — Story 1.51."""

from sqlalchemy import inspect

from app.models.base import TenantMixin, TimestampMixin, UUIDMixin
from app.models.healing_report import (
    HealingItem,
    HealingReport,
    HealingStatus,
    LocatorStrategy,
)


class TestHealingStatusEnum:
    def test_values(self):
        assert HealingStatus.PENDING.value == "pending"
        assert HealingStatus.HEALED.value == "healed"
        assert HealingStatus.NEEDS_REVIEW.value == "needs_review"
        assert HealingStatus.FAILED.value == "failed"
        assert HealingStatus.REJECTED.value == "rejected"


class TestLocatorStrategyEnum:
    def test_values(self):
        assert LocatorStrategy.DATA_TESTID.value == "data-testid"
        assert LocatorStrategy.ROLE_NAME.value == "role+name"
        assert LocatorStrategy.ARIA_LABEL.value == "aria-label"
        assert LocatorStrategy.ID.value == "id"
        assert LocatorStrategy.CSS.value == "css"
        assert LocatorStrategy.XPATH.value == "xpath"

    def test_is_strenum(self):
        # StrEnum -> usable directly as a plain string
        assert LocatorStrategy.DATA_TESTID == "data-testid"


class TestHealingReportModel:
    def test_inherits_mixins(self):
        assert issubclass(HealingReport, UUIDMixin)
        assert issubclass(HealingReport, TenantMixin)
        assert issubclass(HealingReport, TimestampMixin)

    def test_tablename(self):
        assert HealingReport.__tablename__ == "healing_reports"

    def test_has_project_id_fk(self):
        mapper = inspect(HealingReport)
        col = mapper.columns["project_id"]
        fks = list(col.foreign_keys)
        assert any("projects.id" in str(fk.target_fullname) for fk in fks)

    def test_has_version_columns(self):
        mapper = inspect(HealingReport)
        assert "version_a" in mapper.columns
        assert "version_b" in mapper.columns

    def test_has_status_column(self):
        mapper = inspect(HealingReport)
        assert "status" in mapper.columns

    def test_has_stats_column(self):
        mapper = inspect(HealingReport)
        assert "stats" in mapper.columns

    def test_items_relationship(self):
        mapper = inspect(HealingReport)
        assert "items" in mapper.relationships


class TestHealingItemModel:
    def test_inherits_mixins(self):
        assert issubclass(HealingItem, UUIDMixin)
        assert issubclass(HealingItem, TenantMixin)
        assert issubclass(HealingItem, TimestampMixin)

    def test_tablename(self):
        assert HealingItem.__tablename__ == "healing_items"

    def test_has_report_id_fk(self):
        mapper = inspect(HealingItem)
        col = mapper.columns["report_id"]
        fks = list(col.foreign_keys)
        assert any("healing_reports.id" in str(fk.target_fullname) for fk in fks)

    def test_has_test_code_id_fk(self):
        mapper = inspect(HealingItem)
        col = mapper.columns["test_code_id"]
        fks = list(col.foreign_keys)
        assert any("test_codes.id" in str(fk.target_fullname) for fk in fks)

    def test_has_locator_columns(self):
        mapper = inspect(HealingItem)
        for col in (
            "old_locator",
            "old_strategy",
            "new_locator",
            "new_strategy",
            "confidence",
            "healing_method",
            "status",
            "diff_preview",
        ):
            assert col in mapper.columns, f"missing column {col}"

    def test_report_relationship(self):
        mapper = inspect(HealingItem)
        assert "report" in mapper.relationships
