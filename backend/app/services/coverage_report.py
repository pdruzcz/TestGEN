"""Code coverage report service - Story 1.46

Provides code coverage analysis and reporting:
- Coverage data parsing (coverage.py, lcov, jacoco)
- Coverage metrics calculation
- Coverage trend tracking
- Report generation (HTML, JSON, console)
- Branch and line coverage
- Uncovered code highlighting
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.database import get_sync_session
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)


class CoverageFormat(StrEnum):
    """Coverage report formats."""
    PYTHON_COVERAGE = "python_coverage"  # coverage.py
    LCOV = "lcov"  # C/C++
    JACOCO = "jacoco"  # Java
    ISTANBUL = "istanbul"  # JavaScript/TypeScript
    DOTCOVER = "dotcover"  # C#/.NET
    GO_COVERAGE = "go_coverage"  # Go


@dataclass
class CoverageMetrics:
    """Coverage metrics for a file or module."""
    file_path: str
    lines_covered: int
    lines_total: int
    branches_covered: int | None = None
    branches_total: int | None = None
    functions_covered: int | None = None
    functions_total: int | None = None

    @property
    def line_coverage_percent(self) -> float:
        """Line coverage percentage."""
        if self.lines_total == 0:
            return 0.0
        return (self.lines_covered / self.lines_total) * 100

    @property
    def branch_coverage_percent(self) -> float | None:
        """Branch coverage percentage."""
        if self.branches_total is None or self.branches_total == 0:
            return None
        return (self.branches_covered / self.branches_total) * 100

    @property
    def function_coverage_percent(self) -> float | None:
        """Function coverage percentage."""
        if self.functions_total is None or self.functions_total == 0:
            return None
        return (self.functions_covered / self.functions_total) * 100


@dataclass
class CoverageReport:
    """Complete coverage report."""
    project_id: UUID
    timestamp: datetime
    format: CoverageFormat
    overall_coverage: float
    files: list[CoverageMetrics] = field(default_factory=list)
    total_lines: int = 0
    total_covered: int = 0
    total_branches: int = 0
    total_branches_covered: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def coverage_percent(self) -> float:
        """Overall coverage percentage."""
        if self.total_lines == 0:
            return 0.0
        return (self.total_covered / self.total_lines) * 100

    def add_file(self, file_metrics: CoverageMetrics) -> None:
        """Add file metrics to report."""
        self.files.append(file_metrics)
        self.total_lines += file_metrics.lines_total
        self.total_covered += file_metrics.lines_covered
        if file_metrics.branches_total is not None:
            self.total_branches += file_metrics.branches_total
            self.total_branches_covered += file_metrics.branches_covered or 0


class CoverageParser:
    """Parse coverage reports in various formats."""

    def parse_python_coverage(self, report_path: str) -> list[CoverageMetrics]:
        """Parse coverage.py JSON report."""
        with open(report_path, "r") as f:
            data = json.load(f)

        files = []
        for file_path, file_data in data.get("files", {}).items():
            summary = file_data.get("summary", {})

            lines_total = summary.get("num_statements", 0)
            lines_covered = summary.get("covered_lines", 0)

            # Parse coverage to extract missing lines
            missing_lines = summary.get("missing_lines", 0)

            metrics = CoverageMetrics(
                file_path=file_path,
                lines_covered=lines_covered,
                lines_total=lines_total,
                branches_covered=summary.get("covered_branches", None),
                branches_total=summary.get("num_branches", None),
            )
            files.append(metrics)

        return files

    def parse_lcov(self, report_path: str) -> list[CoverageMetrics]:
        """Parse LCOV info file."""
        files_dict = {}

        with open(report_path, "r") as f:
            current_file = None
            lines_found = 0
            lines_hit = 0

            for line in f:
                line = line.strip()
                if line.startswith("SF:"):
                    current_file = line[3:]
                    files_dict[current_file] = {
                        "lines_total": 0,
                        "lines_hit": 0,
                        "branches_total": 0,
                        "branches_hit": 0,
                    }
                elif line.startswith("DA:") and current_file:
                    # Data line: line_number,execution_count
                    parts = line[3:].split(",")
                    if len(parts) == 2:
                        files_dict[current_file]["lines_total"] += 1
                        if int(parts[1]) > 0:
                            files_dict[current_file]["lines_hit"] += 1
                elif line.startswith("BRDA:") and current_file:
                    # Branch data
                    files_dict[current_file]["branches_total"] += 1
                    parts = line[5:].split(",")
                    if len(parts) >= 3 and int(parts[2]) > 0:
                        files_dict[current_file]["branches_hit"] += 1
                elif line.startswith("end_of_record"):
                    current_file = None

        files = []
        for file_path, data in files_dict.items():
            metrics = CoverageMetrics(
                file_path=file_path,
                lines_covered=data["lines_hit"],
                lines_total=data["lines_total"],
                branches_covered=data["branches_hit"],
                branches_total=data["branches_total"],
            )
            files.append(metrics)

        return files

    def parse_istanbul(self, report_path: str) -> list[CoverageMetrics]:
        """Parse Istanbul/JavaScript coverage report."""
        with open(report_path, "r") as f:
            data = json.load(f)

        files = []
        for file_path, file_data in data.items():
            statement_data = file_data.get("s", {})
            branch_data = file_data.get("b", {})
            function_data = file_data.get("f", {})

            # Calculate statements
            statements_total = len(statement_data)
            statements_covered = sum(1 for v in statement_data.values() if v > 0)

            # Calculate branches
            branches_total = sum(len(v) for v in branch_data.values())
            branches_covered = sum(
                sum(1 for hit in branch_hits if hit > 0)
                for branch_hits in branch_data.values()
            )

            # Calculate functions
            functions_total = len(function_data)
            functions_covered = sum(1 for v in function_data.values() if v > 0)

            metrics = CoverageMetrics(
                file_path=file_path,
                lines_covered=statements_covered,
                lines_total=statements_total,
                branches_covered=branches_covered,
                branches_total=branches_total,
                functions_covered=functions_covered,
                functions_total=functions_total,
            )
            files.append(metrics)

        return files


class CoverageReportService:
    """Service for generating and managing coverage reports."""

    def __init__(self):
        self.parser = CoverageParser()

    def generate_report(
        self,
        project_id: UUID,
        coverage_file: str,
        format: CoverageFormat,
    ) -> CoverageReport:
        """Generate coverage report from file.

        Args:
            project_id: Project UUID
            coverage_file: Path to coverage report file
            format: Coverage report format

        Returns:
            CoverageReport with metrics
        """
        report = CoverageReport(
            project_id=project_id,
            timestamp=datetime.utcnow(),
            format=format,
            overall_coverage=0.0,
        )

        # Parse based on format
        if format == CoverageFormat.PYTHON_COVERAGE:
            files = self.parser.parse_python_coverage(coverage_file)
        elif format == CoverageFormat.LCOV:
            files = self.parser.parse_lcov(coverage_file)
        elif format == CoverageFormat.ISTANBUL:
            files = self.parser.parse_istanbul(coverage_file)
        else:
            logger.warning(f"Unsupported coverage format: {format}")
            return report

        # Add files to report
        for file_metrics in files:
            report.add_file(file_metrics)

        report.overall_coverage = report.coverage_percent

        logger.info(
            f"Generated coverage report for project {project_id}: "
            f"{report.coverage_percent:.1f}% coverage"
        )

        return report

    def filter_by_threshold(
        self, report: CoverageReport, min_coverage: float
    ) -> list[CoverageMetrics]:
        """Filter files by minimum coverage threshold.

        Args:
            report: Coverage report
            min_coverage: Minimum coverage percentage (0-100)

        Returns:
            List of files below threshold
        """
        return [
            f for f in report.files
            if f.line_coverage_percent < min_coverage
        ]

    def generate_console_output(self, report: CoverageReport) -> str:
        """Generate console-friendly coverage report.

        Args:
            report: Coverage report

        Returns:
            Formatted string for console output
        """
        lines = [
            f"Coverage Report - {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Coverage: {report.coverage_percent:.1f}%",
            "",
            f"{'File':<50} {'Lines':>10} {'Covered':>10} {'Coverage':>10}",
            "-" * 82,
        ]

        # Sort files by coverage (ascending)
        sorted_files = sorted(report.files, key=lambda f: f.line_coverage_percent)

        for file_metrics in sorted_files[:20]:  # Top 20 worst files
            file_name = Path(file_metrics.file_path).name
            lines.append(
                f"{file_name:<50} "
                f"{file_metrics.lines_total:>10} "
                f"{file_metrics.lines_covered:>10} "
                f"{file_metrics.line_coverage_percent:>9.1f}%"
            )

        lines.append("")
        lines.append(f"Total: {report.total_lines} lines, {report.total_covered} covered")

        if report.total_branches > 0:
            branch_pct = (report.total_branches_covered / report.total_branches) * 100
            lines.append(f"Branch coverage: {branch_pct:.1f}%")

        return "\n".join(lines)

    def generate_json_report(self, report: CoverageReport) -> str:
        """Generate JSON coverage report.

        Args:
            report: Coverage report

        Returns:
            JSON string
        """
        data = {
            "project_id": str(report.project_id),
            "timestamp": report.timestamp.isoformat(),
            "format": report.format.value,
            "overall_coverage": report.coverage_percent,
            "summary": {
                "total_lines": report.total_lines,
                "total_covered": report.total_covered,
                "total_branches": report.total_branches,
                "total_branches_covered": report.total_branches_covered,
            },
            "files": [
                {
                    "file_path": f.file_path,
                    "line_coverage_percent": f.line_coverage_percent,
                    "lines_covered": f.lines_covered,
                    "lines_total": f.lines_total,
                    "branch_coverage_percent": f.branch_coverage_percent,
                    "branches_covered": f.branches_covered,
                    "branches_total": f.branches_total,
                }
                for f in report.files
            ],
        }

        return json.dumps(data, indent=2)

    def save_report(self, report: CoverageReport, output_path: str) -> None:
        """Save coverage report to file.

        Args:
            report: Coverage report
            output_path: Path to save report
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Determine format from extension
        ext = output_file.suffix.lower()
        if ext == ".json":
            content = self.generate_json_report(report)
        else:
            content = self.generate_console_output(report)

        with open(output_file, "w") as f:
            f.write(content)

        logger.info(f"Saved coverage report to {output_path}")


def get_coverage_report_service() -> CoverageReportService:
    """Get or create coverage report service instance."""
    return CoverageReportService()
