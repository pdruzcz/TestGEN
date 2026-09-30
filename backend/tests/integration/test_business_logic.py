"""Tests for business logic reconstruction service - Story 1.24"""

import pytest

from app.services.analysis.business_logic import (
    BusinessEvent,
    BusinessLogicAnalyzer,
    BusinessLogicResult,
    BusinessOperation,
    BusinessRule,
    DomainConcept,
    EventType,
    OperationType,
    RuleType,
    StateTransition,
)


class TestRuleType:
    """Test RuleType enum."""

    def test_rule_types(self):
        """Test all rule types exist."""
        assert RuleType.VALIDATION == "validation"
        assert RuleType.CONSTRAINT == "constraint"
        assert RuleType.CALCULATION == "calculation"
        assert RuleType.AUTHORIZATION == "authorization"
        assert RuleType.CONDITIONAL == "conditional"
        assert RuleType.INvariant == "invariant"


class TestOperationType:
    """Test OperationType enum."""

    def test_operation_types(self):
        """Test all operation types exist."""
        assert OperationType.CREATE == "create"
        assert OperationType.READ == "read"
        assert OperationType.UPDATE == "update"
        assert OperationType.DELETE == "delete"
        assert OperationType.COMMAND == "command"
        assert OperationType.QUERY == "query"
        assert OperationType.WORKFLOW == "workflow"


class TestEventType:
    """Test EventType enum."""

    def test_event_types(self):
        """Test all event types exist."""
        assert EventType.STATE_CHANGE == "state_change"
        assert EventType.BUSINESS_EVENT == "business_event"
        assert EventType.LIFECYCLE == "lifecycle"
        assert EventType.NOTIFICATION == "notification"


class TestBusinessRule:
    """Test BusinessRule dataclass."""

    def test_rule_creation(self):
        """Test creating a business rule."""
        rule = BusinessRule(
            rule_id="rule_1",
            name="user_age_validation",
            rule_type=RuleType.VALIDATION,
            description="User must be 18 or older",
            expression="user.age >= 18",
            entity="User",
            severity="error",
            file_path="users.py",
            line_number=10,
        )
        assert rule.rule_id == "rule_1"
        assert rule.rule_type == RuleType.VALIDATION
        assert rule.entity == "User"


class TestDomainConcept:
    """Test DomainConcept dataclass."""

    def test_concept_creation(self):
        """Test creating a domain concept."""
        concept = DomainConcept(
            name="Order",
            concept_type="aggregate",
            attributes=[{"name": "id", "type": "int"}, {"name": "total", "type": "decimal"}],
            operations=["create", "update", "cancel"],
            file_path="order.py",
            line_start=1,
            line_end=50,
            is_aggregate_root=True,
        )
        assert concept.name == "Order"
        assert concept.concept_type == "aggregate"
        assert concept.is_aggregate_root is True


class TestStateTransition:
    """Test StateTransition dataclass."""

    def test_transition_creation(self):
        """Test creating a state transition."""
        transition = StateTransition(
            entity="Order",
            from_state="pending",
            to_state="processing",
            trigger="start_processing",
            guard_condition="order.is_valid",
            action="notify_customer",
            file_path="order.py",
            line_number=25,
        )
        assert transition.entity == "Order"
        assert transition.from_state == "pending"
        assert transition.to_state == "processing"


class TestBusinessOperation:
    """Test BusinessOperation dataclass."""

    def test_operation_creation(self):
        """Test creating a business operation."""
        operation = BusinessOperation(
            name="create_order",
            operation_type=OperationType.CREATE,
            entity="Order",
            parameters=[{"name": "user_id", "type": "int"}],
            return_type="Order",
            side_effects=["send_notification"],
            file_path="order.py",
            line_start=10,
            line_end=30,
        )
        assert operation.name == "create_order"
        assert operation.operation_type == OperationType.CREATE
        assert operation.entity == "Order"


class TestBusinessEvent:
    """Test BusinessEvent dataclass."""

    def test_event_creation(self):
        """Test creating a business event."""
        event = BusinessEvent(
            name="OrderCreated",
            event_type=EventType.LIFECYCLE,
            entity="Order",
            payload=["order_id", "user_id", "timestamp"],
            handlers=["send_notification", "update_inventory"],
            file_path="order.py",
            line_number=15,
        )
        assert event.name == "OrderCreated"
        assert event.event_type == EventType.LIFECYCLE
        assert event.entity == "Order"


