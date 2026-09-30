"""PlantUML parser — detects diagram type and routes to sub-parsers.

Story 3.1 provides the router, preprocessing, diagram-type scoring, and a
generic structural extraction. Stories 3.2-3.6 register specialized
sub-parsers per diagram type through ``register_subparser``.
"""

import re

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.parsers.base import (
    IPlantUMLSubParser,
    ParsedModel,
    ValidationResult,
)

# Keyword scoring weights per diagram type (architektura sekcja 3.4).
DIAGRAM_KEYWORDS: dict[DiagramType, list[str]] = {
    DiagramType.SEQUENCE: ["participant", "actor", "->", "-->", "alt ", "loop ", "opt ", "activate"],
    DiagramType.USE_CASE: ["usecase", "include", "extends", "left to right direction"],
    DiagramType.CLASS: ["class ", "interface ", "abstract ", "<|--", "..|>", "*--", "o--", "-->"],
    DiagramType.ACTIVITY: ["start", "stop", "if (", "fork", "endif", "endwhile", "repeat"],
    DiagramType.STATE_MACHINE: ["[*]", "state ", "-->"],
}

_COMMENT_RE = re.compile(r"^\s*'.*$", re.MULTILINE)

# Decisive class-diagram markers: structural declarations and the composition /
# aggregation / realization arrows. These tokens do not occur in sequence,
# use-case, activity or state diagrams, so a match short-circuits type scoring
# (whose naive ``:`` / ``->`` keyword counting is dominated by typed members).
_CLASS_MARKER_RE = re.compile(
    r"(?m)^\s*(?:abstract\s+class|class|interface|enum)\s+[\"\w]|\*--|o--|\.\.\|>|<\|\.\.|<\|--",
)


def is_class_diagram(text: str) -> bool:
    return bool(_CLASS_MARKER_RE.search(text))


class PlantUMLParser:
    """Top-level PlantUML parser that routes to per-type sub-parsers."""

    def __init__(self) -> None:
        self._subparsers: dict[DiagramType, IPlantUMLSubParser] = {}

    def register_subparser(self, parser: IPlantUMLSubParser) -> None:
        """Register a specialized sub-parser for a diagram type."""
        self._subparsers[parser.supported_type()] = parser

    def supported_type(self) -> DiagramType | None:
        return None  # router — no single supported type

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "@startuml" not in content:
            errors.append("Brak znacznika @startuml")
        if "@enduml" not in content:
            errors.append("Brak znacznika @enduml")
        return ValidationResult(is_valid=not errors, errors=errors)

    def parse(self, content: str) -> ParsedModel:
        text = self._preprocess(content)
        diagram_type = self._extract_diagram_type(text)
        sub = self._subparsers.get(diagram_type)
        if sub is not None:
            return sub.parse_plantuml(text)
        return self._generic_parse(text, diagram_type)

    def _preprocess(self, text: str) -> str:
        """Strip single-quote comments and normalize blank lines."""
        without_comments = _COMMENT_RE.sub("", text)
        lines = [line.rstrip() for line in without_comments.splitlines()]
        return "\n".join(line for line in lines if line.strip())

    def _extract_diagram_type(self, text: str) -> DiagramType:
        from app.services.analysis.uml.parsers.activity import is_activity_diagram
        from app.services.analysis.uml.parsers.state_machine import is_state_diagram

        if is_class_diagram(text):
            return DiagramType.CLASS
        if is_activity_diagram(text):
            return DiagramType.ACTIVITY
        if is_state_diagram(text):
            return DiagramType.STATE_MACHINE
        lowered = text.lower()
        scores: dict[DiagramType, int] = {dt: 0 for dt in DIAGRAM_KEYWORDS}
        for dtype, keywords in DIAGRAM_KEYWORDS.items():
            for kw in keywords:
                scores[dtype] += lowered.count(kw.lower())
        best = max(scores, key=lambda dt: scores[dt])
        # Default to SEQUENCE when nothing scores (most common interaction diagram).
        return best if scores[best] > 0 else DiagramType.SEQUENCE

    def _generic_parse(self, text: str, diagram_type: DiagramType) -> ParsedModel:
        """Best-effort structural extraction used until a specialized sub-parser exists."""
        participants: list[dict] = []
        seen: set[str] = set()
        participant_re = re.compile(
            r"^\s*(participant|actor|class|interface|state|usecase)\s+\"?([\w .]+)\"?",
            re.IGNORECASE | re.MULTILINE,
        )
        for kind, name in participant_re.findall(text):
            key = name.strip()
            if key and key not in seen:
                seen.add(key)
                participants.append({"name": key, "participant_type": kind.lower()})
        return ParsedModel(diagram_type=diagram_type, participants=participants)
