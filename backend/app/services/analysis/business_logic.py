"""
Business logic reconstruction service - Story 1.24

Analyzes and reconstructs business logic from code:
- Business rules identification (constraints, validations, calculations)
- Domain concepts extraction (entities, value objects, aggregates)
- State machine detection (status transitions, workflows)
- Business operations (CRUD, commands, queries)
- Business events (raised events, side effects)

Creates unified business logic model with rules and operations.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.ast.registry import ASTParserRegistry
from app.services.analysis.ast.ast_tree import ASTTree

logger = logging.getLogger(__name__)


class RuleType(StrEnum):
    """Types of business rules."""
    VALIDATION = "validation"  # Data validation rules
    CONSTRAINT = "constraint"  # Business constraints
    CALCULATION = "calculation"  # Business calculations
    AUTHORIZATION = "authorization"  # Access control rules
    CONDITIONAL = "conditional"  # Conditional business logic
    INvariant = "invariant"  # Invariants that must always hold


class OperationType(StrEnum):
    """Types of business operations."""
    CREATE = "create"  # Create entity
    READ = "read"  # Read/query entity
    UPDATE = "update"  # Update entity
    DELETE = "delete"  # Delete entity
    COMMAND = "command"  # Business command (action)
    QUERY = "query"  # Business query (read-only)
    WORKFLOW = "workflow"  # Multi-step workflow


class EventType(StrEnum):
    """Types of business events."""
    STATE_CHANGE = "state_change"  # Entity state changed
    BUSINESS_EVENT = "business_event"  # Significant business event
    LIFECYCLE = "lifecycle"  # Entity lifecycle event (created, deleted)
    NOTIFICATION = "notification"  # Notification event


@dataclass
class BusinessRule:
    """A business rule extracted from code."""
    rule_id: str
    name: str
    rule_type: RuleType
    description: str
    expression: str  # Rule logic (simplified)
    entity: str | None = None  # Entity this rule applies to
    severity: str = "error"  # error, warning, info
    file_path: str | None = None
    line_number: int | None = None


@dataclass
class DomainConcept:
    """A domain concept (entity, value object, etc.)."""
    name: str
    concept_type: str  # entity, value_object, aggregate, service
    attributes: list[dict]  # name, type
    operations: list[str]  # Operation names
    file_path: str
    line_start: int
    line_end: int
    is_aggregate_root: bool = False


@dataclass
class StateTransition:
    """A state transition in a state machine."""
    entity: str
    from_state: str
    to_state: str
    trigger: str  # What causes the transition
    guard_condition: str | None = None
    action: str | None = None
    file_path: str | None = None
    line_number: int | None = None


@dataclass
class BusinessOperation:
    """A business operation (command/query)."""
    name: str
    operation_type: OperationType
    entity: str | None = None
    parameters: list[dict] = field(default_factory=list)  # name, type
    return_type: str | None = None
    side_effects: list[str] = field(default_factory=list)  # Side effects (e.g., "send_email")
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class BusinessEvent:
    """A business event raised or handled."""
    name: str
    event_type: EventType
    entity: str | None = None
    payload: list[str] = field(default_factory=list)  # Payload fields
    handlers: list[str] = field(default_factory=list)  # Handler function names
    file_path: str | None = None
    line_number: int | None = None


@dataclass
class BusinessLogicResult:
    """Result of business logic reconstruction."""
    language: str
    source_files: list[str] = field(default_factory=list)
    rules: list[BusinessRule] = field(default_factory=list)
    concepts: list[DomainConcept] = field(default_factory=list)
    state_transitions: list[StateTransition] = field(default_factory=list)
    operations: list[BusinessOperation] = field(default_factory=list)
    events: list[BusinessEvent] = field(default_factory=list)
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate statistics for dashboard display."""
        # Count rules by type
        rules_by_type = defaultdict(int)
        for rule in self.rules:
            rules_by_type[rule.rule_type] += 1

        # Count concepts by type
        concepts_by_type = defaultdict(int)
        for concept in self.concepts:
            concepts_by_type[concept.concept_type] += 1

        # Count operations by type
        operations_by_type = defaultdict(int)
        for op in self.operations:
            operations_by_type[op.operation_type] += 1

        # Count events by type
        events_by_type = defaultdict(int)
        for event in self.events:
            events_by_type[event.event_type] += 1

        return {
            "total_rules": len(self.rules),
            "rules_by_type": dict(rules_by_type),
            "total_concepts": len(self.concepts),
            "concepts_by_type": dict(concepts_by_type),
            "aggregate_roots": len([c for c in self.concepts if c.is_aggregate_root]),
            "total_operations": len(self.operations),
            "operations_by_type": dict(operations_by_type),
            "total_state_transitions": len(self.state_transitions),
            "total_events": len(self.events),
            "events_by_type": dict(events_by_type),
        }

    def get_rules_for_entity(self, entity_name: str) -> list[BusinessRule]:
        """Get all business rules for a specific entity."""
        return [r for r in self.rules if r.entity == entity_name]

    def get_operations_for_entity(self, entity_name: str) -> list[BusinessOperation]:
        """Get all operations for a specific entity."""
        return [o for o in self.operations if o.entity == entity_name]

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "rule_type": r.rule_type,
                    "description": r.description,
                    "expression": r.expression,
                    "entity": r.entity,
                    "severity": r.severity,
                    "file_path": r.file_path,
                    "line_number": r.line_number,
                }
                for r in self.rules
            ],
            "concepts": [
                {
                    "name": c.name,
                    "concept_type": c.concept_type,
                    "attributes": c.attributes,
                    "operations": c.operations,
                    "file_path": c.file_path,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "is_aggregate_root": c.is_aggregate_root,
                }
                for c in self.concepts
            ],
            "state_transitions": [
                {
                    "entity": t.entity,
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "trigger": t.trigger,
                    "guard_condition": t.guard_condition,
                    "action": t.action,
                    "file_path": t.file_path,
                    "line_number": t.line_number,
                }
                for t in self.state_transitions
            ],
            "operations": [
                {
                    "name": o.name,
                    "operation_type": o.operation_type,
                    "entity": o.entity,
                    "parameters": o.parameters,
                    "return_type": o.return_type,
                    "side_effects": o.side_effects,
                    "file_path": o.file_path,
                    "line_start": o.line_start,
                    "line_end": o.line_end,
                }
                for o in self.operations
            ],
            "events": [
                {
                    "name": e.name,
                    "event_type": e.event_type,
                    "entity": e.entity,
                    "payload": e.payload,
                    "handlers": e.handlers,
                    "file_path": e.file_path,
                    "line_number": e.line_number,
                }
                for e in self.events
            ],
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "statistics": self.get_statistics(),
        }


