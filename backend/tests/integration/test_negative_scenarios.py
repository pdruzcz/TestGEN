"""Tests for negative and boundary scenario generator - Story 1.33"""

import pytest

from app.models.test_case import TestFramework, TestType
from app.services.generators.negative_scenarios import (
    NegativeScenario,
    NegativeScenarioGenerator,
    NegativeScenarioSuite,
    NegativeScenarioType,
    get_negative_scenario_generator,
)


class TestNegativeScenarioType:
    """Test NegativeScenarioType enum."""

    def test_type_values(self):
        """Test all scenario type values exist."""
        assert NegativeScenarioType.NULL_INPUT == "null_input"
        assert NegativeScenarioType.EMPTY_INPUT == "empty_input"
        assert NegativeScenarioType.INVALID_TYPE == "invalid_type"
        assert NegativeScenarioType.OUT_OF_RANGE == "out_of_range"
        assert NegativeScenarioType.MALFORMED == "malformed"
        assert NegativeScenarioType.DUPLICATE == "duplicate"
        assert NegativeScenarioType.NOT_FOUND == "not_found"
        assert NegativeScenarioType.UNAUTHORIZED == "unauthorized"
        assert NegativeScenarioType.FORBIDDEN == "forbidden"
        assert NegativeScenarioType.CONFLICT == "conflict"
        assert NegativeScenarioType.OVERFLOW == "overflow"
        assert NegativeScenarioType.TIMEOUT == "timeout"


class TestNegativeScenario:
    """Test NegativeScenario dataclass."""

    def test_scenario_creation(self):
        """Test creating a negative scenario."""
        scenario = NegativeScenario(
            name="test_login_with_invalid_credentials",
            description="Test login fails with invalid password",
            scenario_type=NegativeScenarioType.INVALID_TYPE,
            expected_error="InvalidCredentialsError",
            expected_status=401,
            source_function="login",
            test_steps=[
                {"action": "setup", "description": "Create user"},
                {"action": "execute", "description": "Login with wrong password"},
                {"action": "verify", "description": "Check error"},
            ],
            test_data={"username": "test@example.com", "password": "wrong"},
            error_message="Should raise authentication error",
            assertions=["error is not None", "error.type == InvalidCredentials"],
            tags=["auth", "negative"],
        )

        assert scenario.name == "test_login_with_invalid_credentials"
        assert scenario.scenario_type == NegativeScenarioType.INVALID_TYPE
        assert scenario.expected_status == 401
        assert len(scenario.assertions) == 2

    def test_minimal_scenario(self):
        """Test creating minimal scenario."""
        scenario = NegativeScenario(
            name="test_negative",
            description="Negative test",
            scenario_type=NegativeScenarioType.NULL_INPUT,
        )

        assert scenario.name == "test_negative"
        assert len(scenario.test_steps) == 0


class TestNegativeScenarioSuite:
    """Test NegativeScenarioSuite dataclass."""

    def test_suite_creation(self):
        """Test creating scenario suite."""
        suite = NegativeScenarioSuite(
            source_file="app/services/auth.py",
            language="python",
            framework=TestFramework.PYTEST,
        )

        assert suite.source_file == "app/services/auth.py"
        assert suite.framework == TestFramework.PYTEST
        assert len(suite.scenarios) == 0

    def test_suite_statistics(self):
        """Test suite statistics calculation."""
        suite = NegativeScenarioSuite(
            source_file="test.py",
            language="python",
            framework=TestFramework.PYTEST,
        )

        suite.scenarios = [
            NegativeScenario(
                name="test_1",
                description="Test 1",
                scenario_type=NegativeScenarioType.NULL_INPUT,
                expected_error="Error",
                expected_status=400,
            ),
            NegativeScenario(
                name="test_2",
                description="Test 2",
                scenario_type=NegativeScenarioType.EMPTY_INPUT,
            ),
            NegativeScenario(
                name="test_3",
                description="Test 3",
                scenario_type=NegativeScenarioType.NULL_INPUT,
            ),
        ]

        stats = suite.get_statistics()

        assert stats["total_scenarios"] == 3
        assert stats["type_distribution"][NegativeScenarioType.NULL_INPUT] == 2
        assert stats["type_distribution"][NegativeScenarioType.EMPTY_INPUT] == 1
        assert stats["with_expected_errors"] == 1
        assert stats["with_expected_status"] == 1


