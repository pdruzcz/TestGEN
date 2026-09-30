"""Conformance error detector — Epic 5, Story 5.4.

Detects:
  - Public functions / classes without docstring
  - Non-snake_case function names (Python convention heuristic)
"""

import re

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.gap_analysis.error_detectors.base import (
    BaseDetector,
    DetectedError,
)

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
_PASCAL_CASE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


class ConformanceDetector(BaseDetector):
    """Detect convention and documentation conformance issues."""

    category = ErrorCategory.CONFORMANCE

    def detect(
        self,
        tree: ASTTree,
        file_path: str | None = None,
    ) -> list[DetectedError]:
        errors: list[DetectedError] = []

        for func in tree.all_functions():
            if func.name.startswith("_"):
                continue

            # Missing docstring on public function
            if not func.docstring:
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Funkcja publiczna '{func.name}' nie ma "
                            f"docstring"
                        ),
                        file_path=file_path,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        severity="info",
                        rule_id="MISSING_DOCSTRING",
                        suggestion="Dodaj docstring opisujący działanie funkcji.",
                        context={"function": func.name},
                    ),
                )

            # Snake_case convention (Python only)
            if tree.language == "python" and not _SNAKE_CASE.match(func.name):
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Nazwa funkcji '{func.name}' nie jest snake_case"
                        ),
                        file_path=file_path,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        severity="info",
                        rule_id="NAMING_CONVENTION",
                        suggestion="Użyj konwencji snake_case dla nazw funkcji.",
                        context={"function": func.name},
                    ),
                )

        for cls in tree.all_classes():
            if not cls.docstring:
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=f"Klasa '{cls.name}' nie ma docstring",
                        file_path=file_path,
                        line_start=cls.line_start,
                        line_end=cls.line_end,
                        severity="info",
                        rule_id="MISSING_CLASS_DOCSTRING",
                        suggestion="Dodaj docstring opisujący klasę.",
                        context={"class": cls.name},
                    ),
                )

            # PascalCase convention (Python only)
            if tree.language == "python" and not _PASCAL_CASE.match(cls.name):
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Nazwa klasy '{cls.name}' nie jest PascalCase"
                        ),
                        file_path=file_path,
                        line_start=cls.line_start,
                        line_end=cls.line_end,
                        severity="info",
                        rule_id="CLASS_NAMING_CONVENTION",
                        suggestion="Użyj konwencji PascalCase dla nazw klas.",
                        context={"class": cls.name},
                    ),
                )

        return errors
