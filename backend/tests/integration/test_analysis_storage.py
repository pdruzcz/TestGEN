"""Tests for analysis history and results storage service - Story 1.28"""

import pytest
from datetime import datetime

from app.models.analysis_result import AnalysisStatus, EngineMode
from app.services.analysis.analysis_storage import (
    AnalysisComparison,
    AnalysisHistoryEntry,
    AnalysisQuery,
    AnalysisStorageService,
)


class TestAnalysisQuery:
    """Test AnalysisQuery dataclass."""

    def test_query_creation(self):
        """Test creating an analysis query."""
        query = AnalysisQuery(
            project_id="proj-123",
            analysis_type="logic_structures",
            status=AnalysisStatus.COMPLETED,
            limit=50,
        )
        assert query.project_id == "proj-123"
        assert query.analysis_type == "logic_structures"
        assert query.limit == 50


class TestAnalysisHistoryEntry:
    """Test AnalysisHistoryEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a history entry."""
        entry = AnalysisHistoryEntry(
            id="result-123",
            project_id="proj-123",
            source_file_id="file-123",
            analysis_type="logic_structures",
            engine_mode=EngineMode.NATIVE,
            status=AnalysisStatus.COMPLETED,
            created_at="2026-01-01T00:00:00",
            completed_at="2026-01-01T00:01:00",
            duration_ms=1000,
            has_result=True,
            error_message=None,
        )
        assert entry.id == "result-123"
        assert entry.analysis_type == "logic_structures"


class TestAnalysisComparison:
    """Test AnalysisComparison dataclass."""

    def test_comparison_creation(self):
        """Test creating an analysis comparison."""
        current = AnalysisHistoryEntry(
            id="result-2",
            project_id="proj-123",
            source_file_id=None,
            analysis_type="logic_structures",
            engine_mode=EngineMode.NATIVE,
            status=AnalysisStatus.COMPLETED,
            created_at="2026-01-02T00:00:00",
            completed_at="2026-01-02T00:01:00",
            duration_ms=1000,
            has_result=True,
            error_message=None,
        )

        comparison = AnalysisComparison(
            current=current,
            previous=None,
            differences={"status_changed": False},
            metrics_delta={"total_functions": 5},
        )

        assert comparison.current.id == "result-2"
        assert comparison.previous is None


class TestAnalysisStorageService:
    """Test analysis storage service logic."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        service = AnalysisStorageService()
        assert service is not None

    def test_to_history_entry_conversion(self):
        """Test conversion to history entry."""
        service = AnalysisStorageService()

        # Mock AnalysisResult
        class MockResult:
            id = "result-123"
            project_id = "proj-123"
            source_file_id = "file-123"
            module = "logic_structures"
            engine_mode = EngineMode.NATIVE
            status = AnalysisStatus.COMPLETED
            created_at = datetime(2026, 1, 1, 12, 0, 0)
            completed_at = datetime(2026, 1, 1, 12, 1, 0)
            duration_ms = 1000
            result_data = {"test": "data"}
            error_message = None

        mock_result = MockResult()

        entry = service._to_history_entry(mock_result)

        assert entry.id == "result-123"
        assert entry.analysis_type == "logic_structures"
        assert entry.has_result is True

    def test_calculate_differences(self):
        """Test difference calculation between results."""
        service = AnalysisStorageService()

        # Mock results
        class MockResult1:
            status = AnalysisStatus.COMPLETED
            result_data = {"statistics": {"total_functions": 10}}
            duration_ms = 1000

        class MockResult2:
            status = AnalysisStatus.COMPLETED
            result_data = {"statistics": {"total_functions": 12}}
            duration_ms = 1200

        prev = MockResult1()
        curr = MockResult2()

        differences = service._calculate_differences(prev, curr)

        assert differences["duration_delta_ms"] == 200
        assert differences.get("total_functions_delta") == 2

    def test_calculate_metrics_delta(self):
        """Test metrics delta calculation."""
        service = AnalysisStorageService()

        prev_data = {
            "total_functions": 10,
            "total_classes": 2,
            "statistics": {"total_endpoints": 5},
        }
        curr_data = {
            "total_functions": 12,
            "total_classes": 2,
            "statistics": {"total_endpoints": 7},
        }

        # Mock results
        class MockPrev:
            result_data = prev_data

        class MockCurr:
            result_data = curr_data

        delta = service._calculate_metrics_delta(MockPrev(), MockCurr())

        assert delta["total_functions"] == 2
        assert delta["total_classes"] == 0
