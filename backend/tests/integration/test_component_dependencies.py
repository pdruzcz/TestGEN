"""Tests for component dependency analysis service - Story 1.22"""

import pytest

from app.services.analysis.component_dependencies import (
    ComponentDependencyAnalyzer,
    ComponentNode,
    CouplingLevel,
    DependencyAnalysisResult,
    DependencyEdge,
    DependencyType,
    ModuleMetrics,
)


class TestDependencyType:
    """Test DependencyType enum."""

    def test_dependency_types(self):
        """Test all dependency types exist."""
        assert DependencyType.CALLS == "calls"
        assert DependencyType.IMPORTS == "imports"
        assert DependencyType.INHERITS == "inherits"
        assert DependencyType.IMPLEMENTS == "implements"
        assert DependencyType.COMPOSES == "composes"
        assert DependencyType.USES == "uses"


class TestCouplingLevel:
    """Test CouplingLevel enum."""

    def test_coupling_levels(self):
        """Test all coupling levels exist."""
        assert CouplingLevel.TIGHT == "tight"
        assert CouplingLevel.LOOSE == "loose"
        assert CouplingLevel.NONE == "none"


class TestComponentNode:
    """Test ComponentNode dataclass."""

    def test_component_creation(self):
        """Test creating a component node."""
        node = ComponentNode(
            name="UserService",
            component_type="class",
            file_path="services/user.py",
            line_start=10,
            line_end=50,
            is_public=True,
            docstring="Service for user operations",
        )
        assert node.name == "UserService"
        assert node.component_type == "class"
        assert node.is_public is True


class TestDependencyEdge:
    """Test DependencyEdge dataclass."""

    def test_edge_creation(self):
        """Test creating a dependency edge."""
        edge = DependencyEdge(
            source="OrderController",
            target="UserService",
            dependency_type=DependencyType.CALLS,
            coupling_level=CouplingLevel.TIGHT,
            line_number=25,
            file_path="controllers/order.py",
        )
        assert edge.source == "OrderController"
        assert edge.target == "UserService"
        assert edge.dependency_type == DependencyType.CALLS


class TestModuleMetrics:
    """Test ModuleMetrics dataclass."""

    def test_metrics_creation(self):
        """Test creating module metrics."""
        metrics = ModuleMetrics(
            module_name="user_service",
            afferent=5,  # 5 other modules depend on this
            efferent=2,  # This module depends on 2 others
            instability=0.286,  # Ce / (Ca + Ce) = 2 / 7
            abstractness=0.4,  # 40% abstract types
        )
        assert metrics.module_name == "user_service"
        assert metrics.afferent == 5
        assert metrics.efferent == 2
        assert 0 < metrics.instability < 1


