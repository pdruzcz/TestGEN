"""Tests for template engine infrastructure - Story 1.35"""

import time

from app.models.test_case import TestFramework, TestType
from app.services.generators.template_engine import (
    RenderedTemplate,
    TemplateCategory,
    TemplateContext,
    TemplateEngine,
    TemplateLoader,
    get_template_engine,
)


class TestTemplateCategory:
    """Test TemplateCategory enum."""

    def test_category_values(self):
        """Test all category values exist."""
        assert TemplateCategory.BASIC == "basic"
        assert TemplateCategory.FIXTURE == "fixture"
        assert TemplateCategory.PARAMETERIZED == "parameterized"
        assert TemplateCategory.ASYNC == "async"
        assert TemplateCategory.POSITIVE == "positive"
        assert TemplateCategory.NEGATIVE == "negative"
        assert TemplateCategory.BOUNDARY == "boundary"
        assert TemplateCategory.INTEGRATION == "integration"
        assert TemplateCategory.E2E == "e2e"
        assert TemplateCategory.MOCK == "mock"
        assert TemplateCategory.STUB == "stub"
        assert TemplateCategory.SPY == "spy"


class TestTemplateContext:
    """Test TemplateContext dataclass."""

    def test_minimal_context(self):
        """Test creating minimal context."""
        context = TemplateContext(test_name="test_example")

        assert context.test_name == "test_example"
        assert context.test_description is None
        assert context.test_type is None

    def test_full_context(self):
        """Test creating full context."""
        context = TemplateContext(
            test_name="test_full",
            test_description="Full test",
            test_type=TestType.POSITIVE,
            source_function="calculate",
            source_class="Calculator",
            test_data={"input": 42},
            expected_result="84",
            framework=TestFramework.PYTEST,
            language="python",
            extra_vars={"custom": "value"},
        )

        assert context.test_name == "test_full"
        assert context.source_function == "calculate"
        assert context.test_data["input"] == 42
        assert context.extra_vars["custom"] == "value"


class TestRenderedTemplate:
    """Test RenderedTemplate dataclass."""

    def test_rendered_template(self):
        """Test rendered template result."""
        result = RenderedTemplate(
            content="def test(): pass",
            template_name="basic",
            framework=TestFramework.PYTEST,
            category=TemplateCategory.BASIC,
            render_time_ms=15.5,
        )

        assert "def test(): pass" in result.content
        assert result.framework == TestFramework.PYTEST
        assert result.render_time_ms == 15.5
        assert len(result.errors) == 0

    def test_rendered_template_with_errors(self):
        """Test rendered template with errors."""
        result = RenderedTemplate(
            content="",
            template_name="broken",
            framework=TestFramework.PYTEST,
            category=TemplateCategory.BASIC,
            errors=["Variable not found: undefined_var"],
        )

        assert result.content == ""
        assert len(result.errors) == 1
        assert "undefined_var" in result.errors[0]


class TestTemplateLoader:
    """Test custom template loader."""

    def test_loader_initialization(self):
        """Test loader can be initialized."""
        loader = TemplateLoader()
        assert loader.templates_dir is not None

    def test_loader_with_custom_dir(self):
        """Test loader with custom directory."""
        from pathlib import Path

        custom_dir = Path("custom/templates")
        loader = TemplateLoader(templates_dir=custom_dir)
        assert loader.templates_dir == custom_dir


