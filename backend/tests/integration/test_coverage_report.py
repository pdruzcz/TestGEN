"""Tests for code coverage report service - Story 1.46"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.services.coverage_report import (
    CoverageReportService,
    CoverageReport,
    CoverageMetrics,
    CoverageFormat,
    CoverageParser,
    get_coverage_report_service,
)


class TestCoverageFormat:
    """Test CoverageFormat enum (Story 1.46)."""

    def test_format_values(self):
        """Test all format values exist."""
        assert CoverageFormat.PYTHON_COVERAGE == "python_coverage"
        assert CoverageFormat.LCOV == "lcov"
        assert CoverageFormat.JACOCO == "jacoco"
        assert CoverageFormat.ISTANBUL == "istanbul"
        assert CoverageFormat.DOTCOVER == "dotcover"
        assert CoverageFormat.GO_COVERAGE == "go_coverage"


class TestCoverageMetrics:
    """Test CoverageMetrics dataclass (Story 1.46)."""

    def test_metrics_creation(self):
        """Test creating coverage metrics."""
        metrics = CoverageMetrics(
            file_path="test.py",
            lines_covered=80,
            lines_total=100,
            branches_covered=15,
            branches_total=20,
        )
        assert metrics.file_path == "test.py"
        assert metrics.line_coverage_percent == 80.0
        assert metrics.branch_coverage_percent == 75.0

    def test_zero_lines_coverage(self):
        """Test coverage with zero lines."""
        metrics = CoverageMetrics(
            file_path="empty.py",
            lines_covered=0,
            lines_total=0,
        )
        assert metrics.line_coverage_percent == 0.0

    def test_full_coverage(self):
        """Test 100% coverage."""
        metrics = CoverageMetrics(
            file_path="complete.py",
            lines_covered=50,
            lines_total=50,
        )
        assert metrics.line_coverage_percent == 100.0


class TestCoverageReport:
    """Test CoverageReport dataclass (Story 1.46)."""

    def test_report_creation(self):
        """Test creating coverage report."""
        project_id = uuid4()
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=85.0,
        )
        assert report.project_id == project_id
        assert report.format == CoverageFormat.PYTHON_COVERAGE

    def test_add_file_metrics(self):
        """Test adding file metrics to report."""
        report = CoverageReport(
            project_id=uuid4(),
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=0.0,
        )

        metrics = CoverageMetrics(
            file_path="test.py",
            lines_covered=80,
            lines_total=100,
        )
        report.add_file(metrics)

        assert len(report.files) == 1
        assert report.total_lines == 100
        assert report.total_covered == 80
        assert report.coverage_percent == 80.0

    def test_coverage_percent_calculation(self):
        """Test overall coverage percentage calculation."""
        report = CoverageReport(
            project_id=uuid4(),
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=0.0,
        )

        report.add_file(CoverageMetrics("a.py", 50, 100))
        report.add_file(CoverageMetrics("b.py", 30, 50))

        assert report.total_lines == 150
        assert report.total_covered == 80
        assert report.coverage_percent == 53.333333333333336


class TestCoverageParser:
    """Test CoverageParser (Story 1.46)."""

    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = CoverageParser()
        assert parser is not None

    def test_parse_python_coverage(self, tmp_path):
        """Test parsing Python coverage report."""
        parser = CoverageParser()

        # Create mock coverage.py JSON
        coverage_data = {
            "files": {
                "app/main.py": {
                    "summary": {
                        "num_statements": 100,
                        "covered_lines": 85,
                        "num_branches": 20,
                        "covered_branches": 15,
                    }
                }
            }
        }

        coverage_file = tmp_path / "coverage.json"
        with open(coverage_file, "w") as f:
            json.dump(coverage_data, f)

        files = parser.parse_python_coverage(str(coverage_file))
        assert len(files) == 1
        assert files[0].file_path == "app/main.py"
        assert files[0].lines_covered == 85
        assert files[0].lines_total == 100


class TestCoverageReportService:
    """Test CoverageReportService (Story 1.46)."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        service = CoverageReportService()
        assert service is not None
        assert service.parser is not None

    def test_get_coverage_report_service(self):
        """Test getting service singleton."""
        service = get_coverage_report_service()
        assert isinstance(service, CoverageReportService)

    def test_generate_console_output(self):
        """Test console report generation."""
        project_id = uuid4()
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=0.0,  # Will be calculated
        )

        report.add_file(CoverageMetrics("low.py", 30, 100))
        report.add_file(CoverageMetrics("high.py", 90, 100))

        service = CoverageReportService()
        output = service.generate_console_output(report)

        assert "Coverage Report" in output
        assert "60.0%" in output  # (30+90)/(100+100) = 120/200 = 60%
        assert "low.py" in output or "high.py" in output

    def test_generate_json_report(self):
        """Test JSON report generation."""
        project_id = uuid4()
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=80.0,
        )

        report.add_file(CoverageMetrics("test.py", 80, 100))

        service = CoverageReportService()
        json_output = service.generate_json_report(report)

        data = json.loads(json_output)
        assert data["overall_coverage"] == 80.0
        assert len(data["files"]) == 1
        assert data["files"][0]["line_coverage_percent"] == 80.0

    def test_filter_by_threshold(self):
        """Test filtering files by coverage threshold."""
        project_id = uuid4()
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=0.0,
        )

        report.add_file(CoverageMetrics("low.py", 40, 100))  # 40%
        report.add_file(CoverageMetrics("high.py", 90, 100))  # 90%

        service = CoverageReportService()
        low_coverage = service.filter_by_threshold(report, 50.0)

        assert len(low_coverage) == 1
        assert low_coverage[0].file_path == "low.py"

    def test_save_report(self, tmp_path):
        """Test saving report to file."""
        project_id = uuid4()
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=85.0,
        )

        report.add_file(CoverageMetrics("test.py", 85, 100))

        service = CoverageReportService()
        output_path = tmp_path / "coverage_report.txt"
        service.save_report(report, str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "Coverage Report" in content

    def test_save_json_report(self, tmp_path):
        """Test saving JSON report."""
        project_id = uuid4()
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=CoverageFormat.PYTHON_COVERAGE,
            overall_coverage=85.0,
        )

        report.add_file(CoverageMetrics("test.py", 85, 100))

        service = CoverageReportService()
        output_path = tmp_path / "coverage_report.json"
        service.save_report(report, str(output_path))

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["overall_coverage"] == 85.0


