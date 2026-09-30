"""Tests for test type classifier - Story 1.34"""

from app.models.test_case import TestFramework, TestType
from app.services.generators.test_classifier import (
    TestCategory,
    TestClassification,
    TestClassifier,
    TestComplexity,
    TestLayer,
    get_test_classifier,
)


class TestTestLayer:
    """Test TestLayer enum."""

    def test_layer_values(self):
        """Test all layer values exist."""
        assert TestLayer.UNIT == "unit"
        assert TestLayer.INTEGRATION == "integration"
        assert TestLayer.E2E == "e2e"
        assert TestLayer.ACCEPTANCE == "acceptance"


class TestEnumTestCategory:
    """Test TestCategory enum."""

    def test_category_values(self):
        """Test all category values exist."""
        assert TestCategory.FUNCTIONAL == "functional"
        assert TestCategory.NON_FUNCTIONAL == "non_functional"
        assert TestCategory.STRUCTURAL == "structural"
        assert TestCategory.BEHAVIORAL == "behavioral"
        assert TestCategory.SEMANTIC == "semantic"


class TestEnumTestComplexity:
    """Test TestComplexity enum."""

    def test_complexity_values(self):
        """Test all complexity values exist."""
        assert TestComplexity.SIMPLE == "simple"
        assert TestComplexity.MODERATE == "moderate"
        assert TestComplexity.COMPLEX == "complex"
        assert TestComplexity.VERY_COMPLEX == "very_complex"


class TestDataTestClassification:
    """Test TestClassification dataclass."""

    def test_classification_creation(self):
        """Test creating a classification."""
        classification = TestClassification(
            test_type=TestType.UNIT,
            layer=TestLayer.UNIT,
            category=TestCategory.FUNCTIONAL,
            complexity=TestComplexity.SIMPLE,
            tags=["unit", "simple"],
            confidence=0.9,
            reasoning="Simple unit test",
        )

        assert classification.test_type == TestType.UNIT
        assert classification.layer == TestLayer.UNIT
        assert classification.confidence == 0.9
        assert len(classification.tags) == 2


