"""ClassDiagramParser — PlantUML and XMI class diagrams (Story 3.4).

Extracts classes, abstract classes, interfaces and enumerations together with
their attributes, methods, relationships (inheritance / implementation /
association / aggregation / composition / dependency), multiplicity and
packages.
"""

import re
from xml.etree.ElementTree import Element

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.models import (
    AttributeDef,
    ClassDef,
    ClassModel,
    ClassRelationship,
    EnumDef,
    InterfaceDef,
    MethodDef,
    Multiplicity,
    PackageDef,
    ParameterDef,
    Visibility,
)
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult

_COMMENT_RE = re.compile(r"^\s*'.*$", re.MULTILINE)
_NOTE_BLOCK_RE = re.compile(r"^\s*note\b.*?^\s*end\s*note\s*$", re.MULTILINE | re.DOTALL | re.IGNORECASE)
_SKINPARAM_RE = re.compile(r"^\s*(skinparam|hide|title|left to right direction|@startuml|@enduml)\b.*$", re.MULTILINE | re.IGNORECASE)

# Type block header: ``class Foo {`` / ``abstract class Foo`` / ``interface Bar`` / ``enum Baz``.
_TYPE_HEADER_RE = re.compile(
    r"^\s*(?P<kind>abstract\s+class|abstract|class|interface|enum)\s+"
    r'(?P<name>"[^"]+"|[\w.]+)'
    r"(?:\s+as\s+(?P<alias>[\w.]+))?"
    r"(?:\s*<<[^>]*>>)?"
    r"\s*(?P<brace>\{)?\s*$",
    re.IGNORECASE,
)

_PACKAGE_RE = re.compile(
    r'^\s*(?:package|namespace)\s+(?P<name>"[^"]+"|[\w.]+)\s*\{',
    re.IGNORECASE,
)

# Relationship line: LEFT [mult] OP [mult] RIGHT [: label].
_REL_RE = re.compile(
    r'^\s*(?P<left>"[^"]+"|[A-Za-z_]\w*)\s*'
    r'(?:"(?P<lmult>[^"]*)"\s*)?'
    r"(?P<op>[-.<>|*o]{2,})\s*"
    r'(?:"(?P<rmult>[^"]*)"\s*)?'
    r'(?P<right>"[^"]+"|[A-Za-z_]\w*)'
    r"(?:\s*:\s*(?P<label>.+))?\s*$"
)

# Method member: ``+name(params): ReturnType`` with optional modifiers.
_METHOD_RE = re.compile(
    r"^([+\-#~])?\s*"
    r"(?P<mods>(?:\{[^}]*\}\s*|\babstract\b\s*|\bstatic\b\s*)*)"
    r"(?P<name>[\w~]+)\s*"
    r"\((?P<params>[^)]*)\)\s*"
    r"(?::\s*(?P<ret>[\w<>,\[\].\s]+?))?\s*$"
)

# Attribute member: ``+name: Type`` with optional modifiers / default.
_ATTR_RE = re.compile(
    r"^([+\-#~])?\s*"
    r"(?P<mods>(?:\{[^}]*\}\s*|\bstatic\b\s*|\breadonly\b\s*)*)"
    r"(?P<name>[\w~]+)\s*"
    r"(?::\s*(?P<type>[\w<>,\[\].\s]+?))?"
    r"(?:\s*=\s*(?P<default>.+?))?\s*$"
)

_VIS_SYMBOL: dict[str, Visibility] = {
    "+": Visibility.PUBLIC,
    "-": Visibility.PRIVATE,
    "#": Visibility.PROTECTED,
    "~": Visibility.PACKAGE,
}

_VIS_WORD: dict[str, Visibility] = {
    "public": Visibility.PUBLIC,
    "private": Visibility.PRIVATE,
    "protected": Visibility.PROTECTED,
    "package": Visibility.PACKAGE,
}


def _clean_name(token: str) -> str:
    token = token.strip()
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].strip()
    return token


def _visibility(symbol: str | None) -> Visibility:
    return _VIS_SYMBOL.get((symbol or "").strip(), Visibility.PUBLIC)


def _class_rel_type(op: str) -> str:
    has_tri = "<|" in op or "|>" in op
    dashed = "." in op
    if has_tri and dashed:
        return "implementation"
    if has_tri:
        return "inheritance"
    if "*" in op:
        return "composition"
    if "o" in op:
        return "aggregation"
    if dashed:
        return "dependency"
    return "association"


