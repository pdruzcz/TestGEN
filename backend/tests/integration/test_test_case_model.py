"""Tests for TestCase model - Story 1.31"""

import uuid

from app.models.test_case import (
    GenerationEngine,
    TestCase,
    TestCaseExecution,
    TestCaseStatus,
    TestFramework,
    TestPriority,
    TestType,
)


class TestTestPriority:
    """Test TestPriority enum."""

    def test_priority_values(self):
        """Test all priority values exist."""
        assert TestPriority.CRITICAL == "critical"
        assert TestPriority.HIGH == "high"
        assert TestPriority.MEDIUM == "medium"
        assert TestPriority.LOW == "low"


class TestTestType:
    """Test TestType enum."""

    def test_type_values(self):
        """Test all test type values exist."""
        assert TestType.UNIT == "unit"
        assert TestType.INTEGRATION == "integration"
        assert TestType.E2E == "e2e"
        assert TestType.SECURITY == "security"
        assert TestType.PERFORMANCE == "performance"
        assert TestType.POSITIVE == "positive"
        assert TestType.NEGATIVE == "negative"
        assert TestType.BOUNDARY == "boundary"
        assert TestType.ACCESSIBILITY == "accessibility"
        assert TestType.SEMANTIC == "semantic"


class TestTestFramework:
    """Test TestFramework enum."""

    def test_framework_values(self):
        """Test all framework values exist."""
        assert TestFramework.PYTEST == "pytest"
        assert TestFramework.JUNIT == "junit"
        assert TestFramework.NUNIT == "nunit"
        assert TestFramework.MOCHA == "mocha"
        assert TestFramework.JEST == "jest"
        assert TestFramework.SELENIUM == "selenium"
        assert TestFramework.PLAYWRIGHT == "playwright"
        assert TestFramework.APPIUM == "appium"
        assert TestFramework.CYPRESS == "cypress"
        assert TestFramework.SIKULIX == "sikulix"


class TestEnumTestCaseStatus:
    """Test TestCaseStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert TestCaseStatus.DRAFT == "draft"
        assert TestCaseStatus.READY == "ready"
        assert TestCaseStatus.PASSED == "passed"
        assert TestCaseStatus.FAILED == "failed"
        assert TestCaseStatus.SKIPPED == "skipped"
        assert TestCaseStatus.DISABLED == "disabled"


class TestGenerationEngine:
    """Test GenerationEngine enum."""

    def test_engine_values(self):
        """Test all engine values exist."""
        assert GenerationEngine.NATIVE == "native"
        assert GenerationEngine.LLM == "llm"
        assert GenerationEngine.HYBRID == "hybrid"


class TestTestCase:
    """Test TestCase model."""

    def test_test_case_creation(self):
        """Test creating a test case."""
        test_case = TestCase(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            analysis_result_id=uuid.uuid4(),
            title="Test user login",
            description="Verify user can login with valid credentials",
            priority=TestPriority.HIGH,
            type=TestType.POSITIVE,
            framework=TestFramework.PYTEST,
            language="python",
            generation_engine=GenerationEngine.NATIVE,
            source_function="login",
            test_code="def test_login(): pass",
            status=TestCaseStatus.DRAFT,
        )

        assert test_case.title == "Test user login"
        assert test_case.type == TestType.POSITIVE
        assert test_case.framework == TestFramework.PYTEST
        assert test_case.status == TestCaseStatus.DRAFT

    def test_test_case_to_dict(self):
        """Test test case serialization."""
        test_case = TestCase(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            analysis_result_id=uuid.uuid4(),
            title="Test",
            type=TestType.UNIT,
            generation_engine=GenerationEngine.NATIVE,
            status=TestCaseStatus.DRAFT,
        )

        data = test_case.to_dict()

        assert "id" in data
        assert "title" in data
        assert "type" in data
        assert "framework" in data
        assert "status" in data

    def test_test_case_with_scenario_info(self):
        """Test test case with AI scenario info."""
        test_case = TestCase(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            analysis_result_id=uuid.uuid4(),
            title="Test null input",
            type=TestType.BOUNDARY,
            generation_engine=GenerationEngine.LLM,
            status=TestCaseStatus.DRAFT,
            scenario_description="Test with null input",
            scenario_rationale="Null inputs are common edge case",
            edge_case_description="Testing with None/null value",
            confidence_score=0.85,
        )

        assert test_case.scenario_description == "Test with null input"
        assert test_case.confidence_score == 0.85

    def test_test_case_execution_tracking(self):
        """Test execution tracking fields."""
        test_case = TestCase(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            analysis_result_id=uuid.uuid4(),
            title="Test",
            type=TestType.UNIT,
            generation_engine=GenerationEngine.NATIVE,
            status=TestCaseStatus.PASSED,
            execution_count=5,
            pass_count=4,
            fail_count=1,
        )

        assert test_case.execution_count == 5
        assert test_case.pass_count == 4
        assert test_case.fail_count == 1


class TestTestCaseExecution:
    """Test TestCaseExecution model."""

    def test_execution_creation(self):
        """Test creating an execution record."""
        execution = TestCaseExecution(
            id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            status="passed",
            execution_duration_ms=150,
            lines_covered=25,
            coverage_percentage=85.5,
        )

        assert execution.status == "passed"
        assert execution.execution_duration_ms == 150
        assert execution.coverage_percentage == 85.5

    def test_execution_to_dict(self):
        """Test execution serialization."""
        execution = TestCaseExecution(
            id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            status="passed",
        )

        data = execution.to_dict()

        assert "id" in data
        assert "test_case_id" in data
        assert "status" in data
        assert "executed_at" in data

    def test_execution_with_error(self):
        """Test execution with error info."""
        execution = TestCaseExecution(
            id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            status="failed",
            error_message="AssertionError: Expected 200 but got 500",
            error_stack_trace="Traceback...",
        )

        assert execution.status == "failed"
        assert execution.error_message is not None
        assert execution.error_stack_trace is not None

    def test_execution_with_coverage(self):
        """Test execution with coverage data."""
        execution = TestCaseExecution(
            id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            status="passed",
            lines_covered=50,
            branches_covered=10,
            coverage_percentage=92.5,
        )

        assert execution.lines_covered == 50
        assert execution.branches_covered == 10
        assert execution.coverage_percentage == 92.5
