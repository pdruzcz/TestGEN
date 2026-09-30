"""UseCaseParser — PlantUML and XMI use-case diagrams (Story 3.3).

Extracts actors, use cases, relationships (association / include / extend /
generalization) and an optional system boundary, then generates test scenarios
(main / alternative / included) for downstream test generation.
"""

import re
from xml.etree.ElementTree import Element

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.models import (
    Actor,
    ScenarioStep,
    SystemBoundary,
    UCRelationship,
    UCScenario,
    UseCase,
    UseCaseModel,
)
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult

_COMMENT_RE = re.compile(r"^\s*'.*$", re.MULTILINE)

# Declared actor lines, e.g. ``actor "End User" as U`` or ``actor Admin``.
_ACTOR_RE = re.compile(
    r"^\s*actor\s+"
    r'(?::([^:]+):|"([^"]+)"|([\w.]+))'
    r'(?:\s+as\s+(?:"([^"]+)"|([\w.]+)))?',
    re.IGNORECASE,
)

# Declared usecase lines: ``usecase "Login" as UC1`` or ``usecase UC1 as "Login"``.
_USECASE_RE = re.compile(
    r"^\s*usecase\s+"
    r'(?:"([^"]+)"|([\w.]+))'
    r'(?:\s+as\s+(?:"([^"]+)"|([\w.]+)))?',
    re.IGNORECASE,
)

# Parenthesised usecase shorthand: ``(Place Order) as UC1`` or just ``(Place Order)``.
_USECASE_PAREN_RE = re.compile(
    r'^\s*\(([^)]+)\)(?:\s+as\s+(?:"([^"]+)"|([\w.]+)))?',
    re.IGNORECASE,
)

# Relationship line: source ARROW target [: label]. Endpoints may be quoted,
# parenthesised (usecase shorthand) or :Actor:.
_ENDPOINT = r'(?::[^:]+:|\([^)]+\)|"[^"]+"|[\w.]+)'
_REL_RE = re.compile(
    rf"^\s*({_ENDPOINT})\s*"
    r"([.\-]+(?:[|>]|\^)?>?|<\|?[.\-]+|[.\-]+\|>)\s*"
    rf"({_ENDPOINT})\s*"
    r"(?::\s*(.*))?$"
)

# rectangle / package "System" { — opens a system boundary block.
_BOUNDARY_RE = re.compile(
    r'^\s*(?:rectangle|package)\s+(?:"([^"]+)"|([\w.]+))\s*\{',
    re.IGNORECASE,
)


def _clean_endpoint(token: str) -> str:
    token = token.strip()
    if token.startswith(":") and token.endswith(":"):
        return token[1:-1].strip()
    if token.startswith("(") and token.endswith(")"):
        return token[1:-1].strip()
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].strip()
    return token


def _relationship_type(arrow: str, label: str) -> str:
    low = label.lower()
    if "include" in low:
        return "include"
    if "extend" in low:
        return "extend"
    if "|>" in arrow or "<|" in arrow:
        return "generalization"
    if "." in arrow:
        # Dependency arrow without an explicit stereotype defaults to include.
        return "include"
    return "association"


