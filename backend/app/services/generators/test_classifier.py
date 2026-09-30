"""
Test type classification service - Story 1.34

Classifies test cases into appropriate types based on characteristics:
- Unit vs Integration vs E2E classification
- Security test identification
- Performance test detection
- Accessibility test recognition
- Semantic vs structural classification
- Framework-specific classification
- Complexity-based classification

Helps organize and categorize generated tests.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.models.test_case import TestFramework, TestType

logger = logging.getLogger(__name__)


class TestLayer(StrEnum):
    """Test layer/level classification."""
    UNIT = "unit"  # Single function/class
    INTEGRATION = "integration"  # Multiple components
    E2E = "e2e"  # Full system/user flow
    ACCEPTANCE = "acceptance"  # Business requirements


class TestCategory(StrEnum):
    """Test category classification."""
    FUNCTIONAL = "functional"  # Business logic
    NON_FUNCTIONAL = "non_functional"  # Performance, security
    STRUCTURAL = "structural"  # Code structure
    BEHAVIORAL = "behavioral"  # User behavior
    SEMANTIC = "semantic"  # AI-understood meaning


class TestComplexity(StrEnum):
    """Test complexity classification."""
    SIMPLE = "simple"  # Single assertion, straightforward
    MODERATE = "moderate"  # Multiple steps, some setup
    COMPLEX = "complex"  # Many steps, complex setup/teardown
    VERY_COMPLEX = "very_complex"  # Multi-component, extensive setup


@dataclass
class TestClassification:
    """Result of test classification."""
    test_type: TestType
    layer: TestLayer
    category: TestCategory
    complexity: TestComplexity
    tags: list[str]
    confidence: float  # 0.0 to 1.0
    reasoning: str | None = None


@dataclass
class TestAnalysisResult:
    """Analysis result for classification."""
    name: str
    description: str | None
    source_function: str | None
    source_endpoint: str | None
    source_class: str | None
    test_code: str | None
    imports: list[str]
    framework: TestFramework | None
    language: str | None
    has_network_calls: bool
    has_database_calls: bool
    has_external_api_calls: bool
    has_assertions: bool
    assertion_count: int
    setup_complexity: int  # 0-10 scale
    test_steps_count: int
    keywords: list[str]


class TestClassifier:
    """Classifies test cases into appropriate types and categories."""

    def __init__(self):
        # Keywords for different test types
        self.security_keywords = [
            "security",
            "auth",
            "login",
            "permission",
            "authorization",
            "injection",
            "xss",
            "csrf",
            "sql",
            "password",
            "token",
            "encryption",
            "vulnerability",
        ]

        self.performance_keywords = [
            "performance",
            "speed",
            "latency",
            "throughput",
            "load",
            "stress",
            "benchmark",
            "time",
            "duration",
            "optimize",
            "slow",
            "fast",
        ]

        self.accessibility_keywords = [
            "a11y",
            "accessibility",
            "wcag",
            "aria",
            "screen",
            "reader",
            "contrast",
            "focus",
            "keyboard",
            "navigation",
            "label",
        ]

        self.integration_keywords = [
            "integration",
            "api",
            "endpoint",
            "database",
            "external",
            "service",
            "component",
            "module",
        ]

        self.e2e_keywords = [
            "e2e",
            "end-to-end",
            "user",
            "flow",
            "journey",
            "scenario",
            "browser",
            "ui",
            "interface",
            "selenium",
            "playwright",
        ]

    def classify_test(
        self,
        name: str,
        description: str | None = None,
        test_code: str | None = None,
        source_function: str | None = None,
        source_endpoint: str | None = None,
        imports: list[str] | None = None,
        framework: TestFramework | None = None,
    ) -> TestClassification:
        """
        Classify a test case.

        Args:
            name: Test name
            description: Test description
            test_code: Test code
            source_function: Function being tested
            source_endpoint: API endpoint being tested
            imports: Test imports
            framework: Test framework

        Returns:
            TestClassification with type, layer, category, etc.
        """
        # Build analysis result
        analysis = self._analyze_test(
            name=name,
            description=description,
            test_code=test_code or "",
            source_function=source_function,
            source_endpoint=source_endpoint,
            imports=imports or [],
            framework=framework,
        )

        # Determine test type
        test_type = self._determine_test_type(analysis)

        # Determine layer
        layer = self._determine_layer(analysis)

        # Determine category
        category = self._determine_category(analysis, test_type)

        # Determine complexity
        complexity = self._determine_complexity(analysis)

        # Generate tags
        tags = self._generate_tags(analysis, test_type, layer, category, complexity)

        # Calculate confidence
        confidence = self._calculate_confidence(analysis, test_type)

        # Generate reasoning
        reasoning = self._generate_reasoning(analysis, test_type, layer)

        return TestClassification(
            test_type=test_type,
            layer=layer,
            category=category,
            complexity=complexity,
            tags=tags,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _analyze_test(
        self,
        name: str,
        description: str | None,
        test_code: str,
        source_function: str | None,
        source_endpoint: str | None,
        imports: list[str],
        framework: TestFramework | None,
    ) -> TestAnalysisResult:
        """Analyze test for classification features."""

        # Extract keywords
        keywords = self._extract_keywords(name, description, test_code)

        # Check for external dependencies
        has_network_calls = self._has_network_calls(test_code, imports)
        has_database_calls = self._has_database_calls(test_code, imports)
        has_external_api_calls = self._has_external_api_calls(test_code, imports)

        # Count assertions
        assertion_count = self._count_assertions(test_code)

        # Analyze setup complexity
        setup_complexity = self._analyze_setup_complexity(test_code)

        # Count test steps
        test_steps_count = self._count_test_steps(test_code)

        return TestAnalysisResult(
            name=name,
            description=description,
            source_function=source_function,
            source_endpoint=source_endpoint,
            source_class=None,
            test_code=test_code,
            imports=imports,
            framework=framework,
            language=None,
            has_network_calls=has_network_calls,
            has_database_calls=has_database_calls,
            has_external_api_calls=has_external_api_calls,
            has_assertions=assertion_count > 0,
            assertion_count=assertion_count,
            setup_complexity=setup_complexity,
            test_steps_count=test_steps_count,
            keywords=keywords,
        )

    def _analyze_test(
        self,
        name: str,
        description: str | None,
        test_code: str,
        source_function: str | None,
        source_endpoint: str | None,
        imports: list[str],
        framework: TestFramework | None,
    ) -> TestAnalysisResult:
        """Analyze test for classification features."""

        # Extract keywords
        keywords = self._extract_keywords(name, description, test_code)

        # Check for external dependencies
        has_network_calls = self._has_network_calls(test_code, imports)
        has_database_calls = self._has_database_calls(test_code, imports)
        has_external_api_calls = self._has_external_api_calls(test_code, imports)

        # Count assertions
        assertion_count = self._count_assertions(test_code)

        # Analyze setup complexity
        setup_complexity = self._analyze_setup_complexity(test_code)

        # Count test steps
        test_steps_count = self._count_test_steps(test_code)

        return TestAnalysisResult(
            name=name,
            description=description,
            source_function=source_function,
            source_endpoint=source_endpoint,
            source_class=None,
            test_code=test_code,
            imports=imports,
            framework=framework,
            language=None,
            has_network_calls=has_network_calls,
            has_database_calls=has_database_calls,
            has_external_api_calls=has_external_api_calls,
            has_assertions=assertion_count > 0,
            assertion_count=assertion_count,
            setup_complexity=setup_complexity,
            test_steps_count=test_steps_count,
            keywords=keywords,
        )

    def _determine_test_type(self, analysis: TestAnalysisResult) -> TestType:
        """Determine the test type."""

        # Check for security tests
        if any(kw in analysis.keywords for kw in self.security_keywords):
            return TestType.SECURITY

        # Check for performance tests
        if any(kw in analysis.keywords for kw in self.performance_keywords):
            return TestType.PERFORMANCE

        # Check for accessibility tests
        if any(kw in analysis.keywords for kw in self.accessibility_keywords):
            return TestType.ACCESSIBILITY

        # Check for E2E indicators
        if (
            any(kw in analysis.keywords for kw in self.e2e_keywords)
            or analysis.framework in [TestFramework.SELENIUM, TestFramework.PLAYWRIGHT, TestFramework.APPIUM, TestFramework.CYPRESS]
        ):
            return TestType.E2E

        # Check for integration indicators
        if (
            any(kw in analysis.keywords for kw in self.integration_keywords)
            or analysis.has_database_calls
            or analysis.has_external_api_calls
            or analysis.has_network_calls
        ):
            return TestType.INTEGRATION

        # Default to unit
        return TestType.UNIT

    def _determine_layer(self, analysis: TestAnalysisResult) -> TestLayer:
        """Determine the test layer."""

        # Check for E2E framework
        if analysis.framework in [TestFramework.SELENIUM, TestFramework.PLAYWRIGHT, TestFramework.APPIUM, TestFramework.CYPRESS]:
            return TestLayer.E2E

        # Check for E2E keywords
        if any(kw in analysis.keywords for kw in self.e2e_keywords):
            return TestLayer.E2E

        if analysis.has_database_calls or analysis.has_external_api_calls:
            return TestLayer.INTEGRATION

        if analysis.source_endpoint and not analysis.has_database_calls:
            # Could be integration or unit depending on implementation
            if analysis.has_network_calls:
                return TestLayer.INTEGRATION
            return TestLayer.UNIT

        return TestLayer.UNIT

    def _determine_category(
        self, analysis: TestAnalysisResult, test_type: TestType
    ) -> TestCategory:
        """Determine the test category."""

        if test_type in [TestType.SECURITY, TestType.PERFORMANCE, TestType.ACCESSIBILITY]:
            return TestCategory.NON_FUNCTIONAL

        if test_type == TestType.E2E:
            return TestCategory.BEHAVIORAL

        if analysis.has_assertions and analysis.assertion_count > 0:
            return TestCategory.FUNCTIONAL

        return TestCategory.STRUCTURAL

    def _determine_complexity(self, analysis: TestAnalysisResult) -> TestComplexity:
        """Determine test complexity."""

        complexity_score = 0

        # Setup complexity (0-10)
        complexity_score += analysis.setup_complexity

        # Test steps count
        if analysis.test_steps_count > 10:
            complexity_score += 4
        elif analysis.test_steps_count > 5:
            complexity_score += 2
        elif analysis.test_steps_count > 2:
            complexity_score += 1

        # External dependencies
        if analysis.has_external_api_calls:
            complexity_score += 2
        if analysis.has_database_calls:
            complexity_score += 1
        if analysis.has_network_calls:
            complexity_score += 1

        # Assertion count
        if analysis.assertion_count > 5:
            complexity_score += 1

        # Classify based on score
        if complexity_score <= 3:
            return TestComplexity.SIMPLE
        elif complexity_score <= 6:
            return TestComplexity.MODERATE
        elif complexity_score <= 10:
            return TestComplexity.COMPLEX
        else:
            return TestComplexity.VERY_COMPLEX

    def _generate_tags(
        self,
        analysis: TestAnalysisResult,
        test_type: TestType,
        layer: TestLayer,
        category: TestCategory,
        complexity: TestComplexity,
    ) -> list[str]:
        """Generate tags for the test."""
        tags = []

        # Add type/layer/category tags
        tags.append(test_type.value)
        tags.append(layer.value)
        tags.append(category.value)

        # Add framework tag
        if analysis.framework:
            tags.append(analysis.framework.value)

        # Add feature-specific tags
        if analysis.has_database_calls:
            tags.append("database")
        if analysis.has_network_calls:
            tags.append("network")
        if analysis.has_external_api_calls:
            tags.append("external-api")

        # Add complexity tag
        tags.append(f"complexity:{complexity.value}")

        return tags

    def _calculate_confidence(
        self, analysis: TestAnalysisResult, test_type: TestType
    ) -> float:
        """Calculate classification confidence."""

        confidence = 0.5  # Base confidence

        # Increase if test has clear indicators
        if analysis.source_function:
            confidence += 0.1
        if analysis.source_endpoint:
            confidence += 0.1
        if len(analysis.keywords) > 0:
            confidence += 0.2
        if analysis.assertion_count > 0:
            confidence += 0.1

        return min(confidence, 1.0)

    def _generate_reasoning(
        self, analysis: TestAnalysisResult, test_type: TestType, layer: TestLayer
    ) -> str:
        """Generate human-readable reasoning for classification."""

        parts = []

        parts.append(f"Classified as {test_type.value} test")

        if layer == TestLayer.UNIT:
            parts.append("because it tests a single unit")
        elif layer == TestLayer.INTEGRATION:
            parts.append("because it involves multiple components")
        elif layer == TestLayer.E2E:
            parts.append("because it tests end-to-end flow")

        if analysis.has_database_calls:
            parts.append("and includes database operations")
        if analysis.has_external_api_calls:
            parts.append("and calls external APIs")

        return ". ".join(parts) + "."

    def _extract_keywords(
        self, name: str, description: str | None, test_code: str
    ) -> list[str]:
        """Extract classification keywords from test."""
        keywords = []

        # From name
        keywords.extend(name.lower().split("_"))

        # From description
        if description:
            keywords.extend(description.lower().split())

        # From test code (limited)
        if test_code:
            code_words = test_code.lower().split()
            keywords.extend(code_words[:20])  # Limit to prevent noise

        return list(set(kw for kw in keywords if len(kw) > 2))

    def _has_network_calls(self, test_code: str, imports: list[str]) -> bool:
        """Check if test makes network calls."""
        network_indicators = ["requests.", "httpx.", "urllib", "fetch(", "axios."]
        return any(ind in test_code.lower() for ind in network_indicators)

    def _has_database_calls(self, test_code: str, imports: list[str]) -> bool:
        """Check if test makes database calls."""
        db_indicators = ["session.", "db.", "query(", "execute(", ".select(", ".insert("]
        db_imports = ["sqlalchemy", "django.db", "prisma", "mongoose"]
        return (
            any(ind in test_code.lower() for ind in db_indicators)
            or any(imp in str(imports).lower() for imp in db_imports)
        )

    def _has_external_api_calls(self, test_code: str, imports: list[str]) -> bool:
        """Check if test calls external APIs."""
        api_indicators = ["api.", "client.", "http.", "response"]
        return any(ind in test_code.lower() for ind in api_indicators)

    def _count_assertions(self, test_code: str) -> int:
        """Count assertions in test code."""
        assertion_patterns = ["assert", "expect", "should.", "verify"]
        count = 0
        for pattern in assertion_patterns:
            count += test_code.lower().count(pattern)
        return count

    def _analyze_setup_complexity(self, test_code: str) -> int:
        """Analyze test setup complexity (0-10 scale)."""
        complexity = 0

        # Check for fixtures
        if "fixture" in test_code.lower() or "pytest.fixture" in test_code:
            complexity += 2

        # Check for setup methods
        if "setup" in test_code.lower() or "beforeEach" in test_code:
            complexity += 1

        # Check for mocking
        if "mock" in test_code.lower() or "stub" in test_code.lower():
            complexity += 2

        # Check for test data creation
        if "create" in test_code.lower() or "factory" in test_code.lower():
            complexity += 1

        return min(complexity, 10)

    def _count_test_steps(self, test_code: str) -> int:
        """Count distinct test steps."""
        step_indicators = ["given", "when", "then", "step", "call(", "execute("]
        count = 0
        for indicator in step_indicators:
            count += test_code.lower().count(indicator)
        return count


def get_test_classifier() -> TestClassifier:
    """Get or create test classifier instance."""
    return TestClassifier()
