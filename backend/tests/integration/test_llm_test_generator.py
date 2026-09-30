"""Tests for LLM test generator - Story 1.30"""

import pytest

from app.services.generators.llm_test_generator import (
    LLMGeneratedTest,
    LLMTestFramework,
    LLMTestGenerator,
    LLMTestScenario,
    LLMTestSuite,
    LLMTestType,
    get_llm_test_generator,
)


class TestLLMTestFramework:
    """Test LLMTestFramework enum."""

    def test_framework_values(self):
        """Test all framework values exist."""
        assert LLMTestFramework.PYTEST == "pytest"
        assert LLMTestFramework.JUNIT == "junit"
        assert LLMTestFramework.NUNIT == "nunit"
        assert LLMTestFramework.MOCHA == "mocha"
        assert LLMTestFramework.JEST == "jest"
        assert LLMTestFramework.PHPUNIT == "phpunit"  # Story 1.55
        assert LLMTestFramework.PEST == "pest"  # Story 1.55
        assert LLMTestFramework.SELENIUM == "selenium"  # Story 1.56 (AC3)
        assert LLMTestFramework.PLAYWRIGHT == "playwright"  # Story 1.56 (AC3)
        assert LLMTestFramework.APPIUM == "appium"  # Story 1.56 (AC3)


class TestLLMTestType:
    """Test LLMTestType enum."""

    def test_type_values(self):
        """Test all test type values exist."""
        assert LLMTestType.INTELLIGENT == "intelligent"
        assert LLMTestType.EDGE_CASE == "edge_case"
        assert LLMTestType.SECURITY == "security"
        assert LLMTestType.PERFORMANCE == "performance"
        assert LLMTestType.ACCESSIBILITY == "accessibility"
        assert LLMTestType.SEMANTIC == "semantic"


class TestLLMTestScenario:
    """Test LLMTestScenario dataclass."""

    def test_scenario_creation(self):
        """Test creating a test scenario."""
        scenario = LLMTestScenario(
            name="test_null_input_handling",
            description="Test function handles null input gracefully",
            test_type=LLMTestType.EDGE_CASE,
            rationale="Null inputs are common edge case",
            preconditions=["Database is available"],
            test_data={"input": None},
            expected_behavior="Returns error or default value",
            edge_case_description="Testing with None/null input",
        )

        assert scenario.name == "test_null_input_handling"
        assert scenario.test_type == LLMTestType.EDGE_CASE
        assert scenario.preconditions == ["Database is available"]


class TestLLMGeneratedTest:
    """Test LLMGeneratedTest dataclass."""

    def test_generated_test_creation(self):
        """Test creating a generated test."""
        scenario = LLMTestScenario(
            name="test_example",
            description="Example test",
            test_type=LLMTestType.INTELLIGENT,
            rationale="Test example",
        )

        test = LLMGeneratedTest(
            name="test_example",
            description="Example test",
            test_type=LLMTestType.INTELLIGENT,
            framework=LLMTestFramework.PYTEST,
            language="python",
            code="def test_example(): pass",
            source_file="app/test.py",
            source_function="example",
            scenario=scenario,
            confidence=0.9,
            tokens_used=100,
        )

        assert test.name == "test_example"
        assert test.framework == LLMTestFramework.PYTEST
        assert test.confidence == 0.9
        assert test.tokens_used == 100
        assert test.scenario is not None


class TestLLMTestSuite:
    """Test LLMTestSuite dataclass."""

    def test_suite_creation(self):
        """Test creating a test suite."""
        suite = LLMTestSuite(
            name="python_llm_tests",
            framework=LLMTestFramework.PYTEST,
            language="python",
            source_files=["app/test.py"],
        )

        assert suite.name == "python_llm_tests"
        assert suite.framework == LLMTestFramework.PYTEST
        assert len(suite.scenarios) == 0
        assert len(suite.test_cases) == 0

    def test_suite_statistics(self):
        """Test test suite statistics calculation."""
        suite = LLMTestSuite(
            name="python_llm_tests",
            framework=LLMTestFramework.PYTEST,
            language="python",
        )

        suite.test_cases = [
            LLMGeneratedTest(
                name="test_1",
                description="Test 1",
                test_type=LLMTestType.INTELLIGENT,
                framework=LLMTestFramework.PYTEST,
                language="python",
                code="pass",
                source_file="test.py",
                confidence=0.8,
                tokens_used=100,
            ),
            LLMGeneratedTest(
                name="test_2",
                description="Test 2",
                test_type=LLMTestType.EDGE_CASE,
                framework=LLMTestFramework.PYTEST,
                language="python",
                code="pass",
                source_file="test.py",
                confidence=0.6,
                tokens_used=150,
            ),
        ]

        stats = suite.get_statistics()

        assert stats["total_tests"] == 2
        assert stats["test_types"][LLMTestType.INTELLIGENT] == 1
        assert stats["test_types"][LLMTestType.EDGE_CASE] == 1
        assert stats["total_tokens_used"] == 0  # Not set directly
        assert pytest.approx(stats["average_confidence"], 0.1) == 0.7

    def test_suite_to_dict(self):
        """Test test suite serialization to dict."""
        suite = LLMTestSuite(
            name="python_llm_tests",
            framework=LLMTestFramework.PYTEST,
            language="python",
        )

        suite.scenarios = [
            LLMTestScenario(
                name="scenario_1",
                description="Test scenario 1",
                test_type=LLMTestType.INTELLIGENT,
                rationale="Rationale",
            )
        ]

        suite.test_cases = [
            LLMGeneratedTest(
                name="test_1",
                description="Test 1",
                test_type=LLMTestType.INTELLIGENT,
                framework=LLMTestFramework.PYTEST,
                language="python",
                code="def test(): pass",
                source_file="test.py",
                confidence=0.8,
                tokens_used=100,
            )
        ]

        suite.total_tokens_used = 100

        data = suite.to_dict()

        assert data["name"] == "python_llm_tests"
        assert data["framework"] == LLMTestFramework.PYTEST
        assert len(data["scenarios"]) == 1
        assert len(data["test_cases"]) == 1
        assert data["total_tokens_used"] == 100
        assert data["statistics"]["total_tests"] == 1


