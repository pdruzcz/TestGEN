"""Business-logic models for parsed UML diagrams (Story 3.2+).

These Pydantic models are independent of the database. Parsers build them in
memory; ``SequenceModel.to_parsed_model()`` maps onto the JSONB columns of
``ParsedUMLModel`` so the result plugs into the existing persistence flow.
"""

from enum import StrEnum

from pydantic import BaseModel

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.parsers.base import ParsedModel


class Participant(BaseModel):
    name: str
    alias: str | None = None
    # actor / participant / boundary / control / entity
    participant_type: str = "participant"


class Message(BaseModel):
    from_alias: str
    to_alias: str
    label: str = ""
    # sync / async / dashed / return
    message_type: str = "sync"
    sequence_number: int


class FragmentCondition(BaseModel):
    label: str = ""
    message_indices: list[int] = []


class Fragment(BaseModel):
    # alt / loop / opt
    fragment_type: str
    conditions: list[FragmentCondition] = []
    message_indices: list[int] = []


class TestPath(BaseModel):
    # happy / alternative / iterative
    path_type: str
    steps: list[Message] = []
    preconditions: list[str] = []
    initiating_actor: str = ""


class SequenceModel(BaseModel):
    participants: list[Participant] = []
    messages: list[Message] = []
    fragments: list[Fragment] = []
    test_paths: list[TestPath] = []

    def to_parsed_model(self) -> ParsedModel:
        """Map onto the generic ParsedModel (JSONB columns of ParsedUMLModel).

        Messages are stored in ``relationships`` (directed participant edges) and
        reconstructed test paths in ``flows``.
        """
        return ParsedModel(
            diagram_type=DiagramType.SEQUENCE,
            participants=[p.model_dump() for p in self.participants],
            elements=[],
            relationships=[m.model_dump() for m in self.messages],
            fragments=[f.model_dump() for f in self.fragments],
            flows=[t.model_dump() for t in self.test_paths],
        )


# --- Use-case diagrams (Story 3.3) ---------------------------------------


class Actor(BaseModel):
    name: str
    alias: str | None = None
    # primary / secondary
    actor_type: str = "primary"
    stereotype: str | None = None


class UseCase(BaseModel):
    name: str
    alias: str | None = None
    description: str | None = None
    xmi_id: str | None = None


class UCRelationship(BaseModel):
    source: str
    target: str
    # association / include / extend / generalization
    relationship_type: str
    label: str | None = None


class SystemBoundary(BaseModel):
    name: str
    use_case_names: list[str] = []


class ScenarioStep(BaseModel):
    sequence: int
    action: str
    actor: str = ""
    target: str | None = None


class UCScenario(BaseModel):
    use_case_name: str
    primary_actor: str = ""
    preconditions: list[str] = []
    steps: list[ScenarioStep] = []
    expected_result: str = ""
    # main / alternative / included
    scenario_type: str = "main"


class UseCaseModel(BaseModel):
    actors: list[Actor] = []
    use_cases: list[UseCase] = []
    relationships: list[UCRelationship] = []
    system_boundary: SystemBoundary | None = None
    scenarios: list[UCScenario] = []

    def to_parsed_model(self) -> ParsedModel:
        """Map onto the generic ParsedModel (JSONB columns of ParsedUMLModel).

        Actors → ``participants``, use cases → ``elements``, relationships →
        ``relationships``, the system boundary → ``fragments`` (single entry),
        and generated scenarios → ``flows``.
        """
        boundary = [self.system_boundary.model_dump()] if self.system_boundary else []
        return ParsedModel(
            diagram_type=DiagramType.USE_CASE,
            participants=[a.model_dump() for a in self.actors],
            elements=[uc.model_dump() for uc in self.use_cases],
            relationships=[r.model_dump() for r in self.relationships],
            fragments=boundary,
            flows=[s.model_dump() for s in self.scenarios],
        )


# --- Class diagrams (Story 3.4) ------------------------------------------


class Visibility(StrEnum):
    PUBLIC = "+"
    PRIVATE = "-"
    PROTECTED = "#"
    PACKAGE = "~"


class AttributeDef(BaseModel):
    name: str
    type: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    is_readonly: bool = False
    default_value: str | None = None


class ParameterDef(BaseModel):
    name: str
    type: str | None = None
    default_value: str | None = None


class MethodDef(BaseModel):
    name: str
    parameters: list[ParameterDef] = []
    return_type: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    is_abstract: bool = False
    is_static: bool = False


class ClassDef(BaseModel):
    name: str
    is_abstract: bool = False
    attributes: list[AttributeDef] = []
    methods: list[MethodDef] = []
    package: str | None = None


class InterfaceDef(BaseModel):
    name: str
    methods: list[MethodDef] = []
    package: str | None = None


class EnumDef(BaseModel):
    name: str
    values: list[str] = []
    package: str | None = None


class Multiplicity(BaseModel):
    source_end: str | None = None
    target_end: str | None = None
    source_role: str | None = None
    target_role: str | None = None


class ClassRelationship(BaseModel):
    source: str
    target: str
    # inheritance / implementation / association / aggregation / composition / dependency
    relationship_type: str
    label: str | None = None
    multiplicity: Multiplicity | None = None


class PackageDef(BaseModel):
    name: str
    class_names: list[str] = []


