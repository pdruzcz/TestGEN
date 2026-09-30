"""
Template engine infrastructure - Story 1.35

Provides robust template-based test code generation:
- Template loading and management
- Variable substitution and rendering
- Template inheritance and composition
- Multi-framework template support
- Template validation
- Caching for performance

Core infrastructure for framework-specific generators.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from jinja2 import (
    BaseLoader,
    Environment,
    StrictUndefined,
    Template,
    TemplateNotFound,
    TemplateSyntaxError,
)

from app.models.test_case import TestFramework, TestType

logger = logging.getLogger(__name__)


class TemplateCategory(StrEnum):
    """Categories of test templates."""

    # Test structure
    BASIC = "basic"  # Simple test structure
    FIXTURE = "fixture"  # Setup/teardown fixtures
    PARAMETERIZED = "parameterized"  # Data-driven tests
    ASYNC = "async"  # Async test patterns

    # Test types
    POSITIVE = "positive"  # Happy path tests
    NEGATIVE = "negative"  # Error case tests
    BOUNDARY = "boundary"  # Edge case tests
    INTEGRATION = "integration"  # Integration tests
    E2E = "e2e"  # End-to-end tests

    # Special patterns
    MOCK = "mock"  # Mocking patterns
    STUB = "stub"  # Stub patterns
    SPY = "spy"  # Spying patterns


@dataclass
class TemplateContext:
    """Context data for template rendering."""

    # Test metadata
    test_name: str
    test_description: str | None = None
    test_type: TestType | None = None

    # Source code reference
    source_function: str | None = None
    source_class: str | None = None
    source_endpoint: str | None = None
    source_file: str | None = None

    # Test data
    test_data: dict[str, Any] | None = None
    expected_result: str | None = None
    expected_error: str | None = None

    # Test code
    imports: list[str] | None = None
    setup_code: str | None = None
    test_code: str | None = None
    teardown_code: str | None = None

    # Configuration
    framework: TestFramework | None = None
    language: str | None = None

    # Additional context
    extra_vars: dict[str, Any] | None = None


@dataclass
class RenderedTemplate:
    """Result of template rendering."""

    content: str
    template_name: str
    framework: TestFramework
    category: TemplateCategory
    render_time_ms: float | None = None
    errors: list[str] = field(default_factory=list)


class TemplateLoader(BaseLoader):
    """Custom template loader for test templates."""

    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize template loader.

        Args:
            templates_dir: Directory containing templates
        """
        self.templates_dir = templates_dir or Path("app/services/generators/templates")
        super().__init__()

    def get_source(self, environment: Environment, template: str) -> tuple[str, str | None, lambda: bool]:
        """
        Get template source.

        Args:
            environment: Jinja2 environment
            template: Template name/path

        Returns:
            Tuple of (source, path, reload_function)
        """
        path = self.templates_dir / template
        if not path.exists():
            # Try with framework subdirectory
            framework = template.split("/")[0]
            path = self.templates_dir / framework / template.replace(f"{framework}/", "")

        if not path.exists():
            raise TemplateNotFound(template)

        with open(path, encoding="utf-8") as f:
            source = f.read()

        mtime = path.stat().st_mtime

        def reload() -> bool:
            try:
                return path.stat().st_mtime > mtime
            except OSError:
                return False

        return source, str(path), reload


