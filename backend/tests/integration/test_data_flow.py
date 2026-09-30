"""Tests for data flow analysis service - Story 1.23"""

import pytest

from app.services.analysis.data_flow import (
    DataFlowAnalysisResult,
    DataFlowAnalyzer,
    DataFlowPath,
    FlowEdge,
    FlowNode,
    FlowNodeType,
    TransformationType,
)


class TestFlowNodeType:
    """Test FlowNodeType enum."""

    def test_flow_node_types(self):
        """Test all flow node types exist."""
        assert FlowNodeType.VARIABLE == "variable"
        assert FlowNodeType.PARAMETER == "parameter"
        assert FlowNodeType.RETURN_VALUE == "return_value"
        assert FlowNodeType.API_REQUEST == "api_request"
        assert FlowNodeType.API_RESPONSE == "api_response"
        assert FlowNodeType.DB_QUERY == "db_query"
        assert FlowNodeType.DB_RESULT == "db_result"
        assert FlowNodeType.CONSTANT == "constant"
        assert FlowNodeType.EXTERNAL_INPUT == "external_input"


class TestTransformationType:
    """Test TransformationType enum."""

    def test_transformation_types(self):
        """Test all transformation types exist."""
        assert TransformationType.ASSIGNMENT == "assignment"
        assert TransformationType.FUNCTION_CALL == "function_call"
        assert TransformationType.OPERATION == "operation"
        assert TransformationType.CAST == "cast"
        assert TransformationType.VALIDATION == "validation"
        assert TransformationType.SERIALIZATION == "serialization"
        assert TransformationType.DESERIALIZATION == "deserialization"
        assert TransformationType.AGGREGATION == "aggregation"
        assert TransformationType.FILTERING == "filtering"
        assert TransformationType.MAPPING == "mapping"
        assert TransformationType.UNKNOWN == "unknown"


class TestFlowNode:
    """Test FlowNode dataclass."""

    def test_node_creation(self):
        """Test creating a flow node."""
        node = FlowNode(
            name="user_id",
            node_type=FlowNodeType.PARAMETER,
            data_type="int",
            file_path="users.py",
            line_number=10,
            scope="get_user",
            is_mutable=False,
            initial_value=None,
            docstring="User ID parameter",
        )
        assert node.name == "user_id"
        assert node.node_type == FlowNodeType.PARAMETER
        assert node.data_type == "int"
        assert node.is_mutable is False


class TestFlowEdge:
    """Test FlowEdge dataclass."""

    def test_edge_creation(self):
        """Test creating a flow edge."""
        edge = FlowEdge(
            source="user_id",
            target="db_query",
            transformation_type=TransformationType.FUNCTION_CALL,
            line_number=15,
            file_path="users.py",
            metadata={"function": "get_user"},
        )
        assert edge.source == "user_id"
        assert edge.target == "db_query"
        assert edge.transformation_type == TransformationType.FUNCTION_CALL


class TestDataFlowPath:
    """Test DataFlowPath dataclass."""

    def test_path_creation(self):
        """Test creating a data flow path."""
        path = DataFlowPath(
            path_id="path_1",
            source_node="user_id",
            target_node="user_response",
            nodes=["user_id", "db_query", "user_response"],
            transformations=[TransformationType.FUNCTION_CALL, TransformationType.SERIALIZATION],
            hops=2,
        )
        assert path.path_id == "path_1"
        assert path.source_node == "user_id"
        assert path.target_node == "user_response"
        assert path.hops == 2
        assert len(path.transformations) == 2


class TestDataFlowAnalysisResult:
    """Test DataFlowAnalysisResult dataclass."""

    def test_empty_result(self):
        """Test creating empty result."""
        result = DataFlowAnalysisResult(language="python")
        assert result.language == "python"
        assert len(result.nodes) == 0
        assert len(result.edges) == 0
        assert len(result.paths) == 0

    def test_result_statistics(self):
        """Test statistics calculation."""
        result = DataFlowAnalysisResult(language="python")

        result.nodes = [
            FlowNode(
                name="request_data",
                node_type=FlowNodeType.API_REQUEST,
                data_type="dict",
                file_path="api.py",
                line_number=10,
                scope="handle_request",
            ),
            FlowNode(
                name="user_id",
                node_type=FlowNodeType.PARAMETER,
                data_type="int",
                file_path="api.py",
                line_number=10,
                scope="handle_request",
            ),
        ]

        result.edges = [
            FlowEdge(
                source="request_data",
                target="user_id",
                transformation_type=TransformationType.VALIDATION,
                file_path="api.py",
            ),
        ]

        stats = result.get_statistics()

        assert stats["total_data_elements"] == 2
        assert stats["total_data_movements"] == 1
        assert stats["data_elements_by_type"]["api_request"] == 1
        assert stats["data_elements_by_type"]["parameter"] == 1
        assert stats["transformations_by_type"]["validation"] == 1

    def test_find_paths_from(self):
        """Test finding paths from a source node."""
        result = DataFlowAnalysisResult(language="python")

        result.paths = [
            DataFlowPath(
                path_id="path_1",
                source_node="input",
                target_node="output",
                nodes=["input", "output"],
                transformations=[],
                hops=1,
            ),
            DataFlowPath(
                path_id="path_2",
                source_node="input",
                target_node="result",
                nodes=["input", "result"],
                transformations=[],
                hops=1,
            ),
        ]

        paths_from_input = result.find_paths_from("input")
        assert len(paths_from_input) == 2

    def test_find_paths_to(self):
        """Test finding paths to a target node."""
        result = DataFlowAnalysisResult(language="python")

        result.paths = [
            DataFlowPath(
                path_id="path_1",
                source_node="input1",
                target_node="output",
                nodes=["input1", "output"],
                transformations=[],
                hops=1,
            ),
            DataFlowPath(
                path_id="path_2",
                source_node="input2",
                target_node="output",
                nodes=["input2", "output"],
                transformations=[],
                hops=1,
            ),
        ]

        paths_to_output = result.find_paths_to("output")
        assert len(paths_to_output) == 2

    def test_to_dict_serialization(self):
        """Test result can be serialized to dict."""
        result = DataFlowAnalysisResult(language="python")
        result.source_files = ["api.py"]
        result.nodes = [
            FlowNode(
                name="request",
                node_type=FlowNodeType.API_REQUEST,
                data_type="dict",
                file_path="api.py",
                line_number=10,
                scope="handle",
            )
        ]

        data = result.to_dict()

        assert data["language"] == "python"
        assert "api.py" in data["source_files"]
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["name"] == "request"
        assert data["statistics"]["total_data_elements"] == 1


