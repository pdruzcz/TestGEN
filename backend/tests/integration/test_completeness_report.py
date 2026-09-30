"""Tests for analysis completeness report service - Story 1.27"""

import pytest

from app.services.analysis.completeness_report import (
    AnalysisCoverage,
    AnalysisType,
    CompletenessReport,
    CompletenessReportGenerator,
    CoverageLevel,
)


class TestAnalysisType:
    """Test AnalysisType enum."""

    def test_analysis_types(self):
        """Test all analysis types exist."""
        assert AnalysisType.LOGIC_STRUCTURES == "logic_structures"
        assert AnalysisType.ENTRY_POINTS == "entry_points"
        assert AnalysisType.COMPONENT_DEPENDENCIES == "component_dependencies"
        assert AnalysisType.DATA_FLOW == "data_flow"
        assert AnalysisType.BUSINESS_LOGIC == "business_logic"
        assert AnalysisType.NATIVE_ANALYSIS == "native_analysis"
        assert AnalysisType.LLM_ANALYSIS == "llm_analysis"


class TestCoverageLevel:
    """Test CoverageLevel enum."""

    def test_coverage_levels(self):
        """Test all coverage levels exist."""
        assert CoverageLevel.FULL == "full"
        assert CoverageLevel.PARTIAL == "partial"
        assert CoverageLevel.NONE == "none"


class TestAnalysisCoverage:
    """Test AnalysisCoverage dataclass."""

    def test_coverage_creation(self):
        """Test creating analysis coverage."""
        coverage = AnalysisCoverage(
            analysis_type=AnalysisType.LOGIC_STRUCTURES,
            coverage_level=CoverageLevel.FULL,
            files_analyzed=10,
            total_files=10,
            coverage_percentage=100.0,
            missing_files=[],
            quality_score=0.9,
            issues=[],
        )
        assert coverage.analysis_type == AnalysisType.LOGIC_STRUCTURES
        assert coverage.coverage_percentage == 100.0


class TestCompletenessReport:
    """Test CompletenessReport dataclass."""

    def test_empty_report(self):
        """Test creating empty report."""
        report = CompletenessReport(project_id=1)
        assert report.project_id == 1
        assert report.total_files == 0
        assert len(report.coverage_by_type) == 0

    def test_report_summary(self):
        """Test report summary generation."""
        report = CompletenessReport(project_id=1, project_name="Test Project")
        report.total_files = 10
        report.analyzed_files = 8
        report.overall_coverage_percentage = 80.0
        report.missing_analysis = [AnalysisType.DATA_FLOW]
        report.average_quality_score = 0.75

        summary = report.get_summary()

        assert summary["project_id"] == 1
        assert summary["project_name"] == "Test Project"
        assert summary["overall_coverage_percentage"] == 80.0
        assert summary["missing_analysis_count"] == 1

    def test_to_dict_serialization(self):
        """Test report can be serialized to dict."""
        report = CompletenessReport(project_id=1)
        report.coverage_by_type[AnalysisType.LOGIC_STRUCTURES] = AnalysisCoverage(
            analysis_type=AnalysisType.LOGIC_STRUCTURES,
            coverage_level=CoverageLevel.FULL,
            files_analyzed=5,
            total_files=5,
            coverage_percentage=100.0,
        )

        data = report.to_dict()

        assert data["project_id"] == 1
        assert "coverage_by_type" in data
        assert len(data["coverage_by_type"]) == 1