def _parse_parameters(raw: str) -> list[ParameterDef]:
    params: list[ParameterDef] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        default = None
        if "=" in part:
            part, _, default = part.partition("=")
            part = part.strip()
            default = default.strip() or None
        if ":" in part:
            name, _, typ = part.partition(":")
            params.append(
                ParameterDef(name=name.strip() or "param", type=typ.strip() or None, default_value=default)
            )
        else:
            params.append(ParameterDef(name=part, default_value=default))
    return params


class ClassDiagramParser:
    """Sub-parser for class diagrams (PlantUML + XMI)."""

    def supported_type(self) -> DiagramType:
        return DiagramType.CLASS

    # --- IPlantUMLSubParser protocol -------------------------------------

    def parse_plantuml(self, text: str) -> ParsedModel:
        return self.build_class_model(text).to_parsed_model()

    # --- PlantUML --------------------------------------------------------

    def build_class_model(self, text: str) -> ClassModel:
        body = self._preprocess(text)
        lines = body.splitlines()

        packages = self._extract_packages(lines)
        class_to_package: dict[str, str] = {}
        for pkg in packages:
            for cname in pkg.class_names:
                class_to_package[cname] = pkg.name

        classes, interfaces, enumerations, alias_map = self._extract_types(lines)
        for c in classes:
            c.package = class_to_package.get(c.name)
        for i in interfaces:
            i.package = class_to_package.get(i.name)
        for e in enumerations:
            e.package = class_to_package.get(e.name)

        relationships = self._extract_relationships(lines, alias_map)

        return ClassModel(
            classes=classes,
            interfaces=interfaces,
            enumerations=enumerations,
            relationships=relationships,
            packages=packages,
        )

    def _preprocess(self, text: str) -> str:
        text = _NOTE_BLOCK_RE.sub("", text)
        text = _COMMENT_RE.sub("", text)
        text = _SKINPARAM_RE.sub("", text)
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line.strip())

    def _extract_types(
        self, lines: list[str]
    ) -> tuple[list[ClassDef], list[InterfaceDef], list[EnumDef], dict[str, str]]:
        classes: list[ClassDef] = []
        interfaces: list[InterfaceDef] = []
        enumerations: list[EnumDef] = []
        alias_map: dict[str, str] = {}

        i = 0
        n = len(lines)
        while i < n:
            m = _TYPE_HEADER_RE.match(lines[i])
            if not m:
                i += 1
                continue
            kind = m.group("kind").lower()
            name = _clean_name(m.group("name"))
            alias = m.group("alias")
            if alias:
                alias_map[alias] = name

            body, i = self._collect_body(lines, i)
            is_abstract = kind in ("abstract", "abstract class")

            if kind == "interface":
                interfaces.append(InterfaceDef(name=name, methods=self._parse_members(body)[1]))
            elif kind == "enum":
                enumerations.append(EnumDef(name=name, values=self._parse_enum_values(body)))
            else:
                attrs, methods = self._parse_members(body)
                classes.append(
                    ClassDef(name=name, is_abstract=is_abstract, attributes=attrs, methods=methods)
                )
        return classes, interfaces, enumerations, alias_map

    def _collect_body(self, lines: list[str], header_idx: int) -> tuple[list[str], int]:
        """Return (body_lines, next_index) for the type block at ``header_idx``."""
        line = lines[header_idx]
        i = header_idx + 1
        n = len(lines)
        if "{" not in line:
            # Brace may sit on the next line (``class Foo\n{``); otherwise bodyless.
            if i < n and lines[i].strip() == "{":
                i += 1
                depth = 1
            else:
                return [], i
        else:
            depth = line.count("{") - line.count("}")
            if depth <= 0:
                return [], i
        body: list[str] = []
        while i < n and depth > 0:
            current = lines[i]
            depth += current.count("{") - current.count("}")
            if depth > 0:
                body.append(current)
            else:
                trimmed = current[: current.rfind("}")] if "}" in current else current
                if trimmed.strip():
                    body.append(trimmed)
            i += 1
        return body, i

    def _parse_members(self, body: list[str]) -> tuple[list[AttributeDef], list[MethodDef]]:
        attributes: list[AttributeDef] = []
        methods: list[MethodDef] = []
        for raw in body:
            line = raw.strip()
            if not line or line in ("{", "}") or line.startswith(".."):
                continue
            if "(" in line and ")" in line:
                method = self._parse_method(line)
                if method:
                    methods.append(method)
                continue
            attr = self._parse_attribute(line)
            if attr:
                attributes.append(attr)
        return attributes, methods

    def _parse_method(self, line: str) -> MethodDef | None:
        m = _METHOD_RE.match(line)
        if not m:
            return None
        mods = m.group("mods") or ""
        return MethodDef(
            name=m.group("name"),
            parameters=_parse_parameters(m.group("params") or ""),
            return_type=(m.group("ret") or "").strip() or None,
            visibility=_visibility(m.group(1)),
            is_abstract="abstract" in mods.lower(),
            is_static="static" in mods.lower(),
        )

    def _parse_attribute(self, line: str) -> AttributeDef | None:
        m = _ATTR_RE.match(line)
        if not m or not m.group("name"):
            return None
        mods = (m.group("mods") or "").lower()
        return AttributeDef(
            name=m.group("name"),
            type=(m.group("type") or "").strip() or None,
            visibility=_visibility(m.group(1)),
            is_static="static" in mods,
            is_readonly="readonly" in mods,
            default_value=(m.group("default") or "").strip() or None,
        )

    def _parse_enum_values(self, body: list[str]) -> list[str]:
        values: list[str] = []
        for raw in body:
            value = raw.strip().rstrip(",")
            if value and value not in ("{", "}"):
                values.append(value)
        return values

    def _extract_packages(self, lines: list[str]) -> list[PackageDef]:
        packages: list[PackageDef] = []
        i = 0
        n = len(lines)
        while i < n:
            m = _PACKAGE_RE.match(lines[i])
            if not m:
                i += 1
                continue
            name = _clean_name(m.group("name"))
            depth = lines[i].count("{") - lines[i].count("}")
            class_names: list[str] = []
            i += 1
            while i < n and depth > 0:
                depth += lines[i].count("{") - lines[i].count("}")
                hm = _TYPE_HEADER_RE.match(lines[i])
                if hm:
                    class_names.append(_clean_name(hm.group("name")))
                i += 1
            packages.append(PackageDef(name=name, class_names=class_names))
        return packages

    def _extract_relationships(
        self, lines: list[str], alias_map: dict[str, str]
    ) -> list[ClassRelationship]:
        result: list[ClassRelationship] = []
        for raw in lines:
            m = _REL_RE.match(raw)
            if not m:
                continue
            op = m.group("op")
            if "-" not in op and "." not in op:
                continue
            left = _clean_name(m.group("left"))
            right = _clean_name(m.group("right"))
            left = alias_map.get(left, left)
            right = alias_map.get(right, right)
            rel_type = _class_rel_type(op)
            lmult = m.group("lmult")
            rmult = m.group("rmult")

            if rel_type in ("inheritance", "implementation") and "<|" in op:
                # Triangle on the left: left is the parent / interface.
                source, target = right, left
                source_end, target_end = rmult, lmult
            else:
                source, target = left, right
                source_end, target_end = lmult, rmult

            multiplicity = None
            if source_end or target_end:
                multiplicity = Multiplicity(source_end=source_end or None, target_end=target_end or None)

            result.append(
                ClassRelationship(
                    source=source,
                    target=target,
                    relationship_type=rel_type,
                    label=(m.group("label") or "").strip() or None,
                    multiplicity=multiplicity,
                )
            )
        return result

    # --- XMI -------------------------------------------------------------

    def parse_xmi(self, root: Element) -> ParsedModel:
        return self.build_class_model_from_xmi(root).to_parsed_model()

    def build_class_model_from_xmi(self, root: Element) -> ClassModel:
        id_to_name = self._xmi_id_to_name(root)
        classes: list[ClassDef] = []
        interfaces: list[InterfaceDef] = []
        enumerations: list[EnumDef] = []
        for node in root.iter():
            xtype = self._xmi_type(node)
            if xtype.endswith("Class"):
                classes.append(self._xmi_build_class(node, id_to_name))
            elif xtype.endswith("Interface"):
                interfaces.append(self._xmi_build_interface(node, id_to_name))
            elif xtype.endswith("Enumeration"):
                enumerations.append(self._xmi_build_enum(node))
        relationships = self._xmi_extract_relationships(root, id_to_name)
        return ClassModel(
            classes=classes,
            interfaces=interfaces,
            enumerations=enumerations,
            relationships=relationships,
        )

    def _xmi_local(self, tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    def _xmi_attr(self, node: Element, name: str) -> str:
        for key, value in node.attrib.items():
            if self._xmi_local(key) == name:
                return value
        return ""

    def _xmi_type(self, node: Element) -> str:
        return self._xmi_attr(node, "type") or self._xmi_local(node.tag)

    def _xmi_visibility(self, word: str | None) -> Visibility:
        return _VIS_WORD.get((word or "").strip().lower(), Visibility.PUBLIC)

    def _xmi_id_to_name(self, root: Element) -> dict[str, str]:
        id_to_name: dict[str, str] = {}
        for node in root.iter():
            xid = self._xmi_attr(node, "id")
            name = node.attrib.get("name", "")
            if xid and name:
                id_to_name[xid] = name
        return id_to_name

    def _xmi_resolve_type(self, node: Element, id_to_name: dict[str, str]) -> str | None:
        type_ref = node.attrib.get("type")
        if not type_ref:
            for sub in node:
                if self._xmi_local(sub.tag) == "type":
                    type_ref = self._xmi_attr(sub, "idref") or sub.attrib.get("href", "")
                    break
        if not type_ref:
            return None
        if "#" in type_ref:
            type_ref = type_ref.split("#")[-1]
        return id_to_name.get(type_ref, type_ref)

    def _xmi_attributes_and_operations(
        self, node: Element, id_to_name: dict[str, str]
    ) -> tuple[list[AttributeDef], list[MethodDef]]:
        attributes: list[AttributeDef] = []
        methods: list[MethodDef] = []
        for child in node:
            local = self._xmi_local(child.tag)
            ctype = self._xmi_type(child)
            if local == "ownedAttribute" or ctype.endswith("Property"):
                attributes.append(
                    AttributeDef(
                        name=child.attrib.get("name", "") or "field",
                        type=self._xmi_resolve_type(child, id_to_name),
                        visibility=self._xmi_visibility(child.attrib.get("visibility")),
                        is_static=child.attrib.get("isStatic") == "true",
                        is_readonly=child.attrib.get("isReadOnly") == "true",
                    )
                )
            elif local == "ownedOperation" or ctype.endswith("Operation"):
                methods.append(self._xmi_operation(child, id_to_name))
        return attributes, methods

    def _xmi_operation(self, node: Element, id_to_name: dict[str, str]) -> MethodDef:
        params: list[ParameterDef] = []
        return_type: str | None = None
        for sub in node:
            local = self._xmi_local(sub.tag)
            if local == "ownedParameter" or self._xmi_type(sub).endswith("Parameter"):
                direction = sub.attrib.get("direction", "in")
                ptype = self._xmi_resolve_type(sub, id_to_name)
                if direction == "return":
                    return_type = ptype
                else:
                    params.append(ParameterDef(name=sub.attrib.get("name", "") or "param", type=ptype))
        return MethodDef(
            name=node.attrib.get("name", "") or "operation",
            parameters=params,
            return_type=return_type,
            visibility=self._xmi_visibility(node.attrib.get("visibility")),
            is_abstract=node.attrib.get("isAbstract") == "true",
            is_static=node.attrib.get("isStatic") == "true",
        )

    def _xmi_build_class(self, node: Element, id_to_name: dict[str, str]) -> ClassDef:
        attributes, methods = self._xmi_attributes_and_operations(node, id_to_name)
        return ClassDef(
            name=node.attrib.get("name", "") or self._xmi_attr(node, "id"),
            is_abstract=node.attrib.get("isAbstract") == "true",
            attributes=attributes,
            methods=methods,
        )

    def _xmi_build_interface(self, node: Element, id_to_name: dict[str, str]) -> InterfaceDef:
        _, methods = self._xmi_attributes_and_operations(node, id_to_name)
        return InterfaceDef(
            name=node.attrib.get("name", "") or self._xmi_attr(node, "id"),
            methods=methods,
        )

    def _xmi_build_enum(self, node: Element) -> EnumDef:
        values = [
            child.attrib.get("name", "")
            for child in node
            if self._xmi_local(child.tag) == "ownedLiteral" and child.attrib.get("name")
        ]
        return EnumDef(name=node.attrib.get("name", "") or self._xmi_attr(node, "id"), values=values)

    def _xmi_ref(self, node: Element, name: str) -> str:
        """Resolve a reference given as an attribute or a child element idref.

        Handles both ``<generalization general="id"/>`` and the
        ``<generalization><general xmi:idref="id"/></generalization>`` forms.
        """
        direct = node.attrib.get(name) or self._xmi_attr(node, name)
        if direct:
            return direct
        for child in node:
            if self._xmi_local(child.tag) == name:
                return self._xmi_attr(child, "idref") or child.attrib.get("href", "")
        return ""

    def _xmi_owner_name(self, root: Element, target: Element, id_to_name: dict[str, str]) -> str:
        for parent in root.iter():
            for child in parent:
                if child is target:
                    return parent.attrib.get("name", "") or id_to_name.get(self._xmi_attr(parent, "id"), "")
        return ""

    def _xmi_multiplicity(self, prop: Element) -> str | None:
        lower: str | None = None
        upper: str | None = None
        for value in prop:
            local = self._xmi_local(value.tag)
            if local == "lowerValue":
                lower = "*" if "Unlimited" in self._xmi_type(value) else value.attrib.get("value", "0")
            elif local == "upperValue":
                upper = "*" if "Unlimited" in self._xmi_type(value) else value.attrib.get("value", "1")
        if lower is None and upper is None:
            return None
        lower = lower if lower is not None else "0"
        upper = upper if upper is not None else "1"
        return lower if lower == upper else f"{lower}..{upper}"

    def _xmi_extract_relationships(
        self, root: Element, id_to_name: dict[str, str]
    ) -> list[ClassRelationship]:
        def resolve(ref: str) -> str:
            return id_to_name.get(ref, ref)

        result: list[ClassRelationship] = []
        for node in root.iter():
            xtype = self._xmi_type(node)
            local = self._xmi_local(node.tag)

            if xtype.endswith("Generalization") or local == "generalization":
                child = self._xmi_owner_name(root, node, id_to_name)
                parent = resolve(self._xmi_ref(node, "general"))
                if child and parent:
                    result.append(
                        ClassRelationship(source=child, target=parent, relationship_type="inheritance")
                    )
            elif xtype.endswith("Realization") or local == "interfaceRealization":
                client = resolve(self._xmi_ref(node, "client")) or self._xmi_owner_name(root, node, id_to_name)
                supplier = resolve(self._xmi_ref(node, "contract") or self._xmi_ref(node, "supplier"))
                if client and supplier:
                    result.append(
                        ClassRelationship(source=client, target=supplier, relationship_type="implementation")
                    )
            elif xtype.endswith("Association"):
                rel = self._xmi_association(node, id_to_name)
                if rel:
                    result.append(rel)
            elif xtype.endswith("Dependency"):
                client = resolve(self._xmi_ref(node, "client"))
                supplier = resolve(self._xmi_ref(node, "supplier"))
                if client and supplier:
                    result.append(
                        ClassRelationship(source=client, target=supplier, relationship_type="dependency")
                    )
        return result

    def _xmi_association(self, node: Element, id_to_name: dict[str, str]) -> ClassRelationship | None:
        ends = [child for child in node if self._xmi_local(child.tag) == "ownedEnd"]
        if len(ends) < 2:
            return None
        info = []
        for end in ends[:2]:
            # ``type`` (UML) and the namespaced ``xmi:type`` share a local name,
            # so read the plain attribute directly to avoid collisions.
            type_id = end.attrib.get("type") or ""
            info.append(
                {
                    "name": id_to_name.get(type_id, type_id),
                    "aggregation": end.attrib.get("aggregation", "none"),
                    "mult": self._xmi_multiplicity(end),
                }
            )
        whole = next((e for e in info if e["aggregation"] in ("composite", "shared")), None)
        if whole is not None:
            part = info[1] if whole is info[0] else info[0]
            rel_type = "composition" if whole["aggregation"] == "composite" else "aggregation"
            source, target = whole, part
        else:
            rel_type = "association"
            source, target = info[0], info[1]
        multiplicity = None
        if source["mult"] or target["mult"]:
            multiplicity = Multiplicity(source_end=source["mult"], target_end=target["mult"])
        return ClassRelationship(
            source=source["name"],
            target=target["name"],
            relationship_type=rel_type,
            multiplicity=multiplicity,
        )

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "@startuml" not in content and "uml:Class" not in content and "Class" not in content:
            errors.append("Brak znacznika diagramu klas")
        return ValidationResult(is_valid=not errors, errors=errors)
