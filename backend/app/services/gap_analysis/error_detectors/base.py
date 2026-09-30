"""Base classes for code error detectors — Epic 5, Story 5.4."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree


@dataclass
class DetectedError:
    """Intermediate representation — converted to CodeError ORM by the task."""

    category: ErrorCategory
    message: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    severity: str = "warning"
    rule_id: str | None = None
    suggestion: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


class BaseDetector(ABC):
    """Abstract base for all code error detectors."""

    category: ErrorCategory

    @abstractmethod
    def detect(
        self,
        tree: ASTTree,
        file_path: str | None = None,
    ) -> list[DetectedError]:
        """Run detection on a parsed AST tree."""
