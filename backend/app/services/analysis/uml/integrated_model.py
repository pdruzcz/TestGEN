"""Integrated UML model — Epic 3, Story 3.7.

``IntegratedUMLModel`` consolidates the parsed structural models of every UML
diagram in a project and records the cross-diagram mappings discovered by
``CrossDiagramAnalyzer`` (use case ↔ sequence, participant ↔ class, etc.). It is
a pure in-memory Pydantic structure built from the JSONB columns of
``ParsedUMLModel`` — it never touches the database itself.
"""

from pydantic import BaseModel, Field


class DiagramBundle(BaseModel):
    """One parsed diagram's data, keyed by its diagram id (as string)."""

    diagram_id: str
    diagram_type: str
    name: str = ""
    participants: list[dict] = Field(default_factory=list)
    elements: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    fragments: list[dict] = Field(default_factory=list)
    flows: list[dict] = Field(default_factory=list)


class CoverageReport(BaseModel):
    mapped_diagrams: int = 0
    unmapped_diagrams: int = 0
    coverage_percentage: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class IntegratedUMLModel(BaseModel):
    # use_case_id -> [sequence_diagram_id]
    use_case_to_sequences: dict[str, list[str]] = Field(default_factory=dict)
    # participant_name -> class_name
    participant_to_class: dict[str, str] = Field(default_factory=dict)
    # use_case_id -> activity_diagram_id
    use_case_to_activity: dict[str, str] = Field(default_factory=dict)
    # class_name -> state_diagram_id
    class_to_state_machine: dict[str, str] = Field(default_factory=dict)
    # diagram_id -> bundle
    all_models: dict[str, DiagramBundle] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    coverage_report: CoverageReport = Field(default_factory=CoverageReport)

    def bundles_of_type(self, diagram_type: str) -> list[DiagramBundle]:
        return [b for b in self.all_models.values() if b.diagram_type == diagram_type]
