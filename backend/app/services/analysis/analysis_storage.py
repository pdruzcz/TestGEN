"""
Analysis history and results storage service - Story 1.28

Manages storage and retrieval of analysis results:
- Store analysis results with versioning and timestamps
- Retrieve historical analysis results
- Support querying by project, source file, analysis type, date range
- Support comparison between analysis runs
- Track analysis execution metrics (duration, status)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus, EngineMode

logger = logging.getLogger(__name__)


@dataclass
class AnalysisQuery:
    """Query parameters for searching analysis results."""
    project_id: str | None = None
    source_file_id: str | None = None
    analysis_type: str | None = None
    engine_mode: EngineMode | None = None
    status: AnalysisStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 100


@dataclass
class AnalysisHistoryEntry:
    """An entry in the analysis history."""
    id: str
    project_id: str
    source_file_id: str | None
    analysis_type: str
    engine_mode: EngineMode
    status: AnalysisStatus
    created_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    has_result: bool
    error_message: str | None


@dataclass
class AnalysisComparison:
    """Comparison between two analysis runs."""
    current: AnalysisHistoryEntry
    previous: AnalysisHistoryEntry | None
    differences: dict[str, Any] = field(default_factory=dict)
    metrics_delta: dict[str, float] = field(default_factory=dict)


class AnalysisStorageService:
    """Service for storing and retrieving analysis results with history."""

    def store_result(
        self,
        project_id: str,
        analysis_type: str,
        result_data: dict,
        source_file_id: str | None = None,
        engine_mode: EngineMode = EngineMode.HYBRID,
        status: AnalysisStatus = AnalysisStatus.COMPLETED,
        error_message: str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """
        Store an analysis result in the database.

        Args:
            project_id: Project ID
            analysis_type: Type of analysis (e.g., "logic_structures", "entry_points")
            result_data: Analysis result data
            source_file_id: Source file ID (optional)
            engine_mode: Engine mode used (native, llm, hybrid)
            status: Analysis status
            error_message: Error message if failed
            duration_ms: Duration in milliseconds
            metadata: Additional metadata to store

        Returns:
            Created AnalysisResult record
        """
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                result = AnalysisResult(
                    project_id=project_id,
                    source_file_id=source_file_id,
                    engine_mode=engine_mode,
                    module=analysis_type,
                    status=status,
                    result_data=result_data,
                    error_message=error_message,
                    duration_ms=duration_ms,
                )

                if status == AnalysisStatus.COMPLETED:
                    result.completed_at = datetime.utcnow()

                db.add(result)
                db.commit()
                db.refresh(result)

                logger.info(f"Stored analysis result: {analysis_type} for project {project_id}")
                return result

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to store analysis result: {e}")
            raise

    def get_result(self, result_id: str) -> AnalysisResult | None:
        """
        Get a single analysis result by ID.

        Args:
            result_id: Analysis result ID

        Returns:
            AnalysisResult or None if not found
        """
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                result = db.query(AnalysisResult).filter(
                    AnalysisResult.id == result_id
                ).first()
                return result
            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to get analysis result: {e}")
            return None

    def query_results(self, query: AnalysisQuery) -> list[AnalysisResult]:
        """
        Query analysis results with filters.

        Args:
            query: AnalysisQuery with filter parameters

        Returns:
            List of AnalysisResult records
        """
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                results = db.query(AnalysisResult)

                # Apply filters
                if query.project_id:
                    results = results.filter(AnalysisResult.project_id == query.project_id)

                if query.source_file_id:
                    results = results.filter(AnalysisResult.source_file_id == query.source_file_id)

                if query.analysis_type:
                    results = results.filter(AnalysisResult.module == query.analysis_type)

                if query.engine_mode:
                    results = results.filter(AnalysisResult.engine_mode == query.engine_mode)

                if query.status:
                    results = results.filter(AnalysisResult.status == query.status)

                if query.date_from:
                    results = results.filter(AnalysisResult.created_at >= query.date_from)

                if query.date_to:
                    results = results.filter(AnalysisResult.created_at <= query.date_to)

                # Order by most recent first
                results = results.order_by(desc(AnalysisResult.created_at))

                # Apply limit
                if query.limit:
                    results = results.limit(query.limit)

                return results.all()

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to query analysis results: {e}")
            return []

    def get_history(
        self,
        project_id: str,
        source_file_id: str | None = None,
        analysis_type: str | None = None,
        limit: int = 50,
    ) -> list[AnalysisHistoryEntry]:
        """
        Get analysis history for a project or source file.

        Args:
            project_id: Project ID
            source_file_id: Source file ID (optional)
            analysis_type: Analysis type filter (optional)
            limit: Maximum number of entries to return

        Returns:
            List of analysis history entries
        """
        query = AnalysisQuery(
            project_id=project_id,
            source_file_id=source_file_id,
            analysis_type=analysis_type,
            limit=limit,
        )

        results = self.query_results(query)

        history = []
        for result in results:
            entry = AnalysisHistoryEntry(
                id=str(result.id),
                project_id=str(result.project_id),
                source_file_id=str(result.source_file_id) if result.source_file_id else None,
                analysis_type=result.module,
                engine_mode=result.engine_mode,
                status=result.status,
                created_at=result.created_at,
                completed_at=result.completed_at,
                duration_ms=result.duration_ms,
                has_result=result.result_data is not None,
                error_message=result.error_message,
            )
            history.append(entry)

        return history

    def get_latest_result(
        self,
        project_id: str,
        analysis_type: str,
        source_file_id: str | None = None,
    ) -> AnalysisResult | None:
        """
        Get the latest analysis result for a project.

        Args:
            project_id: Project ID
            analysis_type: Analysis type
            source_file_id: Source file ID (optional)

        Returns:
            Latest AnalysisResult or None
        """
        query = AnalysisQuery(
            project_id=project_id,
            source_file_id=source_file_id,
            analysis_type=analysis_type,
            status=AnalysisStatus.COMPLETED,
            limit=1,
        )

        results = self.query_results(query)
        return results[0] if results else None

    def compare_with_previous(
        self,
        current_result_id: str,
    ) -> AnalysisComparison | None:
        """
        Compare current analysis result with previous run.

        Args:
            current_result_id: Current analysis result ID

        Returns:
            AnalysisComparison or None if no previous result found
        """
        current = self.get_result(current_result_id)
        if not current:
            return None

        # Find previous result for same project and analysis type
        query = AnalysisQuery(
            project_id=str(current.project_id),
            analysis_type=current.module,
            date_to=current.created_at,
            limit=1,
        )

        previous_results = self.query_results(query)
        previous = previous_results[0] if previous_results else None

        if not previous:
            return AnalysisComparison(
                current=self._to_history_entry(current),
                previous=None,
            )

        # Calculate differences
        differences = self._calculate_differences(previous, current)
        metrics_delta = self._calculate_metrics_delta(previous, current)

        return AnalysisComparison(
            current=self._to_history_entry(current),
            previous=self._to_history_entry(previous),
            differences=differences,
            metrics_delta=metrics_delta,
        )

    def _to_history_entry(self, result: AnalysisResult) -> AnalysisHistoryEntry:
        """Convert AnalysisResult to AnalysisHistoryEntry."""
        return AnalysisHistoryEntry(
            id=str(result.id),
            project_id=str(result.project_id),
            source_file_id=str(result.source_file_id) if result.source_file_id else None,
            analysis_type=result.module,
            engine_mode=result.engine_mode,
            status=result.status,
            created_at=result.created_at,
            completed_at=result.completed_at,
            duration_ms=result.duration_ms,
            has_result=result.result_data is not None,
            error_message=result.error_message,
        )

    def _calculate_differences(
        self, previous: AnalysisResult, current: AnalysisResult
    ) -> dict[str, Any]:
        """Calculate differences between two analysis results."""
        differences = {
            "status_changed": previous.status != current.status,
            "result_exists_changed": (previous.result_data is None) != (current.result_data is None),
            "duration_delta_ms": (current.duration_ms or 0) - (previous.duration_ms or 0),
        }

        # Compare statistics if available
        prev_stats = (previous.result_data or {}).get("statistics", {})
        curr_stats = (current.result_data or {}).get("statistics", {})

        if prev_stats and curr_stats:
            for key in set(prev_stats) | set(curr_stats):
                if key in prev_stats and key in curr_stats:
                    differences[f"{key}_delta"] = curr_stats[key] - prev_stats[key]

        return differences

    def _calculate_metrics_delta(
        self, previous: AnalysisResult, current: AnalysisResult
    ) -> dict[str, float]:
        """Calculate delta in key metrics between two results."""
        delta = {}

        prev_data = previous.result_data or {}
        curr_data = current.result_data or {}

        # Compare common metrics
        metric_keys = [
            "total_functions",
            "total_classes",
            "total_endpoints",
            "total_dependencies",
            "total_rules",
        ]

        for key in metric_keys:
            prev_val = prev_data.get(key, prev_data.get("statistics", {}).get(key, 0))
            curr_val = curr_data.get(key, curr_data.get("statistics", {}).get(key, 0))

            if isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
                delta[key] = curr_val - prev_val

        return delta

    def delete_old_results(
        self,
        project_id: str,
        keep_last_n: int = 10,
        analysis_type: str | None = None,
    ) -> int:
        """
        Delete old analysis results, keeping only the most recent N.

        Args:
            project_id: Project ID
            keep_last_n: Number of recent results to keep
            analysis_type: Analysis type filter (optional)

        Returns:
            Number of deleted results
        """
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                # Get all results for project
                query = db.query(AnalysisResult).filter(
                    AnalysisResult.project_id == project_id
                )

                if analysis_type:
                    query = query.filter(AnalysisResult.module == analysis_type)

                # Order by creation date (oldest first)
                all_results = query.order_by(AnalysisResult.created_at).all()

                # Keep only the most recent N
                if len(all_results) > keep_last_n:
                    to_delete = all_results[:-keep_last_n]
                    for result in to_delete:
                        db.delete(result)

                    db.commit()
                    return len(to_delete)

                return 0

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to delete old results: {e}")
            return 0


def get_analysis_storage_service() -> AnalysisStorageService:
    """Get or create analysis storage service instance."""
    return AnalysisStorageService()
