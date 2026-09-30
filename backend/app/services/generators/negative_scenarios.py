"""
Negative and boundary test scenario generator - Story 1.33

Generates error case and edge case test scenarios:
- Invalid input handling
- Boundary conditions (empty, min, max, overflow)
- Null/None value handling
- Error response testing
- Validation failure scenarios
- Resource not found scenarios
- Unauthorized/forbidden scenarios
- Malformed input scenarios

Focuses on what should fail or be handled gracefully.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.models.test_case import TestFramework

logger = logging.getLogger(__name__)


class NegativeScenarioType(StrEnum):
    """Types of negative/boundary scenarios."""

    NULL_INPUT = "null_input"  # None/nil values
    EMPTY_INPUT = "empty_input"  # Empty strings, zero-length arrays
    INVALID_TYPE = "invalid_type"  # Wrong data type
    OUT_OF_RANGE = "out_of_range"  # Below/above valid range
    MALFORMED = "malformed"  # Invalid structure/format
    DUPLICATE = "duplicate"  # Duplicate key/resource
    NOT_FOUND = "not_found"  # Resource doesn't exist
    UNAUTHORIZED = "unauthorized"  # No auth/invalid auth
    FORBIDDEN = "forbidden"  # Auth but no permission
    CONFLICT = "conflict"  # State conflict
    OVERFLOW = "overflow"  # Numeric overflow
    TIMEOUT = "timeout"  # Timeout scenarios


@dataclass
class NegativeScenario:
    """A negative (error/edge case) test scenario."""

    name: str
    description: str
    scenario_type: NegativeScenarioType
    expected_error: str | None = None
    expected_status: int | None = None  # HTTP status or error code
    source_function: str | None = None
    source_endpoint: str | None = None
    preconditions: list[str] = field(default_factory=list)
    test_steps: list[dict[str, Any]] = field(default_factory=list)
    test_data: dict[str, Any] | None = None
    error_message: str | None = None
    assertions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class NegativeScenarioSuite:
    """Collection of negative scenarios."""

    source_file: str
    language: str
    framework: TestFramework
    scenarios: list[NegativeScenario] = field(default_factory=list)

    def get_statistics(self) -> dict[str, Any]:
        """Get suite statistics."""
        type_counts = {}
        for scenario in self.scenarios:
            type_counts[scenario.scenario_type] = type_counts.get(scenario.scenario_type, 0) + 1

        return {
            "total_scenarios": len(self.scenarios),
            "type_distribution": type_counts,
            "with_expected_errors": sum(1 for s in self.scenarios if s.expected_error),
            "with_expected_status": sum(1 for s in self.scenarios if s.expected_status),
        }


class NegativeScenarioGenerator:
    """Generates negative and boundary test scenarios."""

    def __init__(self):
        pass

    def generate_null_scenarios(
        self,
        func_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate null/None input scenarios.

        Args:
            func_data: Function analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of null input scenarios
        """
        scenarios = []
        name = func_data.get("name", "unknown")
        params = func_data.get("parameters", [])

        for param in params:
            param_name = param.get("name")
            param_type = param.get("type", "")

            # Skip if param is not nullable
            if param_type in ["bool", "int", "float"]:
                continue

            scenario = NegativeScenario(
                name=f"test_{name}_with_null_{param_name}",
                description=f"Test {name} with None/null for {param_name}",
                scenario_type=NegativeScenarioType.NULL_INPUT,
                expected_error="TypeError or ValueError",
                source_function=name,
                test_steps=[
                    {"action": "setup", "description": "Prepare None input"},
                    {"action": "execute", "description": f"Call {name} with None"},
                    {"action": "verify", "description": "Check error is raised"},
                ],
                test_data={param_name: None},
                error_message=f"Expected error when {param_name} is None",
                assertions=["with pytest.raises(TypeError):", "with pytest.raises(ValueError):"],
                tags=["negative", "null", param_name],
            )
            scenarios.append(scenario)

        return scenarios

    def generate_empty_scenarios(
        self,
        func_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate empty input scenarios.

        Args:
            func_data: Function analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of empty input scenarios
        """
        scenarios = []
        name = func_data.get("name", "unknown")
        params = func_data.get("parameters", [])

        for param in params:
            param_name = param.get("name")
            param_type = param.get("type", "")

            if param_type in ["str", "string", "list", "array", "dict"]:
                empty_value = self._get_empty_value_for_type(param_type)

                scenario = NegativeScenario(
                    name=f"test_{name}_with_empty_{param_name}",
                    description=f"Test {name} with empty {param_type}",
                    scenario_type=NegativeScenarioType.EMPTY_INPUT,
                    expected_error="ValueError or empty result",
                    source_function=name,
                    test_steps=[
                        {"action": "setup", "description": f"Prepare empty {param_type}"},
                        {"action": "execute", "description": f"Call {name} with empty input"},
                        {"action": "verify", "description": "Check error or empty handling"},
                    ],
                    test_data={param_name: empty_value},
                    error_message=f"Handles empty {param_type} correctly",
                    assertions=["result is None or result == [] or result == {}"],
                    tags=["negative", "empty", param_name],
                )
                scenarios.append(scenario)

        return scenarios

    def generate_out_of_range_scenarios(
        self,
        func_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate out-of-range input scenarios.

        Args:
            func_data: Function analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of out-of-range scenarios
        """
        scenarios = []
        name = func_data.get("name", "unknown")
        params = func_data.get("parameters", [])

        for param in params:
            param_name = param.get("name")
            param_type = param.get("type", "")

            if param_type in ["int", "integer", "float"]:
                # Negative value scenario
                scenario = NegativeScenario(
                    name=f"test_{name}_with_negative_{param_name}",
                    description=f"Test {name} with negative {param_name}",
                    scenario_type=NegativeScenarioType.OUT_OF_RANGE,
                    expected_error="ValueError or overflow",
                    source_function=name,
                    test_steps=[
                        {"action": "execute", "description": f"Call {name} with negative value"},
                        {"action": "verify", "description": "Check error handling"},
                    ],
                    test_data={param_name: -999999},
                    error_message="Handles negative values correctly",
                    assertions=["with pytest.raises(ValueError):"],
                    tags=["negative", "out-of-range", param_name],
                )
                scenarios.append(scenario)

                # Overflow scenario
                scenario = NegativeScenario(
                    name=f"test_{name}_with_overflow_{param_name}",
                    description=f"Test {name} with overflow value",
                    scenario_type=NegativeScenarioType.OVERFLOW,
                    expected_error="OverflowError",
                    source_function=name,
                    test_steps=[
                        {"action": "execute", "description": "Call with max value + 1"},
                        {"action": "verify", "description": "Check overflow handling"},
                    ],
                    test_data={param_name: 999999999999},
                    error_message="Handles overflow correctly",
                    assertions=["with pytest.raises(OverflowError):"],
                    tags=["negative", "overflow", param_name],
                )
                scenarios.append(scenario)

        return scenarios

    def generate_invalid_type_scenarios(
        self,
        func_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate invalid type scenarios.

        Args:
            func_data: Function analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of invalid type scenarios
        """
        scenarios = []
        name = func_data.get("name", "unknown")
        params = func_data.get("parameters", [])

        for param in params:
            param_name = param.get("name")
            param_type = param.get("type", "")

            # Provide wrong type
            invalid_value = self._get_invalid_value_for_type(param_type)

            scenario = NegativeScenario(
                name=f"test_{name}_with_invalid_type_{param_name}",
                description=f"Test {name} with wrong type for {param_name}",
                scenario_type=NegativeScenarioType.INVALID_TYPE,
                expected_error="TypeError",
                source_function=name,
                test_steps=[
                    {"action": "execute", "description": f"Call {name} with invalid type"},
                    {"action": "verify", "description": "Check type error"},
                ],
                test_data={param_name: invalid_value},
                error_message="Raises TypeError for wrong type",
                assertions=["with pytest.raises(TypeError):"],
                tags=["negative", "invalid-type", param_name],
            )
            scenarios.append(scenario)

        return scenarios

    def generate_endpoint_not_found(
        self,
        endpoint_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate not found scenarios for endpoints.

        Args:
            endpoint_data: Endpoint analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of not found scenarios
        """
        scenarios = []
        path = endpoint_data.get("path") or "/"
        method = endpoint_data.get("http_method") or "GET"
        name = endpoint_data.get("name", "")

        # Not found scenario
        if "{id}" in path or "{uuid}" in path:
            scenario = NegativeScenario(
                name=f"test_{name}_not_found",
                description=f"Test {method} {path} with non-existent ID",
                scenario_type=NegativeScenarioType.NOT_FOUND,
                expected_status=404,
                source_endpoint=name,
                test_steps=[
                    {"action": "execute", "description": f"Call {method} with invalid ID"},
                    {"action": "verify", "description": "Check 404 response"},
                ],
                test_data={"id": "00000000-0000-0000-0000-000000000000"},
                error_message="Returns 404 for non-existent resource",
                assertions=["response.status_code == 404"],
                tags=["api", "not-found", method.lower()],
            )
            scenarios.append(scenario)

        return scenarios

    def generate_endpoint_unauthorized(
        self,
        endpoint_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate unauthorized scenarios for endpoints.

        Args:
            endpoint_data: Endpoint analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of unauthorized scenarios
        """
        scenarios = []
        path = endpoint_data.get("path") or "/"
        method = endpoint_data.get("http_method") or "GET"
        name = endpoint_data.get("name", "")

        scenario = NegativeScenario(
            name=f"test_{name}_unauthorized",
            description=f"Test {method} {path} without authentication",
            scenario_type=NegativeScenarioType.UNAUTHORIZED,
            expected_status=401,
            source_endpoint=name,
            test_steps=[
                {"action": "setup", "description": "Remove auth headers"},
                {"action": "execute", "description": f"Call {method} without auth"},
                {"action": "verify", "description": "Check 401 response"},
            ],
            test_data={"auth": None},
            error_message="Returns 401 without authentication",
            assertions=["response.status_code == 401"],
            tags=["api", "unauthorized", method.lower()],
        )
        scenarios.append(scenario)

        return scenarios

    def generate_endpoint_malformed(
        self,
        endpoint_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate malformed request scenarios for endpoints.

        Args:
            endpoint_data: Endpoint analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of malformed scenarios
        """
        scenarios = []
        path = endpoint_data.get("path") or "/"
        method = endpoint_data.get("http_method") or "GET"
        name = endpoint_data.get("name", "")

        if method in ["POST", "PUT", "PATCH"]:
            scenario = NegativeScenario(
                name=f"test_{name}_malformed_body",
                description=f"Test {method} {path} with malformed JSON",
                scenario_type=NegativeScenarioType.MALFORMED,
                expected_status=400,
                source_endpoint=name,
                test_steps=[
                    {"action": "execute", "description": "Send malformed JSON body"},
                    {"action": "verify", "description": "Check 400 response"},
                ],
                test_data={"body": "{invalid json}"},
                error_message="Returns 400 for malformed request",
                assertions=["response.status_code == 400"],
                tags=["api", "malformed", method.lower()],
            )
            scenarios.append(scenario)

        return scenarios

    def generate_all_negative_scenarios(
        self,
        func_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate all negative scenarios for a function.

        Args:
            func_data: Function analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of all negative scenarios
        """
        all_scenarios = []

        all_scenarios.extend(self.generate_null_scenarios(func_data, language, framework))
        all_scenarios.extend(self.generate_empty_scenarios(func_data, language, framework))
        all_scenarios.extend(self.generate_out_of_range_scenarios(func_data, language, framework))
        all_scenarios.extend(self.generate_invalid_type_scenarios(func_data, language, framework))

        logger.debug(f"Generated {len(all_scenarios)} negative scenarios for {func_data.get('name')}")
        return all_scenarios

    def generate_all_endpoint_scenarios(
        self,
        endpoint_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[NegativeScenario]:
        """
        Generate all negative scenarios for an endpoint.

        Args:
            endpoint_data: Endpoint analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of all negative scenarios
        """
        all_scenarios = []

        all_scenarios.extend(self.generate_endpoint_not_found(endpoint_data, language, framework))
        all_scenarios.extend(self.generate_endpoint_unauthorized(endpoint_data, language, framework))
        all_scenarios.extend(self.generate_endpoint_malformed(endpoint_data, language, framework))

        logger.debug(f"Generated {len(all_scenarios)} negative scenarios for {endpoint_data.get('name')}")
        return all_scenarios

    def _get_empty_value_for_type(self, param_type: str) -> Any:
        """Get empty value for a type."""
        type_map = {
            "str": "",
            "string": "",
            "list": [],
            "array": [],
            "dict": {},
        }
        return type_map.get(param_type.lower(), None)

    def _get_invalid_value_for_type(self, param_type: str) -> Any:
        """Get invalid value for a type."""
        type_map = {
            "str": 123,  # Number instead of string
            "int": "not_a_number",  # String instead of int
            "float": "not_a_float",
            "bool": "true",  # String instead of bool
            "list": {},  # Dict instead of list
            "dict": [],  # List instead of dict
        }
        return type_map.get(param_type.lower(), "invalid_value")


def get_negative_scenario_generator() -> NegativeScenarioGenerator:
    """Get or create negative scenario generator instance."""
    return NegativeScenarioGenerator()
