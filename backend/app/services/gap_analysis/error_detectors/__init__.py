"""Code error detection detectors — Epic 5, Stories 5.4 + 5.10.

Detector categories operating on parsed ASTTree data:
  - syntax:       tree-sitter parse errors
  - logic:        empty functions, high complexity, missing returns
  - semantic:     missing type annotations
  - conformance:  missing docstrings, naming convention violations
  - dead_code:    project-wide uncalled private/internal code (5.10)
"""

from app.services.gap_analysis.error_detectors.base import (
    BaseDetector,
    DetectedError,
)
from app.services.gap_analysis.error_detectors.conformance_detector import (
    ConformanceDetector,
)
from app.services.gap_analysis.error_detectors.dead_code_detector import (
    DeadCodeDetector,
    ParsedFile,
)
from app.services.gap_analysis.error_detectors.logic_detector import (
    LogicDetector,
)
from app.services.gap_analysis.error_detectors.semantic_detector import (
    SemanticDetector,
)
from app.services.gap_analysis.error_detectors.syntax_detector import (
    SyntaxDetector,
)

__all__ = [
    "BaseDetector",
    "ConformanceDetector",
    "DeadCodeDetector",
    "DetectedError",
    "LogicDetector",
    "ParsedFile",
    "SemanticDetector",
    "SyntaxDetector",
]