class BusinessLogicAnalyzer:
    """Analyzes and reconstructs business logic from code."""

    def __init__(self):
        self.parser_registry = ASTParserRegistry.get_instance()

        # Business rule patterns
        self._rule_patterns = {
            "validation": [
                (r"validate\s+(\w+)", "validate"),
                (r"check\s+(\w+)", "check"),
                (r"ensure\s+", "ensure"),
                (r"if\s+not\s+.*:", "conditional_validation"),
            ],
            "constraint": [
                (r"must\s+", "must"),
                (r"cannot\s+", "cannot"),
                (r"required\s*", "required"),
                (r"unique\s+", "unique"),
            ],
        }

    def analyze_file(self, source_code: str, file_path: str, language: str) -> BusinessLogicResult:
        """Analyze a single file for business logic."""
        result = BusinessLogicResult(language=language)

        try:
            parser = self.parser_registry.get_parser(language)
            ast_tree = parser.parse(source_code, file_path)

            # Extract domain concepts (classes)
            self._extract_domain_concepts(ast_tree, file_path, result)

            # Extract business operations (functions)
            self._extract_business_operations(ast_tree, file_path, result)

            # Extract business rules
            self._extract_business_rules(source_code, file_path, result)

            # Detect state transitions
            self._detect_state_transitions(ast_tree, source_code, file_path, result)

            # Detect business events
            self._detect_business_events(ast_tree, source_code, file_path, result)

            result.source_files.append(file_path)

        except Exception as e:
            logger.error(f"Failed to analyze business logic in {file_path}: {e}")

        return result

    def _extract_domain_concepts(self, ast_tree: ASTTree, file_path: str, result: BusinessLogicResult):
        """Extract domain concepts (entities, value objects, etc.)."""
        for cls in ast_tree.all_classes():
            # Determine concept type based on naming patterns
            concept_type = self._classify_concept_type(cls)

            concept = DomainConcept(
                name=cls.name,
                concept_type=concept_type,
                attributes=[],  # TODO: extract from AST
                operations=[m.name for m in cls.methods],
                file_path=file_path,
                line_start=cls.line_start,
                line_end=cls.line_end,
                is_aggregate_root=concept_type == "aggregate",
            )
            result.concepts.append(concept)

    def _classify_concept_type(self, class_node) -> str:
        """Classify a class as entity, value object, aggregate, or service."""
        name = class_node.name.lower()

        # Service pattern
        if "service" in name or "handler" in name or "processor" in name:
            return "service"

        # Aggregate pattern
        if name.endswith("aggregate") or self._has_entity_operations(class_node):
            return "aggregate"

        # Entity pattern (default for domain classes)
        return "entity"

    def _has_entity_operations(self, class_node) -> bool:
        """Check if class has typical entity operations (CRUD)."""
        method_names = [m.name.lower() for m in class_node.methods]
        crud_keywords = ["create", "read", "update", "delete", "save", "get", "find"]
        return any(keyword in " ".join(method_names) for keyword in crud_keywords)

    def _extract_business_operations(self, ast_tree: ASTTree, file_path: str, result: BusinessLogicResult):
        """Extract business operations (commands/queries)."""
        # Extract top-level functions
        for func in ast_tree.all_functions(include_nested=False):
            operation_type = self._classify_operation_type(func)
            entity = self._extract_entity_from_function(func)

            operation = BusinessOperation(
                name=func.name,
                operation_type=operation_type,
                entity=entity,
                parameters=[{"name": p.name, "type": p.type} for p in func.parameters],
                return_type=func.return_type,
                side_effects=[],
                file_path=file_path,
                line_start=func.line_start,
                line_end=func.line_end,
            )
            result.operations.append(operation)

        # Extract class methods as operations
        for cls in ast_tree.all_classes():
            for method in cls.methods:
                if method.name != "__init__":  # Skip constructor
                    operation_type = self._classify_operation_type(method)
                    entity = cls.name  # Class methods operate on the class entity

                    operation = BusinessOperation(
                        name=f"{cls.name}.{method.name}",
                        operation_type=operation_type,
                        entity=entity,
                        parameters=[{"name": p.name, "type": p.type} for p in method.parameters if p.name != "self"],
                        return_type=method.return_type,
                        side_effects=[],
                        file_path=file_path,
                        line_start=method.line_start,
                        line_end=method.line_end,
                    )
                    result.operations.append(operation)

    def _classify_operation_type(self, func_node) -> OperationType:
        """Classify a function as command, query, or other operation type."""
        name = func_node.name.lower()

        # CRUD patterns
        if any(k in name for k in ["create", "add", "insert", "post"]):
            return OperationType.CREATE
        if any(k in name for k in ["get", "find", "fetch", "list", "query", "read", "show"]):
            return OperationType.QUERY
        if any(k in name for k in ["update", "edit", "modify", "put", "patch"]):
            return OperationType.UPDATE
        if any(k in name for k in ["delete", "remove", "destroy"]):
            return OperationType.DELETE

        # Default to command if it mutates, query if read-only
        if func_node.return_type and "none" in func_node.return_type.lower():
            return OperationType.COMMAND
        return OperationType.QUERY

    def _extract_entity_from_function(self, func_node) -> str | None:
        """Extract entity name from function name."""
        name = func_node.name

        # Common patterns: get_user, create_order, etc.
        for prefix in ["get_", "create_", "update_", "delete_", "find_", "list_"]:
            if name.startswith(prefix):
                return name[len(prefix):].capitalize()

        # Try snake_case to CamelCase
        parts = name.split("_")
        if len(parts) >= 2:
            return "".join(p.capitalize() for p in parts[:-1])

        return None

    def _extract_business_rules(self, source_code: str, file_path: str, result: BusinessLogicResult):
        """Extract business rules from source code using patterns."""
        rule_id = 0

        for rule_type, patterns in self._rule_patterns.items():
            for pattern, keyword in patterns:
                for match in re.finditer(pattern, source_code, re.IGNORECASE):
                    rule_id += 1
                    rule = BusinessRule(
                        rule_id=f"rule_{rule_id}",
                        name=f"{keyword}_{rule_id}",
                        rule_type=RuleType(rule_type),
                        description=f"Business rule detected via '{keyword}' pattern",
                        expression=match.group(0),
                        severity="error",
                        file_path=file_path,
                        line_number=source_code[:match.start()].count("\n") + 1,
                    )
                    result.rules.append(rule)

    def _detect_state_transitions(self, ast_tree: ASTTree, source_code: str, file_path: str, result: BusinessLogicResult):
        """Detect state machine transitions."""
        # Look for patterns like: order.status = "processing"
        status_pattern = r'(\w+)\.status\s*=\s*["\'](\w+)["\']'

        for match in re.finditer(status_pattern, source_code):
            entity = match.group(1)
            to_state = match.group(2)
            line_number = source_code[:match.start()].count("\n") + 1

            transition = StateTransition(
                entity=entity,
                from_state="unknown",  # Would need more sophisticated analysis
                to_state=to_state,
                trigger="assignment",
                file_path=file_path,
                line_number=line_number,
            )
            result.state_transitions.append(transition)

    def _detect_business_events(self, ast_tree: ASTTree, source_code: str, file_path: str, result: BusinessLogicResult):
        """Detect business events being raised or handled."""
        # Look for event patterns: emit, publish, raise, notify
        event_patterns = [
            (r"emit\(['\"](\w+)['\"]", "emit"),
            (r"publish\(['\"](\w+)['\"]", "publish"),
            (r"raise\s+(\w+Event)", "raise"),
            (r"notify\(['\"](\w+)['\"]", "notify"),
        ]

        for pattern, action in event_patterns:
            for match in re.finditer(pattern, source_code):
                event_name = match.group(1)
                line_number = source_code[:match.start()].count("\n") + 1

                event = BusinessEvent(
                    name=event_name,
                    event_type=EventType.BUSINESS_EVENT,
                    file_path=file_path,
                    line_number=line_number,
                )
                result.events.append(event)

    def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
    ) -> BusinessLogicResult:
        """Analyze multiple source files and create unified business logic model."""
        unified_result = BusinessLogicResult(language="multi")

        for file_info in source_files:
            try:
                file_result = self.analyze_file(
                    source_code=file_info["content"],
                    file_path=file_info["file_path"],
                    language=file_info["language"],
                )
                unified_result.source_files.extend(file_result.source_files)
                unified_result.rules.extend(file_result.rules)
                unified_result.concepts.extend(file_result.concepts)
                unified_result.state_transitions.extend(file_result.state_transitions)
                unified_result.operations.extend(file_result.operations)
                unified_result.events.extend(file_result.events)
            except Exception as e:
                logger.error(f"Failed to analyze {file_info.get('file_path')}: {e}")

        # Save to database
        self._save_to_database(unified_result, project_id)

        return unified_result

    def _save_to_database(self, result: BusinessLogicResult, project_id: int):
        """Save analysis results to database."""
        with get_sync_session() as db:
            analysis_result = AnalysisResult(
                project_id=project_id,
                analysis_type="business_logic",
                status=AnalysisStatus.COMPLETED,
                result_data=result.to_dict(),
                metadata={"statistics": result.get_statistics()},
            )
            db.add(analysis_result)
            db.commit()


def get_business_logic_analyzer() -> BusinessLogicAnalyzer:
    """Get or create business logic analyzer instance."""
    return BusinessLogicAnalyzer()
