"""UMLParserOrchestrator — format/type detection and parser routing (Story 3.1)."""

import asyncio
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import download_file_bytes
from app.models.uml_diagram import (
    DiagramType,
    ParsedUMLModel,
    UMLDiagram,
    UMLDiagramStatus,
    UMLFormat,
    is_visual_format,
)
from app.services.analysis.uml.parsers.activity import (
    ActivityDiagramParser,
    is_activity_diagram,
)
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult
from app.services.analysis.uml.parsers.class_diagram import ClassDiagramParser
from app.services.analysis.uml.parsers.sequence import SequenceDiagramParser
from app.services.analysis.uml.parsers.state_machine import (
    StateMachineParser,
    is_state_diagram,
)
from app.services.analysis.uml.parsers.use_case import UseCaseParser
from app.services.analysis.uml.plantuml_parser import (
    DIAGRAM_KEYWORDS,
    PlantUMLParser,
    is_class_diagram,
)
from app.services.analysis.uml.visual_parser import VisualUMLParser
from app.services.analysis.uml.xmi_parser import XMIParser

logger = logging.getLogger(__name__)

_XML_HEADER_RE = re.compile(r"<\?xml|<xmi:XMI|<XMI", re.IGNORECASE)
_PLANTUML_RE = re.compile(r"@startuml", re.IGNORECASE)
_XMI_SEQUENCE_RE = re.compile(r"Lifeline|:Interaction\b|uml:Interaction", re.IGNORECASE)
_XMI_USECASE_RE = re.compile(r"uml:UseCase|:UseCase\b|uml:Actor", re.IGNORECASE)
_XMI_CLASS_RE = re.compile(r"uml:Class\b|uml:Interface\b|uml:Enumeration\b", re.IGNORECASE)
_XMI_ACTIVITY_RE = re.compile(r"uml:Activity\b|:Activity\b|InitialNode|OpaqueAction", re.IGNORECASE)
_XMI_STATE_RE = re.compile(r"uml:StateMachine|:StateMachine\b|Pseudostate|uml:FinalState|uml:Transition", re.IGNORECASE)