class TestTemplateEngine:
    """Test template engine."""

    def test_engine_initialization(self):
        """Test engine can be initialized."""
        engine = TemplateEngine()
        assert engine is not None
        assert engine.env is not None
        assert engine._builtin_templates is not None

    def test_render_builtin_template(self):
        """Test rendering built-in template."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_example",
            test_description="Example test",
            expected_result="True",
        )

        result = engine.render_string(
            template_string="def {{ test_name }}():\n    '''{{ test_description }}'''\n    assert {{ expected_result }}",
            context=context,
        )

        assert "def test_example():" in result.content
        assert "Example test" in result.content
        assert "assert True" in result.content
        assert len(result.errors) == 0

    def test_render_with_complex_context(self):
        """Test rendering with complex context."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_with_data",
            test_data={"username": "test", "email": "test@example.com"},
            imports=["pytest", "models"],
        )

        result = engine.render_string(
            template_string="""{{ test_name }}:
    imports: {{ imports }}
    username: {{ test_data.username }}
    email: {{ test_data.email }}
""",
            context=context,
        )

        assert "test_with_data:" in result.content
        assert "test" in result.content
        assert "test@example.com" in result.content

    def test_render_with_extra_vars(self):
        """Test rendering with extra variables."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_custom",
            extra_vars={"custom_var": "custom_value", "another": 123},
        )

        result = engine.render_string(
            template_string="{{ test_name }}: {{ custom_var }}, {{ another }}",
            context=context,
        )

        assert "custom_value" in result.content
        assert "123" in result.content

    def test_render_with_missing_variable(self):
        """Test rendering with undefined variable."""
        engine = TemplateEngine()

        context = TemplateContext(test_name="test")

        result = engine.render_string(
            template_string="{{ test_name }}: {{ undefined_var }}",
            context=context,
        )

        # Should have error due to strict undefined
        assert len(result.errors) > 0

    def test_render_performance(self):
        """Test template rendering performance."""
        engine = TemplateEngine()

        context = TemplateContext(test_name="test_perf", test_description="Performance test")

        start = time.time()
        result = engine.render_string(
            template_string="def {{ test_name }}(): '''{{ test_description }}'''",
            context=context,
        )
        elapsed = time.time() - start

        assert result.render_time_ms is not None
        assert elapsed < 1.0  # Should be fast

    def test_get_template_list(self):
        """Test getting template list."""
        engine = TemplateEngine()

        # Pytest should have built-in templates
        pytest_templates = engine.get_template_list(TestFramework.PYTEST)

        assert isinstance(pytest_templates, list)

    def test_cache_functionality(self):
        """Test template caching."""
        engine = TemplateEngine()

        context = TemplateContext(test_name="test", test_description="Test")

        # First render
        result1 = engine.render_string(
            template_string="{{ test_name }}: {{ test_description }}",
            context=context,
        )

        # Second render should use cache
        result2 = engine.render_string(
            template_string="{{ test_name }}: {{ test_description }}",
            context=context,
        )

        assert result1.content == result2.content

    def test_clear_cache(self):
        """Test clearing template cache."""
        engine = TemplateEngine()

        # Add something to cache
        context = TemplateContext(test_name="test")
        engine.render_string(template_string="{{ test_name }}", context=context)

        # Clear cache
        engine.clear_cache()
        assert len(engine._template_cache) == 0

    def test_validate_valid_template(self):
        """Test validating valid template."""
        engine = TemplateEngine()

        is_valid = engine.validate_template(
            template_name="test",
            framework=TestFramework.PYTEST,
        )

        # Should not raise exception
        assert isinstance(is_valid, bool)

    def test_render_positive_scenario(self):
        """Test rendering positive test scenario."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_login_success",
            test_description="Verify user can login",
            test_type=TestType.POSITIVE,
            source_function="login",
            test_data={"username": "user", "password": "pass"},
            expected_result="auth_token is not None",
            framework=TestFramework.PYTEST,
        )

        # Use built-in positive template
        result = engine.render_string(
            template_string="""def {{ test_name }}():
    '''{{ test_description }}'''
    {% if source_function %}
    # Testing {{ source_function }}
    {% endif %}
    {% if expected_result %}
    {{ expected_result }}
    {% endif %}
""",
            context=context,
        )

        assert "test_login_success" in result.content
        assert "login" in result.content
        assert "auth_token" in result.content

    def test_render_negative_scenario(self):
        """Test rendering negative test scenario."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_login_invalid",
            test_description="Verify login fails with invalid credentials",
            test_type=TestType.NEGATIVE,
            expected_error="InvalidCredentials",
        )

        result = engine.render_string(
            template_string="""def {{ test_name }}():
    '''{{ test_description }}'''
    with pytest.raises({{ expected_error }}):
        login("invalid", "credentials")
""",
            context=context,
        )

        assert "InvalidCredentials" in result.content
        assert "pytest.raises" in result.content

    def test_render_with_setup_teardown(self):
        """Test rendering with setup and teardown."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_with_setup",
            setup_code="user = create_test_user()",
            test_code="result = process(user)",
            teardown_code="delete_test_user(user)",
        )

        result = engine.render_string(
            template_string="""def {{ test_name }}():
    {% if setup_code %}
    # Setup
    {{ setup_code }}
    {% endif %}
    {% if test_code %}
    # Test
    {{ test_code }}
    {% endif %}
    {% if teardown_code %}
    # Teardown
    {{ teardown_code }}
    {% endif %}
""",
            context=context,
        )

        assert "create_test_user()" in result.content
        assert "process(user)" in result.content
        assert "delete_test_user(user)" in result.content

    def test_render_integration_test(self):
        """Test rendering integration test template."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_api_integration",
            test_description="Test API endpoint integration",
            test_type=TestType.INTEGRATION,
            source_endpoint="/api/users",
            framework=TestFramework.PYTEST,
        )

        result = engine.render_string(
            template_string="""def {{ test_name }}():
    '''{{ test_description }} - {{ test_type }}'''
    endpoint = "{{ source_endpoint }}"
    # Make request
    response = client.get(endpoint)
    assert response.status_code == 200
""",
            context=context,
        )

        assert "api_integration" in result.content
        assert "/api/users" in result.content
        assert "integration" in result.content

    def test_render_with_imports(self):
        """Test rendering with imports."""
        engine = TemplateEngine()

        context = TemplateContext(
            test_name="test_with_imports",
            imports=["pytest", "from app.models import User"],
        )

        result = engine.render_string(
            template_string="""{{ test_name }}():
    # Imports: {{ imports }}
    pass
""",
            context=context,
        )

        # Check imports are included
        assert "Imports:" in result.content

    def test_multiple_frameworks(self):
        """Test templates work for different frameworks."""
        engine = TemplateEngine()

        # Pytest
        pytest_context = TemplateContext(
            test_name="pytest_test",
            framework=TestFramework.PYTEST,
        )
        pytest_result = engine.render_string(
            template_string="def {{ test_name }}(): pass (framework: {{ framework }})",
            context=pytest_context,
        )
        assert "pytest" in pytest_result.content

        # JUnit
        junit_context = TemplateContext(
            test_name="junitTest",
            framework=TestFramework.JUNIT,
        )
        junit_result = engine.render_string(
            template_string="@Test\npublic void {{ test_name }}() {} // framework: {{ framework }}",
            context=junit_context,
        )
        assert "junit" in junit_result.content


def test_get_template_engine():
    """Test getting template engine instance."""
    engine = get_template_engine()
    assert isinstance(engine, TemplateEngine)