class UseCaseParser:
    """Sub-parser for use-case diagrams (PlantUML + XMI)."""

    def supported_type(self) -> DiagramType:
        return DiagramType.USE_CASE

    # --- IPlantUMLSubParser protocol -------------------------------------

    def parse_plantuml(self, text: str) -> ParsedModel:
        return self.build_use_case_model(text).to_parsed_model()

    # --- PlantUML --------------------------------------------------------

    def build_use_case_model(self, text: str) -> UseCaseModel:
        body = self._preprocess(text)
        lines = body.splitlines()

        actors = self._extract_actors(lines)
        use_cases = self._extract_use_cases(lines)
        relationships = self._extract_relationships(lines)
        boundary = self._extract_system_boundary(lines)

        # Auto-register endpoints referenced in relationships but never declared.
        self._merge_referenced(actors, use_cases, relationships)

        model = UseCaseModel(
            actors=actors,
            use_cases=use_cases,
            relationships=relationships,
            system_boundary=boundary,
        )
        model.scenarios = self.generate_scenarios(model)
        return model

    def _preprocess(self, text: str) -> str:
        without_comments = _COMMENT_RE.sub("", text)
        lines = [line.rstrip() for line in without_comments.splitlines()]
        return "\n".join(line for line in lines if line.strip())

    def _extract_actors(self, lines: list[str]) -> list[Actor]:
        result: list[Actor] = []
        seen: set[str] = set()
        for line in lines:
            m = _ACTOR_RE.match(line)
            if not m:
                continue
            name = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            alias = (m.group(4) or m.group(5) or name).strip()
            if alias in seen:
                continue
            seen.add(alias)
            result.append(Actor(name=name, alias=alias, actor_type="primary"))
        return result

    def _extract_use_cases(self, lines: list[str]) -> list[UseCase]:
        result: list[UseCase] = []
        seen: set[str] = set()
        for line in lines:
            m = _USECASE_RE.match(line)
            if m:
                name = (m.group(1) or m.group(2) or "").strip()
                alias = (m.group(3) or m.group(4) or name).strip()
            else:
                pm = _USECASE_PAREN_RE.match(line)
                if not pm:
                    continue
                name = pm.group(1).strip()
                alias = (pm.group(2) or pm.group(3) or name).strip()
            if alias in seen:
                continue
            seen.add(alias)
            result.append(UseCase(name=name, alias=alias))
        return result

    def _extract_relationships(self, lines: list[str]) -> list[UCRelationship]:
        result: list[UCRelationship] = []
        for line in lines:
            stripped = line.strip()
            if stripped.endswith("{") or stripped in ("}", "@startuml", "@enduml"):
                continue
            m = _REL_RE.match(line)
            if not m:
                continue
            source = _clean_endpoint(m.group(1))
            arrow = m.group(2)
            target = _clean_endpoint(m.group(3))
            label = (m.group(4) or "").strip()
            if not source or not target:
                continue
            rel_type = _relationship_type(arrow, label)
            # Generalization arrows point child --|> parent; keep child as source.
            clean_label = re.sub(r"<<\s*(include|extend)\s*>>", "", label).strip() or None
            result.append(
                UCRelationship(
                    source=source,
                    target=target,
                    relationship_type=rel_type,
                    label=clean_label,
                )
            )
        return result

    def _extract_system_boundary(self, lines: list[str]) -> SystemBoundary | None:
        boundary_name: str | None = None
        depth = 0
        collected: list[str] = []
        seen: set[str] = set()
        for line in lines:
            m = _BOUNDARY_RE.match(line)
            if m and depth == 0:
                boundary_name = (m.group(1) or m.group(2) or "").strip()
                depth = 1
                continue
            if depth > 0:
                stripped = line.strip()
                depth += stripped.count("{")
                depth -= stripped.count("}")
                uc = _USECASE_RE.match(line)
                if uc:
                    name = (uc.group(1) or uc.group(2) or "").strip()
                    if name and name not in seen:
                        seen.add(name)
                        collected.append(name)
                else:
                    pm = _USECASE_PAREN_RE.match(line)
                    if pm:
                        name = pm.group(1).strip()
                        if name and name not in seen:
                            seen.add(name)
                            collected.append(name)
                if depth <= 0:
                    break
        if boundary_name is None:
            return None
        return SystemBoundary(name=boundary_name, use_case_names=collected)

    def _merge_referenced(
        self,
        actors: list[Actor],
        use_cases: list[UseCase],
        relationships: list[UCRelationship],
    ) -> None:
        known = {a.alias for a in actors} | {a.name for a in actors}
        known |= {u.alias for u in use_cases} | {u.name for u in use_cases}
        for rel in relationships:
            for endpoint in (rel.source, rel.target):
                if endpoint and endpoint not in known:
                    known.add(endpoint)
                    # Undeclared endpoints in use-case diagrams are treated as use cases.
                    use_cases.append(UseCase(name=endpoint, alias=endpoint))

    # --- Scenario generation ---------------------------------------------

    def generate_scenarios(self, model: UseCaseModel) -> list[UCScenario]:
        actor_aliases = {a.alias for a in model.actors} | {a.name for a in model.actors}
        uc_by_key = {}
        for uc in model.use_cases:
            for key in (uc.alias, uc.name):
                if key:
                    uc_by_key[key] = uc

        # association: actor ↔ use case
        actor_of_uc: dict[str, str] = {}
        includes: dict[str, list[str]] = {}
        extends: dict[str, list[tuple[str, str | None]]] = {}
        for rel in model.relationships:
            if rel.relationship_type == "association":
                src_is_actor = rel.source in actor_aliases
                actor, uc = (
                    (rel.source, rel.target)
                    if src_is_actor
                    else (rel.target, rel.source)
                )
                actor_of_uc.setdefault(uc, actor)
            elif rel.relationship_type == "include":
                includes.setdefault(rel.source, []).append(rel.target)
            elif rel.relationship_type == "extend":
                # extend points from extending UC → base UC.
                extends.setdefault(rel.target, []).append((rel.source, rel.label))

        def display(key: str) -> str:
            uc = uc_by_key.get(key)
            return uc.name if uc else key

        scenarios: list[UCScenario] = []
        for uc in model.use_cases:
            key = uc.alias or uc.name
            actor = actor_of_uc.get(key, actor_of_uc.get(uc.name, ""))
            steps: list[ScenarioStep] = []
            seq = 1
            # Inject included use-case steps first (shared/common steps).
            for inc in includes.get(key, []):
                steps.append(
                    ScenarioStep(
                        sequence=seq,
                        action=f"Wykonaj: {display(inc)}",
                        actor=actor,
                        target=display(inc),
                    )
                )
                seq += 1
            steps.append(
                ScenarioStep(
                    sequence=seq,
                    action=f"Wykonaj: {uc.name}",
                    actor=actor,
                    target=uc.name,
                )
            )
            scenarios.append(
                UCScenario(
                    use_case_name=uc.name,
                    primary_actor=actor,
                    steps=steps,
                    expected_result=f"{uc.name} zakończone powodzeniem",
                    scenario_type="main",
                )
            )
            # extend: each extending UC becomes an alternative scenario.
            for ext_uc, guard in extends.get(key, []):
                scenarios.append(
                    UCScenario(
                        use_case_name=display(ext_uc),
                        primary_actor=actor,
                        preconditions=[guard] if guard else [],
                        steps=[
                            ScenarioStep(
                                sequence=1,
                                action=f"Wykonaj: {uc.name}",
                                actor=actor,
                                target=uc.name,
                            ),
                            ScenarioStep(
                                sequence=2,
                                action=f"Rozszerzenie: {display(ext_uc)}",
                                actor=actor,
                                target=display(ext_uc),
                            ),
                        ],
                        expected_result=f"{display(ext_uc)} zakończone powodzeniem",
                        scenario_type="alternative",
                    )
                )
        return scenarios

    # --- XMI -------------------------------------------------------------

    def parse_xmi(self, root: Element) -> ParsedModel:
        return self.build_use_case_model_from_xmi(root).to_parsed_model()

    def build_use_case_model_from_xmi(self, root: Element) -> UseCaseModel:
        actors, use_cases, id_to_name = self._xmi_extract_nodes(root)
        relationships = self._xmi_extract_relationships(root, id_to_name)
        boundary = self._xmi_extract_system_boundary(root, id_to_name)
        model = UseCaseModel(
            actors=actors,
            use_cases=use_cases,
            relationships=relationships,
            system_boundary=boundary,
        )
        model.scenarios = self.generate_scenarios(model)
        return model

    def _xmi_local(self, tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    def _xmi_attr(self, node: Element, name: str) -> str:
        for key, value in node.attrib.items():
            if self._xmi_local(key) == name:
                return value
        return ""

    def _xmi_type(self, node: Element) -> str:
        return self._xmi_attr(node, "type") or self._xmi_local(node.tag)

    def _xmi_extract_nodes(
        self, root: Element
    ) -> tuple[list[Actor], list[UseCase], dict[str, str]]:
        actors: list[Actor] = []
        use_cases: list[UseCase] = []
        id_to_name: dict[str, str] = {}
        for node in root.iter():
            xtype = self._xmi_type(node)
            xid = self._xmi_attr(node, "id")
            name = node.attrib.get("name", "")
            if xtype.endswith("Actor"):
                if xid:
                    id_to_name[xid] = name or xid
                actors.append(Actor(name=name or xid, alias=xid, actor_type="primary"))
            elif xtype.endswith("UseCase"):
                if xid:
                    id_to_name[xid] = name or xid
                use_cases.append(UseCase(name=name or xid, alias=xid, xmi_id=xid))
        return actors, use_cases, id_to_name

    def _xmi_extract_relationships(
        self, root: Element, id_to_name: dict[str, str]
    ) -> list[UCRelationship]:
        def resolve(ref: str) -> str:
            return id_to_name.get(ref, ref)

        result: list[UCRelationship] = []
        for node in root.iter():
            xtype = self._xmi_type(node)
            if xtype.endswith("Include"):
                src = self._xmi_attr(node, "includingCase") or self._xmi_attr(node, "client")
                tgt = self._xmi_attr(node, "addition")
                if not src:
                    src = self._xmi_owner_id(root, node)
                if src and tgt:
                    result.append(
                        UCRelationship(
                            source=resolve(src),
                            target=resolve(tgt),
                            relationship_type="include",
                        )
                    )
            elif xtype.endswith("Extend"):
                src = self._xmi_attr(node, "extension") or self._xmi_owner_id(root, node)
                tgt = self._xmi_attr(node, "extendedCase")
                if src and tgt:
                    result.append(
                        UCRelationship(
                            source=resolve(src),
                            target=resolve(tgt),
                            relationship_type="extend",
                        )
                    )
            elif xtype.endswith("Generalization"):
                child = self._xmi_owner_id(root, node)
                parent = self._xmi_attr(node, "general")
                if child and parent:
                    result.append(
                        UCRelationship(
                            source=resolve(child),
                            target=resolve(parent),
                            relationship_type="generalization",
                        )
                    )
            elif xtype.endswith("Association"):
                ends = self._xmi_association_ends(root, node)
                if len(ends) == 2:
                    result.append(
                        UCRelationship(
                            source=resolve(ends[0]),
                            target=resolve(ends[1]),
                            relationship_type="association",
                        )
                    )
        return result

    def _xmi_owner_id(self, root: Element, target: Element) -> str:
        """Find xmi:id of the element that directly owns ``target``."""
        for parent in root.iter():
            for child in parent:
                if child is target:
                    return self._xmi_attr(parent, "id")
        return ""

    def _xmi_association_ends(self, root: Element, node: Element) -> list[str]:
        """Resolve the two connected element ids of an association."""
        ends: list[str] = []
        member_end = self._xmi_attr(node, "memberEnd")
        type_ids: list[str] = []
        for child in node:
            if self._xmi_local(child.tag) == "ownedEnd":
                tid = self._xmi_attr(child, "type")
                if tid:
                    type_ids.append(tid)
        if len(type_ids) >= 2:
            return type_ids[:2]
        if member_end:
            refs = member_end.split()
            prop_type = {}
            for prop in root.iter():
                if self._xmi_local(prop.tag) in ("ownedAttribute", "ownedEnd"):
                    pid = self._xmi_attr(prop, "id")
                    tid = self._xmi_attr(prop, "type")
                    if pid:
                        prop_type[pid] = tid
            for ref in refs:
                tid = prop_type.get(ref)
                if tid:
                    ends.append(tid)
        return ends

    def _xmi_extract_system_boundary(
        self, root: Element, id_to_name: dict[str, str]
    ) -> SystemBoundary | None:
        for node in root.iter():
            xtype = self._xmi_type(node)
            if not xtype.endswith("Component"):
                continue
            name = node.attrib.get("name", "")
            uc_names: list[str] = []
            for child in node.iter():
                if self._xmi_type(child).endswith("UseCase") and child is not node:
                    uc_names.append(child.attrib.get("name", "") or self._xmi_attr(child, "id"))
            if name or uc_names:
                return SystemBoundary(name=name or "System", use_case_names=uc_names)
        return None

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "@startuml" not in content and "UseCase" not in content:
            errors.append("Brak znacznika diagramu przypadków użycia")
        return ValidationResult(is_valid=not errors, errors=errors)
