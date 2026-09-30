"""Semantic error detector — Epic 5, Story 5.4.

Detects:
  - Public functions without return type annotation
  - Parameters without type annotations (except self / cls)
"""

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.gap_analysis.error_detectors.base import (
    BaseDetector,
    DetectedError,
)

_SELF_PARAMS = {"self", "cls"}


class SemanticDetector(BaseDetector):
    """Detect semantic-level type annotation issues."""

    category = ErrorCategory.SEMANTIC

    def detect(
        self,
        tree: ASTTree,
        file_path: str | None = None,
    ) -> list[DetectedError]:
        errors: list[DetectedError] = []

        for func in tree.all_functions():
            # Skip dunder / private
            if func.name.startswith("_"):
                continue

            # Missing return type on public function
            if not func.return_type:
                errors.append(
                    DetectedError(
                        category=self.category,
                        message=(
                            f"Funkcja '{func.name}' nie ma adnotacji "
                            f"typu zwracanego"
                        ),
                        file_path=file_path,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        severity="info",
                        rule_id="MISSING_RETURN_TYPE",
                        suggestion="Dodaj adnotację typu zwracanego.",
                        context={"function": func.name},
                    ),
                )

            # Parameters without type annotations
            for param in func.parameters:
                if param.name in _SELF_PARAMS:
                    continue
                if param.type is None:
                    errors.append(
                        DetectedError(
                            category=self.category,
                            message=(
                                f"Parametr '{param.name}' w funkcji "
                                f"'{func.name}' nie ma adnotacji typu"
                            ),
                            file_path=file_path,
                            line_start=func.line_start,
                            line_end=func.line_end,
                            severity="info",
                            rule_id="MISSING_PARAM_TYPE",
                            suggestion=f"Dodaj adnotację typu dla parametru '{param.name}'.",
                            context={
                                "function": func.name,
                                "parameter": param.name,
                            },
                        ),
                    )

        return errors