@pytest.mark.integration
class TestCoverageReportIntegration:
    """Integration tests for coverage report service (Story 1.46)."""

    def test_full_coverage_workflow(self, tmp_path):
        """Test complete coverage report workflow."""
        # Create mock coverage data
        coverage_data = {
            "files": {
                "app/service.py": {
                    "summary": {
                        "num_statements": 200,
                        "covered_lines": 180,
                    }
                },
                "app/utils.py": {
                    "summary": {
                        "num_statements": 50,
                        "covered_lines": 25,
                    }
                },
            }
        }

        coverage_file = tmp_path / "coverage.json"
        with open(coverage_file, "w") as f:
            json.dump(coverage_data, f)

        # Generate report
        service = CoverageReportService()
        report = service.generate_report(
            project_id=uuid4(),
            coverage_file=str(coverage_file),
            format=CoverageFormat.PYTHON_COVERAGE,
        )

        # Verify report
        assert len(report.files) == 2
        assert report.total_lines == 250
        assert report.total_covered == 205
        assert report.coverage_percent == 82.0

        # Find low coverage files
        low_coverage = service.filter_by_threshold(report, 60.0)
        assert len(low_coverage) == 1
        assert "utils.py" in low_coverage[0].file_path

        # Generate console output
        console_output = service.generate_console_output(report)
        assert "82.0%" in console_output

        # Save JSON report
        json_path = tmp_path / "report.json"
        service.save_report(report, str(json_path))
        assert json_path.exists()