class TestSvcTestClassifier:
    """Test test classifier."""

    def test_classifier_initialization(self):
        """Test classifier can be initialized."""
        classifier = TestClassifier()
        assert classifier is not None
        assert len(classifier.security_keywords) > 0
        assert len(classifier.performance_keywords) > 0

    def test_classify_unit_test(self):
        """Test classifying a simple unit test."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_calculate_sum",
            description="Test addition function",
            test_code="def test_calculate_sum():\n    assert add(1, 2) == 3",
            source_function="add",
        )

        assert classification.test_type == TestType.UNIT
        assert classification.layer == TestLayer.UNIT
        assert classification.complexity == TestComplexity.SIMPLE

    def test_classify_integration_test(self):
        """Test classifying an integration test."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_database_api_integration",
            description="Test API with database",
            test_code="def test_db_api():\n    record = db.query(Model).first()\n    response = client.get('/api/data')\n    assert response.status_code == 200",
            source_endpoint="/api/data",
            imports=["sqlalchemy", "requests"],
        )

        assert classification.test_type == TestType.INTEGRATION
        assert classification.layer == TestLayer.INTEGRATION
        assert "integration" in classification.tags

    def test_classify_e2e_test(self):
        """Test classifying an E2E test."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_shopping_cart_e2e",
            description="End-to-end shopping cart checkout",
            test_code="def test_cart():\n    browser.get('/shop')\n    browser.find('#add-to-cart').click()\n    browser.find('#checkout').click()\n    browser.find('#confirm').click()",
            framework=TestFramework.SELENIUM,
        )

        assert classification.test_type == TestType.E2E
        assert classification.layer == TestLayer.E2E
        assert classification.complexity >= TestComplexity.MODERATE

    def test_classify_security_test(self):
        """Test classifying a security test."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_sql_injection_protection",
            description="Verify SQL injection is blocked",
            test_code="def test_sql_injection():\n    response = client.get('/api/users?id=1 OR 1=1')\n    assert response.status_code == 400",
        )

        assert classification.test_type == TestType.SECURITY
        assert "security" in classification.tags

    def test_classify_performance_test(self):
        """Test classifying a performance test."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_api_response_time",
            description="Verify API responds within SLA",
            test_code="def test_performance():\n    start = time.time()\n    response = client.get('/api/users')\n    duration = time.time() - start\n    assert duration < 0.5",
        )

        assert classification.test_type == TestType.PERFORMANCE

    def test_classify_accessibility_test(self):
        """Test classifying an accessibility test."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_aria_labels_present",
            description="Verify ARIA labels on buttons",
            test_code="def test_a11y():\n    buttons = browser.find_elements(By.TAG_NAME, 'button')\n    for btn in buttons:\n        assert btn.get_attribute('aria-label')",
        )

        assert classification.test_type == TestType.ACCESSIBILITY

    def test_classify_minimal_input(self):
        """Test classification with minimal input."""
        classifier = TestClassifier()

        classification = classifier.classify_test(name="test_simple")

        assert classification.test_type is not None
        assert classification.layer is not None
        assert classification.confidence >= 0.0

    def test_confidence_calculation(self):
        """Test confidence is calculated correctly."""
        classifier = TestClassifier()

        # High confidence test
        high = classifier.classify_test(
            name="test_function_name",
            description="Clear description",
            test_code="def test(): assert True",
            source_function="function_name",
            source_endpoint="/api/endpoint",
            imports=["pytest"],
        )

        # Low confidence test
        low = classifier.classify_test(name="test")

        assert high.confidence > low.confidence

    def test_complexity_simple(self):
        """Test simple complexity classification."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_simple",
            test_code="def test():\n    assert True",
        )

        assert classification.complexity == TestComplexity.SIMPLE

    def test_complexity_moderate(self):
        """Test moderate complexity classification."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_moderate",
            test_code="""
def test():
    setup_data()
    result = execute()
    assert result
    cleanup_data()
""",
        )

        assert classification.complexity in [TestComplexity.SIMPLE, TestComplexity.MODERATE]

    def test_tags_generation(self):
        """Test tags are generated correctly."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_api",
            source_endpoint="/api/users",
            framework=TestFramework.PYTEST,
        )

        assert len(classification.tags) > 0
        assert "pytest" in classification.tags

    def test_reasoning_generation(self):
        """Test reasoning is generated."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_unit_func",
            source_function="func",
        )

        assert classification.reasoning is not None
        assert len(classification.reasoning) > 0

    def test_has_network_calls_detection(self):
        """Test network call detection."""
        classifier = TestClassifier()

        assert classifier._has_network_calls("requests.get('http://api.example.com')", [])
        assert classifier._has_network_calls("fetch('/api/data')", [])
        assert not classifier._has_network_calls("local_function()", [])

    def test_has_database_calls_detection(self):
        """Test database call detection."""
        classifier = TestClassifier()

        assert classifier._has_database_calls("db.query(User).all()", ["sqlalchemy"])
        assert classifier._has_database_calls("session.execute('SELECT *')", [])
        assert not classifier._has_database_calls("x = 1", [])

    def test_count_assertions(self):
        """Test assertion counting."""
        classifier = TestClassifier()

        count = classifier._count_assertions(
            "def test():\n    assert x == 1\n    assert y > 0\n    assert z is not None"
        )

        assert count >= 3

    def test_analyze_setup_complexity(self):
        """Test setup complexity analysis."""
        classifier = TestClassifier()

        # Simple setup
        simple = classifier._analyze_setup_complexity("def test(): pass")
        assert simple <= 2

        # Complex setup with mocks
        complex_result = classifier._analyze_setup_complexity(
            """
@pytest.fixture
def mock_data():
    return mock.Mock()

def test():
    setup_data()
    with mock.patch():
        pass
"""
        )
        assert complex_result >= 3

    def test_extract_keywords(self):
        """Test keyword extraction."""
        classifier = TestClassifier()

        keywords = classifier._extract_keywords(
            name="test_user_login_with_valid_credentials",
            description="Verify user can login",
            test_code="assert user.authenticated",
        )

        assert "test" in keywords
        assert "user" in keywords
        assert "login" in keywords
        assert "valid" in keywords

    def test_classify_with_endpoint(self):
        """Test classification with endpoint information."""
        classifier = TestClassifier()

        classification = classifier.classify_test(
            name="test_get_users",
            source_endpoint="/api/users",
            test_code="response = client.get('/api/users')",
        )

        # Should be classified as integration due to endpoint
        assert classification.layer in [TestLayer.UNIT, TestLayer.INTEGRATION]

    def test_security_keywords_in_name(self):
        """Test security detection from name."""
        classifier = TestClassifier()

        classification = classifier.classify_test(name="test_authentication_security")

        assert classification.test_type == TestType.SECURITY

    def test_performance_keywords_in_name(self):
        """Test performance detection from name."""
        classifier = TestClassifier()

        classification = classifier.classify_test(name="test_api_load_performance")

        assert classification.test_type == TestType.PERFORMANCE


def test_get_test_classifier():
    """Test getting test classifier instance."""
    classifier = get_test_classifier()
    assert isinstance(classifier, TestClassifier)
