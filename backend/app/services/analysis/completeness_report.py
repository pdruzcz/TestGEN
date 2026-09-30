"""
Analysis completeness report service - Story 1.27

Generates reports showing what analysis was completed:
- Coverage metrics per analysis type (logic structures, entry points, etc.)
- Missing analysis identification and gap reporting
- Quality metrics (confidence scores, data completeness)
- Analysis status timeline
- Recommendations for incomplete analysis

Helps identify which parts of the codebase need more analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus

logger = logging.getLogger(__name__)


class AnalysisType(StrEnum):
    """Types of code analysis."""
    LOGIC_STRUCTURES = "logic_structures"
    ENTRY_POINTS = "entry_points"
    COMPONENT_DEPENDENCIES = "component_dependencies"
    DATA_FLOW = "data_flow"
    BUSINESS_LOGIC = "business_logic"
    NATIVE_ANALYSIS = "native_analysis"
    LLM_ANALYSIS = "llm_analysis"


class CoverageLevel(StrEnum):
    """Coverage levels for analysis completeness."""
    FULL = "full"  # All expected data present
    PARTIAL = "partial"  # Some data present
    NONE = "none"  # No data present


@dataclass
class AnalysisCoverage:
    """Coverage metrics for a specific analysis type."""
    analysis_type: AnalysisType
    coverage_level: CoverageLevel
    files_analyzed: int
    total_files: int
    coverage_percentage: float  # 0.0 to 100.0
    missing_files: list[str] = field(default_factory=list)
    quality_score: float = 0.0  # 0.0 to 1.0
    issues: list[str] = field(default_factory=list)


@dataclass
class CompletenessReport:
    """Report showing analysis completeness status."""
    project_id: int
    project_name: str | None = None
    generated_at: datetime = field(default_factory=datetime.utcnow)

    # Overall metrics
    total_files: int = 0
    analyzed_files: int = 0
    overall_coverage_percentage: float = 0.0

    # Coverage by analysis type
    coverage_by_type: dict[AnalysisType, AnalysisCoverage] = field(default_factory=dict)

    # Missing analysis
    missing_analysis: list[AnalysisType] = field(default_factory=list)
    incomplete_analysis: list[AnalysisType] = field(default_factory=dict)

    # Quality metrics
    average_quality_score: float = 0.0
    quality_by_type: dict[AnalysisType, float] = field(default_factory=dict)

    # Timeline
    analysis_history: list[dict] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of completeness report."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "total_files": self.total_files,
            "analyzed_files": self.analyzed_files,
            "overall_coverage_percentage": self.overall_coverage_percentage,
            "missing_analysis_count": len(self.missing_analysis),
            "incomplete_analysis_count": len(self.incomplete_analysis),
            "average_quality_score": self.average_quality_score,
            "recommendations_count": len(self.recommendations),
        }

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "generated_at": self.generated_at.isoformat(),
            "total_files": self.total_files,
            "analyzed_files": self.analyzed_files,
            "overall_coverage_percentage": self.overall_coverage_percentage,
            "coverage_by_type": {
                at.value: {
                    "analysis_type": at.value,
                    "coverage_level": ac.coverage_level,
                    "files_analyzed": ac.files_analyzed,
                    "total_files": ac.total_files,
                    "coverage_percentage": ac.coverage_percentage,
                    "missing_files": ac.missing_files,
                    "quality_score": ac.quality_score,
                    "issues": ac.issues,
                }
                for at, ac in self.coverage_by_type.items()
            },
            "missing_analysis": [at.value for at in self.missing_analysis],
            "incomplete_analysis": self.incomplete_analysis,
            "average_quality_score": self.average_quality_score,
            "quality_by_type": {at.value: score for at, score in self.quality_by_type.items()},
            "analysis_history": self.analysis_history,
            "recommendations": self.recommendations,
            "summary": self.get_summary(),
        }


class CompletenessReportGenerator:
    """Generates completeness reports for analysis results."""

    def __init__(self):
        self.expected_analysis_types = [
            AnalysisType.LOGIC_STRUCTURES,
            AnalysisType.ENTRY_POINTS,
            AnalysisType.COMPONENT_DEPENDENCIES,
            AnalysisType.DATA_FLOW,
            AnalysisType.BUSINESS_LOGIC,
        ]

    def generate_report(
        self,
        project_id: int,
        source_files: list[str] | None = None,
        project_name: str | None = None,
    ) -> CompletenessReport:
        """
        Generate completeness report for a project.

        Args:
            project_id: Project ID to generate report for
            source_files: List of source files (optional, for coverage calculation)
            project_name: Project name (optional)
        """
        report = CompletenessReport(
            project_id=project_id,
            project_name=project_name,
        )

        # Get total file count
        if source_files:
            report.total_files = len(source_files)

        # Get analysis results from database
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                results = db.query(AnalysisResult).filter(
                    AnalysisResult.project_id == project_id
                ).all()

                # Analyze each result
                for result in results:
                    self._analyze_result(result, report)

                # Get analysis history
                report.analysis_history = self._get_analysis_history(db, project_id)
            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to query analysis results: {e}")

        # Calculate coverage for each analysis type
        for analysis_type in self.expected_analysis_types:
            if analysis_type not in report.coverage_by_type:
                # No analysis found for this type
                coverage = AnalysisCoverage(
                    analysis_type=analysis_type,
                    coverage_level=CoverageLevel.NONE,
                    files_analyzed=0,
                    total_files=report.total_files,
                    coverage_percentage=0.0,
                    quality_score=0.0,
                    issues=["No analysis performed"],
                )
                report.coverage_by_type[analysis_type] = coverage
                report.missing_analysis.append(analysis_type)

        # Calculate overall metrics
        report.analyzed_files = len({f for c in report.coverage_by_type.values() for f in c.missing_files})
        report.overall_coverage_percentage = self._calculate_overall_coverage(report)

        # Calculate quality scores
        report.average_quality_score = self._calculate_average_quality(report)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        return report

    def _analyze_result(self, result: AnalysisResult, report: CompletenessReport):
        """Analyze a single analysis result and update report."""
        analysis_type = result.analysis_type

        # Skip if not a recognized analysis type
        try:
            analysis_type_enum = AnalysisType(analysis_type)
        except ValueError:
            return

        result_data = result.result_data if isinstance(result.result_data, dict) else {}

        # Count analyzed files
        files_analyzed = len(result_data.get("source_files", []))

        # Determine coverage level
        coverage_level = CoverageLevel.FULL
        issues = []

        if result.status != AnalysisStatus.COMPLETED:
            coverage_level = CoverageLevel.NONE
            issues.append(f"Analysis status: {result.status}")
        elif files_analyzed == 0:
            coverage_level = CoverageLevel.NONE
            issues.append("No files analyzed")
        elif files_analyzed < report.total_files:
            coverage_level = CoverageLevel.PARTIAL
            missing = set(source_files or []) - set(result_data.get("source_files", []))
            if missing:
                issues.append(f"Missing {len(missing)} files")

        # Calculate quality score based on result data completeness
        quality_score = self._calculate_quality_score(result_data)

        coverage = AnalysisCoverage(
            analysis_type=analysis_type_enum,
            coverage_level=coverage_level,
            files_analyzed=files_analyzed,
            total_files=report.total_files,
            coverage_percentage=(files_analyzed / report.total_files * 100) if report.total_files > 0 else 0.0,
            missing_files=list(set(source_files or []) - set(result_data.get("source_files", []))),
            quality_score=quality_score,
            issues=issues,
        )

        report.coverage_by_type[analysis_type_enum] = coverage

    def _calculate_quality_score(self, result_data: dict) -> float:
        """Calculate quality score for analysis result (0.0 to 1.0)."""
        if not result_data:
            return 0.0

        score = 0.0

        # Check for expected fields
        expected_fields = ["source_files", "statistics"]
        present_fields = sum(1 for field in expected_fields if field in result_data and result_data[field])
        score += present_fields / len(expected_fields) * 0.5

        # Check statistics completeness
        if "statistics" in result_data and isinstance(result_data["statistics"], dict):
            stats = result_data["statistics"]
            if stats:  # Has some statistics
                score += 0.3

        # Check for detailed data
        if any(key in result_data for key in ["nodes", "edges", "functions", "classes", "rules"]):
            if result_data.get("nodes") or result_data.get("functions") or result_data.get("rules"):
                score += 0.2

        return min(score, 1.0)

    def _calculate_overall_coverage(self, report: CompletenessReport) -> float:
        """Calculate overall coverage percentage across all analysis types."""
        if not report.coverage_by_type:
            return 0.0

        total_coverage = sum(c.coverage_percentage for c in report.coverage_by_type.values())
        return total_coverage / len(report.coverage_by_type)

    def _calculate_average_quality(self, report: CompletenessReport) -> float:
        """Calculate average quality score across all analysis types."""
        if not report.coverage_by_type:
            return 0.0

        total_quality = sum(c.quality_score for c in report.coverage_by_type.values())
        return total_quality / len(report.coverage_by_type)

    def _get_analysis_history(self, db: Session, project_id: int) -> list[dict]:
        """Get analysis history for the project."""
        results = db.query(AnalysisResult).filter(
            AnalysisResult.project_id == project_id
        ).order_by(AnalysisResult.created_at).all()

        history = []
        for result in results:
            history.append({
                "analysis_type": result.analysis_type,
                "status": result.status,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                "has_result": result.result_data is not None,
            })

        return history

    def _generate_recommendations(self, report: CompletenessReport) -> list[str]:
        """Generate recommendations based on completeness gaps."""
        recommendations = []

        # Check for missing analysis
        if report.missing_analysis:
            recommendations.append(f"Run missing analysis: {', '.join([at.value for at in report.missing_analysis])}")

        # Check for incomplete analysis
        incomplete = [at for at, cov in report.coverage_by_type.items() if cov.coverage_level == CoverageLevel.PARTIAL]
        if incomplete:
            recommendations.append(f"Complete partial analysis: {', '.join([at.value for at in incomplete])}")

        # Check quality issues
        low_quality = [
            at for at, cov in report.coverage_by_type.items()
            if cov.quality_score < 0.5
        ]
        if low_quality:
            recommendations.append(f"Improve quality of: {', '.join([at.value for at in low_quality])}")

        # Check coverage percentage
        if report.overall_coverage_percentage < 50:
            recommendations.append("Overall coverage is below 50% - run more analysis")
        elif report.overall_coverage_percentage < 80:
            recommendations.append("Consider running additional analysis for better coverage")

        return recommendations


def get_completeness_report_generator() -> CompletenessReportGenerator:
    """Get or create completeness report generator instance."""
    return CompletenessReportGenerator()