class TestBusinessLogicResult:
    """Test BusinessLogicResult dataclass."""

    def test_empty_result(self):
        """Test creating empty result."""
        result = BusinessLogicResult(language="python")
        assert result.language == "python"
        assert len(result.rules) == 0
        assert len(result.concepts) == 0
        assert len(result.operations) == 0

    def test_result_statistics(self):
        """Test statistics calculation."""
        result = BusinessLogicResult(language="python")

        result.rules = [
            BusinessRule(
                rule_id="r1",
                name="age_validation",
                rule_type=RuleType.VALIDATION,
                description="User must be 18+",
                expression="age >= 18",
                entity="User",
            ),
            BusinessRule(
                rule_id="r2",
                name="email_unique",
                rule_type=RuleType.CONSTRAINT,
                description="Email must be unique",
                expression="email.is_unique()",
                entity="User",
            ),
        ]

        result.concepts = [
            DomainConcept(
                name="User",
                concept_type="entity",
                attributes=[],
                operations=["create", "update"],
                file_path="user.py",
                line_start=1,
                line_end=50,
                is_aggregate_root=False,
            ),
            DomainConcept(
                name="Order",
                concept_type="aggregate",
                attributes=[],
                operations=["create", "cancel"],
                file_path="order.py",
                line_start=1,
                line_end=100,
                is_aggregate_root=True,
            ),
        ]

        result.operations = [
            BusinessOperation(
                name="create_user",
                operation_type=OperationType.CREATE,
                entity="User",
                parameters=[],
                return_type="User",
            ),
            BusinessOperation(
                name="get_user",
                operation_type=OperationType.QUERY,
                entity="User",
                parameters=[],
                return_type="User",
            ),
        ]

        stats = result.get_statistics()

        assert stats["total_rules"] == 2
        assert stats["rules_by_type"]["validation"] == 1
        assert stats["rules_by_type"]["constraint"] == 1
        assert stats["total_concepts"] == 2
        assert stats["aggregate_roots"] == 1
        assert stats["total_operations"] == 2
        assert stats["operations_by_type"]["create"] == 1
        assert stats["operations_by_type"]["query"] == 1

    def test_get_rules_for_entity(self):
        """Test getting rules for a specific entity."""
        result = BusinessLogicResult(language="python")

        result.rules = [
            BusinessRule(
                rule_id="r1",
                name="age_validation",
                rule_type=RuleType.VALIDATION,
                description="User must be 18+",
                expression="age >= 18",
                entity="User",
            ),
            BusinessRule(
                rule_id="r2",
                name="amount_validation",
                rule_type=RuleType.VALIDATION,
                description="Amount must be positive",
                expression="amount > 0",
                entity="Order",
            ),
        ]

        user_rules = result.get_rules_for_entity("User")
        assert len(user_rules) == 1
        assert user_rules[0].entity == "User"

    def test_get_operations_for_entity(self):
        """Test getting operations for a specific entity."""
        result = BusinessLogicResult(language="python")

        result.operations = [
            BusinessOperation(
                name="create_user",
                operation_type=OperationType.CREATE,
                entity="User",
                parameters=[],
                return_type="User",
            ),
            BusinessOperation(
                name="create_order",
                operation_type=OperationType.CREATE,
                entity="Order",
                parameters=[],
                return_type="Order",
            ),
        ]

        user_ops = result.get_operations_for_entity("User")
        assert len(user_ops) == 1
        assert user_ops[0].name == "create_user"

    def test_to_dict_serialization(self):
        """Test result can be serialized to dict."""
        result = BusinessLogicResult(language="python")
        result.source_files = ["order.py"]
        result.rules = [
            BusinessRule(
                rule_id="r1",
                name="age_validation",
                rule_type=RuleType.VALIDATION,
                description="User must be 18+",
                expression="age >= 18",
            )
        ]

        data = result.to_dict()

        assert data["language"] == "python"
        assert "order.py" in data["source_files"]
        assert len(data["rules"]) == 1
        assert data["rules"][0]["name"] == "age_validation"