class TestCompletenessReportGenerator:
    """Test completeness report generator."""

    def test_generator_initialization(self):
        """Test generator can be initialized."""
        generator = CompletenessReportGenerator()
        assert generator.expected_analysis_types is not None
        assert len(generator.expected_analysis_types) >= 5

    def test_expected_analysis_types(self):
        """Test expected analysis types list."""
        generator = CompletenessReportGenerator()

        expected = [
            AnalysisType.LOGIC_STRUCTURES,
            AnalysisType.ENTRY_POINTS,
            AnalysisType.COMPONENT_DEPENDENCIES,
            AnalysisType.DATA_FLOW,
            AnalysisType.BUSINESS_LOGIC,
        ]

        for analysis_type in expected:
            assert analysis_type in generator.expected_analysis_types

    def test_generate_report_empty_project(self):
        """Test generating report for project with no analysis."""
        generator = CompletenessReportGenerator()

        # Create a report directly without database access
        report = CompletenessReport(
            project_id=1,
            project_name="Empty Project",
            total_files=2,
        )

        # Simulate missing analysis (no database access in test)
        for analysis_type in generator.expected_analysis_types:
            report.coverage_by_type[analysis_type] = AnalysisCoverage(
                analysis_type=analysis_type,
                coverage_level=CoverageLevel.NONE,
                files_analyzed=0,
                total_files=2,
                coverage_percentage=0.0,
                quality_score=0.0,
                issues=["No analysis performed"],
            )
            report.missing_analysis.append(analysis_type)

        report.overall_coverage_percentage = generator._calculate_overall_coverage(report)
        report.average_quality_score = generator._calculate_average_quality(report)
        report.recommendations = generator._generate_recommendations(report)

        assert report.project_id == 1
        assert report.project_name == "Empty Project"
        assert report.total_files == 2
        # All analysis should be missing
        assert len(report.missing_analysis) >= 5
        # Should have recommendations
        assert len(report.recommendations) > 0

    def test_calculate_quality_score(self):
        """Test quality score calculation."""
        generator = CompletenessReportGenerator()

        # Full data with statistics
        full_data = {
            "source_files": ["test.py"],
            "statistics": {"total_functions": 5},
            "functions": [{"name": "test"}],
        }
        score = generator._calculate_quality_score(full_data)
        assert score > 0.7

        # Minimal data
        minimal_data = {"source_files": ["test.py"]}
        score = generator._calculate_quality_score(minimal_data)
        assert 0.0 <= score <= 1.0

        # Empty data
        empty_data = {}
        score = generator._calculate_quality_score(empty_data)
        assert score == 0.0

    def test_calculate_overall_coverage(self):
        """Test overall coverage calculation."""
        generator = CompletenessReportGenerator()

        report = CompletenessReport(project_id=1, total_files=10)

        # Add some coverage
        report.coverage_by_type[AnalysisType.LOGIC_STRUCTURES] = AnalysisCoverage(
            analysis_type=AnalysisType.LOGIC_STRUCTURES,
            coverage_level=CoverageLevel.FULL,
            files_analyzed=10,
            total_files=10,
            coverage_percentage=100.0,
        )
        report.coverage_by_type[AnalysisType.ENTRY_POINTS] = AnalysisCoverage(
            analysis_type=AnalysisType.ENTRY_POINTS,
            coverage_level=CoverageLevel.PARTIAL,
            files_analyzed=5,
            total_files=10,
            coverage_percentage=50.0,
        )

        coverage = generator._calculate_overall_coverage(report)
        assert coverage == 75.0  # (100 + 50) / 2

    def test_calculate_average_quality(self):
        """Test average quality calculation."""
        generator = CompletenessReportGenerator()

        report = CompletenessReport(project_id=1)

        report.coverage_by_type[AnalysisType.LOGIC_STRUCTURES] = AnalysisCoverage(
            analysis_type=AnalysisType.LOGIC_STRUCTURES,
            coverage_level=CoverageLevel.FULL,
            files_analyzed=10,
            total_files=10,
            coverage_percentage=100.0,
            quality_score=0.8,
        )
        report.coverage_by_type[AnalysisType.ENTRY_POINTS] = AnalysisCoverage(
            analysis_type=AnalysisType.ENTRY_POINTS,
            coverage_level=CoverageLevel.FULL,
            files_analyzed=10,
            total_files=10,
            coverage_percentage=100.0,
            quality_score=0.6,
        )

        avg_quality = generator._calculate_average_quality(report)
        assert avg_quality == 0.7  # (0.8 + 0.6) / 2

    def test_generate_recommendations_full_coverage(self):
        """Test recommendations for full coverage."""
        generator = CompletenessReportGenerator()

        report = CompletenessReport(
            project_id=1,
            total_files=10,
            analyzed_files=10,
            overall_coverage_percentage=100.0,
        )

        # All analysis complete
        for analysis_type in generator.expected_analysis_types:
            report.coverage_by_type[analysis_type] = AnalysisCoverage(
                analysis_type=analysis_type,
                coverage_level=CoverageLevel.FULL,
                files_analyzed=10,
                total_files=10,
                coverage_percentage=100.0,
                quality_score=0.8,
            )

        recommendations = generator._generate_recommendations(report)

        # Should have minimal recommendations
        assert len(recommendations) == 0

    def test_generate_recommendations_low_coverage(self):
        """Test recommendations for low coverage."""
        generator = CompletenessReportGenerator()

        report = CompletenessReport(
            project_id=1,
            total_files=10,
            analyzed_files=2,
            overall_coverage_percentage=20.0,
        )

        # Missing analysis
        report.missing_analysis = [AnalysisType.DATA_FLOW, AnalysisType.BUSINESS_LOGIC]

        recommendations = generator._generate_recommendations(report)

        # Should recommend running missing analysis
        assert len(recommendations) > 0
        assert any("missing" in rec.lower() for rec in recommendations)

    def test_generate_recommendations_low_quality(self):
        """Test recommendations for low quality."""
        generator = CompletenessReportGenerator()

        report = CompletenessReport(project_id=1, overall_coverage_percentage=80.0)

        # Low quality analysis
        report.coverage_by_type[AnalysisType.LOGIC_STRUCTURES] = AnalysisCoverage(
            analysis_type=AnalysisType.LOGIC_STRUCTURES,
            coverage_level=CoverageLevel.FULL,
            files_analyzed=10,
            total_files=10,
            coverage_percentage=100.0,
            quality_score=0.3,  # Low quality
        )

        recommendations = generator._generate_recommendations(report)

        # Should recommend improving quality
        assert any("quality" in rec.lower() or "improve" in rec.lower() for rec in recommendations)