class ClassModel(BaseModel):
    classes: list[ClassDef] = []
    interfaces: list[InterfaceDef] = []
    enumerations: list[EnumDef] = []
    relationships: list[ClassRelationship] = []
    packages: list[PackageDef] = []

    def to_parsed_model(self) -> ParsedModel:
        """Map onto the generic ParsedModel (JSONB columns of ParsedUMLModel).

        Classes, interfaces and enumerations are stored together in
        ``elements`` (discriminated by ``element_kind``), relationships map to
        ``relationships`` and packages to ``fragments``.
        """
        elements: list[dict] = []
        for c in self.classes:
            data = c.model_dump()
            data["element_kind"] = "class"
            elements.append(data)
        for i in self.interfaces:
            data = i.model_dump()
            data["element_kind"] = "interface"
            elements.append(data)
        for e in self.enumerations:
            data = e.model_dump()
            data["element_kind"] = "enum"
            elements.append(data)
        return ParsedModel(
            diagram_type=DiagramType.CLASS,
            participants=[],
            elements=elements,
            relationships=[r.model_dump() for r in self.relationships],
            fragments=[p.model_dump() for p in self.packages],
            flows=[],
        )


# --- Activity diagrams (Story 3.5) ---------------------------------------


class ActivityNodeType(StrEnum):
    START = "start"
    STOP = "stop"
    ACTION = "action"
    DECISION = "decision"
    MERGE = "merge"
    FORK = "fork"
    JOIN = "join"


class ActivityNode(BaseModel):
    id: str
    name: str = ""
    node_type: ActivityNodeType
    swimlane: str | None = None


class ActivityEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    guard: str | None = None
    label: str | None = None


class Swimlane(BaseModel):
    name: str
    node_ids: list[str] = []


class ActivityPathStep(BaseModel):
    node_id: str
    name: str
    node_type: ActivityNodeType
    swimlane: str | None = None
    guard: str | None = None


class ActivityScenario(BaseModel):
    path_id: str
    # main / alternative
    scenario_type: str = "main"
    steps: list[ActivityPathStep] = []
    preconditions: list[str] = []
    expected_result: str = ""


class ActivityModel(BaseModel):
    nodes: list[ActivityNode] = []
    edges: list[ActivityEdge] = []
    swimlanes: list[Swimlane] = []
    scenarios: list[ActivityScenario] = []
    warnings: list[str] = []

    def to_parsed_model(self) -> ParsedModel:
        """Map onto the generic ParsedModel (JSONB columns of ParsedUMLModel).

        Activity nodes → ``elements`` (discriminated by ``node_type``), edges →
        ``relationships``, swimlanes → ``fragments`` and generated path
        scenarios → ``flows``. ``warnings`` are appended as the first fragment
        entry under the ``__warnings__`` key when present.
        """
        fragments: list[dict] = [s.model_dump() for s in self.swimlanes]
        if self.warnings:
            fragments.append({"__warnings__": self.warnings})
        return ParsedModel(
            diagram_type=DiagramType.ACTIVITY,
            participants=[],
            elements=[n.model_dump() for n in self.nodes],
            relationships=[e.model_dump() for e in self.edges],
            fragments=fragments,
            flows=[s.model_dump() for s in self.scenarios],
        )


# --- State machine diagrams (Story 3.6) ----------------------------------


class StateNode(BaseModel):
    id: str
    name: str = ""
    is_initial: bool = False
    is_final: bool = False
    entry_action: str | None = None
    do_action: str | None = None
    exit_action: str | None = None
    parent_state_id: str | None = None


class Transition(BaseModel):
    id: str
    source_id: str
    target_id: str
    event: str | None = None
    guard: str | None = None
    action: str | None = None


class CompositeState(BaseModel):
    id: str
    name: str = ""
    child_ids: list[str] = []
    internal_transition_ids: list[str] = []


class StateScenario(BaseModel):
    scenario_id: str
    # transition / state / path / negative
    scenario_type: str = "transition"
    title: str = ""
    steps: list[str] = []
    source_state: str | None = None
    event: str | None = None
    guard: str | None = None
    action: str | None = None
    target_state: str | None = None
    expected_result: str = ""
    is_negative: bool = False


class StateModel(BaseModel):
    states: list[StateNode] = []
    transitions: list[Transition] = []
    composite_states: list[CompositeState] = []
    initial_state_id: str | None = None
    final_state_ids: list[str] = []
    scenarios: list[StateScenario] = []
    warnings: list[str] = []

    def to_parsed_model(self) -> ParsedModel:
        """Map onto the generic ParsedModel (JSONB columns of ParsedUMLModel).

        States → ``elements``, transitions → ``relationships``, composite
        states → ``fragments`` and generated coverage scenarios → ``flows``.
        ``warnings`` are appended as a trailing ``__warnings__`` fragment entry.
        """
        fragments: list[dict] = [c.model_dump() for c in self.composite_states]
        if self.warnings:
            fragments.append({"__warnings__": self.warnings})
        return ParsedModel(
            diagram_type=DiagramType.STATE_MACHINE,
            participants=[],
            elements=[s.model_dump() for s in self.states],
            relationships=[t.model_dump() for t in self.transitions],
            fragments=fragments,
            flows=[s.model_dump() for s in self.scenarios],
        )
