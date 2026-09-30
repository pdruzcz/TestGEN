"""Tests for native (deterministic) code analysis service - Story 1.25"""

import pytest

from app.services.analysis.native_analysis import (
    NativeAnalysisOrchestrator,
    NativeAnalysisResult,
)


class TestNativeAnalysisResult:
    """Test NativeAnalysisResult dataclass."""

    def test_empty_result(self):
        """Test creating empty result."""
        result = NativeAnalysisResult(language="python")
        assert result.language == "python"
        assert len(result.source_files) == 0
        assert result.logic_structures is None
        assert result.entry_points is None

    def test_statistics_with_partial_results(self):
        """Test statistics calculation with only some analyzers run."""
        result = NativeAnalysisResult(language="python")

        # Mock logic structures result
        from app.services.analysis.logic_structures import CodeStructureCatalog

        result.logic_structures = CodeStructureCatalog(language="python")
        result.logic_structures.total_functions = 10
        result.logic_structures.total_classes = 2

        stats = result.get_statistics()

        assert stats["language"] == "python"
        assert "logic_structures" in stats
        assert stats["logic_structures"]["total_functions"] == 10

    def test_combined_metrics(self):
        """Test combined metrics calculation."""
        result = NativeAnalysisResult(language="python")

        # Mock results
        from app.services.analysis.logic_structures import CodeStructureCatalog
        from app.services.analysis.entry_points import EntryPointCatalog

        result.logic_structures = CodeStructureCatalog(language="python")
        result.logic_structures.total_functions = 10
        result.logic_structures.total_classes = 2

        result.entry_points = EntryPointCatalog(language="python")
        result.entry_points.endpoints = []
        result.entry_points.framework_detected = True

        metrics = result.get_combined_metrics()

        assert metrics["total_functions"] == 10
        assert metrics["total_classes"] == 2
        assert metrics["framework_detected"] is True


class TestNativeAnalysisOrchestrator:
    """Test native analysis orchestrator."""

    def test_orchestrator_initialization(self):
        """Test orchestrator can be initialized."""
        orchestrator = NativeAnalysisOrchestrator()
        assert orchestrator.parser_registry is not None
        assert orchestrator.logic_analyzer is not None
        assert orchestrator.entry_points_analyzer is not None
        assert orchestrator.dependencies_analyzer is not None
        assert orchestrator.data_flow_analyzer is not None
        assert orchestrator.business_logic_analyzer is not None

    def test_get_available_analyzers(self):
        """Test getting list of available analyzers."""
        orchestrator = NativeAnalysisOrchestrator()
        analyzers = orchestrator.get_available_analyzers()

        expected = ["logic_structures", "entry_points", "dependencies", "data_flow", "business_logic"]
        for analyzer in expected:
            assert analyzer in analyzers

    def test_analyze_file_all_analyzers(self):
        """Test analyzing a file with all analyzers."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
class UserService:
    '''Service for user operations.'''

    def get_user(self, user_id: int) -> dict:
        '''Get user by ID.'''
        user = db.query(User).get(user_id)
        return user.to_dict()

    def create_user(self, name: str, email: str) -> dict:
        '''Create a new user.'''
        if not self.validate_email(email):
            raise ValueError('Invalid email')
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
        return user.to_dict()
"""

        result = orchestrator.analyze_file(source_code, "user_service.py", "python")

        assert result.language == "python"
        assert len(result.source_files) >= 1

        # Check that all analyzers produced results
        assert result.logic_structures is not None
        assert result.entry_points is not None
        assert result.dependencies is not None
        assert result.data_flow is not None
        assert result.business_logic is not None

    def test_analyze_file_selective_analyzers(self):
        """Test analyzing with only specific analyzers."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
def hello_world():
    '''A simple function.'''
    print("Hello, World!")
"""

        result = orchestrator.analyze_file(
            source_code,
            "hello.py",
            "python",
            analyzers=["logic_structures", "entry_points"],
        )

        assert result.language == "python"
        assert result.logic_structures is not None
        assert result.entry_points is not None
        # Other analyzers should be None
        assert result.dependencies is None
        assert result.data_flow is None
        assert result.business_logic is None

    def test_analyze_file_logic_structures(self):
        """Test that logic structures analyzer produces results."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
class OrderService:
    def create_order(self, user_id: int, items: list) -> Order:
        '''Create a new order.'''
        order = Order(user_id=user_id)
        for item in items:
            order.add_item(item)
        order.save()
        return order

    def cancel_order(self, order_id: int):
        '''Cancel an order.'''
        order = Order.get(order_id)
        order.status = "cancelled"
        order.save()
"""

        result = orchestrator.analyze_file(
            source_code,
            "order_service.py",
            "python",
            analyzers=["logic_structures"],
        )

        assert result.logic_structures is not None
        assert len(result.logic_structures.classes) >= 1
        # Check class has methods
        order_service = next((c for c in result.logic_structures.classes if c.name == "OrderService"), None)
        assert order_service is not None
        assert len(order_service.methods) >= 2

    def test_analyze_file_entry_points(self):
        """Test that entry points analyzer produces results."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
def list_users():
    '''List all users.'''
    return []

def get_user(user_id: int):
    '''Get user by ID.'''
    return {"id": user_id}

def main():
    '''Main entry point.'''
    app.run()
"""

        result = orchestrator.analyze_file(
            source_code,
            "app.py",
            "python",
            analyzers=["entry_points"],
        )

        assert result.entry_points is not None
        # Should find public functions and main
        assert len(result.entry_points.public_functions) >= 2
        assert len(result.entry_points.main_functions) >= 1

    def test_analyze_file_dependencies(self):
        """Test that dependencies analyzer produces results."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
from services.user_service import UserService
from utils.helpers import validate_input

class UserController:
    def __init__(self):
        self.service = UserService()

    def handle_request(self, data):
        if not validate_input(data):
            raise ValueError('Invalid input')
        return self.service.process(data)
"""

        result = orchestrator.analyze_file(
            source_code,
            "user_controller.py",
            "python",
            analyzers=["dependencies"],
        )

        assert result.dependencies is not None
        assert len(result.dependencies.nodes) > 0

    def test_analyze_file_data_flow(self):
        """Test that data flow analyzer produces results."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
def process_user_data(user_id: int) -> dict:
    '''Process user data through pipeline.'''
    # Get user from database
    user = get_user(user_id)

    # Transform data
    result = {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'processed': True
    }

    return result
"""

        result = orchestrator.analyze_file(
            source_code,
            "processors.py",
            "python",
            analyzers=["data_flow"],
        )

        assert result.data_flow is not None
        assert len(result.data_flow.nodes) > 0

    def test_analyze_file_business_logic(self):
        """Test that business logic analyzer produces results."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = """
