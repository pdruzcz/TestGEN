"""Tests for positive scenario generator - Story 1.32"""

import pytest

from app.models.test_case import TestFramework, TestType
from app.services.generators.positive_scenarios import (
    PositiveScenario,
    PositiveScenarioGenerator,
    PositiveScenarioSuite,
    ScenarioComplexity,
    get_positive_scenario_generator,
)


class TestScenarioComplexity:
    """Test ScenarioComplexity enum."""

    def test_complexity_values(self):
        """Test all complexity values exist."""
        assert ScenarioComplexity.SIMPLE == "simple"
        assert ScenarioComplexity.MEDIUM == "medium"
        assert ScenarioComplexity.COMPLEX == "complex"


class TestPositiveScenario:
    """Test PositiveScenario dataclass."""

    def test_scenario_creation(self):
        """Test creating a positive scenario."""
        scenario = PositiveScenario(
            name="test_user_login_success",
            description="Verify user can login with valid credentials",
            complexity=ScenarioComplexity.SIMPLE,
            source_function="login",
            preconditions=["User exists", "User is active"],
            test_steps=[
                {"action": "setup", "description": "Create test user"},
                {"action": "execute", "description": "Call login with valid creds"},
                {"action": "verify", "description": "Check auth token"},
            ],
            expected_result="User receives valid auth token",
            test_data={"username": "test@example.com", "password": "SecurePass123"},
            assertions=["token is not None", "token.expires_at > now"],
            tags=["auth", "happy-path"],
        )

        assert scenario.name == "test_user_login_success"
        assert scenario.complexity == ScenarioComplexity.SIMPLE
        assert len(scenario.preconditions) == 2
        assert scenario.test_data is not None

    def test_minimal_scenario(self):
        """Test creating minimal scenario."""
        scenario = PositiveScenario(
            name="test_simple",
            description="Simple test",
            complexity=ScenarioComplexity.SIMPLE,
        )

        assert scenario.name == "test_simple"
        assert len(scenario.preconditions) == 0
        assert len(scenario.test_steps) == 0


class TestPositiveScenarioSuite:
    """Test PositiveScenarioSuite dataclass."""

    def test_suite_creation(self):
        """Test creating scenario suite."""
        suite = PositiveScenarioSuite(
            source_file="app/services/auth.py",
            language="python",
            framework=TestFramework.PYTEST,
        )

        assert suite.source_file == "app/services/auth.py"
        assert suite.framework == TestFramework.PYTEST
        assert len(suite.scenarios) == 0

    def test_suite_statistics(self):
        """Test suite statistics calculation."""
        suite = PositiveScenarioSuite(
            source_file="test.py",
            language="python",
            framework=TestFramework.PYTEST,
        )

        suite.scenarios = [
            PositiveScenario(
                name="test_1",
                description="Test 1",
                complexity=ScenarioComplexity.SIMPLE,
                test_data={"input": "value"},
                assertions=["assert True"],
            ),
            PositiveScenario(
                name="test_2",
                description="Test 2",
                complexity=ScenarioComplexity.MEDIUM,
                test_data={"input": "value"},
            ),
            PositiveScenario(
                name="test_3",
                description="Test 3",
                complexity=ScenarioComplexity.SIMPLE,
                assertions=["assert True"],
            ),
        ]

        stats = suite.get_statistics()

        assert stats["total_scenarios"] == 3
        assert stats["complexity_distribution"][ScenarioComplexity.SIMPLE] == 2
        assert stats["complexity_distribution"][ScenarioComplexity.MEDIUM] == 1
        assert stats["with_test_data"] == 2
        assert stats["with_assertions"] == 2


