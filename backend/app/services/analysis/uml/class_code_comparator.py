"""DiagramCodeComparator — compare a parsed class diagram with source code (Story 3.4).

The source of truth for code structure is Epic 1's ``logic_structures`` AST
analysis, supplied to the comparator by ``LogicStructuresCodeProvider``
(``app.services.analysis.uml.code_structure_provider``).
``StubCodeStructureProvider`` remains as a test/fallback for projects that have
no ``logic_structures`` analysis yet, in which case every diagram class is
reported as ``diagram_only``.
"""

import re
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.services.analysis.uml.models import (
    ClassDef,
    ClassModel,
    ClassRelationship,
    EnumDef,
    InterfaceDef,
    PackageDef,
)


def class_model_from_columns(
    elements: list[dict] | None,
    relationships: list[dict] | None,
    fragments: list[dict] | None,
) -> ClassModel:
    """Rebuild a ``ClassModel`` from persisted ``ParsedUMLModel`` JSONB columns."""
    classes: list[ClassDef] = []
    interfaces: list[InterfaceDef] = []
    enumerations: list[EnumDef] = []
    for element in elements or []:
        data = {k: v for k, v in element.items() if k != "element_kind"}
        kind = element.get("element_kind")
        if kind == "interface":
            interfaces.append(InterfaceDef.model_validate(data))
        elif kind == "enum":
            enumerations.append(EnumDef.model_validate(data))
        else:
            classes.append(ClassDef.model_validate(data))
    return ClassModel(
        classes=classes,
        interfaces=interfaces,
        enumerations=enumerations,
        relationships=[ClassRelationship.model_validate(r) for r in relationships or []],
        packages=[PackageDef.model_validate(p) for p in fragments or []],
    )


class CodeAttribute(BaseModel):
    name: str
    type: str | None = None
    visibility: str | None = None


class CodeMethod(BaseModel):
    name: str
    return_type: str | None = None
    parameter_count: int = 0


class CodeClass(BaseModel):
    name: str
    attributes: list[CodeAttribute] = []
    methods: list[CodeMethod] = []


class CodeInterface(BaseModel):
    name: str
    methods: list[CodeMethod] = []


class ICodeStructureProvider(Protocol):
    """Supplies the code-side structure for a project (Epic 1 integration point)."""

    def get_classes(self, project_id: UUID) -> list[CodeClass]: ...

    def get_interfaces(self, project_id: UUID) -> list[CodeInterface]: ...


class StubCodeStructureProvider:
    """Empty provider — test/fallback when a project has no ``logic_structures`` analysis."""

    def get_classes(self, project_id: UUID) -> list[CodeClass]:
        return []

    def get_interfaces(self, project_id: UUID) -> list[CodeInterface]:
        return []


class Discrepancy(BaseModel):
    # missing_attribute / missing_method / type_mismatch / missing_relationship / extra_in_code
    type: str
    class_name: str
    details: str
    # info / warning / error
    severity: str


class ClassMatch(BaseModel):
    diagram_class: str
    code_class: str
    # ``None`` marks an unassessable dimension — the diagram side extracted no
    # members (e.g. an OCR/visual class diagram, Story 3.1b). Reporting a
    # vacuous 100 % on empty lists would be misleading, so ``None`` signals
    # "incomplete_extraction" instead. A real 0.0-1.0 ratio is returned whenever
    # the diagram side has at least one member.
    attribute_match_pct: float | None
    method_match_pct: float | None


class DiagramCodeComparison(BaseModel):
    matching_classes: list[ClassMatch] = []
    diagram_only_classes: list[str] = []
    code_only_classes: list[str] = []
    discrepancies: list[Discrepancy] = []


def _normalize(name: str) -> str:
    return re.sub(r"[_\s]+", "", name).lower()


