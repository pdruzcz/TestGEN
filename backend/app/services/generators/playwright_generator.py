"""Playwright test generator - Story 1.41

Generates Playwright E2E tests:
- Modern browser automation
- Multi-browser support (Chromium, Firefox, WebKit)
- Auto-waiting for elements
- Network interception
- Screenshot and video recording
- Trace viewing
- Parallel test execution
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
class PlaywrightTestSpec:
    """Specification for Playwright test generation."""
    test_name: str
    description: str
    browser: str = "chromium"  # chromium, firefox, webkit
    headless: bool = True
    url: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[str] = field(default_factory=list)
    screenshot_on_failure: bool = True
    video_recording: bool = False
    trace: bool = False
    viewport: dict[str, int] | None = None


class PlaywrightTestGenerator:
    """Generates Playwright E2E tests."""

    def __init__(self):
        self.engine = get_template_engine()

    def generate_test(self, spec: PlaywrightTestSpec) -> str:
        """Generate Playwright test from specification."""
        context = TemplateContext(
            test_name=spec.test_name,
            test_description=spec.description,
            framework=TestFramework.PLAYWRIGHT,
            extra_vars={
                "browser": spec.browser,
                "headless": spec.headless,
                "url": spec.url,
                "steps": spec.steps,
                "assertions": spec.assertions,
                "screenshot_on_failure": spec.screenshot_on_failure,
                "video_recording": spec.video_recording,
                "trace": spec.trace,
                "viewport": spec.viewport,
            },
        )

        template = self._get_playwright_template()
        result = self.engine.render_string(template, context)

        return result.content

    def _get_playwright_template(self) -> str:
        """Get Playwright test template."""
        return '''import pytest
from playwright.sync_api import Page, expect

class Test{{ test_name | title }}:
    """{{ test_description }}"""

    @pytest.fixture(autouse=True)
    async def page(self):
        async with async_playwright() as p:
            browser = await p.{{ browser }}.launch(
                headless={{ "True" if headless else "False" }}
                {% if viewport %}
                viewport={"width": {{ viewport.width }}, "height": {{ viewport.height }}}
                {% endif %}
            )
            context = await browser.new_context(
                {% if video_recording %}
                record_video_dir="videos/"
                {% endif %}
                {% if trace %}
                trace="on"
                {% endif %}
            )
            page = await context.new_page()
            {% if url %}
            await page.goto("{{ url }}")
            {% endif %}
            yield page
            {% if video_recording or trace %}
            await context.close()
            {% endif %}
            await browser.close()

    async def test_{{ test_name | lower }}(self, page: Page):
        """{{ test_description }}"""
        {% for step in steps %}
        # {{ step.description }}
        {% if step.action == "click" %}
        await page.click("{{ step.selector }}")
        {% elif step.action == "fill" %}
        await page.fill("{{ step.selector }}", "{{ step.value }}")
        {% elif step.action == "goto" %}
        await page.goto("{{ step.url }}")
        {% elif step.action == "wait" %}
        await page.wait_for_selector("{{ step.selector }}")
        {% elif step.action == "screenshot" %}
        await page.screenshot(path="{{ step.filename }}")
        {% endif %}

        {% endfor %}

        # Assertions
        {% for assertion in assertions %}
        # {{ assertion }}
        {% if "visible" in assertion %}
        await expect(page.locator("{{ assertion.selector }}")).to_be_visible()
        {% elif "url" in assertion %}
        await expect(page).to_have_url("{{ assertion.expected_url }}")
        {% endif %}
        {% endfor %}

    async def test_{{ test_name | lower }}_screenshot(self, page: Page):
        """{{ test_description }} with screenshot."""
        {% if url %}
        await page.goto("{{ url }}")
        {% endif %}
        await page.screenshot(path="screenshots/{{ test_name | lower }}.png")
'''


def get_playwright_generator() -> PlaywrightTestGenerator:
    """Get or create Playwright test generator instance."""
    return PlaywrightTestGenerator()
