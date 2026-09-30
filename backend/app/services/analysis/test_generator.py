"""Test generator module for Epic 2.

This module generates test cases from requirements using templates
and pattern matching for different requirement types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.document import (
        DocumentStructure,
        ExtractedRequirementSchema,
    )


@dataclass
class GeneratedTestCase:
    """Generated test case from requirement."""

    test_id: str
    name: str
    description: str
    steps: list[str]
    expected_result: str
    priority: str
    requirement_id: str
    test_type: str  # 'functional', 'api', 'ui', 'performance', 'security'
    automation_feasibility: str  # 'auto', 'manual', 'semi_auto'
    generated_code: str | None = None


@dataclass
class TestGenerationResult:
    """Result of test generation operation."""

    document_name: str
    total_requirements: int
    generated_tests: int
    tests: list[GeneratedTestCase]
    coverage_percentage: float


class TestGenerator:
    """Generate test cases from requirements.

    Analyzes requirements and generates appropriate test cases
    based on requirement type and priority.
    """

    def __init__(self) -> None:
        self.test_counter = 0

    def generate(
        self,
        doc: DocumentStructure,
        requirements: list[ExtractedRequirementSchema],
    ) -> TestGenerationResult:
        """Generate test cases from requirements.

        Args:
            doc: Document structure
            requirements: Extracted requirements

        Returns:
            Test generation result
        """
        tests: list[GeneratedTestCase] = []

        for req in requirements:
            test_cases = self._generate_tests_for_requirement(req, doc)
            tests.extend(test_cases)

        # Calculate coverage (requirements with at least one test)
        requirements_with_tests = len(set(t.requirement_id for t in tests))
        coverage = requirements_with_tests / len(requirements) * 100 if requirements else 0.0

        return TestGenerationResult(
            document_name=doc.metadata.get("filename", "Unknown"),
            total_requirements=len(requirements),
            generated_tests=len(tests),
            tests=tests,
            coverage_percentage=coverage,
        )

    def _generate_tests_for_requirement(
        self,
        req: ExtractedRequirementSchema,
        doc: DocumentStructure,
    ) -> list[GeneratedTestCase]:
        """Generate test cases for a single requirement.

        Args:
            req: Requirement to generate tests for
            doc: Document structure for context

        Returns:
            List of generated test cases
        """
        tests: list[GeneratedTestCase] = []

        # Determine test type based on requirement
        test_type = self._determine_test_type(req)

        # Generate test name and description
        test_name = self._generate_test_name(req)
        test_description = req["text"]

        # Generate steps based on requirement text
        steps = self._generate_test_steps(req)

        # Generate expected result
        expected_result = self._generate_expected_result(req)

        # Determine automation feasibility
        automation = self._determine_automation_feasibility(req)

        test = GeneratedTestCase(
            test_id=f"TC-{self.test_counter:03d}",
            name=test_name,
            description=test_description,
            steps=steps,
            expected_result=expected_result,
            priority=req.get("priority", "medium") or "medium",
            requirement_id=req["req_id"],
            test_type=test_type,
            automation_feasibility=automation,
        )
        tests.append(test)

        self.test_counter += 1

        # For complex requirements, generate additional test cases
        if self._is_complex_requirement(req):
            # Negative test case
            negative_test = self._generate_negative_test(req)
            if negative_test:
                tests.append(negative_test)

        return tests

    def _determine_test_type(self, req: ExtractedRequirementSchema) -> str:
        """Determine appropriate test type for requirement.

        Args:
            req: Requirement to analyze

        Returns:
            Test type string
        """
        text_lower = req["text"].lower()

        # Performance-related requirements
        if any(kw in text_lower for kw in ["czas", "opóźnienie", "wydajność", "sekund", "procent"]):
            return "performance"

        # Security-related requirements
        if any(kw in text_lower for kw in ["bezpieczeń", "autoryzacj", "uprawnien", "szyfrowani"]):
            return "security"

        # UI-related requirements
        if any(kw in text_lower for kw in ["interfejs", "ekran", "formularz", "przycisk"]):
            return "ui"

        # API-related requirements
        if any(kw in text_lower for kw in ["api", "endpoint", "json", "http"]):
            return "api"

        return "functional"

    def _generate_test_name(self, req: ExtractedRequirementSchema) -> str:
        """Generate descriptive test name from requirement.

        Args:
            req: Requirement to name test for

        Returns:
            Test name
        """
        # Extract key action/object from requirement
        text = req["text"]

        # Remove common prefixes
        prefixes_to_remove = ["System ", "Aplikacja ", "Moduł "]
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                text = text[len(prefix) :]

        # Truncate and clean
        name = text[:60] + ("..." if len(text) > 60 else "")
        return f"Test: {name}"

    def _generate_test_steps(self, req: ExtractedRequirementSchema) -> list[str]:
        """Generate test steps from requirement text.

        Args:
            req: Requirement to generate steps for

        Returns:
            List of test steps
        """
        text = req["text"]

        # Parse requirement into actionable steps
        steps: list[str] = []

        # Common patterns
        if "zaloguj" in text.lower() or "logowanie" in text.lower():
            steps = [
                "Otwórz stronę logowania",
                "Wprowadź poprawne dane logowania",
                "Kliknij przycisk 'Zaloguj'",
                "Weryfikuj poprawne zalogowania",
            ]
        elif "rejestracj" in text.lower():
            steps = [
                "Otwórz formularz rejestracji",
                "Wypełnij wszystkie wymagane pola",
                "Zaakceptuj regulamin",
                "Kliknij 'Zarejestruj'",
                "Weryfikuj utworzenie konta",
            ]
        else:
            # Generic steps for other requirements
            steps = [
                "Przygotuj środowisko testowe",
                f"Wykonuj czynność: {text[:50]}...",
                "Weryfikuj wynik",
            ]

        return steps

    def _generate_expected_result(self, req: ExtractedRequirementSchema) -> str:
        """Generate expected result from requirement.

        Args:
            req: Requirement to analyze

        Returns:
            Expected result description
        """
        text = req["text"]

        # Common patterns for expected results
        if "zostało utworzone" in text.lower():
            return "Konto użytkownika zostało pomyślnie utworzone"

        if "zalogowany" in text.lower() or "zalogować się" in text.lower():
            return "Użytkownik jest zalogowany do systemu"

        if "błąd" in text.lower() or "błędu" in text.lower():
            return "System wyświetla odpowiedni komunikat błędu"

        # Generic expected result
        return "System zachowuje się zgodnie z wymaganieniem"

    def _determine_automation_feasibility(self, req: ExtractedRequirementSchema) -> str:
        """Determine if test can be automated.

        Args:
            req: Requirement to analyze

        Returns:
            Automation feasibility
        """
        text_lower = req["text"].lower()

        # Hard to automate indicators
        if any(kw in text_lower for kw in ["wizualnie", "ręcznie", "manulnie", "ocena"]):
            return "manual"

        # UI tests often require human verification
        if req["type"] == "functional" and any(kw in text_lower for kw in ["ekran", "interfejs", "widoczny"]):
            return "semi_auto"

        # Security tests often require manual verification
        if req["type"] == "non-functional" and "bezpieczeń" in text_lower:
            return "manual"

        # Most functional and API tests can be automated
        return "auto"

    def _is_complex_requirement(self, req: ExtractedRequirementSchema) -> bool:
        """Check if requirement is complex enough for multiple tests.

        Args:
            req: Requirement to check

        Returns:
            True if requirement is complex
        """
        # Complex if long or contains multiple conditions
        return len(req["text"]) > 100 or "lub" in req["text"].lower()[:50]

    def _generate_negative_test(self, req: ExtractedRequirementSchema) -> GeneratedTestCase | None:
        """Generate negative test case for requirement.

        Args:
            req: Requirement to generate negative test for

        Returns:
            Negative test case or None
        """
        # Only generate negative tests for certain requirement types
        if req["type"] != "functional":
            return None

        self.test_counter += 1

        return GeneratedTestCase(
            test_id=f"TC-{self.test_counter:03d}",
            name=f"Test (negatywny): {req['req_id']}",
            description=f"Weryfikacja zachowania przy nieprawidłowych danych: {req['text'][:50]}",
            steps=[
                "Przygotuj nieprawidłowe dane testowe",
                "Wykonaj czynność zgodnie z wymaganieniem",
                "Weryfikuj wystąpienie błędu/odrzucenia",
            ],
            expected_result="System odrzuca nieprawidłowe dane z odpowiednim komunikatem",
            priority=req.get("priority", "medium") or "medium",
            requirement_id=req["req_id"],
            test_type="functional",
            automation_feasibility="auto",
        )


def generate_tests_from_requirements(
    doc: DocumentStructure,
    requirements: list[ExtractedRequirementSchema],
) -> TestGenerationResult:
    """Convenience function to generate tests from requirements.

    Args:
        doc: Document structure
        requirements: Extracted requirements

    Returns:
        Test generation result
    """
    generator = TestGenerator()
    return generator.generate(doc, requirements)


# ── Persistence (result_data) — Story 2.10 closure ────────────────────────────


def test_generation_to_result_data(result: TestGenerationResult) -> dict[str, Any]:
    """Serialize a ``TestGenerationResult`` into a flat ``result_data`` payload.

    Mirrors the traceability serializer (Story 2.9): the shape is already flat,
    so it is stored 1:1 in the frontend's ``TestGenerationResult`` interface
    shape and the API returns ``result_data`` directly (no deserializer needed).
    Each entry matches ``GeneratedTestCase`` (``test_id`` / ``name`` /
    ``description`` / ``steps`` / ``expected_result`` / ``priority`` /
    ``requirement_id`` / ``test_type`` / ``automation_feasibility``).

    The previous ``statistics`` leak (``tests.__dict__``) is intentionally
    dropped — it duplicated the explicit top-level fields and had no consumer
    (the API call was live-dead before this closure).
    """
    return {
        "document_name": result.document_name,
        "total_requirements": result.total_requirements,
        "generated_tests": result.generated_tests,
        "coverage_percentage": result.coverage_percentage,
        "tests": [
            {
                "test_id": t.test_id,
                "name": t.name,
                "description": t.description,
                "steps": list(t.steps),
                "expected_result": t.expected_result,
                "priority": t.priority,
                "requirement_id": t.requirement_id,
                "test_type": t.test_type,
                "automation_feasibility": t.automation_feasibility,
            }
            for t in result.tests
        ],
    }
