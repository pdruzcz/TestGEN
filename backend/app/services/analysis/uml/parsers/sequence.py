"""SequenceDiagramParser — PlantUML and XMI sequence diagrams (Story 3.2).

Extracts participants, ordered messages, and combined fragments (alt/loop/opt),
then reconstructs test paths (happy / alternative / iterative) for downstream
test generation.
"""

import re
from xml.etree.ElementTree import Element

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.models import (
    Fragment,
    FragmentCondition,
    Message,
    Participant,
    SequenceModel,
    TestPath,
)
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult

_COMMENT_RE = re.compile(r"^\s*'.*$", re.MULTILINE)

# Declared participant lines, e.g. ``actor "End User" as U`` or ``participant DB``.
_PARTICIPANT_RE = re.compile(
    r"^\s*(participant|actor|boundary|control|entity|database|collections|queue)\s+"
    r'(?:"([^"]+)"|([\w.]+))'
    r'(?:\s+as\s+(?:"([^"]+)"|([\w.]+)))?',
    re.IGNORECASE,
)

# Message lines, e.g. ``A -> B : label`` (also -->, ->>, <--, <<--).
_MESSAGE_RE = re.compile(
    r'^\s*(?:"([^"]+)"|([\w.]+))\s*'
    r"([-<>]{2,})\s*"
    r'(?:"([^"]+)"|([\w.]+))\s*'
    r"(?::\s*(.*))?$"
)

_FRAGMENT_TYPE_KEYWORDS = {"database", "collections", "queue"}

_RIGHT_ARROW_TYPES = {
    "->": "sync",
    "->>": "dashed",
    "-->": "async",
    "-->>": "dashed",
}
_LEFT_ARROW_TYPES = {
    "<-": "return",
    "<--": "return",
    "<<-": "return",
    "<<--": "return",
}


def _participant_type(keyword: str) -> str:
    kw = keyword.lower()
    if kw in ("actor",):
        return "actor"
    if kw in ("boundary", "control", "entity"):
        return kw
    return "participant"


