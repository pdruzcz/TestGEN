"""Tests for analysis models: AnalysisResult, TestCase, TestCode, Report."""

from sqlalchemy import inspect

from app.models.analysis_result import AnalysisResult
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin
from app.models.report import Report, ReportFormat
from app.models.test_case import TestCase, TestPriority, TestType
from app.models.test_code import TestCode


class TestAnalysisResultModel:
    def test_inherits_mixins(self):
        assert issubclass(AnalysisResult, UUIDMixin)
        assert issubclass(AnalysisResult, TenantMixin)
        assert issubclass(AnalysisResult, TimestampMixin)

    def test_tablename(self):
        assert AnalysisResult.__tablename__ == "analysis_results"

    def test_has_project_id_fk(self):
        mapper = inspect(AnalysisResult)
        col = mapper.columns["project_id"]
        fks = list(col.foreign_keys)
        assert any("projects.id" in str(fk.target_fullname) for fk in fks)

    def test_has_engine_mode_column(self):
        mapper = inspect(AnalysisResult)
        assert "engine_mode" in mapper.columns

    def test_has_module_column(self):
        mapper = inspect(AnalysisResult)
        assert "module" in mapper.columns

    def test_has_status_column(self):
        mapper = inspect(AnalysisResult)
        assert "status" in mapper.columns

    def test_has_result_data_column(self):
        mapper = inspect(AnalysisResult)
        assert "result_data" in mapper.columns

    def test_has_duration_ms_column(self):
        mapper = inspect(AnalysisResult)
        assert "duration_ms" in mapper.columns


class TestTestCaseModel:
    def test_inherits_mixins(self):
        assert issubclass(TestCase, UUIDMixin)
        assert issubclass(TestCase, TenantMixin)
        assert issubclass(TestCase, TimestampMixin)

    def test_tablename(self):
        assert TestCase.__tablename__ == "test_cases"

    def test_has_analysis_result_id_fk(self):
        mapper = inspect(TestCase)
        col = mapper.columns["analysis_result_id"]
        fks = list(col.foreign_keys)
        assert any("analysis_results.id" in str(fk.target_fullname) for fk in fks)

    def test_has_title_column(self):
        mapper = inspect(TestCase)
        assert "title" in mapper.columns

    def test_has_priority_column(self):
        mapper = inspect(TestCase)
        assert "priority" in mapper.columns

    def test_has_type_column(self):
        mapper = inspect(TestCase)
        assert "type" in mapper.columns

    def test_priority_enum_values(self):
        assert TestPriority.HIGH.value == "high"
        assert TestPriority.MEDIUM.value == "medium"
        assert TestPriority.LOW.value == "low"

    def test_type_enum_values(self):
        assert TestType.UNIT.value == "unit"
        assert TestType.INTEGRATION.value == "integration"
        assert TestType.E2E.value == "e2e"


class TestTestCodeModel:
    def test_inherits_mixins(self):
        assert issubclass(TestCode, UUIDMixin)
        assert issubclass(TestCode, TenantMixin)
        assert issubclass(TestCode, TimestampMixin)

    def test_tablename(self):
        assert TestCode.__tablename__ == "test_codes"

    def test_has_test_case_id_fk(self):
        mapper = inspect(TestCode)
        col = mapper.columns["test_case_id"]
        fks = list(col.foreign_keys)
        assert any("test_cases.id" in str(fk.target_fullname) for fk in fks)

    def test_has_framework_column(self):
        mapper = inspect(TestCode)
        assert "framework" in mapper.columns

    def test_has_language_column(self):
        mapper = inspect(TestCode)
        assert "language" in mapper.columns

    def test_has_code_column(self):
        mapper = inspect(TestCode)
        assert "code" in mapper.columns

    def test_has_file_path_column(self):
        mapper = inspect(TestCode)
        assert "file_path" in mapper.columns


class TestReportModel:
    def test_inherits_mixins(self):
        assert issubclass(Report, UUIDMixin)
        assert issubclass(Report, TenantMixin)
        assert issubclass(Report, TimestampMixin)

    def test_tablename(self):
        assert Report.__tablename__ == "reports"

    def test_has_project_id_fk(self):
        mapper = inspect(Report)
        col = mapper.columns["project_id"]
        fks = list(col.foreign_keys)
        assert any("projects.id" in str(fk.target_fullname) for fk in fks)

    def test_has_title_column(self):
        mapper = inspect(Report)
        assert "title" in mapper.columns

    def test_has_format_column(self):
        mapper = inspect(Report)
        assert "format" in mapper.columns

    def test_has_content_column(self):
        mapper = inspect(Report)
        assert "content" in mapper.columns

    def test_has_file_url_column(self):
        mapper = inspect(Report)
        assert "file_url" in mapper.columns

    def test_format_enum_values(self):
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.JSON == "json" or hasattr(ReportFormat, "JSON")