class TestDependencyAnalysisResult:
    """Test DependencyAnalysisResult dataclass."""

    def test_empty_result(self):
        """Test creating empty result."""
        result = DependencyAnalysisResult(language="python")
        assert result.language == "python"
        assert len(result.nodes) == 0
        assert len(result.edges) == 0
        assert len(result.circular_dependencies) == 0

    def test_result_statistics(self):
        """Test statistics calculation."""
        result = DependencyAnalysisResult(language="python")

        result.nodes = [
            ComponentNode(
                name="UserController",
                component_type="class",
                file_path="controllers.py",
                line_start=1,
                line_end=20,
                is_public=True,
            ),
            ComponentNode(
                name="UserService",
                component_type="class",
                file_path="services.py",
                line_start=1,
                line_end=30,
                is_public=True,
            ),
        ]

        result.edges = [
            DependencyEdge(
                source="UserController",
                target="UserService",
                dependency_type=DependencyType.CALLS,
                coupling_level=CouplingLevel.TIGHT,
                file_path="controllers.py",
            ),
            DependencyEdge(
                source="controllers",
                target="services",
                dependency_type=DependencyType.IMPORTS,
                coupling_level=CouplingLevel.LOOSE,
                file_path="controllers.py",
            ),
        ]

        stats = result.get_statistics()

        assert stats["total_components"] == 2
        assert stats["total_dependencies"] == 2
        assert stats["components_by_type"]["class"] == 2
        assert stats["dependencies_by_type"]["calls"] == 1
        assert stats["dependencies_by_type"]["imports"] == 1
        assert stats["tight_coupling_count"] == 1
        assert stats["loose_coupling_count"] == 1

    def test_get_dependencies_for(self):
        """Test getting outgoing dependencies for a component."""
        result = DependencyAnalysisResult(language="python")

        result.edges = [
            DependencyEdge(
                source="OrderController",
                target="UserService",
                dependency_type=DependencyType.CALLS,
                coupling_level=CouplingLevel.TIGHT,
            ),
            DependencyEdge(
                source="OrderController",
                target="ProductService",
                dependency_type=DependencyType.CALLS,
                coupling_level=CouplingLevel.TIGHT,
            ),
        ]

        deps = result.get_dependencies_for("OrderController")
        assert len(deps) == 2
        assert all(e.source == "OrderController" for e in deps)

    def test_get_dependents(self):
        """Test getting incoming dependencies (dependents) for a component."""
        result = DependencyAnalysisResult(language="python")

        result.edges = [
            DependencyEdge(
                source="OrderController",
                target="UserService",
                dependency_type=DependencyType.CALLS,
                coupling_level=CouplingLevel.TIGHT,
            ),
            DependencyEdge(
                source="ProductController",
                target="UserService",
                dependency_type=DependencyType.CALLS,
                coupling_level=CouplingLevel.TIGHT,
            ),
        ]

        dependents = result.get_dependents("UserService")
        assert len(dependents) == 2
        assert all(e.target == "UserService" for e in dependents)

    def test_to_dict_serialization(self):
        """Test result can be serialized to dict."""
        result = DependencyAnalysisResult(language="python")
        result.source_files = ["services.py"]
        result.nodes = [
            ComponentNode(
                name="UserService",
                component_type="class",
                file_path="services.py",
                line_start=1,
                line_end=30,
                is_public=True,
            )
        ]

        data = result.to_dict()

        assert data["language"] == "python"
        assert "services.py" in data["source_files"]
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["name"] == "UserService"
        assert data["statistics"]["total_components"] == 1