class TestBusinessLogicAnalyzer:
    """Test business logic analyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized."""
        analyzer = BusinessLogicAnalyzer()
        assert analyzer.parser_registry is not None

    def test_analyze_domain_entity(self):
        """Test analyzing domain entity."""
        analyzer = BusinessLogicAnalyzer()

        source_code = """
class Order:
    '''Order entity representing a customer order.'''
    def __init__(self, user_id: int, total: decimal.Decimal):
        self.user_id = user_id
        self.total = total
        self.status = "pending"

    def create(self):
        '''Create the order.'''
        pass

    def cancel(self):
        '''Cancel the order.'''
        self.status = "cancelled"
"""

        result = analyzer.analyze_file(source_code, "order.py", "python")

        assert result.language == "python"
        # Should extract domain concept
        assert len(result.concepts) >= 1
        assert any(c.name == "Order" for c in result.concepts)

    def test_analyze_business_operations(self):
        """Test analyzing business operations."""
        analyzer = BusinessLogicAnalyzer()

        source_code = """
class UserService:
    def create_user(self, name: str, email: str) -> User:
        '''Create a new user.'''
        if not self.validate_email(email):
            raise ValueError('Invalid email')
        return User(name=name, email=email)

    def get_user(self, user_id: int) -> User:
        '''Get user by ID.'''
        return db.query(User).get(user_id)

    def update_user(self, user_id: int, data: dict) -> User:
        '''Update user.'''
        user = self.get_user(user_id)
        user.update(data)
        return user

    def delete_user(self, user_id: int):
        '''Delete user.'''
        user = self.get_user(user_id)
        user.delete()
"""

        result = analyzer.analyze_file(source_code, "user_service.py", "python")

        assert result.language == "python"
        # Should extract operations
        assert len(result.operations) >= 4

        # Check operation types
        create_ops = [o for o in result.operations if o.operation_type == OperationType.CREATE]
        query_ops = [o for o in result.operations if o.operation_type == OperationType.QUERY]
        update_ops = [o for o in result.operations if o.operation_type == OperationType.UPDATE]
        delete_ops = [o for o in result.operations if o.operation_type == OperationType.DELETE]

        assert len(create_ops) >= 1
        assert len(query_ops) >= 1
        assert len(update_ops) >= 1
        assert len(delete_ops) >= 1

    def test_detect_state_transitions(self):
        """Test detecting state transitions."""
        analyzer = BusinessLogicAnalyzer()

        source_code = """
class Order:
    def start_processing(self):
        '''Start processing the order.'''
        self.status = "processing"

    def complete(self):
        '''Mark order as complete.'''
        self.status = "completed"

    def cancel(self):
        '''Cancel the order.'''
        self.status = "cancelled"
"""

        result = analyzer.analyze_file(source_code, "order.py", "python")

        assert result.language == "python"
        # Should detect state transitions
        assert len(result.state_transitions) >= 1

    def test_detect_business_events(self):
        """Test detecting business events."""
        analyzer = BusinessLogicAnalyzer()

        source_code = """
class OrderService:
    def create_order(self, data: dict) -> Order:
        '''Create order and emit event.'''
        order = Order(**data)
        emit('OrderCreated', order.to_dict())
        return order

    def ship_order(self, order_id: int):
        '''Ship order and publish event.'''
        order = self.get_order(order_id)
        order.ship()
        publish('OrderShipped', {'order_id': order_id})
"""

        result = analyzer.analyze_file(source_code, "order_service.py", "python")

        assert result.language == "python"
        # Should detect business events
        assert len(result.events) >= 1

    def test_classify_service_concept(self):
        """Test classification of service concepts."""
        analyzer = BusinessLogicAnalyzer()

        source_code = """
class OrderService:
    '''Service for order operations.'''
    def create_order(self, data):
        pass

    def process_payment(self, order_id):
        pass
"""

        result = analyzer.analyze_file(source_code, "order_service.py", "python")

        assert result.language == "python"
        # Should classify as service
        service_concepts = [c for c in result.concepts if c.concept_type == "service"]
        assert len(service_concepts) >= 1

    def test_classify_aggregate_concept(self):
        """Test classification of aggregate concepts."""
        analyzer = BusinessLogicAnalyzer()

        source_code = """
class OrderAggregate:
    '''Order aggregate root.'''
    def create(self, data):
        pass

    def update(self, data):
        pass

    def delete(self):
        pass
"""

        result = analyzer.analyze_file(source_code, "order_aggregate.py", "python")

        assert result.language == "python"
        # Should classify as aggregate (has CRUD operations)
        aggregate_concepts = [c for c in result.concepts if c.concept_type == "aggregate"]
        assert len(aggregate_concepts) >= 1

    def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple files."""
        analyzer = BusinessLogicAnalyzer()

        source_files = [
            {
                "file_path": "domain/order.py",
                "content": """
class Order:
    '''Order entity.'''
    def __init__(self, user_id, total):
        self.user_id = user_id
        self.total = total
        self.status = "pending"
""",
                "language": "python",
            },
            {
                "file_path": "services/order_service.py",
                "content": """
class OrderService:
    def create_order(self, data):
        '''Create new order.'''
        order = Order(**data)
        emit('OrderCreated', order)
        return order
""",
                "language": "python",
            },
        ]

        # Analyze without database save
        unified_result = BusinessLogicResult(language="multi")
        for file_info in source_files:
            file_result = analyzer.analyze_file(
                source_code=file_info["content"],
                file_path=file_info["file_path"],
                language=file_info["language"],
            )
            unified_result.source_files.extend(file_result.source_files)
            unified_result.rules.extend(file_result.rules)
            unified_result.concepts.extend(file_result.concepts)
            unified_result.operations.extend(file_result.operations)
            unified_result.state_transitions.extend(file_result.state_transitions)
            unified_result.events.extend(file_result.events)

        assert unified_result.language == "multi"
        assert len(unified_result.source_files) == 2
        # Should have concepts from both files
        assert len(unified_result.concepts) > 0
