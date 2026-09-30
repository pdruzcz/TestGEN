"""UML diagram models — Epic 3: UML & GUI analysis.

Stores uploaded UML diagrams (XMI / PlantUML), their detected type, and the
parsed structural model (participants, elements, relationships). Tenant scope is
enforced at the DB level via RLS, analogous to ``SourceFile``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class UMLFormat(StrEnum):
    """Supported UML source formats.

    Tier 1 (semantic/textual): XMI, PlantUML — parsed structurally (Story 3.1).
    Tier 2 (visual): SVG, PDF, RASTER (PNG/JPEG) — parsed via OCR + shape
    inference (Story 3.1b). ``source``/``confidence`` on the parsed model
    distinguishes the lower-fidelity visual path.
    """

    XMI = "xmi"
    PLANTUML = "plantuml"
    SVG = "svg"
    PDF = "pdf"
    RASTER = "raster"


class UMLModelSource(StrEnum):
    """How a parsed model was produced — structural parser vs OCR inference."""

    PARSER = "parser"
    OCR = "ocr"


def is_visual_format(fmt: UMLFormat) -> bool:
    """True for Tier 2 formats parsed via OCR + shape inference."""
    return fmt in (UMLFormat.SVG, UMLFormat.PDF, UMLFormat.RASTER)


class DiagramType(StrEnum):
    """UML diagram categories detected by the orchestrator."""

    SEQUENCE = "sequence"
    USE_CASE = "use_case"
    CLASS = "class"
    ACTIVITY = "activity"
    STATE_MACHINE = "state_machine"


class UMLDiagramStatus(StrEnum):
    """Lifecycle status of a UML diagram's parsing pipeline."""

    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class UMLDiagram(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "uml_diagrams"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(1000))
    format: Mapped[UMLFormat] = mapped_column(_enum_col(UMLFormat, "uml_format"), index=True)
    diagram_type: Mapped[DiagramType | None] = mapped_column(
        _enum_col(DiagramType, "uml_diagram_type"),
        default=None,
        index=True,
    )
    raw_content: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[UMLDiagramStatus] = mapped_column(
        _enum_col(UMLDiagramStatus, "uml_diagram_status"),
        default=UMLDiagramStatus.PENDING,
        index=True,
    )
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(100), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    project = relationship("Project", lazy="raise")
    parsed_models = relationship(
        "ParsedUMLModel",
        back_populates="diagram",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        try:
            return (
                f"<UMLDiagram id={self.id} filename={self.filename!r} "
                f"format={self.format.value} type={self.diagram_type} status={self.status.value}>"
            )
        except Exception:
            return "<UMLDiagram (detached)>"


class ParsedUMLModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "parsed_uml_models"

    diagram_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uml_diagrams.id", ondelete="CASCADE"),
        index=True,
    )
    model_type: Mapped[DiagramType] = mapped_column(_enum_col(DiagramType, "uml_diagram_type"))
    participants: Mapped[list | None] = mapped_column(JSONB, default=None)
    elements: Mapped[list | None] = mapped_column(JSONB, default=None)
    relationships: Mapped[list | None] = mapped_column(JSONB, default=None)
    fragments: Mapped[list | None] = mapped_column(JSONB, default=None)
    flows: Mapped[list | None] = mapped_column(JSONB, default=None)
    source: Mapped[UMLModelSource] = mapped_column(
        _enum_col(UMLModelSource, "uml_model_source"),
        default=UMLModelSource.PARSER,
    )
    confidence: Mapped[float | None] = mapped_column(Float, default=None)

    diagram = relationship("UMLDiagram", back_populates="parsed_models", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<ParsedUMLModel id={self.id} type={self.model_type.value} diagram={self.diagram_id}>"
        except Exception:
            return "<ParsedUMLModel (detached)>"
