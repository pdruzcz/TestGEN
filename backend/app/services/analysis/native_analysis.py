"""
Native (deterministic) code analysis service - Story 1.25

Combines all AST-based analyzers into unified native analysis:
- Logic structures (functions, classes, complexity)
- Entry points & API endpoints
- Component dependencies (coupling, circular deps)
- Data flow (transformations, paths)
- Business logic (rules, operations, events)

Provides deterministic, consistent analysis results using tree-sitter parsers.
"""

import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.ast.registry import ASTParserRegistry
from app.services.analysis.business_logic import BusinessLogicAnalyzer, BusinessLogicResult
from app.services.analysis.component_dependencies import ComponentDependencyAnalyzer, DependencyAnalysisResult
from app.services.analysis.data_flow import DataFlowAnalysisResult, DataFlowAnalyzer
from app.services.analysis.entry_points import EntryPointCatalog, EntryPointsAnalyzer
from app.services.analysis.logic_structures import CodeStructureCatalog, LogicStructuresAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class NativeAnalysisResult:
    """Combined result from all native (AST-based) analyzers."""

    language: str
    source_files: list[str] = field(default_factory=list)

    # Component analysis results
    logic_structures: CodeStructureCatalog | None = None
    entry_points: EntryPointCatalog | None = None
    dependencies: DependencyAnalysisResult | None = None
    data_flow: DataFlowAnalysisResult | None = None
    business_logic: BusinessLogicResult | None = None

    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate combined statistics from all analyzers."""
        stats = {
            "language": self.language,
            "source_files_count": len(self.source_files),
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
        }

        # Add logic structures stats
        if self.logic_structures:
            stats["logic_structures"] = self.logic_structures.get_statistics()

        # Add entry points stats
        if self.entry_points:
            stats["entry_points"] = self.entry_points.get_statistics()

        # Add dependencies stats
        if self.dependencies:
            stats["dependencies"] = self.dependencies.get_statistics()

        # Add data flow stats
        if self.data_flow:
            stats["data_flow"] = self.data_flow.get_statistics()

        # Add business logic stats
        if self.business_logic:
            stats["business_logic"] = self.business_logic.get_statistics()

        return stats

    def get_combined_metrics(self) -> dict[str, Any]:
        """Get high-level combined metrics."""
        metrics = {
            "total_functions": 0,
            "total_classes": 0,
            "total_endpoints": 0,
            "total_dependencies": 0,
            "total_business_rules": 0,
            "average_complexity": 0.0,
            "framework_detected": False,
        }

        if self.logic_structures:
            metrics["total_functions"] = self.logic_structures.total_functions
            metrics["total_classes"] = self.logic_structures.total_classes
            metrics["average_complexity"] = self.logic_structures.get_statistics().get("average_complexity", 0.0)

        if self.entry_points:
            metrics["total_endpoints"] = len(self.entry_points.endpoints)
            metrics["framework_detected"] = self.entry_points.framework_detected

        if self.dependencies:
            metrics["total_dependencies"] = len(self.dependencies.edges)

        if self.business_logic:
            metrics["total_business_rules"] = len(self.business_logic.rules)

        return metrics

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "logic_structures": self.logic_structures.to_dict() if self.logic_structures else None,
            "entry_points": self.entry_points.to_dict() if self.entry_points else None,
            "dependencies": self.dependencies.to_dict() if self.dependencies else None,
            "data_flow": self.data_flow.to_dict() if self.data_flow else None,
            "business_logic": self.business_logic.to_dict() if self.business_logic else None,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "statistics": self.get_statistics(),
            "combined_metrics": self.get_combined_metrics(),
        }


class NativeAnalysisOrchestrator:
    """Orchestrates all native (AST-based) analyzers."""

    def __init__(self):
        self.parser_registry = ASTParserRegistry.get_instance()

        # Initialize all analyzers
        self.logic_analyzer = LogicStructuresAnalyzer()
        self.entry_points_analyzer = EntryPointsAnalyzer()
        self.dependencies_analyzer = ComponentDependencyAnalyzer()
        self.data_flow_analyzer = DataFlowAnalyzer()
        self.business_logic_analyzer = BusinessLogicAnalyzer()

    def analyze_file(
        self,
        source_code: str,
        file_path: str,
        language: str,
        analyzers: list[str] | None = None,
    ) -> NativeAnalysisResult:
        """
        Analyze a single file using all or specified native analyzers.

        Args:
            source_code: Source code to analyze
            file_path: Path to the source file
            language: Programming language
            analyzers: List of analyzer names to run (default: all)
                Available: logic_structures, entry_points, dependencies, data_flow, business_logic
        """
        result = NativeAnalysisResult(language=language)

        if analyzers is None:
            analyzers = ["logic_structures", "entry_points", "dependencies", "data_flow", "business_logic"]

        try:
            # Run logic structures analysis
            if "logic_structures" in analyzers:
                result.logic_structures = self.logic_analyzer.analyze_file(source_code, file_path, language)
                result.source_files.extend(result.logic_structures.source_files)

            # Run entry points analysis
            if "entry_points" in analyzers:
                result.entry_points = self.entry_points_analyzer.analyze_file(source_code, file_path, language)
                result.source_files.extend(result.entry_points.source_files)

            # Run dependencies analysis
            if "dependencies" in analyzers:
                result.dependencies = self.dependencies_analyzer.analyze_file(source_code, file_path, language)
                result.source_files.extend(result.dependencies.source_files)

            # Run data flow analysis
            if "data_flow" in analyzers:
                result.data_flow = self.data_flow_analyzer.analyze_file(source_code, file_path, language)
                result.source_files.extend(result.data_flow.source_files)

            # Run business logic analysis
            if "business_logic" in analyzers:
                result.business_logic = self.business_logic_analyzer.analyze_file(source_code, file_path, language)
                result.source_files.extend(result.business_logic.source_files)

            # Deduplicate source files
            result.source_files = list(set(result.source_files))

        except Exception as e:
            logger.error(f"Failed to analyze {file_path}: {e}")

        return result

    def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
        analyzers: list[str] | None = None,
        save_to_db: bool = True,
    ) -> NativeAnalysisResult:
        """
        Analyze multiple source files using all or specified native analyzers.

        Args:
            source_files: List of file dictionaries with file_path, content, language
            project_id: Project ID for database storage
            analyzers: List of analyzer names to run (default: all)
            save_to_db: If False, skip internal _save_to_database (caller handles persistence)
        """
        if analyzers is None:
            analyzers = ["logic_structures", "entry_points", "dependencies", "data_flow", "business_logic"]

        # Detect primary language from files
        languages = {f.get("language", "unknown") for f in source_files}
        primary_language = languages.pop() if len(languages) == 1 else "multi"

        unified_result = NativeAnalysisResult(language=primary_language)

        # Collect all file info for each analyzer
        files_by_analyzer = {analyzer: [] for analyzer in analyzers}

        for file_info in source_files:
            for analyzer in analyzers:
                files_by_analyzer[analyzer].append(file_info)

        try:
            # Run logic structures analysis
            if "logic_structures" in analyzers:
                unified_result.logic_structures = self.logic_analyzer.analyze_project(
                    files_by_analyzer["logic_structures"],
                    project_id=project_id,
                    save_to_db=False,  # Pipeline handles persistence
                )
                unified_result.source_files.extend(unified_result.logic_structures.source_files)

            # Run entry points analysis
            if "entry_points" in analyzers:
                unified_result.entry_points = EntryPointCatalog(language=primary_language)
                for file_info in files_by_analyzer["entry_points"]:
                    file_result = self.entry_points_analyzer.analyze_file(
                        source_code=file_info["content"],
                        file_path=file_info["file_path"],
                        language=file_info["language"],
                    )
                    unified_result.entry_points.endpoints.extend(file_result.endpoints)
                    unified_result.entry_points.main_functions.extend(file_result.main_functions)
                    unified_result.entry_points.public_functions.extend(file_result.public_functions)
                    unified_result.entry_points.source_files.extend(file_result.source_files)
                    if file_result.framework_detected:
                        unified_result.entry_points.framework_detected = True
                unified_result.source_files.extend(unified_result.entry_points.source_files)

            # Run dependencies analysis
            if "dependencies" in analyzers:
                unified_result.dependencies = DependencyAnalysisResult(language=primary_language)
                for file_info in files_by_analyzer["dependencies"]:
                    file_result = self.dependencies_analyzer.analyze_file(
                        source_code=file_info["content"],
                        file_path=file_info["file_path"],
                        language=file_info["language"],
                    )
                    unified_result.dependencies.nodes.extend(file_result.nodes)
                    unified_result.dependencies.edges.extend(file_result.edges)
                    unified_result.dependencies.source_files.extend(file_result.source_files)

                # Calculate module metrics for unified result
                unified_result.dependencies.module_metrics = self.dependencies_analyzer._calculate_module_metrics(
                    unified_result.dependencies
                )
                unified_result.source_files.extend(unified_result.dependencies.source_files)

            # Run data flow analysis
            if "data_flow" in analyzers:
                unified_result.data_flow = DataFlowAnalysisResult(language=primary_language)
                for file_info in files_by_analyzer["data_flow"]:
                    file_result = self.data_flow_analyzer.analyze_file(
                        source_code=file_info["content"],
                        file_path=file_info["file_path"],
                        language=file_info["language"],
                    )
                    unified_result.data_flow.nodes.extend(file_result.nodes)
                    unified_result.data_flow.edges.extend(file_result.edges)
                    unified_result.data_flow.paths.extend(file_result.paths)
                    unified_result.data_flow.source_files.extend(file_result.source_files)
                unified_result.source_files.extend(unified_result.data_flow.source_files)

            # Run business logic analysis
            if "business_logic" in analyzers:
                unified_result.business_logic = BusinessLogicResult(language=primary_language)
                for file_info in files_by_analyzer["business_logic"]:
                    file_result = self.business_logic_analyzer.analyze_file(
                        source_code=file_info["content"],
                        file_path=file_info["file_path"],
                        language=file_info["language"],
                    )
                    unified_result.business_logic.rules.extend(file_result.rules)
                    unified_result.business_logic.concepts.extend(file_result.concepts)
                    unified_result.business_logic.state_transitions.extend(file_result.state_transitions)
                    unified_result.business_logic.operations.extend(file_result.operations)
                    unified_result.business_logic.events.extend(file_result.events)
                    unified_result.business_logic.source_files.extend(file_result.source_files)
                unified_result.source_files.extend(unified_result.business_logic.source_files)

            # Deduplicate source files
            unified_result.source_files = list(set(unified_result.source_files))

        except Exception as e:
            logger.error(f"Failed to analyze project: {e}")

        # Save to database (unless caller wants to handle persistence)
        if save_to_db:
            self._save_to_database(unified_result, project_id)

        return unified_result

    def _save_to_database(self, result: NativeAnalysisResult, project_id: int):
        """Save analysis results to database."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                analysis_result = AnalysisResult(
                    project_id=project_id,
                    analysis_type="native_analysis",
                    status=AnalysisStatus.COMPLETED,
                    result_data=result.to_dict(),
                    metadata={
                        "statistics": result.get_statistics(),
                        "combined_metrics": result.get_combined_metrics(),
                    },
                )
                db.add(analysis_result)
                db.commit()
            finally:
                with contextlib.suppress(Exception):
                    session_generator.close()
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")

    def get_available_analyzers(self) -> list[str]:
        """Get list of available native analyzers."""
        return [
            "logic_structures",
            "entry_points",
            "dependencies",
            "data_flow",
            "business_logic",
        ]


def get_native_analysis_orchestrator() -> NativeAnalysisOrchestrator:
    """Get or create native analysis orchestrator instance."""
    return NativeAnalysisOrchestrator()