class TestDataFlowAnalyzer:
    """Test data flow analyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized."""
        analyzer = DataFlowAnalyzer()
        assert analyzer.parser_registry is not None

    def test_analyze_python_function(self):
        """Test analyzing Python function data flow."""
        analyzer = DataFlowAnalyzer()

        source_code = """
def get_user(user_id: int) -> dict:
    '''Get user by ID.'''
    # Query database
    user = db.query(User).get(user_id)
    return user.to_dict()
"""

        result = analyzer.analyze_file(source_code, "users.py", "python")

        assert result.language == "python"
        # Should extract parameter node
        param_nodes = [n for n in result.nodes if n.node_type == FlowNodeType.PARAMETER]
        assert len(param_nodes) >= 1
        # Should extract return value node
        return_nodes = [n for n in result.nodes if n.node_type == FlowNodeType.RETURN_VALUE]
        assert len(return_nodes) >= 1

    def test_analyze_class_method(self):
        """Test analyzing class method data flow."""
        analyzer = DataFlowAnalyzer()

        source_code = """
class UserService:
    def create_user(self, name: str, email: str) -> User:
        '''Create a new user.'''
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
        return user
"""

        result = analyzer.analyze_file(source_code, "services.py", "python")

        assert result.language == "python"
        # Should extract class method parameters (excluding self)
        param_nodes = [n for n in result.nodes if n.node_type == FlowNodeType.PARAMETER and n.scope.startswith("UserService")]
        assert len(param_nodes) >= 2  # name and email

    def test_analyze_multiple_functions(self):
        """Test analyzing multiple functions with data flow."""
        analyzer = DataFlowAnalyzer()

        source_code = """
def validate_input(data: dict) -> bool:
    '''Validate input data.'''
    return 'name' in data and 'email' in data

def process_request(data: dict) -> dict:
    '''Process API request.'''
    if not validate_input(data):
        raise ValueError('Invalid input')

    result = transform_data(data)
    return result

def transform_data(data: dict) -> dict:
    '''Transform data for response.'''
    return {'processed': True, 'data': data}
"""

        result = analyzer.analyze_file(source_code, "api.py", "python")

        assert result.language == "python"
        # Should have multiple parameter nodes
        param_nodes = [n for n in result.nodes if n.node_type == FlowNodeType.PARAMETER]
        assert len(param_nodes) >= 3  # validate_input.data, process_request.data, transform_data.data
        # Should have return value nodes
        return_nodes = [n for n in result.nodes if n.node_type == FlowNodeType.RETURN_VALUE]
        assert len(return_nodes) >= 3

    def test_build_flow_paths(self):
        """Test building flow paths between nodes."""
        analyzer = DataFlowAnalyzer()

        # Create a mock result with known paths
        result = DataFlowAnalysisResult(language="python")
        result.nodes = [
            FlowNode(name="func.param", node_type=FlowNodeType.PARAMETER, data_type="int", file_path="test.py", line_number=1, scope="func"),
            FlowNode(name="func.return", node_type=FlowNodeType.RETURN_VALUE, data_type="int", file_path="test.py", line_number=1, scope="func"),
        ]
        result.edges = [
            FlowEdge(
                source="func.param",
                target="func.return",
                transformation_type=TransformationType.FUNCTION_CALL,
                file_path="test.py",
            ),
        ]

        paths = analyzer._build_flow_paths(result)

        # Should find at least one path
        assert len(paths) >= 1
        if paths:
            assert paths[0].source_node == "func.param"
            assert paths[0].target_node == "func.return"

    def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple files."""
        analyzer = DataFlowAnalyzer()

        source_files = [
            {
                "file_path": "services/user_service.py",
                "content": """
class UserService:
    def get_user(self, user_id: int) -> dict:
        return {'id': user_id, 'name': 'Test'}
""",
                "language": "python",
            },
            {
                "file_path": "controllers/user_controller.py",
                "content": """
def handle_get(user_id: int) -> dict:
    '''Handle user GET request.'''
    service = UserService()
    return service.get_user(user_id)
""",
                "language": "python",
            },
        ]

        # Analyze without database save
        unified_result = DataFlowAnalysisResult(language="multi")
        for file_info in source_files:
            file_result = analyzer.analyze_file(
                source_code=file_info["content"],
                file_path=file_info["file_path"],
                language=file_info["language"],
            )
            unified_result.source_files.extend(file_result.source_files)
            unified_result.nodes.extend(file_result.nodes)
            unified_result.edges.extend(file_result.edges)

        assert unified_result.language == "multi"
        assert len(unified_result.source_files) == 2
        # Should have nodes from both files
        assert len(unified_result.nodes) > 0