class TemplateEngine:
    """
    Template engine for test code generation.

    Provides Jinja2-based template rendering with caching,
    validation, and multi-framework support.
    """

    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize template engine.

        Args:
            templates_dir: Directory containing templates
        """
        self.templates_dir = templates_dir or Path("app/services/generators/templates")
        self.loader = TemplateLoader(self.templates_dir)

        # Create Jinja2 environment
        self.env = Environment(
            loader=self.loader,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Template cache
        self._template_cache: dict[str, Template] = {}

        # Built-in templates (for fallback)
        self._builtin_templates = self._load_builtin_templates()

    def render(
        self,
        template_name: str,
        context: TemplateContext,
        framework: TestFramework,
        category: TemplateCategory = TemplateCategory.BASIC,
    ) -> RenderedTemplate:
        """
        Render a template with given context.

        Args:
            template_name: Name of template to render
            context: Template context data
            framework: Test framework
            category: Template category

        Returns:
            Rendered template result
        """
        import time

        start_time = time.time()
        errors = []

        try:
            # Get template
            template = self._get_template(framework.value, template_name, category)

            # Build context dict
            context_dict = self._build_context_dict(context)

            # Render
            content = template.render(**context_dict)

            render_time_ms = (time.time() - start_time) * 1000

            return RenderedTemplate(
                content=content,
                template_name=template_name,
                framework=framework,
                category=category,
                render_time_ms=render_time_ms,
                errors=errors,
            )

        except Exception as e:
            errors.append(str(e))
            render_time_ms = (time.time() - start_time) * 1000

            return RenderedTemplate(
                content="",
                template_name=template_name,
                framework=framework,
                category=category,
                render_time_ms=render_time_ms,
                errors=errors,
            )

    def render_string(
        self,
        template_string: str,
        context: TemplateContext,
    ) -> RenderedTemplate:
        """
        Render a template string directly.

        Args:
            template_string: Template content as string
            context: Template context data

        Returns:
            Rendered template result
        """
        import time

        start_time = time.time()
        errors = []

        try:
            template = self.env.from_string(template_string)
            context_dict = self._build_context_dict(context)
            content = template.render(**context_dict)

            render_time_ms = (time.time() - start_time) * 1000

            return RenderedTemplate(
                content=content,
                template_name="<string>",
                framework=TestFramework.PYTEST,  # Default
                category=TemplateCategory.BASIC,
                render_time_ms=render_time_ms,
                errors=errors,
            )

        except Exception as e:
            errors.append(str(e))
            render_time_ms = (time.time() - start_time) * 1000

            return RenderedTemplate(
                content="",
                template_name="<string>",
                framework=TestFramework.PYTEST,
                category=TemplateCategory.BASIC,
                render_time_ms=render_time_ms,
                errors=errors,
            )

    def validate_template(self, template_name: str, framework: TestFramework) -> bool:
        """
        Validate template syntax.

        Args:
            template_name: Name of template
            framework: Test framework

        Returns:
            True if template is valid
        """
        try:
            self._get_template(framework.value, template_name, TemplateCategory.BASIC)
            return True
        except (TemplateSyntaxError, TemplateNotFound):
            return False

    def get_template_list(self, framework: TestFramework) -> list[str]:
        """
        Get list of available templates for a framework.

        Args:
            framework: Test framework

        Returns:
            List of template names
        """
        framework_dir = self.templates_dir / framework.value
        if not framework_dir.exists():
            return []

        templates = []
        for path in framework_dir.glob("*.j2"):
            templates.append(path.stem)

        return templates

    def _get_template(self, framework: str, name: str, category: TemplateCategory) -> Template:
        """Get template from cache or load it."""
        cache_key = f"{framework}/{category}/{name}"

        if cache_key in self._template_cache:
            return self._template_cache[cache_key]

        # Try loading from file
        try:
            template = self.env.get_template(f"{framework}/{category}/{name}.j2")
            self._template_cache[cache_key] = template
            return template
        except TemplateNotFound:
            pass

        # Try built-in templates
        builtin_key = f"{framework}_{category.value}_{name}"
        if builtin_key in self._builtin_templates:
            template = self.env.from_string(self._builtin_templates[builtin_key])
            self._template_cache[cache_key] = template
            return template

        # Fallback to basic template
        fallback = f"{framework}_basic_{name}"
        if fallback in self._builtin_templates:
            template = self.env.from_string(self._builtin_templates[fallback])
            self._template_cache[cache_key] = template
            return template

        raise TemplateNotFound(name)

    def _build_context_dict(self, context: TemplateContext) -> dict[str, Any]:
        """Build Jinja2 context dict from TemplateContext."""
        ctx = {
            "test_name": context.test_name,
            "test_description": context.test_description or "",
            "test_type": context.test_type.value if context.test_type else "unit",
            "source_function": context.source_function,
            "source_class": context.source_class,
            "source_endpoint": context.source_endpoint,
            "source_file": context.source_file,
            "test_data": context.test_data or {},
            "expected_result": context.expected_result,
            "expected_error": context.expected_error,
            "imports": context.imports or [],
            "setup_code": context.setup_code or "",
            "test_code": context.test_code or "",
            "teardown_code": context.teardown_code or "",
            "framework": context.framework.value if context.framework else "pytest",
            "language": context.language or "python",
        }

        # Add extra variables
        if context.extra_vars:
            ctx.update(context.extra_vars)

        return ctx

    def _load_builtin_templates(self) -> dict[str, str]:
        """Load built-in templates for fallback."""
        return {
            # Pytest basic test
            "pytest_basic_test": """def {{ test_name }}():
    '''{{ test_description }}'''
    {% if setup_code %}
{{ setup_code }}
    {% endif %}
    {% if test_code %}
{{ test_code }}
    {% else %}
    # Test implementation
    pass
    {% endif %}
    {% if teardown_code %}
{{ teardown_code }}
    {% endif %}
    {% if expected_result %}
    assert {{ expected_result }}
    {% endif %}
""",
            # Pytest negative test
            "pytest_negative_test": """def {{ test_name }}():
    '''{{ test_description }}'''
    {% if setup_code %}
{{ setup_code }}
    {% endif %}
    {% if test_code %}
{{ test_code }}
    {% endif %}
    {% if expected_error %}
    with pytest.raises({{ expected_error }}):
        pass
    {% endif %}
""",
            # JUnit basic test
            "junit_basic_test": """@Test
public void {{ test_name }}() {
    // {{ test_description }}
    {% if setup_code %}
{{ setup_code }}
    {% endif %}
    {% if expected_result %}
    assertEquals({{ expected_result }}, result);
    {% endif %}
}
""",
        }

    def clear_cache(self):
        """Clear template cache."""
        self._template_cache.clear()


def get_template_engine() -> TemplateEngine:
    """Get or create template engine instance."""
    return TemplateEngine()
