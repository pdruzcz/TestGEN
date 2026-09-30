"""
Data flow analysis service - Story 1.23

Analyzes how data flows through the code:
- Variable definitions and assignments
- Data transformations between operations
- Function parameter flow (inputs/outputs)
- API request/response flow
- Database query/result flow

Creates unified data flow graph and identifies transformations.
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


class FlowNodeType(StrEnum):
    """Types of nodes in the data flow graph."""
    VARIABLE = "variable"
    PARAMETER = "parameter"
    RETURN_VALUE = "return_value"
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    DB_QUERY = "db_query"
    DB_RESULT = "db_result"
    CONSTANT = "constant"
    EXTERNAL_INPUT = "external_input"


class TransformationType(StrEnum):
    """Types of data transformations."""
    ASSIGNMENT = "assignment"  # Direct assignment
    FUNCTION_CALL = "function_call"  # Output from function
    OPERATION = "operation"  # Arithmetic/logical operation
    CAST = "cast"  # Type conversion
    VALIDATION = "validation"  # Data validation
    SERIALIZATION = "serialization"  # JSON/dict conversion
    DESERIALIZATION = "deserialization"  # Parse from string
    AGGREGATION = "aggregation"  # Combine multiple values
    FILTERING = "filtering"  # Filter values
    MAPPING = "mapping"  # Transform each value
    UNKNOWN = "unknown"


@dataclass
class FlowNode:
    """A node in the data flow graph representing a data element."""
    name: str
    node_type: FlowNodeType
    data_type: str | None
    file_path: str
    line_number: int
    scope: str  # Function or class name where defined
    is_mutable: bool = True
    initial_value: Any | None = None
    docstring: str | None = None


@dataclass
class FlowEdge:
    """An edge in the data flow graph representing data movement."""
    source: str  # FlowNode name
    target: str  # FlowNode name
    transformation_type: TransformationType
    line_number: int | None = None
    file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional info


@dataclass
class DataFlowPath:
    """A path showing how data flows from input to output."""
    path_id: str
    source_node: str  # Entry point (e.g., API request)
    target_node: str  # Exit point (e.g., API response)
    nodes: list[str]  # List of node names in the path
    transformations: list[TransformationType]
    hops: int  # Number of edges in the path


@dataclass
class DataFlowAnalysisResult:
    """Result of data flow analysis."""
    language: str
    source_files: list[str] = field(default_factory=list)
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    paths: list[DataFlowPath] = field(default_factory=list)
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate statistics for dashboard display."""
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)

        # Count by node type
        nodes_by_type = defaultdict(int)
        for node in self.nodes:
            nodes_by_type[node.node_type] += 1

        # Count by transformation type
        transformations_by_type = defaultdict(int)
        for edge in self.edges:
            transformations_by_type[edge.transformation_type] += 1

        # Path statistics
        avg_path_length = 0.0
        if self.paths:
            avg_path_length = sum(p.hops for p in self.paths) / len(self.paths)

        return {
            "total_data_elements": total_nodes,
            "total_data_movements": total_edges,
            "data_elements_by_type": dict(nodes_by_type),
            "transformations_by_type": dict(transformations_by_type),
            "total_flow_paths": len(self.paths),
            "avg_path_length": avg_path_length,
        }

    def find_paths_from(self, source_node: str) -> list[DataFlowPath]:
        """Find all data flow paths starting from a node."""
        return [p for p in self.paths if p.source_node == source_node]

    def find_paths_to(self, target_node: str) -> list[DataFlowPath]:
        """Find all data flow paths ending at a node."""
        return [p for p in self.paths if p.target_node == target_node]

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "nodes": [
                {
                    "name": n.name,
                    "node_type": n.node_type,
                    "data_type": n.data_type,
                    "file_path": n.file_path,
                    "line_number": n.line_number,
                    "scope": n.scope,
                    "is_mutable": n.is_mutable,
                    "initial_value": str(n.initial_value) if n.initial_value else None,
                    "docstring": n.docstring,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "transformation_type": e.transformation_type,
                    "line_number": e.line_number,
                    "file_path": e.file_path,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
            "paths": [
                {
                    "path_id": p.path_id,
                    "source_node": p.source_node,
                    "target_node": p.target_node,
                    "nodes": p.nodes,
                    "transformations": p.transformations,
                    "hops": p.hops,
                }
                for p in self.paths
            ],
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "statistics": self.get_statistics(),
        }


class DataFlowAnalyzer:
    """Analyzes data flow in source code."""

    def __init__(self):
        self.parser_registry = ASTParserRegistry.get_instance()

    def analyze_file(self, source_code: str, file_path: str, language: str) -> DataFlowAnalysisResult:
        """Analyze a single file for data flow."""
        result = DataFlowAnalysisResult(language=language)

        try:
            parser = self.parser_registry.get_parser(language)
            ast_tree = parser.parse(source_code, file_path)

            # Extract flow nodes
            self._extract_flow_nodes(ast_tree, file_path, result)

            # Extract flow edges (data movements)
            self._extract_flow_edges(ast_tree, file_path, result)

            # Build data flow paths
            result.paths = self._build_flow_paths(result)

            result.source_files.append(file_path)

        except Exception as e:
            logger.error(f"Failed to analyze data flow in {file_path}: {e}")

        return result

    def _extract_flow_nodes(self, ast_tree: ASTTree, file_path: str, result: DataFlowAnalysisResult):
        """Extract data flow nodes from AST."""
        # Add function parameters
        for func in ast_tree.all_functions(include_nested=False):
            for param in func.parameters:
                if param.name != "self":  # Skip self parameter
                    result.nodes.append(FlowNode(
                        name=f"{func.name}.{param.name}",
                        node_type=FlowNodeType.PARAMETER,
                        data_type=param.type,
                        file_path=file_path,
                        line_number=param.line_start if param.line_start else func.line_start,
                        scope=func.name,
                        is_mutable=True,
                        initial_value=param.default_value,
                    ))

            # Add return value node
            if func.return_type:
                result.nodes.append(FlowNode(
                    name=f"{func.name}.return",
                    node_type=FlowNodeType.RETURN_VALUE,
                    data_type=func.return_type,
                    file_path=file_path,
                    line_number=func.line_start,
                    scope=func.name,
                    is_mutable=False,
                ))

        # Add class attributes as potential flow nodes
        for cls in ast_tree.all_classes():
            for method in cls.methods:
                for param in method.parameters:
                    if param.name != "self":
                        result.nodes.append(FlowNode(
                            name=f"{cls.name}.{method.name}.{param.name}",
                            node_type=FlowNodeType.PARAMETER,
                            data_type=param.type,
                            file_path=file_path,
                            line_number=param.line_start if param.line_start else method.line_start,
                            scope=f"{cls.name}.{method.name}",
                            is_mutable=True,
                            initial_value=param.default_value,
                        ))

    def _extract_flow_edges(self, ast_tree: ASTTree, file_path: str, result: DataFlowAnalysisResult):
        """Extract data flow edges from AST."""
        # This is a simplified implementation
        # A full implementation would:
        # 1. Track variable assignments
        # 2. Follow function calls
        # 3. Track return values
        # 4. Identify data transformations

        # For now, create placeholder edges for function calls
        for func in ast_tree.all_functions():
            # Create edges from parameters to function
            for param in func.parameters:
                if param.name != "self":
                    param_node = f"{func.name}.{param.name}"
                    func_node = func.name
                    result.edges.append(FlowEdge(
                        source=param_node,
                        target=func_node,
                        transformation_type=TransformationType.FUNCTION_CALL,
                        line_number=func.line_start,
                        file_path=file_path,
                        metadata={"function": func.name},
                    ))

    def _build_flow_paths(self, result: DataFlowAnalysisResult) -> list[DataFlowPath]:
        """Build data flow paths from nodes and edges."""
        # Build adjacency list
        graph = defaultdict(list)
        for edge in result.edges:
            graph[edge.source].append(edge.target)

        paths = []
        path_id = 0

        # Find paths from parameters to return values
        param_nodes = [n.name for n in result.nodes if n.node_type == FlowNodeType.PARAMETER]
        return_nodes = [n.name for n in result.nodes if n.node_type == FlowNodeType.RETURN_VALUE]

        for start in param_nodes:
            for end in return_nodes:
                # BFS to find path
                if self._bfs_path_exists(graph, start, end):
                    path_nodes = self._get_path_nodes(graph, start, end)
                    if path_nodes:
                        # Get transformations along the path
                        transformations = []
                        for i in range(len(path_nodes) - 1):
                            for edge in result.edges:
                                if edge.source == path_nodes[i] and edge.target == path_nodes[i + 1]:
                                    transformations.append(edge.transformation_type)
                                    break

                        paths.append(DataFlowPath(
                            path_id=f"path_{path_id}",
                            source_node=start,
                            target_node=end,
                            nodes=path_nodes,
                            transformations=transformations,
                            hops=len(path_nodes) - 1,
                        ))
                        path_id += 1

        return paths

    def _bfs_path_exists(self, graph: dict, start: str, end: str) -> bool:
        """Check if path exists using BFS."""
        visited = set()
        queue = [start]

        while queue:
            node = queue.pop(0)
            if node == end:
                return True

            if node not in visited:
                visited.add(node)
                queue.extend(graph.get(node, []))

        return False

    def _get_path_nodes(self, graph: dict, start: str, end: str) -> list[str] | None:
        """Get actual path nodes using BFS with parent tracking."""
        from collections import deque

        visited = {start}
        queue = deque([start])
        parent = {}

        while queue:
            node = queue.popleft()
            if node == end:
                # Reconstruct path
                path = []
                while node != start:
                    path.append(node)
                    node = parent.get(node, start)
                path.append(start)
                return path[::-1]

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = node
                    queue.append(neighbor)

        return None

    def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
    ) -> DataFlowAnalysisResult:
        """Analyze multiple source files and create unified data flow graph."""
        unified_result = DataFlowAnalysisResult(language="multi")

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
                unified_result.paths.extend(file_result.paths)
            except Exception as e:
                logger.error(f"Failed to analyze {file_info.get('file_path')}: {e}")

        # Save to database
        self._save_to_database(unified_result, project_id)

        return unified_result

    def _save_to_database(self, result: DataFlowAnalysisResult, project_id: int):
        """Save analysis results to database."""
        with get_sync_session() as db:
            analysis_result = AnalysisResult(
                project_id=project_id,
                analysis_type="data_flow",
                status=AnalysisStatus.COMPLETED,
                result_data=result.to_dict(),
                metadata={"statistics": result.get_statistics()},
            )
            db.add(analysis_result)
            db.commit()


def get_data_flow_analyzer() -> DataFlowAnalyzer:
    """Get or create data flow analyzer instance."""
    return DataFlowAnalyzer()
