"""
Positive test scenario generator - Story 1.32

Generates happy path test scenarios from code analysis:
- Extract success paths from functions
- Identify normal flow endpoints
- Generate valid input combinations
- Create expected success behaviors
- Map business logic success scenarios

Focuses on what should work correctly.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.models.test_case import TestFramework

logger = logging.getLogger(__name__)


class ScenarioComplexity(StrEnum):
    """Complexity level of test scenario."""

    SIMPLE = "simple"  # Single operation, straightforward
    MEDIUM = "medium"  # Multiple steps, some setup
    COMPLEX = "complex"  # Many steps, complex setup


@dataclass
class PositiveScenario:
    """A positive (happy path) test scenario."""

    name: str
    description: str
    complexity: ScenarioComplexity
    source_function: str | None = None
    source_endpoint: str | None = None
    preconditions: list[str] = field(default_factory=list)
    test_steps: list[dict[str, Any]] = field(default_factory=list)
    expected_result: str | None = None
    test_data: dict[str, Any] | None = None
    assertions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class PositiveScenarioSuite:
    """Collection of positive scenarios."""

    source_file: str
    language: str
    framework: TestFramework
    scenarios: list[PositiveScenario] = field(default_factory=list)

    def get_statistics(self) -> dict[str, Any]:
        """Get suite statistics."""
        complexity_counts = {}
        for scenario in self.scenarios:
            complexity_counts[scenario.complexity] = complexity_counts.get(scenario.complexity, 0) + 1

        return {
            "total_scenarios": len(self.scenarios),
            "complexity_distribution": complexity_counts,
            "with_test_data": sum(1 for s in self.scenarios if s.test_data),
            "with_assertions": sum(1 for s in self.scenarios if s.assertions),
        }


class PositiveScenarioGenerator:
    """Generates positive (happy path) test scenarios."""

    def __init__(self):
        pass

    def generate_from_function(
        self,
        func_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[PositiveScenario]:
        """
        Generate positive scenarios from function analysis.

        Args:
            func_data: Function analysis data from native analysis
            language: Programming language
            framework: Test framework

        Returns:
            List of positive scenarios
        """
        scenarios = []

        name = func_data.get("name", "unknown_function")
        return_type = func_data.get("return_type", "unknown")
        params = func_data.get("parameters", [])

        # Generate basic success scenario
        basic_scenario = self._generate_basic_success_scenario(name, params, return_type, language, framework)
        scenarios.append(basic_scenario)

        # Generate scenarios for different parameter combinations
        if len(params) > 1:
            combo_scenario = self._generate_parameter_combination_scenario(
                name, params, return_type, language, framework
            )
            scenarios.append(combo_scenario)

        # Generate boundary success scenario (max valid values)
        boundary_scenario = self._generate_boundary_success_scenario(name, params, return_type, language, framework)
        scenarios.append(boundary_scenario)

        logger.debug(f"Generated {len(scenarios)} scenarios for function {name}")
        return scenarios

    def generate_from_endpoint(
        self,
        endpoint_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[PositiveScenario]:
        """
        Generate positive scenarios from API endpoint analysis.

        Args:
            endpoint_data: Endpoint analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of positive scenarios
        """
        scenarios = []

        path = endpoint_data.get("path") or "/"
        method = endpoint_data.get("http_method") or "GET"
        name = endpoint_data.get("name", f"{method.lower()}_{path.replace('/', '_')}")

        # Basic success scenario
        basic = PositiveScenario(
            name=f"test_{name}_success",
            description=f"Successful {method} {path}",
            complexity=ScenarioComplexity.SIMPLE,
            source_endpoint=name,
            test_steps=[
                {"action": "send_request", "method": method, "path": path},
                {"action": "verify_status", "expected": 200},
            ],
            expected_result="Request returns 200 OK",
            assertions=["response.status_code == 200"],
            tags=["api", method.lower()],
        )
        scenarios.append(basic)

        # Success with valid body (for POST/PUT)
        if method in ["POST", "PUT", "PATCH"]:
            body_scenario = self._generate_endpoint_body_scenario(path, method, endpoint_data, framework)
            scenarios.append(body_scenario)

        # Success with path parameters
        if "{id}" in path or "{uuid}" in path:
            param_scenario = self._generate_endpoint_param_scenario(path, method, framework)
            scenarios.append(param_scenario)

        logger.debug(f"Generated {len(scenarios)} scenarios for endpoint {name}")
        return scenarios

    def generate_from_class(
        self,
        class_data: dict[str, Any],
        language: str = "python",
        framework: TestFramework = TestFramework.PYTEST,
    ) -> list[PositiveScenario]:
        """
        Generate positive scenarios from class analysis.

        Args:
            class_data: Class analysis data
            language: Programming language
            framework: Test framework

        Returns:
            List of positive scenarios
        """
        scenarios = []

        class_name = class_data.get("name", "UnknownClass")
        methods = class_data.get("methods", [])

        # Generate scenarios for key methods
        for method in methods[:5]:  # Limit to prevent too many
            method_name = method.get("name", "")
            if method_name.startswith("_"):
                continue  # Skip private methods

            scenario = self._generate_method_scenario(class_name, method, language, framework)
            scenarios.append(scenario)

        logger.debug(f"Generated {len(scenarios)} scenarios for class {class_name}")
        return scenarios

    def _generate_basic_success_scenario(
        self,
        name: str,
        params: list[dict],
        return_type: str,
        language: str,
        framework: TestFramework,
    ) -> PositiveScenario:
        """Generate basic success scenario."""
        # Create valid test data
        test_data = {}
        for param in params:
            param_name = param.get("name", "arg")
            param_type = param.get("type", "any")
            test_data[param_name] = self._get_valid_value_for_type(param_type)

        return PositiveScenario(
            name=f"test_{name}_success",
            description=f"Test {name} with valid inputs returns expected result",
            complexity=ScenarioComplexity.SIMPLE,
            source_function=name,
            test_steps=[
                {"action": "setup", "description": f"Prepare inputs for {name}"},
                {"action": "execute", "description": f"Call {name} with valid parameters"},
                {"action": "verify", "description": "Check return value"},
            ],
            test_data=test_data,
            expected_result=f"Function returns valid {return_type}",
            assertions=["result is not None", "isinstance(result, expected_type)"],
            tags=["unit", "happy-path"],
        )

    def _generate_parameter_combination_scenario(
        self,
        name: str,
        params: list[dict],
        return_type: str,
        language: str,
        framework: TestFramework,
    ) -> PositiveScenario:
        """Generate scenario with various parameter combinations."""
        test_data = {}
        for param in params:
            param_name = param.get("name")
            param_type = param.get("type")
            # Use edge of valid range
            test_data[param_name] = self._get_edge_value_for_type(param_type)

        return PositiveScenario(
            name=f"test_{name}_with_edge_values",
            description=f"Test {name} with edge-of-range valid values",
            complexity=ScenarioComplexity.MEDIUM,
            source_function=name,
            test_steps=[
                {"action": "setup", "description": "Prepare edge case valid inputs"},
                {"action": "execute", "description": f"Call {name}"},
                {"action": "verify", "description": "Check behavior with edge values"},
            ],
            test_data=test_data,
            expected_result="Function handles edge values correctly",
            assertions=["result is not None"],
            tags=["unit", "edge-case", "positive"],
        )

    def _generate_boundary_success_scenario(
        self,
        name: str,
        params: list[dict],
        return_type: str,
        language: str,
        framework: TestFramework,
    ) -> PositiveScenario:
        """Generate scenario with max valid values."""
        test_data = {}
        for param in params:
            param_name = param.get("name")
            param_type = param.get("type")
            test_data[param_name] = self._get_max_value_for_type(param_type)

        return PositiveScenario(
            name=f"test_{name}_with_max_values",
            description=f"Test {name} with maximum valid input values",
            complexity=ScenarioComplexity.MEDIUM,
            source_function=name,
            test_steps=[
                {"action": "setup", "description": "Prepare maximum valid inputs"},
                {"action": "execute", "description": f"Call {name} with max values"},
                {"action": "verify", "description": "Check result"},
            ],
            test_data=test_data,
            expected_result="Function handles max values without overflow",
            assertions=["result is not None"],
            tags=["unit", "boundary", "positive"],
        )

    def _generate_endpoint_body_scenario(
        self, path: str, method: str, endpoint_data: dict, framework: TestFramework
    ) -> PositiveScenario:
        """Generate scenario with request body."""
        return PositiveScenario(
            name=f"test_{method.lower()}_{path.replace('/', '_')}_with_body",
            description=f"Test {method} {path} with valid request body",
            complexity=ScenarioComplexity.MEDIUM,
            source_endpoint=endpoint_data.get("name", ""),
            test_steps=[
                {"action": "setup", "description": "Prepare valid request body"},
                {"action": "send_request", "method": method, "path": path, "with_body": True},
                {"action": "verify_status", "expected": 201 if method == "POST" else 200},
                {"action": "verify_response", "description": "Check response data"},
            ],
            test_data={"body": self._get_sample_body_for_endpoint(endpoint_data)},
            expected_result="Request processed successfully",
            assertions=["response.status_code in [200, 201]"],
            tags=["api", method.lower(), "with-body"],
        )

    def _generate_endpoint_param_scenario(self, path: str, method: str, framework: TestFramework) -> PositiveScenario:
        """Generate scenario with path parameters."""
        return PositiveScenario(
            name=f"test_{method.lower()}_{path.replace('/', '_')}_with_id",
            description=f"Test {method} {path} with valid ID parameter",
            complexity=ScenarioComplexity.SIMPLE,
            test_steps=[
                {"action": "setup", "description": "Get valid resource ID"},
                {"action": "send_request", "method": method, "path": path, "with_id": True},
                {"action": "verify_status", "expected": 200},
            ],
            test_data={"id": "valid-uuid-1234"},
            expected_result="Resource retrieved successfully",
            assertions=["response.status_code == 200"],
            tags=["api", method.lower(), "with-param"],
        )

    def _generate_method_scenario(
        self, class_name: str, method: dict, language: str, framework: TestFramework
    ) -> PositiveScenario:
        """Generate scenario for class method."""
        method_name = method.get("name", "unknown")
        return PositiveScenario(
            name=f"test_{class_name}_{method_name}",
            description=f"Test {class_name}.{method_name} method",
            complexity=ScenarioComplexity.SIMPLE,
            source_function=f"{class_name}.{method_name}",
            test_steps=[
                {"action": "setup", "description": f"Create {class_name} instance"},
                {"action": "execute", "description": f"Call {method_name}"},
                {"action": "verify", "description": "Check result"},
            ],
            expected_result=f"Method {method_name} executes successfully",
            assertions=["result is not None"],
            tags=["unit", "class"],
        )

    def _get_valid_value_for_type(self, param_type: str) -> Any:
        """Get a valid test value for a type."""
        type_map = {
            "str": "test_value",
            "string": "test_value",
            "int": 42,
            "integer": 42,
            "float": 3.14,
            "bool": True,
            "boolean": True,
            "list": [1, 2, 3],
            "array": [1, 2, 3],
            "dict": {"key": "value"},
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
        }
        return type_map.get(param_type.lower(), "test_value")

    def _get_edge_value_for_type(self, param_type: str) -> Any:
        """Get edge-of-range valid value for a type."""
        type_map = {
            "str": "a",  # Minimum length
            "int": 1,  # Minimum positive
            "float": 0.01,
            "bool": True,
        }
        return type_map.get(param_type.lower(), self._get_valid_value_for_type(param_type))

    def _get_max_value_for_type(self, param_type: str) -> Any:
        """Get maximum valid value for a type."""
        type_map = {
            "str": "a" * 100,  # Long string
            "int": 999999,
            "float": 999999.99,
        }
        return type_map.get(param_type.lower(), self._get_valid_value_for_type(param_type))

    def _get_sample_body_for_type(self, param_type: str) -> dict:
        """Get sample request body for type."""
        return {"name": "Test", "value": 123}

    def _get_sample_body_for_endpoint(self, endpoint_data: dict) -> dict:
        """Generate sample request body for endpoint."""
        # Could be enhanced based on endpoint analysis
        return {"name": "test_resource", "active": True}


def get_positive_scenario_generator() -> PositiveScenarioGenerator:
    """Get or create positive scenario generator instance."""
    return PositiveScenarioGenerator()
