"""XMI parser — OMG-standard UML interchange (XMI 2.x).

Story 3.1 establishes secure XML parsing (defusedxml) and structural extraction
of UML classes, interfaces, and relationships, with XMI-namespace and idref
resolution. Compatible with Enterprise Architect, StarUML, Visual Paradigm.
"""

from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult

# Known XMI / UML namespaces (OMG + Eclipse UML2).
_XMI_NAMESPACES = (
    "http://www.omg.org/XMI",
    "http://www.omg.org/spec/XMI/20131001",
    "http://schema.omg.org/spec/XMI/2.1",
)
_UML_NAMESPACES = (
    "http://www.eclipse.org/uml2/5.0.0/UML",
    "http://www.eclipse.org/uml2/3.0.0/UML",
    "http://schema.omg.org/spec/UML/2.1",
)


def _local(tag: str) -> str:
    """Strip the ``{namespace}`` prefix from an element tag."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


class XMIParser:
    """Universal XMI parser (works across diagram types)."""

    def supported_type(self) -> DiagramType | None:
        return None  # universal

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        try:
            fromstring(content)
        except Exception as exc:  # malformed XML
            errors.append(f"Niepoprawny XML: {exc}")
        return ValidationResult(is_valid=not errors, errors=errors)

    def parse(self, content: str) -> ParsedModel:
        root = fromstring(content)
        xmi_version = self._parse_xmi_namespace(root)

        wanted = {"Class", "Interface", "Actor", "UseCase", "State"}
        elements: list[dict] = []
        index: dict[str, dict] = {}
        for node in root.iter():
            element_type = self._classify(node)
            if element_type in wanted:
                xmi_id = self._xmi_id(node)
                entry = {
                    "xmi_id": xmi_id,
                    "element_type": element_type,
                    "name": node.attrib.get("name", ""),
                    "attributes": self._extract_attributes(node),
                }
                elements.append(entry)
                if xmi_id:
                    index[xmi_id] = entry

        relationships = self._extract_relationships(root, index)

        return ParsedModel(
            diagram_type=DiagramType.CLASS,
            elements=elements,
            relationships=relationships,
            participants=[{"name": e["name"], "participant_type": e["element_type"]} for e in elements if e["name"]],
            fragments=[{"xmi_version": xmi_version}],
        )

    def _parse_xmi_namespace(self, root: Element) -> str:
        """Detect XMI version from attributes/namespaces (2.1, 2.5...)."""
        for key, value in root.attrib.items():
            if _local(key) == "version":
                return value
        tag_ns = root.tag.split("}", 1)[0].lstrip("{") if "}" in root.tag else ""
        if "20131001" in tag_ns or "2.5" in tag_ns:
            return "2.5"
        return "2.1"

    def _classify(self, node: Element) -> str:
        """Resolve the UML metaclass of a node from xmi:type or its element tag.

        Handles both XMI styles: ``<packagedElement xmi:type="uml:Class">`` and
        the namespaced ``<uml:Class>`` element form.
        """
        for key, value in node.attrib.items():
            if _local(key) == "type":
                return value.split(":", 1)[-1]
        return _local(node.tag)

    def _xmi_id(self, node: Element) -> str:
        for key, value in node.attrib.items():
            if _local(key) == "id":
                return value
        return ""

    def _extract_attributes(self, node: Element) -> list[dict]:
        attrs: list[dict] = []
        for child in node:
            if _local(child.tag) == "ownedAttribute":
                attrs.append(
                    {
                        "name": child.attrib.get("name", ""),
                        "type": child.attrib.get("type", ""),
                        "visibility": child.attrib.get("visibility", "public"),
                    }
                )
        return attrs

    def _extract_relationships(self, root: Element, index: dict[str, dict]) -> list[dict]:
        """Resolve generalization / association relationships via xmi:idref.

        A child→parent map lets us attribute each ``generalization`` element to
        the classifier that owns it (the relationship source).
        """
        parent_of: dict[Element, Element] = {}
        for parent in root.iter():
            for child in parent:
                parent_of[child] = parent

        relationships: list[dict] = []
        for node in root.iter():
            local = _local(node.tag)
            if local == "generalization":
                owner = parent_of.get(node)
                relationships.append(
                    {
                        "relationship_type": "generalization",
                        "source": self._xmi_id(owner) if owner is not None else "",
                        "target": self._resolve_idref(node, "general"),
                    }
                )
            elif local in ("ownedEnd", "memberEnd"):
                target = self._resolve_idref(node, "type")
                if target:
                    relationships.append({"relationship_type": "association", "target": target})
        return relationships

    def _resolve_idref(self, node: Element, attr: str) -> str:
        """Resolve an attribute that may be a direct value or an xmi:idref child."""
        if attr in node.attrib:
            return node.attrib[attr]
        for child in node:
            if _local(child.tag) == attr:
                for key, value in child.attrib.items():
                    if _local(key) in ("idref", "id"):
                        return value
        return ""
