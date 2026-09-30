"""Traceability service — Epic 3, Story 3.15.

Builds and queries the :class:`TraceabilityMatrix` for a project, linking each
source element (UML diagram element / GUI component) to the reconstructed
``UserFlow`` and generated ``GherkinFeature`` derived from it, and deriving a
``coverage_status``.

Linkage chain (real, queryable in the current schema):

    UML element / GUI component
        → UserFlow (``source_ids`` / ``flow_steps`` reference the parent
          diagram/screenshot)
        → GherkinFeature (``source_flow_id``) — the generated BDD scenario
        → GherkinFeature.status == APPROVED — proxy for "test accepted"

.. note:: **Coverage semantics — honest Gherkin-proxy (Story 3-15 closure, AC4).**

   Story 3.15 assumed a ``TestCase.source_flow_id`` link and a
   ``GeneratedTestCode`` model. Neither exists in the current schema: ``TestCase``
   binds to ``analysis_results`` and the Cypress/SikuliX ``TestCode`` pipeline
   binds to ``TestCase``, neither to UML/GUI source elements. The real,
   queryable test artefact here is therefore the linked **Gherkin feature** (a
   BDD scenario), **not** compiled/derived test code. The coverage tiers reflect
   that honestly:

   * ``COVERED`` — a covering flow has an APPROVED Gherkin scenario. This is a
     proxy for "the element's behaviour is specified and accepted as a test"; it
     does NOT assert that executable test code has been generated.
   * ``PARTIAL`` — a Gherkin scenario exists but none is APPROVED.
   * ``UNCOVERED`` — no Gherkin scenario is linked to a covering flow.

   ``test_case_id`` stays NULL on this pipeline for the same reason; wiring a
   real element → TestCase → TestCode chain is tracked as a follow-up (it would
   require new relations and is out of scope of this closure).
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gherkin_feature import GherkinFeature, GherkinStatus
from app.models.gui_screenshot import GUIAnalysisResult, GUIComponent, GUIScreenshot
from app.models.traceability import (
    UML_ELEMENT_NAMESPACE,
    CoverageStatus,
    TraceabilityMatrix,
)
from app.models.uml_diagram import ParsedUMLModel, UMLDiagram
from app.models.user_flow import FlowStep, UserFlow
from app.schemas.traceability import CoverageBreakdown, TraceabilitySummaryOut

# Mapping of raw UML element/participant type tokens to canonical source types.
# Covers both structural tokens (XMI/PlantUML ``element_kind``/``type``) and the
# visual tokens emitted by the OCR/shape path (``element_type`` — e.g.
# ``"decision"`` for activity diamonds, ``"node"`` for generic shapes).
_UML_TYPE_MAP = {
    "actor": "actor",
    "participant": "participant",
    "usecase": "use_case",
    "use_case": "use_case",
    "class": "class",
    "interface": "class",
    "enum": "class",
    "state": "state",
    "transition": "transition",
    "message": "interaction",
    "action": "activity",
    "activity": "activity",
    "decision": "activity",
}


def _element_name(raw: dict) -> str:
    return str(raw.get("name") or raw.get("label") or raw.get("alias") or raw.get("title") or "unnamed")


def _element_type(raw: dict, default: str, *, category: str | None = None) -> str:
    """Resolve a canonical source element type from a raw UML element dict.

    Story 3-15 closure (AC1): reads the structural discriminator
    ``element_kind`` **first** — emitted by both the XMI/PlantUML parsers and,
    since the 3-1b closure, the visual/OCR path. This removes the post-3-1b
    asymmetry where a class from OCR (``element_type="class"``) and a class from
    XMI (``element_kind="class"``, no ``element_type``) canonicalised to
    different tokens (``"class"`` vs the ``default``). Both now resolve to
    ``"class"`` regardless of source.

    Story 3-15 closure (AC2): visual activity/state nodes carry the generic
    token ``"node"`` (``"decision"`` maps directly to ``"activity"``). ``"node"``
    is ambiguous on its own, so the parent diagram ``category`` disambiguates
    it — ``"activity"`` → ``"activity"``, ``"state_machine"`` → ``"state"`` —
    which only the collector knows at build time.
    """
    token = str(raw.get("element_kind") or raw.get("element_type") or raw.get("type") or default).lower()
    if token in _UML_TYPE_MAP:
        return _UML_TYPE_MAP[token]
    if token == "node" and category:
        if category == "activity":
            return "activity"
        if category == "state_machine":
            return "state"
    return token or default


def _uml_element_id(diagram_id: uuid.UUID, etype: str, name: str, index: int) -> uuid.UUID:
    return uuid.uuid5(UML_ELEMENT_NAMESPACE, f"{diagram_id}:{etype}:{name}:{index}")


class _SourceElement:
    """A normalised source element awaiting coverage resolution."""

    __slots__ = (
        "category_key",
        "confidence",
        "diagram_id",
        "element_id",
        "element_type",
        "name",
        "screenshot_id",
        "source",
        "source_type",
    )

    def __init__(
        self,
        source_type: str,
        element_id: uuid.UUID,
        element_type: str,
        name: str,
        category_key: str,
        diagram_id: uuid.UUID | None = None,
        screenshot_id: uuid.UUID | None = None,
        source: str | None = None,
        confidence: float | None = None,
    ):
        self.source_type = source_type
        self.element_id = element_id
        self.element_type = element_type
        self.name = name
        self.category_key = category_key
        self.diagram_id = diagram_id
        self.screenshot_id = screenshot_id
        self.source = source
        self.confidence = confidence


class TraceabilityService:
    """Build/query the traceability matrix for a project."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----- build ---------------------------------------------------------

    async def build_matrix(self, project_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """(Re)build the traceability matrix for a project. Returns row count."""
        uml_elements = await self._collect_uml_elements(project_id)
        gui_elements = await self._collect_gui_elements(project_id)
        ref_to_flows = await self._build_flow_index(project_id)
        flow_to_features = await self._build_gherkin_index(project_id)

        await self.db.execute(delete(TraceabilityMatrix).where(TraceabilityMatrix.project_id == project_id))

        rows: list[TraceabilityMatrix] = []
        for el in (*uml_elements, *gui_elements):
            ref = str(el.diagram_id or el.screenshot_id or "")
            covering_flows = ref_to_flows.get(ref, [])
            features: list[GherkinFeature] = []
            for fid in covering_flows:
                features.extend(flow_to_features.get(fid, []))

            has_test = len(features) > 0
            approved = next((f for f in features if f.status == GherkinStatus.APPROVED), None)
            has_code = approved is not None

            if has_code:
                status = CoverageStatus.COVERED
            elif has_test:
                status = CoverageStatus.PARTIAL
            else:
                status = CoverageStatus.UNCOVERED

            linked_feature = approved or (features[0] if features else None)
            rows.append(
                TraceabilityMatrix(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    source_type=el.source_type,
                    source_element_id=el.element_id,
                    source_element_type=el.element_type,
                    source_element_name=el.name,
                    source=el.source,
                    confidence=el.confidence,
                    source_diagram_id=el.diagram_id,
                    source_screenshot_id=el.screenshot_id,
                    linked_flow_id=covering_flows[0] if covering_flows else None,
                    linked_gherkin_id=linked_feature.id if linked_feature else None,
                    code_reference=approved.feature_name if approved else None,
                    code_framework="gherkin/bdd" if has_code else None,
                    coverage_status=status,
                )
            )

        self.db.add_all(rows)
        await self.db.flush()
        return len(rows)

    # ----- collection helpers -------------------------------------------

    async def _collect_uml_elements(self, project_id: uuid.UUID) -> list[_SourceElement]:
        result = await self.db.execute(
            select(UMLDiagram.id, UMLDiagram.diagram_type, ParsedUMLModel)
            .join(ParsedUMLModel, ParsedUMLModel.diagram_id == UMLDiagram.id)
            .where(UMLDiagram.project_id == project_id)
        )
        elements: list[_SourceElement] = []
        for diagram_id, diagram_type, parsed in result.all():
            category = diagram_type.value if diagram_type else "unknown"
            # Provenance (AC3): ParsedUMLModel records how the model was produced
            # — structural parser vs OCR inference — plus the OCR confidence.
            prov_source = parsed.source.value if parsed.source else None
            prov_confidence = parsed.confidence
            raw_participants = parsed.participants or []
            raw_elements = parsed.elements or []
            index = 0
            for raw in raw_participants:
                if not isinstance(raw, dict):
                    continue
                name = _element_name(raw)
                etype = _element_type(raw, "participant", category=category)
                elements.append(
                    _SourceElement(
                        source_type="uml",
                        element_id=_uml_element_id(diagram_id, etype, name, index),
                        element_type=etype,
                        name=name,
                        category_key=category,
                        diagram_id=diagram_id,
                        source=prov_source,
                        confidence=prov_confidence,
                    )
                )
                index += 1
            for raw in raw_elements:
                if not isinstance(raw, dict):
                    continue
                name = _element_name(raw)
                etype = _element_type(raw, "element", category=category)
                elements.append(
                    _SourceElement(
                        source_type="uml",
                        element_id=_uml_element_id(diagram_id, etype, name, index),
                        element_type=etype,
                        name=name,
                        category_key=category,
                        diagram_id=diagram_id,
                        source=prov_source,
                        confidence=prov_confidence,
                    )
                )
                index += 1
        return elements

    async def _collect_gui_elements(self, project_id: uuid.UUID) -> list[_SourceElement]:
        result = await self.db.execute(
            select(GUIScreenshot.id, GUIComponent)
            .join(GUIAnalysisResult, GUIAnalysisResult.screenshot_id == GUIScreenshot.id)
            .join(GUIComponent, GUIComponent.analysis_id == GUIAnalysisResult.id)
            .where(GUIScreenshot.project_id == project_id)
        )
        elements: list[_SourceElement] = []
        for screenshot_id, component in result.all():
            ctype = component.component_type.value if component.component_type else "unknown"
            elements.append(
                _SourceElement(
                    source_type="gui",
                    element_id=component.id,
                    element_type=ctype,
                    name=component.label or ctype,
                    category_key=ctype,
                    screenshot_id=screenshot_id,
                )
            )
        return elements

    async def _build_flow_index(self, project_id: uuid.UUID) -> dict[str, list[uuid.UUID]]:
        """Map a diagram/screenshot id (str) → list of covering flow ids."""
        flows = (await self.db.execute(select(UserFlow).where(UserFlow.project_id == project_id))).scalars().all()
        flow_ids = [f.id for f in flows]
        steps_by_flow: dict[uuid.UUID, list[FlowStep]] = {fid: [] for fid in flow_ids}
        if flow_ids:
            steps = (await self.db.execute(select(FlowStep).where(FlowStep.flow_id.in_(flow_ids)))).scalars().all()
            for step in steps:
                steps_by_flow.setdefault(step.flow_id, []).append(step)

        ref_to_flows: dict[str, list[uuid.UUID]] = {}
        for flow in flows:
            refs: set[str] = set()
            for sid in flow.source_ids or []:
                refs.add(str(sid))
            for step in steps_by_flow.get(flow.id, []):
                if step.source_diagram_id:
                    refs.add(str(step.source_diagram_id))
                if step.source_screenshot_id:
                    refs.add(str(step.source_screenshot_id))
            for ref in refs:
                ref_to_flows.setdefault(ref, []).append(flow.id)
        return ref_to_flows

    async def _build_gherkin_index(self, project_id: uuid.UUID) -> dict[uuid.UUID, list[GherkinFeature]]:
        features = (
            (await self.db.execute(select(GherkinFeature).where(GherkinFeature.project_id == project_id)))
            .scalars()
            .all()
        )
        index: dict[uuid.UUID, list[GherkinFeature]] = {}
        for feature in features:
            if feature.source_flow_id is None:
                continue
            index.setdefault(feature.source_flow_id, []).append(feature)
        return index

    # ----- query --------------------------------------------------------

    async def get_matrix(
        self,
        project_id: uuid.UUID,
        source_type: str | None = None,
        coverage_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TraceabilityMatrix], int]:
        base = select(TraceabilityMatrix).where(TraceabilityMatrix.project_id == project_id)
        if source_type:
            base = base.where(TraceabilityMatrix.source_type == source_type)
        if coverage_status:
            base = base.where(TraceabilityMatrix.coverage_status == coverage_status)

        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        rows = (
            (
                await self.db.execute(
                    base.order_by(
                        TraceabilityMatrix.source_type,
                        TraceabilityMatrix.source_element_name,
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    async def get_summary(self, project_id: uuid.UUID) -> TraceabilitySummaryOut:
        rows = (
            (await self.db.execute(select(TraceabilityMatrix).where(TraceabilityMatrix.project_id == project_id)))
            .scalars()
            .all()
        )

        uml = [r for r in rows if r.source_type == "uml"]
        gui = [r for r in rows if r.source_type == "gui"]

        def _coverage_pct(items: list[TraceabilityMatrix]) -> float:
            if not items:
                return 0.0
            tested = sum(1 for r in items if r.coverage_status != CoverageStatus.UNCOVERED)
            return round(tested / len(items) * 100.0, 1)

        code_total = len(rows)
        code_covered = sum(1 for r in rows if r.coverage_status == CoverageStatus.COVERED)
        code_pct = round(code_covered / code_total * 100.0, 1) if code_total else 0.0

        return TraceabilitySummaryOut(
            uml_total=len(uml),
            gui_total=len(gui),
            uml_coverage_pct=_coverage_pct(uml),
            gui_coverage_pct=_coverage_pct(gui),
            code_coverage_pct=code_pct,
            breakdown_per_uml_type=self._breakdown(uml, project_id, by="diagram"),
            breakdown_per_gui_category=self._breakdown(gui, project_id, by="component"),
        )

    @staticmethod
    def _breakdown(rows: list[TraceabilityMatrix], project_id: uuid.UUID, by: str) -> list[CoverageBreakdown]:
        grouped: dict[str, list[TraceabilityMatrix]] = {}
        for r in rows:
            grouped.setdefault(r.source_element_type, []).append(r)
        out: list[CoverageBreakdown] = []
        for key, items in sorted(grouped.items()):
            out.append(
                CoverageBreakdown(
                    key=key,
                    total=len(items),
                    covered=sum(1 for r in items if r.coverage_status == CoverageStatus.COVERED),
                    partial=sum(1 for r in items if r.coverage_status == CoverageStatus.PARTIAL),
                    uncovered=sum(1 for r in items if r.coverage_status == CoverageStatus.UNCOVERED),
                )
            )
        return out

    async def recalculate_coverage(self, project_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Rebuild the matrix (coverage is derived, so a rebuild is authoritative)."""
        return await self.build_matrix(project_id, tenant_id)
