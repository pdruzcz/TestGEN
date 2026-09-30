"""Traceability matrix model — Epic 3, Story 3.15.

Persists the traceability links between a project's *source elements* (UML
diagram elements and GUI components) and the artefacts derived from them
(reconstructed ``UserFlow`` → generated ``GherkinFeature`` test scenarios), with
a per-element ``coverage_status``.

Linkage chain used (real, queryable in the current schema):

    UML element / GUI component
        → UserFlow (``source_ids`` references the parent diagram/screenshot)
        → GherkinFeature (``source_flow_id``) — the generated BDD scenario
        → GherkinFeature.status == APPROVED — proxy for "test accepted"

The Gherkin scenario is a BDD specification, **not** generated/compiled test
code; ``coverage_status='covered'`` therefore means an accepted scenario is
linked, not that executable test code exists (see service docstring, AC4).

Note: the Cypress/SikuliX ``TestCode`` pipeline links to ``TestCase`` /
``analysis_results`` and is **not** joined to UML/GUI source elements in the
current data model, so ``test_case_id`` stays null for this pipeline; the test
artefact is the linked Gherkin feature (``linked_gherkin_id``). Tenant scope is
enforced at the DB level via RLS, analogous to ``user_flows``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin

# Stable namespace for deriving deterministic IDs of UML elements (which live in
# ParsedUMLModel JSONB rather than as their own rows).
UML_ELEMENT_NAMESPACE = uuid.UUID("6f1b2c34-5d6e-4f80-9a1b-2c3d4e5f6071")


class CoverageStatus(StrEnum):
    COVERED = "covered"
    PARTIAL = "partial"
    UNCOVERED = "uncovered"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class TraceabilityMatrix(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "traceability_matrix"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(10), index=True)  # "uml" | "gui"
    source_element_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_element_type: Mapped[str] = mapped_column(String(50))
    source_element_name: Mapped[str] = mapped_column(String(500))

    # Provenance (Story 3-15 closure, AC3): how the source element was derived.
    # ``source`` mirrors ``ParsedUMLModel.source`` ("parser" for structural
    # XMI/PlantUML, "ocr" for the visual/OCR path); ``confidence`` is the OCR
    # score (0.0-1.0) and ``None`` for the deterministic structural parsers.
    # Both are ``None`` for GUI components, which have no parser/OCR split here.
    source: Mapped[str | None] = mapped_column(String(20), default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)

    source_diagram_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("uml_diagrams.id", ondelete="SET NULL"),
        default=None,
    )
    source_screenshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gui_screenshots.id", ondelete="SET NULL"),
        default=None,
    )

    linked_flow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_flows.id", ondelete="SET NULL"),
        default=None,
    )
    linked_gherkin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gherkin_features.id", ondelete="SET NULL"),
        default=None,
    )
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_cases.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    code_reference: Mapped[str | None] = mapped_column(String(1000), default=None)
    code_framework: Mapped[str | None] = mapped_column(String(50), default=None)

    coverage_status: Mapped[CoverageStatus] = mapped_column(
        _enum_col(CoverageStatus, "coverage_status"),
        default=CoverageStatus.UNCOVERED,
        index=True,
    )

    def __repr__(self) -> str:
        try:
            return (
                f"<TraceabilityMatrix {self.source_type}:{self.source_element_name!r} "
                f"status={self.coverage_status.value}>"
            )
        except Exception:
            return "<TraceabilityMatrix (detached)>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "source_type": self.source_type,
            "source_element_id": str(self.source_element_id),
            "source_element_type": self.source_element_type,
            "source_element_name": self.source_element_name,
            "source": self.source,
            "confidence": self.confidence,
            "source_diagram_id": str(self.source_diagram_id) if self.source_diagram_id else None,
            "source_screenshot_id": str(self.source_screenshot_id) if self.source_screenshot_id else None,
            "linked_flow_id": str(self.linked_flow_id) if self.linked_flow_id else None,
            "linked_gherkin_id": str(self.linked_gherkin_id) if self.linked_gherkin_id else None,
            "test_case_id": str(self.test_case_id) if self.test_case_id else None,
            "code_reference": self.code_reference,
            "code_framework": self.code_framework,
            "coverage_status": self.coverage_status.value if self.coverage_status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
