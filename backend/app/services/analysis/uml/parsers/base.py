"""Parser interfaces and shared data structures for the UML module.

A ``ParsedModel`` is the in-memory result produced by a parser before it is
persisted as a ``ParsedUMLModel`` row. It is intentionally a plain dataclass of
JSON-serializable fields so it maps directly onto the JSONB columns.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.models.uml_diagram import DiagramType, UMLModelSource


@dataclass
class ValidationResult:
    """Outcome of validating a diagram's syntax."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ParsedModel:
    """Structural model extracted from a UML diagram.

    All fields are JSON-serializable so the result maps onto the JSONB columns
    of ``ParsedUMLModel``.

    ``source`` distinguishes structural parsing (Tier 1) from OCR/shape
    inference (Tier 2, Story 3.1b); ``confidence`` (0.0-1.0) is populated for
    OCR-derived models and ``None`` for the deterministic structural parsers.
    """

    diagram_type: DiagramType
    participants: list[dict] = field(default_factory=list)
    elements: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    fragments: list[dict] = field(default_factory=list)
    flows: list[dict] = field(default_factory=list)
    source: UMLModelSource = UMLModelSource.PARSER
    confidence: float | None = None
    # Transient parse-time warnings (not persisted); the orchestrator logs them.
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class IUMLParser(Protocol):
    """Top-level parser for a UML source format (XMI or PlantUML)."""

    def parse(self, content: str) -> ParsedModel: ...

    def supported_type(self) -> DiagramType | None: ...

    def validate(self, content: str) -> ValidationResult: ...


@runtime_checkable
class IPlantUMLSubParser(Protocol):
    """Parser specialized for a single PlantUML diagram type."""

    def parse_plantuml(self, text: str) -> ParsedModel: ...

    def supported_type(self) -> DiagramType: ...
