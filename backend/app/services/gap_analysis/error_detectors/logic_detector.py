"""Logic error detector — Epic 5, Story 5.4.

Detects:
  - Empty / trivial function bodies (only `pass`)
  - Functions with declared return type but no return statement
  - Excessive cyclomatic complexity (>15)
"""

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.gap_analysis.error_detectors.base import (
    BaseDetector,
    DetectedError,
)

_COMPLEXITY_THRESHOLD = 15


class LogicDetector(BaseDetector):
    """Detect logic-level code issues."""

    category = ErrorCategory.LOGIC

    def detect(
        self,
        tree: ASTTree,
        file_path: str | None = None,
    ) -> list[DetectedError]:
        errors: list[DetectedError] = []

        for func in tree.all_functions():
            # Empty / trivial body — complexity 1 and ≤3 LOC
            body_span = func.line_end - func.line_start
            if func.complexity <= 1 and body_span <= 2:
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Funkcja '{func.name}' ma pustą lub trywialną "
                            f"treść (może brakować implementacji)"
                        ),
                        file_path=file_path,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        severity="warning",
                        rule_id="EMPTY_FUNCTION",
                        suggestion=(
                            "Dodaj implementację lub oznacz jako abstrakcyjną."
                        ),
                        context={"function": func.name},
                    ),
                )

            # Declared return type but complexity=1 suggests no return path
            if (
                func.return_type
                and func.return_type != "void"
                and func.complexity <= 1
                and func.name != "__init__"
            ):
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Funkcja '{func.name}' deklaruje zwracany typ "
                            f"'{func.return_type}', ale może nie mieć "
                            f"instrukcji return"
                        ),
                        file_path=file_path,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        severity="warning",
                        rule_id="MISSING_RETURN",
                        suggestion="Dodaj instrukcję return lub zmień typ na void.",
                        context={
                            "function": func.name,
                            "return_type": func.return_type,
                        },
                    ),
                )

            # High complexity
            if func.complexity > _COMPLEXITY_THRESHOLD:
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Funkcja '{func.name}' ma wysoką złożoność "
                            f"cyklomatyczną ({func.complexity})"
                        ),
                        file_path=file_path,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        severity="warning",
                        rule_id="HIGH_COMPLEXITY",
                        suggestion="Rozważ rozbicie funkcji na mniejsze.",
                        context={
                            "function": func.name,
                            "complexity": func.complexity,
                        },
                    ),
                )

        return errors
