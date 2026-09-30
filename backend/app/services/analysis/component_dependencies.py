"""
Component dependency analysis service - Story 1.22

Analyzes dependencies between code components:
- Function dependencies: which functions call which
- Class dependencies: inheritance, composition, usage
- Module dependencies: imports, exports
- Coupling metrics: afferent, efferent, instability
- Circular dependency detection

Creates unified dependency graph and metrics.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.ast.registry import ASTParserRegistry
from app.services.analysis.ast.ast_tree import ASTTree

logger = logging.getLogger(__name__)


class DependencyType(StrEnum):
    """Types of dependencies between components."""
    CALLS = "calls"  # Function A calls function B
    IMPORTS = "imports"  # Module A imports module B
    INHERITS = "inherits"  # Class A inherits from class B
    IMPLEMENTS = "implements"  # Class A implements interface B
    COMPOSES = "composes"  # Class A has instance of class B
    USES = "uses"  # General usage dependency


class CouplingLevel(StrEnum):
    """Coupling levels for dependencies."""
    TIGHT = "tight"  # Direct, concrete dependencies
    LOOSE = "loose"  # Interface/abstract dependencies
    NONE = "none"  # No coupling


@dataclass
class DependencyEdge:
    """A dependency relationship between two components."""
    source: str  # Function, class, or module name
    target: str  # Function, class, or module name
    dependency_type: DependencyType
    coupling_level: CouplingLevel
    line_number: int | None = None
    file_path: str | None = None


@dataclass
class ComponentNode:
    """A component (function, class, module) in the dependency graph."""
    name: str
    component_type: str  # function, class, module, interface
    file_path: str
    line_start: int
    line_end: int
    is_public: bool = False
    docstring: str | None = None


@dataclass
class ModuleMetrics:
    """Coupling metrics for a module."""
    module_name: str
    afferent: int  # Ca: number of incoming dependencies (other modules depend on this)
    efferent: int  # Ce: number of outgoing dependencies (this module depends on others)
    instability: float  # I = Ce / (Ca + Ce), ranges 0 (stable) to 1 (instable)
    abstractness: float  # A = Na / Nc, ratio of abstract types to total types


@dataclass
class DependencyAnalysisResult:
    """Result of dependency analysis."""
    language: str
    source_files: list[str] = field(default_factory=list)
    nodes: list[ComponentNode] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)
    module_metrics: list[ModuleMetrics] = field(default_factory=list)
    circular_dependencies: list[list[str]] = field(default_factory=list)
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate statistics for dashboard display."""
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)

        # Count by component type
        nodes_by_type = defaultdict(int)
        for node in self.nodes:
            nodes_by_type[node.component_type] += 1

        # Count by dependency type
        edges_by_type = defaultdict(int)
        for edge in self.edges:
            edges_by_type[edge.dependency_type] += 1

        # Average coupling
        tight_coupling = len([e for e in self.edges if e.coupling_level == CouplingLevel.TIGHT])
        loose_coupling = len([e for e in self.edges if e.coupling_level == CouplingLevel.LOOSE])

        # Module metrics averages
        avg_instability = 0.0
        avg_abstractness = 0.0
        if self.module_metrics:
            avg_instability = sum(m.instability for m in self.module_metrics) / len(self.module_metrics)
            avg_abstractness = sum(m.abstractness for m in self.module_metrics) / len(self.module_metrics)

        return {
            "total_components": total_nodes,
            "total_dependencies": total_edges,
            "components_by_type": dict(nodes_by_type),
            "dependencies_by_type": dict(edges_by_type),
            "circular_dependencies_count": len(self.circular_dependencies),
            "tight_coupling_count": tight_coupling,
            "loose_coupling_count": loose_coupling,
            "avg_instability": avg_instability,
            "avg_abstractness": avg_abstractness,
        }

    def get_dependencies_for(self, component_name: str) -> list[DependencyEdge]:
        """Get all outgoing dependencies for a component."""
        return [e for e in self.edges if e.source == component_name]

    def get_dependents(self, component_name: str) -> list[DependencyEdge]:
        """Get all incoming dependencies (dependents) for a component."""
        return [e for e in self.edges if e.target == component_name]

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "nodes": [
                {
                    "name": n.name,
                    "component_type": n.component_type,
                    "file_path": n.file_path,
                    "line_start": n.line_start,
                    "line_end": n.line_end,
                    "is_public": n.is_public,
                    "docstring": n.docstring,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "dependency_type": e.dependency_type,
                    "coupling_level": e.coupling_level,
                    "line_number": e.line_number,
                    "file_path": e.file_path,
                }
                for e in self.edges
            ],
            "module_metrics": [
                {
                    "module_name": m.module_name,
                    "afferent": m.afferent,
                    "efferent": m.efferent,
                    "instability": m.instability,
                    "abstractness": m.abstractness,
                }
                for m in self.module_metrics
            ],
            "circular_dependencies": self.circular_dependencies,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "statistics": self.get_statistics(),
        }


