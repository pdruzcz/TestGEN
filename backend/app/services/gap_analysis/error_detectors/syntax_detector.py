"""Syntax error detector — Epic 5, Story 5.4.

Uses tree-sitter ERROR / MISSING nodes already captured in ASTTree.
No additional parsing needed.
"""

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.gap_analysis.error_detectors.base import (
    BaseDetector,
    DetectedError,
)


class SyntaxDetector(BaseDetector):
    """Detect syntax errors from tree-sitter parse output."""

    category = ErrorCategory.SYNTAX

    def detect(
        self,
        tree: ASTTree,
        file_path: str | None = None,
    ) -> list[DetectedError]:
        errors: list[DetectedError] = []

        for err_node in tree.error_nodes:
            errors.append(
                DetectedError(
                    category=self.category,
                    message=err_node.message
                    or f"Błąd składni w linii {err_node.line_start}",
                    file_path=file_path,
                    line_start=err_node.line_start,
                    line_end=err_node.line_end,
                    severity="critical",
                    rule_id="SYNTAX_ERROR",
                    suggestion="Napraw błąd składni, aby kod był poprawny.",
                    context={"node_type": err_node.type},
                )
            )

        return errors