class DiagramCodeComparator:
    """Compares a parsed ``ClassModel`` against code structure from a provider."""

    def compare(
        self,
        diagram_model: ClassModel,
        code_structure: ICodeStructureProvider,
        project_id: UUID,
    ) -> DiagramCodeComparison:
        code_classes = code_structure.get_classes(project_id)
        code_by_norm = {_normalize(c.name): c for c in code_classes}

        matching: list[ClassMatch] = []
        diagram_only: list[str] = []
        discrepancies: list[Discrepancy] = []
        matched_code: set[str] = set()

        for cls in diagram_model.classes:
            norm = _normalize(cls.name)
            code_cls = code_by_norm.get(norm)
            if code_cls is None:
                diagram_only.append(cls.name)
                discrepancies.append(
                    Discrepancy(
                        type="missing_in_code",
                        class_name=cls.name,
                        details=f"Klasa '{cls.name}' z diagramu nie ma odpowiednika w kodzie.",
                        severity="error",
                    )
                )
                continue

            matched_code.add(norm)
            attr_pct, attr_discr = self._compare_attributes(cls.name, cls.attributes, code_cls.attributes)
            method_pct, method_discr = self._compare_methods(cls.name, cls.methods, code_cls.methods)
            matching.append(
                ClassMatch(
                    diagram_class=cls.name,
                    code_class=code_cls.name,
                    attribute_match_pct=attr_pct,
                    method_match_pct=method_pct,
                )
            )
            discrepancies.extend(attr_discr)
            discrepancies.extend(method_discr)

        code_only = [c.name for c in code_classes if _normalize(c.name) not in matched_code]
        for name in code_only:
            discrepancies.append(
                Discrepancy(
                    type="extra_in_code",
                    class_name=name,
                    details=f"Klasa '{name}' istnieje w kodzie, ale brak jej na diagramie.",
                    severity="info",
                )
            )

        return DiagramCodeComparison(
            matching_classes=matching,
            diagram_only_classes=diagram_only,
            code_only_classes=code_only,
            discrepancies=discrepancies,
        )

    def _compare_attributes(self, class_name, diagram_attrs, code_attrs):
        code_by_name = {_normalize(a.name): a for a in code_attrs}
        matched = 0
        discrepancies: list[Discrepancy] = []
        for attr in diagram_attrs:
            code_attr = code_by_name.get(_normalize(attr.name))
            if code_attr is None:
                discrepancies.append(
                    Discrepancy(
                        type="missing_attribute",
                        class_name=class_name,
                        details=f"Atrybut '{attr.name}' z diagramu nie istnieje w kodzie.",
                        severity="warning",
                    )
                )
                continue
            matched += 1
            if attr.type and code_attr.type and _normalize(attr.type) != _normalize(code_attr.type):
                discrepancies.append(
                    Discrepancy(
                        type="type_mismatch",
                        class_name=class_name,
                        details=(f"Atrybut '{attr.name}': typ diagramu '{attr.type}' ≠ typ kodu '{code_attr.type}'."),
                        severity="warning",
                    )
                )
        # Empty diagram side ⇒ unassessable, NOT a vacuous 100 % match. OCR/visual
        # class diagrams (Story 3.1b) extract no members, so surface ``None`` as
        # an explicit "incomplete_extraction" marker for that dimension.
        pct = matched / len(diagram_attrs) if diagram_attrs else None
        return pct, discrepancies

    def _compare_methods(self, class_name, diagram_methods, code_methods):
        code_by_name = {_normalize(m.name): m for m in code_methods}
        matched = 0
        discrepancies: list[Discrepancy] = []
        for method in diagram_methods:
            code_method = code_by_name.get(_normalize(method.name))
            if code_method is None:
                discrepancies.append(
                    Discrepancy(
                        type="missing_method",
                        class_name=class_name,
                        details=f"Metoda '{method.name}' z diagramu nie istnieje w kodzie.",
                        severity="warning",
                    )
                )
                continue
            matched += 1
        # Empty diagram side ⇒ unassessable, NOT a vacuous 100 % match (see
        # _compare_attributes). Surface ``None`` so callers can distinguish an
        # OCR/visual diagram (no extracted members) from a true 0.0-1.0 result.
        pct = matched / len(diagram_methods) if diagram_methods else None
        return pct, discrepancies