class TestComponentDependencyAnalyzer:
    """Test component dependency analyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized."""
        analyzer = ComponentDependencyAnalyzer()
        assert analyzer.parser_registry is not None

    def test_analyze_python_code(self):
        """Test analyzing Python code for dependencies."""
        analyzer = ComponentDependencyAnalyzer()

        source_code = """
import os
import sys
from typing import List

from app.utils import helper_function

class BaseController:
    '''Base controller with common methods.'''

class UserController(BaseController):
    def list_users(self) -> List[str]:
        return helper_function()

def main():
    controller = UserController()
    controller.list_users()
"""

        result = analyzer.analyze_file(source_code, "app.py", "python")

        assert result.language == "python"
        # Should extract component nodes
        assert len(result.nodes) > 0
        # Should have module node
        assert any(n.component_type == "module" for n in result.nodes)
        # Should have class nodes
        assert any(n.component_type == "class" for n in result.nodes)

    def test_analyze_inheritance_dependencies(self):
        """Test analyzing inheritance dependencies."""
        analyzer = ComponentDependencyAnalyzer()

        source_code = """
class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof!"

class Cat(Animal):
    def speak(self):
        return "Meow!"
"""

        result = analyzer.analyze_file(source_code, "animals.py", "python")

        # Should find inheritance edges
        inherit_edges = [e for e in result.edges if e.dependency_type == DependencyType.INHERITS]
        assert len(inherit_edges) >= 2  # Dog -> Animal, Cat -> Animal

        # Check inheritance relationships
        dog_inherits = [e for e in inherit_edges if e.source == "Dog"]
        assert len(dog_inherits) == 1
        assert dog_inherits[0].target == "Animal"

    def test_analyze_import_dependencies(self):
        """Test analyzing import dependencies."""
        analyzer = ComponentDependencyAnalyzer()

        source_code = """
import os
from typing import List, Dict
from collections import defaultdict

def process_items(items: List[str]) -> Dict:
    return defaultdict(list)
"""

        result = analyzer.analyze_file(source_code, "utils.py", "python")

        # Should find import edges
        import_edges = [e for e in result.edges if e.dependency_type == DependencyType.IMPORTS]
        assert len(import_edges) >= 1

    def test_detect_circular_dependencies(self):
        """Test circular dependency detection."""
        analyzer = ComponentDependencyAnalyzer()

        # Create a result with circular dependencies
        result = DependencyAnalysisResult(language="python")
        result.nodes = [
            ComponentNode(name="A", component_type="module", file_path="a.py", line_start=1, line_end=10),
            ComponentNode(name="B", component_type="module", file_path="b.py", line_start=1, line_end=10),
            ComponentNode(name="C", component_type="module", file_path="c.py", line_start=1, line_end=10),
        ]
        result.edges = [
            DependencyEdge(source="A", target="B", dependency_type=DependencyType.IMPORTS, coupling_level=CouplingLevel.LOOSE),
            DependencyEdge(source="B", target="C", dependency_type=DependencyType.IMPORTS, coupling_level=CouplingLevel.LOOSE),
            DependencyEdge(source="C", target="A", dependency_type=DependencyType.IMPORTS, coupling_level=CouplingLevel.LOOSE),
        ]

        analyzer._extract_nodes = lambda *args: None
        analyzer._extract_dependencies = lambda *args: None

        circular = analyzer._detect_circular_dependencies(result)

        assert len(circular) >= 1
        # The cycle should be A -> B -> C -> A (or similar)
        assert any("A" in cycle and "B" in cycle and "C" in cycle for cycle in circular)

    def test_calculate_module_metrics(self):
        """Test module metrics calculation."""
        analyzer = ComponentDependencyAnalyzer()

        result = DependencyAnalysisResult(language="python")

        # Add module nodes and edges
        result.nodes = [
            ComponentNode(name="user_service", component_type="module", file_path="user_service.py", line_start=1, line_end=100),
            ComponentNode(name="order_service", component_type="module", file_path="order_service.py", line_start=1, line_end=100),
            ComponentNode(name="product_service", component_type="module", file_path="product_service.py", line_start=1, line_end=100),
            ComponentNode(name="IUserRepository", component_type="interface", file_path="user_service.py", line_start=10, line_end=20, is_public=True),
            ComponentNode(name="UserRepository", component_type="class", file_path="user_service.py", line_start=30, line_end=100, is_public=True),
        ]

        result.edges = [
            # order_service depends on user_service and product_service (outgoing)
            DependencyEdge(source="order_service", target="user_service", dependency_type=DependencyType.IMPORTS, coupling_level=CouplingLevel.LOOSE),
            DependencyEdge(source="order_service", target="product_service", dependency_type=DependencyType.IMPORTS, coupling_level=CouplingLevel.LOOSE),
            # user_service is depended on by order_service (incoming)
            DependencyEdge(source="order_service", target="user_service", dependency_type=DependencyType.IMPORTS, coupling_level=CouplingLevel.LOOSE),
        ]

        metrics = analyzer._calculate_module_metrics(result)

        # Should have metrics for each module
        assert len(metrics) >= 1

        # Check user_service metrics (Ca=1, Ce=0, I=0)
        user_metrics = next((m for m in metrics if m.module_name == "user_service"), None)
        assert user_metrics is not None
        assert user_metrics.afferent >= 1  # At least order_service depends on it

    def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple files."""
        analyzer = ComponentDependencyAnalyzer()

        source_files = [
            {
                "file_path": "services/user_service.py",
                "content": """
class UserService:
    def get_user(self, user_id: int):
        return {"id": user_id}
""",
                "language": "python",
            },
            {
                "file_path": "controllers/user_controller.py",
                "content": """
from services.user_service import UserService

class UserController:
    def __init__(self):
        self.service = UserService()

    def handle_get(self, user_id: int):
        return self.service.get_user(user_id)
""",
                "language": "python",
            },
        ]

        # Analyze without database save
        unified_result = DependencyAnalysisResult(language="multi")
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