class TestNegativeScenarioGenerator:
    """Test negative scenario generator."""

    def test_generator_initialization(self):
        """Test generator can be initialized."""
        generator = NegativeScenarioGenerator()
        assert generator is not None

    def test_generate_null_scenarios(self):
        """Test generating null input scenarios."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "process_user",
            "parameters": [
                {"name": "user_id", "type": "uuid"},
                {"name": "name", "type": "str"},
                {"name": "age", "type": "int"},  # Should be skipped (not nullable)
            ],
        }

        scenarios = generator.generate_null_scenarios(func_data)

        # Should generate for uuid and str, not int
        assert len(scenarios) >= 1
        assert all(s.scenario_type == NegativeScenarioType.NULL_INPUT for s in scenarios)
        assert any("null_name" in s.name for s in scenarios)

    def test_generate_empty_scenarios(self):
        """Test generating empty input scenarios."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "process_data",
            "parameters": [
                {"name": "text", "type": "str"},
                {"name": "items", "type": "list"},
                {"name": "config", "type": "dict"},
            ],
        }

        scenarios = generator.generate_empty_scenarios(func_data)

        assert len(scenarios) == 3
        assert all(s.scenario_type == NegativeScenarioType.EMPTY_INPUT for s in scenarios)
        assert any("empty_text" in s.name for s in scenarios)

    def test_generate_out_of_range_scenarios(self):
        """Test generating out-of-range scenarios."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "calculate",
            "parameters": [
                {"name": "value", "type": "int"},
                {"name": "rate", "type": "float"},
            ],
        }

        scenarios = generator.generate_out_of_range_scenarios(func_data)

        # Should generate negative and overflow for each numeric param
        assert len(scenarios) >= 2
        assert any(
            s.scenario_type == NegativeScenarioType.OUT_OF_RANGE for s in scenarios
        )
        assert any(s.scenario_type == NegativeScenarioType.OVERFLOW for s in scenarios)

    def test_generate_invalid_type_scenarios(self):
        """Test generating invalid type scenarios."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "process",
            "parameters": [
                {"name": "count", "type": "int"},
                {"name": "name", "type": "str"},
            ],
        }

        scenarios = generator.generate_invalid_type_scenarios(func_data)

        assert len(scenarios) == 2
        assert all(s.scenario_type == NegativeScenarioType.INVALID_TYPE for s in scenarios)

    def test_generate_endpoint_not_found(self):
        """Test generating not found scenarios for endpoints."""
        generator = NegativeScenarioGenerator()

        endpoint_data = {
            "path": "/api/users/{id}",
            "http_method": "GET",
            "name": "get_user",
        }

        scenarios = generator.generate_endpoint_not_found(endpoint_data)

        assert len(scenarios) == 1
        assert scenarios[0].scenario_type == NegativeScenarioType.NOT_FOUND
        assert scenarios[0].expected_status == 404
        assert "not_found" in scenarios[0].name

    def test_generate_endpoint_not_found_no_params(self):
        """Test not found scenarios for endpoint without parameters."""
        generator = NegativeScenarioGenerator()

        endpoint_data = {
            "path": "/api/users",
            "http_method": "GET",
            "name": "get_users",
        }

        scenarios = generator.generate_endpoint_not_found(endpoint_data)

        # Should not generate if no {id} parameter
        assert len(scenarios) == 0

    def test_generate_endpoint_unauthorized(self):
        """Test generating unauthorized scenarios."""
        generator = NegativeScenarioGenerator()

        endpoint_data = {
            "path": "/api/admin",
            "http_method": "GET",
            "name": "get_admin",
        }

        scenarios = generator.generate_endpoint_unauthorized(endpoint_data)

        assert len(scenarios) == 1
        assert scenarios[0].scenario_type == NegativeScenarioType.UNAUTHORIZED
        assert scenarios[0].expected_status == 401
        assert "unauthorized" in scenarios[0].name

    def test_generate_endpoint_malformed_post(self):
        """Test generating malformed scenarios for POST."""
        generator = NegativeScenarioGenerator()

        endpoint_data = {
            "path": "/api/users",
            "http_method": "POST",
            "name": "create_user",
        }

        scenarios = generator.generate_endpoint_malformed(endpoint_data)

        assert len(scenarios) == 1
        assert scenarios[0].scenario_type == NegativeScenarioType.MALFORMED
        assert scenarios[0].expected_status == 400

    def test_generate_endpoint_malformed_get(self):
        """Test malformed scenarios for GET (should be empty)."""
        generator = NegativeScenarioGenerator()

        endpoint_data = {
            "path": "/api/users",
            "http_method": "GET",
            "name": "get_users",
        }

        scenarios = generator.generate_endpoint_malformed(endpoint_data)

        # GET doesn't have body to be malformed
        assert len(scenarios) == 0

    def test_generate_all_negative_scenarios(self):
        """Test generating all negative scenarios for function."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "process",
            "parameters": [
                {"name": "text", "type": "str"},
                {"name": "count", "type": "int"},
            ],
        }

        scenarios = generator.generate_all_negative_scenarios(func_data)

        # Should have multiple scenario types
        assert len(scenarios) > 0
        scenario_types = {s.scenario_type for s in scenarios}
        assert len(scenario_types) > 1

    def test_generate_all_endpoint_scenarios(self):
        """Test generating all negative scenarios for endpoint."""
        generator = NegativeScenarioGenerator()

        endpoint_data = {
            "path": "/api/users/{id}",
            "http_method": "POST",
            "name": "update_user",
        }

        scenarios = generator.generate_all_endpoint_scenarios(endpoint_data)

        # Should have not_found, unauthorized, malformed
        assert len(scenarios) >= 2
        scenario_types = {s.scenario_type for s in scenarios}
        assert NegativeScenarioType.NOT_FOUND in scenario_types
        assert NegativeScenarioType.UNAUTHORIZED in scenario_types

    def test_scenario_has_expected_error(self):
        """Test scenario includes expected error."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "func",
            "parameters": [{"name": "arg", "type": "str"}],
        }

        scenarios = generator.generate_null_scenarios(func_data)

        assert scenarios[0].expected_error is not None

    def test_scenario_has_test_data(self):
        """Test scenario includes test data."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "func",
            "parameters": [{"name": "arg", "type": "str"}],
        }

        scenarios = generator.generate_null_scenarios(func_data)

        assert scenarios[0].test_data is not None
        assert "arg" in scenarios[0].test_data

    def test_scenario_has_assertions(self):
        """Test scenario includes assertions."""
        generator = NegativeScenarioGenerator()

        func_data = {
            "name": "func",
            "parameters": [{"name": "arg", "type": "int"}],
        }

        scenarios = generator.generate_out_of_range_scenarios(func_data)

        assert len(scenarios[0].assertions) > 0

    def test_get_empty_value_for_type(self):
        """Test getting empty values for types."""
        generator = NegativeScenarioGenerator()

        assert generator._get_empty_value_for_type("str") == ""
        assert generator._get_empty_value_for_type("list") == []
        assert generator._get_empty_value_for_type("dict") == {}

    def test_get_invalid_value_for_type(self):
        """Test getting invalid values for types."""
        generator = NegativeScenarioGenerator()

        assert generator._get_invalid_value_for_type("str") == 123
        assert generator._get_invalid_value_for_type("int") == "not_a_number"
        assert isinstance(generator._get_invalid_value_for_type("bool"), str)


def test_get_negative_scenario_generator():
    """Test getting negative scenario generator instance."""
    generator = get_negative_scenario_generator()
    assert isinstance(generator, NegativeScenarioGenerator)