class SequenceDiagramParser:
    """Sub-parser for sequence diagrams (PlantUML + XMI)."""

    def supported_type(self) -> DiagramType:
        return DiagramType.SEQUENCE

    # --- IPlantUMLSubParser protocol -------------------------------------

    def parse_plantuml(self, text: str) -> ParsedModel:
        """Protocol entry point — returns the generic ParsedModel for persistence."""
        return self.build_sequence_model(text).to_parsed_model()

    # --- PlantUML --------------------------------------------------------

    def build_sequence_model(self, text: str) -> SequenceModel:
        """Build the rich SequenceModel (participants, messages, fragments, paths)."""
        body = self._preprocess(text)
        lines = body.splitlines()

        declared = self._extract_declared_participants(lines)
        messages, fragments = self._scan_body(lines)
        participants = self._merge_participants(declared, messages)

        model = SequenceModel(
            participants=participants,
            messages=messages,
            fragments=fragments,
        )
        model.test_paths = self.reconstruct_test_paths(model)
        return model

    def _preprocess(self, text: str) -> str:
        without_comments = _COMMENT_RE.sub("", text)
        lines = [line.rstrip() for line in without_comments.splitlines()]
        return "\n".join(line for line in lines if line.strip())

    def _extract_declared_participants(self, lines: list[str]) -> list[Participant]:
        result: list[Participant] = []
        seen: set[str] = set()
        for line in lines:
            m = _PARTICIPANT_RE.match(line)
            if not m:
                continue
            keyword = m.group(1)
            name = m.group(2) or m.group(3) or ""
            alias = m.group(4) or m.group(5) or name
            if alias in seen:
                continue
            seen.add(alias)
            result.append(
                Participant(
                    name=name.strip(),
                    alias=alias.strip(),
                    participant_type=_participant_type(keyword),
                )
            )
        return result

    def _scan_body(self, lines: list[str]) -> tuple[list[Message], list[Fragment]]:
        """Single pass: collect ordered messages and (possibly nested) fragments."""
        messages: list[Message] = []
        fragments: list[Fragment] = []
        stack: list[Fragment] = []

        for line in lines:
            stripped = line.strip()
            lowered = stripped.lower()

            if lowered.startswith(("alt ", "alt\t")) or lowered == "alt":
                frag = Fragment(
                    fragment_type="alt",
                    conditions=[FragmentCondition(label=stripped[3:].strip())],
                )
                stack.append(frag)
                continue
            if lowered.startswith("loop"):
                frag = Fragment(
                    fragment_type="loop",
                    conditions=[FragmentCondition(label=stripped[4:].strip())],
                )
                stack.append(frag)
                continue
            if lowered.startswith("opt"):
                frag = Fragment(
                    fragment_type="opt",
                    conditions=[FragmentCondition(label=stripped[3:].strip())],
                )
                stack.append(frag)
                continue
            if lowered.startswith("else"):
                if stack:
                    stack[-1].conditions.append(
                        FragmentCondition(label=stripped[4:].strip())
                    )
                continue
            if lowered == "end" or lowered.startswith("end "):
                if stack:
                    fragments.append(stack.pop())
                continue

            msg = self._parse_message_line(line, len(messages))
            if msg is None:
                continue
            idx = len(messages)
            messages.append(msg)
            for frag in stack:
                frag.message_indices.append(idx)
                if frag.conditions:
                    frag.conditions[-1].message_indices.append(idx)

        # Close any unterminated fragments (defensive).
        while stack:
            fragments.append(stack.pop())
        return messages, fragments

    def _parse_message_line(self, line: str, seq: int) -> Message | None:
        m = _MESSAGE_RE.match(line)
        if not m:
            return None
        left = (m.group(1) or m.group(2) or "").strip()
        arrow = m.group(3)
        right = (m.group(4) or m.group(5) or "").strip()
        label = (m.group(6) or "").strip()
        if not left or not right:
            return None

        if arrow.startswith("<"):
            msg_type = _LEFT_ARROW_TYPES.get(arrow, "return")
            source, target = right, left
        else:
            msg_type = _RIGHT_ARROW_TYPES.get(arrow)
            if msg_type is None:
                return None
            source, target = left, right

        return Message(
            from_alias=source,
            to_alias=target,
            label=label,
            message_type=msg_type,
            sequence_number=seq,
        )

    def _merge_participants(
        self, declared: list[Participant], messages: list[Message]
    ) -> list[Participant]:
        by_alias = {p.alias: p for p in declared}
        ordered = list(declared)
        for msg in messages:
            for alias in (msg.from_alias, msg.to_alias):
                if alias and alias not in by_alias:
                    p = Participant(name=alias, alias=alias, participant_type="participant")
                    by_alias[alias] = p
                    ordered.append(p)
        return ordered

    # --- Test-path reconstruction ----------------------------------------

    def reconstruct_test_paths(self, model: SequenceModel) -> list[TestPath]:
        msgs = model.messages
        if not msgs:
            return []
        actor = msgs[0].from_alias

        alt_frags = [f for f in model.fragments if f.fragment_type == "alt"]
        loop_frags = [f for f in model.fragments if f.fragment_type == "loop"]

        # Indices that belong to non-first ALT branches are excluded from happy path.
        excluded: set[int] = set()
        for f in alt_frags:
            for cond in f.conditions[1:]:
                excluded.update(cond.message_indices)

        happy_steps = [m for i, m in enumerate(msgs) if i not in excluded]
        paths: list[TestPath] = [
            TestPath(
                path_type="happy",
                steps=happy_steps,
                preconditions=[],
                initiating_actor=actor,
            )
        ]

        for f in alt_frags:
            if not f.conditions:
                continue
            first_branch = set(f.conditions[0].message_indices)
            for cond in f.conditions[1:]:
                # Drop the first branch, keep this alternative branch.
                alt_excluded = (excluded - set(cond.message_indices)) | first_branch
                steps = [m for i, m in enumerate(msgs) if i not in alt_excluded]
                paths.append(
                    TestPath(
                        path_type="alternative",
                        steps=steps,
                        preconditions=[cond.label] if cond.label else [],
                        initiating_actor=actor,
                    )
                )

        for f in loop_frags:
            steps = [msgs[i] for i in f.message_indices if 0 <= i < len(msgs)]
            label = f.conditions[0].label if f.conditions else ""
            paths.append(
                TestPath(
                    path_type="iterative",
                    steps=steps,
                    preconditions=[label] if label else [],
                    initiating_actor=actor,
                )
            )
        return paths

    # --- XMI -------------------------------------------------------------

    def parse_xmi(self, root: Element) -> ParsedModel:
        return self.build_sequence_model_from_xmi(root).to_parsed_model()

    def build_sequence_model_from_xmi(self, root: Element) -> SequenceModel:
        lifelines = self._xmi_extract_lifelines(root)
        messages, occ_to_lifeline = self._xmi_extract_messages(root, lifelines)
        fragments = self._xmi_extract_fragments(root, messages, occ_to_lifeline)

        participants = [
            Participant(name=name, alias=lid, participant_type="participant")
            for lid, name in lifelines.items()
        ]
        model = SequenceModel(
            participants=participants,
            messages=messages,
            fragments=fragments,
        )
        model.test_paths = self.reconstruct_test_paths(model)
        return model

    def _xmi_local(self, tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    def _xmi_attr(self, node: Element, name: str) -> str:
        for key, value in node.attrib.items():
            if self._xmi_local(key) == name:
                return value
        return ""

    def _xmi_extract_lifelines(self, root: Element) -> dict[str, str]:
        """Map lifeline xmi:id → display name."""
        lifelines: dict[str, str] = {}
        for node in root.iter():
            if self._xmi_local(node.tag) == "lifeline":
                lid = self._xmi_attr(node, "id")
                name = node.attrib.get("name", "") or self._xmi_attr(node, "represents") or lid
                if lid:
                    lifelines[lid] = name
        return lifelines

    def _xmi_extract_messages(
        self, root: Element, lifelines: dict[str, str]
    ) -> tuple[list[Message], dict[str, str]]:
        """Extract ordered messages; resolve source/target via occurrence → lifeline."""
        # Map MessageOccurrenceSpecification id → covered lifeline id.
        occ_to_lifeline: dict[str, str] = {}
        for node in root.iter():
            if self._xmi_local(node.tag) in ("fragment", "occurrence"):
                oid = self._xmi_attr(node, "id")
                covered = self._xmi_attr(node, "covered")
                if oid and covered:
                    occ_to_lifeline[oid] = covered

        sort_map = {
            "synchCall": "sync",
            "asynchCall": "async",
            "asynchSignal": "async",
            "reply": "return",
        }
        messages: list[Message] = []
        for node in root.iter():
            if self._xmi_local(node.tag) != "message":
                continue
            send = self._xmi_attr(node, "sendEvent")
            recv = self._xmi_attr(node, "receiveEvent")
            source = occ_to_lifeline.get(send, send)
            target = occ_to_lifeline.get(recv, recv)
            sort = self._xmi_attr(node, "messageSort")
            messages.append(
                Message(
                    from_alias=source,
                    to_alias=target,
                    label=node.attrib.get("name", ""),
                    message_type=sort_map.get(sort, "sync"),
                    sequence_number=len(messages),
                )
            )
        return messages, occ_to_lifeline

    def _xmi_extract_fragments(
        self,
        root: Element,
        messages: list[Message],
        occ_to_lifeline: dict[str, str],
    ) -> list[Fragment]:
        fragments: list[Fragment] = []
        for node in root.iter():
            if self._xmi_local(node.tag) != "fragment":
                continue
            if "CombinedFragment" not in self._xmi_attr(node, "type"):
                continue
            operator = self._xmi_attr(node, "interactionOperator") or "alt"
            frag = Fragment(fragment_type=operator)
            for operand in node:
                if self._xmi_local(operand.tag) != "operand":
                    continue
                guard = ""
                for child in operand.iter():
                    if self._xmi_local(child.tag) == "specification":
                        guard = child.attrib.get("value", "") or guard
                    elif self._xmi_local(child.tag) == "guard":
                        guard = guard or self._xmi_attr(child, "value")
                frag.conditions.append(FragmentCondition(label=guard))
            if not frag.conditions:
                frag.conditions.append(FragmentCondition())
            fragments.append(frag)
        return fragments

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "@startuml" not in content and "Interaction" not in content:
            errors.append("Brak znacznika diagramu sekwencji")
        return ValidationResult(is_valid=not errors, errors=errors)