class OrderService:
    def create_order(self, user_id: int, amount: decimal.Decimal) -> Order:
        '''Create order with business rules.'''
        # Validation: amount must be positive
        if amount <= 0:
            raise ValueError('Amount must be positive')

        # Constraint: daily limit check
        if self.get_daily_total(user_id) + amount > 10000:
            raise ValueError('Daily limit exceeded')

        order = Order(user_id=user_id, amount=amount)
        order.status = "pending"
        emit('OrderCreated', order.to_dict())
        return order

    def get_daily_total(self, user_id: int) -> decimal.Decimal:
        '''Get total order amount for today.'''
        return db.query(Order).filter_by(
            user_id=user_id,
            created_at=today()
        ).sum('amount')
"""

        result = orchestrator.analyze_file(
            source_code,
            "order_service.py",
            "python",
            analyzers=["business_logic"],
        )

        assert result.business_logic is not None
        assert len(result.business_logic.concepts) > 0
        assert len(result.business_logic.operations) > 0

    def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple files."""
        orchestrator = NativeAnalysisOrchestrator()

        source_files = [
            {
                "file_path": "services/user_service.py",
                "content": """
class UserService:
    def get_user(self, user_id: int) -> dict:
        '''Get user by ID.'''
        return db.query(User).get(user_id).to_dict()

    def create_user(self, name: str, email: str) -> dict:
        '''Create new user.'''
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
        return user.to_dict()
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
        '''Handle GET request.'''
        return self.service.get_user(user_id)

    def handle_post(self, data: dict):
        '''Handle POST request.'''
        return self.service.create_user(data['name'], data['email'])
""",
                "language": "python",
            },
        ]

        # Analyze individual files and combine manually
        results = []
        for file_info in source_files:
            result = orchestrator.analyze_file(
                file_info["content"],
                file_info["file_path"],
                file_info["language"],
                analyzers=["logic_structures", "dependencies"],
            )
            results.append(result)

        # Combine results manually
        combined = NativeAnalysisResult(language="python")
        for result in results:
            combined.source_files.extend(result.source_files)
            if result.logic_structures:
                if combined.logic_structures is None:
                    combined.logic_structures = result.logic_structures
                else:
                    combined.logic_structures.classes.extend(result.logic_structures.classes)
            if result.dependencies:
                if combined.dependencies is None:
                    combined.dependencies = result.dependencies
                else:
                    combined.dependencies.nodes.extend(result.dependencies.nodes)
                    combined.dependencies.edges.extend(result.dependencies.edges)

        # Verify combined results
        assert combined.language == "python"
        assert len(set(combined.source_files)) == 2
        assert combined.logic_structures is not None
        assert combined.dependencies is not None

    def test_to_dict_serialization(self):
        """Test result can be serialized to dict."""
        orchestrator = NativeAnalysisOrchestrator()

        source_code = "def hello(): pass"

        result = orchestrator.analyze_file(source_code, "test.py", "python", analyzers=["logic_structures"])

        data = result.to_dict()

        assert data["language"] == "python"
        assert "statistics" in data
        assert "combined_metrics" in data