class UMLParserOrchestrator:
    """Detects format and diagram type, then routes to the correct parser."""

    def __init__(self) -> None:
        self._plantuml = PlantUMLParser()
        self._xmi = XMIParser()
        self._sequence = SequenceDiagramParser()
        self._use_case = UseCaseParser()
        self._class = ClassDiagramParser()
        self._activity = ActivityDiagramParser()
        self._state = StateMachineParser()
        # Tier 2 visual parser (SVG / PDF / raster) — Story 3.1b.
        self._visual = VisualUMLParser()
        # Register specialized PlantUML sub-parsers.
        self._plantuml.register_subparser(self._sequence)
        self._plantuml.register_subparser(self._use_case)
        self._plantuml.register_subparser(self._class)
        self._plantuml.register_subparser(self._activity)
        self._plantuml.register_subparser(self._state)

    def detect_format(self, content: str) -> UMLFormat:
        """Content sniffing: PlantUML markers win, otherwise XML headers → XMI."""
        if _PLANTUML_RE.search(content):
            return UMLFormat.PLANTUML
        if _XML_HEADER_RE.search(content):
            return UMLFormat.XMI
        # Fallback heuristic: angle-bracket-heavy content is XMI, else PlantUML.
        return UMLFormat.XMI if content.lstrip().startswith("<") else UMLFormat.PLANTUML

    def detect_diagram_type(self, content: str) -> DiagramType:
        """Keyword-scoring classifier across the five supported diagram types."""
        if is_class_diagram(content):
            return DiagramType.CLASS
        if is_activity_diagram(content):
            return DiagramType.ACTIVITY
        if is_state_diagram(content):
            return DiagramType.STATE_MACHINE
        lowered = content.lower()
        scores: dict[DiagramType, int] = {dt: 0 for dt in DIAGRAM_KEYWORDS}
        for dtype, keywords in DIAGRAM_KEYWORDS.items():
            for kw in keywords:
                scores[dtype] += lowered.count(kw.lower())
        best = max(scores, key=lambda dt: scores[dt])
        return best if scores[best] > 0 else DiagramType.SEQUENCE

    def validate(self, content: str, fmt: UMLFormat) -> ValidationResult:
        parser = self._xmi if fmt == UMLFormat.XMI else self._plantuml
        return parser.validate(content)

    def _parse_content(self, content: str, fmt: UMLFormat) -> ParsedModel:
        if fmt == UMLFormat.XMI:
            if _XMI_SEQUENCE_RE.search(content):
                from defusedxml.ElementTree import fromstring

                return self._sequence.parse_xmi(fromstring(content))
            if _XMI_USECASE_RE.search(content):
                from defusedxml.ElementTree import fromstring

                return self._use_case.parse_xmi(fromstring(content))
            if _XMI_STATE_RE.search(content):
                from defusedxml.ElementTree import fromstring

                return self._state.parse_xmi(fromstring(content))
            if _XMI_ACTIVITY_RE.search(content):
                from defusedxml.ElementTree import fromstring

                return self._activity.parse_xmi(fromstring(content))
            if _XMI_CLASS_RE.search(content):
                from defusedxml.ElementTree import fromstring

                return self._class.parse_xmi(fromstring(content))
            return self._xmi.parse(content)
        return self._plantuml.parse(content)

    async def parse(self, diagram_id: uuid.UUID, db: AsyncSession) -> ParsedUMLModel:
        """Main entry point: load diagram, parse, persist result, update status."""
        result = await db.execute(select(UMLDiagram).where(UMLDiagram.id == diagram_id))
        diagram = result.scalar_one_or_none()
        if diagram is None:
            raise ValueError(f"UMLDiagram {diagram_id} not found")

        diagram.status = UMLDiagramStatus.PARSING
        await db.flush()

        try:
            fmt = diagram.format
            if is_visual_format(fmt):
                # Tier 2 — OCR + shape inference (Story 3.1b). Validation is
                # inherent to shape extraction (malformed input → empty model +
                # warnings), so no separate text-validation step.
                parsed = await self._parse_visual(diagram)
            else:
                content = diagram.raw_content or ""
                validation = self.validate(content, fmt)
                if not validation.is_valid:
                    diagram.status = UMLDiagramStatus.FAILED
                    diagram.error_message = "; ".join(validation.errors)
                    await db.flush()
                    raise ValueError(f"Walidacja nieudana: {diagram.error_message}")
                parsed = self._parse_content(content, fmt)

            diagram.diagram_type = parsed.diagram_type
            model = ParsedUMLModel(
                diagram_id=diagram.id,
                model_type=parsed.diagram_type,
                participants=parsed.participants,
                elements=parsed.elements,
                relationships=parsed.relationships,
                fragments=parsed.fragments,
                flows=parsed.flows,
                source=parsed.source,
                confidence=parsed.confidence,
            )
            db.add(model)
            diagram.status = UMLDiagramStatus.COMPLETED
            diagram.error_message = None
            for warning in parsed.warnings:
                logger.info("UML visual parse notice [%s]: %s", diagram_id, warning)
            await db.flush()
            return model
        except ValueError:
            raise
        except Exception as exc:  # parser failure
            logger.exception("UML parsing failed for diagram %s", diagram_id)
            diagram.status = UMLDiagramStatus.FAILED
            diagram.error_message = str(exc)
            await db.flush()
            raise

    async def _parse_visual(self, diagram: UMLDiagram) -> ParsedModel:
        """Tier 2 entry: SVG from ``raw_content``; PDF/raster fetched from MinIO."""
        fmt = diagram.format
        if fmt == UMLFormat.SVG:
            return self._visual.parse_svg(diagram.raw_content or "")
        # Binary payloads (PDF / raster) are stored in MinIO, not raw_content.
        bucket = get_settings().minio_bucket_name
        data = await asyncio.to_thread(download_file_bytes, bucket, diagram.storage_key)
        return self._visual.parse_bytes(data, fmt)