class TestPositiveScenarioGenerator:
    """Test positive scenario generator."""

    def test_generator_initialization(self):
        """Test generator can be initialized."""
        generator = PositiveScenarioGenerator()
        assert generator is not None

    def test_generate_from_function_basic(self):
        """Test generating scenarios from basic function."""
        generator = PositiveScenarioGenerator()

        func_data = {
            "name": "add_numbers",
            "return_type": "int",
            "parameters": [
                {"name": "a", "type": "int"},
                {"name": "b", "type": "int"},
            ],
        }

        scenarios = generator.generate_from_function(
            func_data, language="python", framework=TestFramework.PYTEST
        )

        assert len(scenarios) >= 2  # basic, parameter combo, boundary
        assert any("success" in s.name for s in scenarios)
        assert all(s.source_function == "add_numbers" for s in scenarios)

    def test_generate_from_function_no_params(self):
        """Test generating scenarios from parameterless function."""
        generator = PositiveScenarioGenerator()

        func_data = {
            "name": "get_current_time",
            "return_type": "datetime",
            "parameters": [],
        }

        scenarios = generator.generate_from_function(func_data)

        # Should still generate basic scenario
        assert len(scenarios) >= 1
        assert scenarios[0].source_function == "get_current_time"

    def test_generate_from_endpoint_get(self):
        """Test generating scenarios from GET endpoint."""
        generator = PositiveScenarioGenerator()

        endpoint_data = {
            "path": "/api/users",
            "http_method": "GET",
            "name": "get_users",
        }

        scenarios = generator.generate_from_endpoint(endpoint_data)

        assert len(scenarios) >= 1
        assert scenarios[0].source_endpoint == "get_users"
        assert "get" in scenarios[0].tags

    def test_generate_from_endpoint_post(self):
        """Test generating scenarios from POST endpoint."""
        generator = PositiveScenarioGenerator()

        endpoint_data = {
            "path": "/api/users",
            "http_method": "POST",
            "name": "create_user",
        }

        scenarios = generator.generate_from_endpoint(endpoint_data)

        # Should have basic and body scenarios
        assert len(scenarios) >= 2
        assert any("with_body" in s.name for s in scenarios)
        assert all("post" in s.tags for s in scenarios)

    def test_generate_from_endpoint_with_params(self):
        """Test generating scenarios from endpoint with path parameters."""
        generator = PositiveScenarioGenerator()

        endpoint_data = {
            "path": "/api/users/{id}",
            "http_method": "GET",
            "name": "get_user",
        }

        scenarios = generator.generate_from_endpoint(endpoint_data)

        # Should have basic and parameter scenarios
        assert len(scenarios) >= 2
        assert any("with_id" in s.name for s in scenarios)

    def test_generate_from_class(self):
        """Test generating scenarios from class."""
        generator = PositiveScenarioGenerator()

        class_data = {
            "name": "UserService",
            "methods": [
                {"name": "create_user"},
                {"name": "get_user"},
                {"name": "_private_method"},  # Should be skipped
                {"name": "update_user"},
                {"name": "delete_user"},
            ],
        }

        scenarios = generator.generate_from_class(class_data)

        # Should generate for non-private methods
        assert len(scenarios) == 4
        assert all("UserService" in s.source_function for s in scenarios)

    def test_generate_from_class_empty(self):
        """Test generating scenarios from class with no methods."""
        generator = PositiveScenarioGenerator()

        class_data = {"name": "EmptyClass", "methods": []}

        scenarios = generator.generate_from_class(class_data)

        assert len(scenarios) == 0

    def test_scenario_complexity_simple(self):
        """Test simple scenario complexity."""
        generator = PositiveScenarioGenerator()

        func_data = {"name": "simple_func", "return_type": "bool", "parameters": []}

        scenarios = generator.generate_from_function(func_data)
        basic = scenarios[0]

        assert basic.complexity == ScenarioComplexity.SIMPLE

    def test_scenario_has_test_data(self):
        """Test scenario includes test data."""
        generator = PositiveScenarioGenerator()

        func_data = {
            "name": "calculate",
            "return_type": "int",
            "parameters": [{"name": "x", "type": "int"}],
        }

        scenarios = generator.generate_from_function(func_data)
        basic = scenarios[0]

        assert basic.test_data is not None
        assert "x" in basic.test_data

    def test_scenario_has_assertions(self):
        """Test scenario includes assertions."""
        generator = PositiveScenarioGenerator()

        func_data = {
            "name": "process",
            "return_type": "str",
            "parameters": [],
        }

        scenarios = generator.generate_from_function(func_data)
        basic = scenarios[0]

        assert len(basic.assertions) > 0

    def test_get_valid_value_for_type(self):
        """Test getting valid values for types."""
        generator = PositiveScenarioGenerator()

        assert generator._get_valid_value_for_type("str") == "test_value"
        assert generator._get_valid_value_for_type("int") == 42
        assert generator._get_valid_value_for_type("bool") is True

    def test_get_edge_value_for_type(self):
        """Test getting edge values for types."""
        generator = PositiveScenarioGenerator()

        assert generator._get_edge_value_for_type("str") == "a"
        assert generator._get_edge_value_for_type("int") == 1

    def test_get_max_value_for_type(self):
        """Test getting max values for types."""
        generator = PositiveScenarioGenerator()

        max_str = generator._get_max_value_for_type("str")
        assert len(max_str) == 100  # Long string


def test_get_positive_scenario_generator():
    """Test getting positive scenario generator instance."""
    generator = get_positive_scenario_generator()
    assert isinstance(generator, PositiveScenarioGenerator)