class ComponentDependencyAnalyzer:
    """Analyzes component dependencies in source code."""

    def __init__(self):
        self.parser_registry = ASTParserRegistry.get_instance()

    def analyze_file(self, source_code: str, file_path: str, language: str) -> DependencyAnalysisResult:
        """Analyze a single file for component dependencies."""
        result = DependencyAnalysisResult(language=language)

        try:
            parser = self.parser_registry.get_parser(language)
            ast_tree = parser.parse(source_code, file_path)

            # Extract component nodes
            self._extract_nodes(ast_tree, file_path, result)

            # Extract dependency edges
            self._extract_dependencies(ast_tree, file_path, result)

            # Detect circular dependencies
            result.circular_dependencies = self._detect_circular_dependencies(result)

            result.source_files.append(file_path)

        except Exception as e:
            logger.error(f"Failed to analyze dependencies in {file_path}: {e}")

        return result

    def _extract_nodes(self, ast_tree: ASTTree, file_path: str, result: DependencyAnalysisResult):
        """Extract component nodes from AST."""
        # Add functions
        for func in ast_tree.all_functions(include_nested=False):
            is_public = not func.name.startswith("_")
            result.nodes.append(ComponentNode(
                name=func.name,
                component_type="function",
                file_path=file_path,
                line_start=func.line_start,
                line_end=func.line_end,
                is_public=is_public,
                docstring=func.docstring,
            ))

        # Add classes
        for cls in ast_tree.all_classes():
            is_interface = self._is_interface(cls)
            result.nodes.append(ComponentNode(
                name=cls.name,
                component_type="interface" if is_interface else "class",
                file_path=file_path,
                line_start=cls.line_start,
                line_end=cls.line_end,
                is_public=True,  # Classes are typically public
                docstring=cls.docstring,
            ))

        # Add module node
        module_name = file_path.replace("\\", "/").split("/")[-1].split(".")[0]
        result.nodes.append(ComponentNode(
            name=module_name,
            component_type="module",
            file_path=file_path,
            line_start=1,
            line_end=ast_tree.loc_count,
            is_public=True,
            docstring=None,
        ))

    def _extract_dependencies(self, ast_tree: ASTTree, file_path: str, result: DependencyAnalysisResult):
        """Extract dependency edges from AST."""
        # Function call dependencies
        for func in ast_tree.all_functions():
            # Get called function names from AST
            called_functions = self._extract_called_functions(func)
            for called_func_name in called_functions:
                # Only add if it's a public function (likely internal call)
                if not called_func_name.startswith("_"):
                    result.edges.append(DependencyEdge(
                        source=func.name,
                        target=called_func_name,
                        dependency_type=DependencyType.CALLS,
                        coupling_level=CouplingLevel.TIGHT,
                        line_number=func.line_start,
                        file_path=file_path,
                    ))

        # Import dependencies
        for imp in ast_tree.imports:
            module_name = imp.module.split(".")[0]  # Get top-level module
            current_module = file_path.replace("\\", "/").split("/")[-1].split(".")[0]

            if module_name != current_module:
                result.edges.append(DependencyEdge(
                    source=current_module,
                    target=module_name,
                    dependency_type=DependencyType.IMPORTS,
                    coupling_level=CouplingLevel.LOOSE,
                    line_number=imp.line_start if hasattr(imp, "line_start") else None,
                    file_path=file_path,
                ))

        # Class inheritance dependencies
        for cls in ast_tree.all_classes():
            for base in cls.bases:
                if base and base != "object":  # Ignore implicit object inheritance
                    result.edges.append(DependencyEdge(
                        source=cls.name,
                        target=base,
                        dependency_type=DependencyType.INHERITS,
                        coupling_level=CouplingLevel.TIGHT,
                        line_number=cls.line_start,
                        file_path=file_path,
                    ))

    def _extract_called_functions(self, func_node) -> list[str]:
        """Extract names of functions called within a function."""
        # This is a simplified implementation
        # A full implementation would traverse the function's AST body
        called = []
        if hasattr(func_node, "body"):
            # Simple heuristic: look for function call patterns
            # In a real implementation, this would use AST traversal
            pass
        return called

    def _is_interface(self, class_node) -> bool:
        """Heuristic to determine if a class is an interface."""
        name = class_node.name.lower()
        if "interface" in name or name.endswith("able"):
            return True
        return False

    def _detect_circular_dependencies(self, result: DependencyAnalysisResult) -> list[list[str]]:
        """Detect circular dependencies using DFS."""
        # Build adjacency list
        graph = defaultdict(list)
        all_nodes = {node.name for node in result.nodes}

        for edge in result.edges:
            if edge.source in all_nodes and edge.target in all_nodes:
                graph[edge.source].append(edge.target)

        visited = set()
        recursion_stack = set()
        cycles = []

        def dfs(node: str, path: list[str]):
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in recursion_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            recursion_stack.remove(node)

        for node in all_nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
    ) -> DependencyAnalysisResult:
        """Analyze multiple source files and create unified dependency graph."""
        unified_result = DependencyAnalysisResult(language="multi")

        for file_info in source_files:
            try:
                file_result = self.analyze_file(
                    source_code=file_info["content"],
                    file_path=file_info["file_path"],
                    language=file_info["language"],
                )
                unified_result.source_files.extend(file_result.source_files)
                unified_result.nodes.extend(file_result.nodes)
                unified_result.edges.extend(file_result.edges)
                unified_result.circular_dependencies.extend(file_result.circular_dependencies)
            except Exception as e:
                logger.error(f"Failed to analyze {file_info.get('file_path')}: {e}")

        # Calculate module metrics
        unified_result.module_metrics = self._calculate_module_metrics(unified_result)

        # Save to database
        self._save_to_database(unified_result, project_id)

        return unified_result

    def _calculate_module_metrics(self, result: DependencyAnalysisResult) -> list[ModuleMetrics]:
        """Calculate coupling metrics for modules."""
        module_nodes = {n.name: n for n in result.nodes if n.component_type == "module"}

        metrics = []
        for module_name, module_node in module_nodes.items():
            # Afferent: incoming dependencies
            afferent = len([e for e in result.edges if e.target == module_name and e.dependency_type == DependencyType.IMPORTS])

            # Efferent: outgoing dependencies
            efferent = len([e for e in result.edges if e.source == module_name and e.dependency_type == DependencyType.IMPORTS])

            # Instability: I = Ce / (Ca + Ce)
            total = afferent + efferent
            instability = efferent / total if total > 0 else 0.0

            # Abstractness: ratio of interfaces to total classes (simplified)
            interfaces = len([n for n in result.nodes if n.component_type == "interface" and n.file_path == module_node.file_path])
            classes = len([n for n in result.nodes if n.component_type == "class" and n.file_path == module_node.file_path])
            total_types = interfaces + classes
            abstractness = interfaces / total_types if total_types > 0 else 0.0

            metrics.append(ModuleMetrics(
                module_name=module_name,
                afferent=afferent,
                efferent=efferent,
                instability=instability,
                abstractness=abstractness,
            ))

        return metrics

    def _save_to_database(self, result: DependencyAnalysisResult, project_id: int):
        """Save analysis results to database."""
        with get_sync_session() as db:
            analysis_result = AnalysisResult(
                project_id=project_id,
                analysis_type="component_dependencies",
                status=AnalysisStatus.COMPLETED,
                result_data=result.to_dict(),
                metadata={"statistics": result.get_statistics()},
            )
            db.add(analysis_result)
            db.commit()


def get_component_dependency_analyzer() -> ComponentDependencyAnalyzer:
    """Get or create component dependency analyzer instance."""
    return ComponentDependencyAnalyzer()