class TestLLMTestGenerator:
    """Test LLM test generator."""

    def test_generator_initialization(self):
        """Test generator can be initialized."""
        generator = LLMTestGenerator()
        assert generator.llm_gateway is not None
        assert generator.prompt_manager is not None

    def test_build_scenario_prompt(self):
        """Test scenario prompt building."""
        generator = LLMTestGenerator()

        source_code = "def add(a, b): return a + b"
        file_path = "math.py"
        language = "python"

        prompt = generator._build_scenario_prompt(source_code, file_path, language, None)

        assert file_path in prompt
        assert source_code in prompt
        assert language in prompt
        assert "edge case" in prompt.lower()
        assert "security" in prompt.lower()

    def test_build_scenario_prompt_with_analysis(self):
        """Test scenario prompt with analysis result."""
        generator = LLMTestGenerator()

        source_code = "def add(a, b): return a + b"
        analysis_result = {"functions": [{"name": "add", "params": ["a", "b"]}]}

        prompt = generator._build_scenario_prompt(source_code, "math.py", "python", analysis_result)

        assert "analysis context" in prompt.lower()

    def test_build_test_code_prompt(self):
        """Test test code prompt building."""
        generator = LLMTestGenerator()

        scenario = LLMTestScenario(
            name="test_large_number_addition",
            description="Test adding large numbers",
            test_type=LLMTestType.EDGE_CASE,
            rationale="Testing integer overflow",
            preconditions=["No memory constraints"],
            test_data={"a": 999999999999, "b": 1},
            expected_behavior="Correct sum or overflow error",
            edge_case_description="Very large integers",
        )

        source_code = "def add(a, b): return a + b"

        prompt = generator._build_test_code_prompt(scenario, source_code, "math.py", "python", LLMTestFramework.PYTEST)

        assert "test_large_number_addition" in prompt
        assert "edge_case" in prompt
        assert "999999999999" in prompt
        assert "pytest" in prompt.lower()

    def test_parse_scenarios_valid_json(self):
        """Test parsing valid JSON scenarios."""
        generator = LLMTestGenerator()

        json_content = """[
            {
                "name": "test_null_input",
                "description": "Test null input handling",
                "test_type": "edge_case",
                "rationale": "Null inputs are common",
                "preconditions": ["DB available"],
                "test_data": {"input": null},
                "expected_behavior": "Returns error",
                "edge_case_description": "Testing with null"
            },
            {
                "name": "test_empty_string",
                "description": "Test empty string",
                "test_type": "edge_case",
                "rationale": "Empty strings need handling"
            }
        ]"""

        scenarios = generator._parse_scenarios(json_content, "test.py")

        assert len(scenarios) == 2
        assert scenarios[0].name == "test_null_input"
        assert scenarios[0].test_type == LLMTestType.EDGE_CASE
        assert scenarios[0].preconditions == ["DB available"]
        assert scenarios[1].name == "test_empty_string"

    def test_parse_scenarios_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        generator = LLMTestGenerator()

        scenarios = generator._parse_scenarios("not json", "test.py")

        assert len(scenarios) == 0

    def test_parse_scenarios_partial_invalid(self):
        """Test parsing with some invalid scenarios."""
        generator = LLMTestGenerator()

        json_content = """[
            {
                "name": "test_valid",
                "description": "Valid test",
                "test_type": "intelligent",
                "rationale": "Valid"
            },
            {
                "name": "test_invalid",
                "description": "Invalid test",
                "test_type": "not_a_type",
                "rationale": "Invalid type"
            }
        ]"""

        scenarios = generator._parse_scenarios(json_content, "test.py")

        # Should skip invalid scenario
        assert len(scenarios) == 1
        assert scenarios[0].name == "test_valid"

    def test_parse_scenarios_malformed_items(self):
        """Test parsing scenarios with missing required fields."""
        generator = LLMTestGenerator()

        json_content = """[
            {
                "name": "test_ok",
                "description": "OK test",
                "test_type": "intelligent",
                "rationale": "OK"
            },
            {
                "description": "Missing name and type"
            }
        ]"""

        scenarios = generator._parse_scenarios(json_content, "test.py")

        # First scenario should work (defaults provided), second might fail
        # At minimum, should have one valid scenario
        assert len(scenarios) >= 1


def test_get_llm_test_generator():
    """Test getting LLM test generator instance."""
    generator = get_llm_test_generator()
    assert isinstance(generator, LLMTestGenerator)
