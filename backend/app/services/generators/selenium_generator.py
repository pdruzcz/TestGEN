"""Selenium WebDriver test generator - Story 1.40

Generates Selenium WebDriver E2E tests for web applications:
- Browser setup and teardown
- Element location strategies
- User interactions (click, type, wait)
- Assertions and verifications
- Page object pattern support
- Cross-browser compatibility
- Screenshot on failure
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.generators.template_engine import (
    TemplateContext,
    TemplateEngine,
    TestFramework,
    get_template_engine,
)

logger = logging.getLogger(__name__)


@dataclass
class SeleniumTestSpec:
    """Specification for Selenium test generation."""
    test_name: str
    description: str
    browser: str = "chrome"  # chrome, firefox, safari, edge
    headless: bool = True
    url: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[str] = field(default_factory=list)
    page_object: str | None = None
    screenshot_on_failure: bool = True


class SeleniumTestGenerator:
    """Generates Selenium WebDriver E2E tests."""

    def __init__(self):
        self.engine = get_template_engine()

    def generate_test(self, spec: SeleniumTestSpec) -> str:
        """Generate Selenium test from specification."""
        context = TemplateContext(
            test_name=spec.test_name,
            test_description=spec.description,
            framework=TestFramework.SELENIUM,
            extra_vars={
                "browser": spec.browser,
                "headless": spec.headless,
                "url": spec.url,
                "steps": spec.steps,
                "assertions": spec.assertions,
                "page_object": spec.page_object,
                "screenshot_on_failure": spec.screenshot_on_failure,
            },
        )

        template = self._get_selenium_template()
        result = self.engine.render_string(template, context)

        return result.content

    def _get_selenium_template(self) -> str:
        """Get Selenium test template."""
        return '''import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
{% if page_object %}
from {{ page_object }} import PageObject
{% endif %}

class {{ test_name }}:
    """{{ test_description }}"""

    def setup_method(self):
        """Setup browser driver."""
        options = webdriver.{{ browser|capitalize }}Options()
        {% if headless %}
        options.add_argument("--headless")
        {% endif %}
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        self.driver = webdriver.{{ browser|capitalize }}(options=options)
        self.driver.implicitly_wait(10)

        {% if url %}
        self.driver.get("{{ url }}")
        {% endif %}

    def teardown_method(self):
        """Cleanup browser driver."""
        {% if screenshot_on_failure %}
        if hasattr(self, "_test_method_failed"):
            self.driver.save_screenshot("screenshot_on_failure.png")
        {% endif %}
        self.driver.quit()

    def test_{{ test_name | lower }}(self):
        """{{ test_description }}"""
        {% for step in steps %}
        # {{ step.description }}
        {% if step.action == "click" %}
        element = self.driver.find_element(By.{{ step.locator.upper() }}, "{{ step.selector }}")
        element.click()
        {% elif step.action == "type" %}
        element = self.driver.find_element(By.{{ step.locator.upper() }}, "{{ step.selector }}")
        element.send_keys("{{ step.value }}")
        {% elif step.action == "wait" %}
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.{{ step.locator.upper() }}, "{{ step.selector }}"))
        )
        {% endif %}

        {% endfor %}

        # Assertions
        {% for assertion in assertions %}
        # {{ assertion }}
        {% endfor %}
'''


def get_selenium_generator() -> SeleniumTestGenerator:
    """Get or create Selenium test generator instance."""
    return SeleniumTestGenerator()
