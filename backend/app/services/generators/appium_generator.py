"""Appium mobile test generator - Story 1.42

Generates Appium mobile E2E tests:
- iOS and Android support
- Native and hybrid apps
- Element location strategies
- Touch gestures (tap, swipe, scroll)
- App setup and cleanup
- Screenshot on failure
- Device capabilities
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.services.generators.template_engine import (
    TemplateContext,
    TemplateEngine,
    TestFramework,
    get_template_engine,
)

logger = logging.getLogger(__name__)


class MobilePlatform(StrEnum):
    """Mobile platforms."""
    IOS = "ios"
    ANDROID = "android"


class AppType(StrEnum):
    """Application types."""
    NATIVE = "native"
    HYBRID = "hybrid"
    WEB = "web"


@dataclass
class AppiumTestSpec:
    """Specification for Appium test generation."""
    test_name: str
    description: str
    platform: MobilePlatform
    app_type: AppType
    app_package: str | None = None  # e.g., com.example.app
    app_activity: str | None = None  # Android activity
    automation_name: str = "UiAutomator2"
    device_name: str | None = None
    udid: str | None = None  # Unique device ID
    steps: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[str] = field(default_factory=list)
    screenshot_on_failure: bool = True


class AppiumTestGenerator:
    """Generates Appium mobile E2E tests."""

    def __init__(self):
        self.engine = get_template_engine()

    def generate_test(self, spec: AppiumTestSpec) -> str:
        """Generate Appium test from specification."""
        context = TemplateContext(
            test_name=spec.test_name,
            test_description=spec.description,
            framework=TestFramework.APPIUM,
            extra_vars={
                "platform": spec.platform.value,
                "app_type": spec.app_type.value,
                "app_package": spec.app_package,
                "app_activity": spec.app_activity,
                "automation_name": spec.automation_name,
                "device_name": spec.device_name,
                "udid": spec.udid,
                "steps": spec.steps,
                "assertions": spec.assertions,
                "screenshot_on_failure": spec.screenshot_on_failure,
            },
        )

        template = self._get_appium_template(spec.platform)
        result = self.engine.render_string(template, context)

        return result.content

    def _get_appium_template(self, platform: MobilePlatform) -> str:
        """Get Appium template for platform."""
        if platform == MobilePlatform.ANDROID:
            return self._get_android_template()
        else:
            return self._get_ios_template()

    def _get_android_template(self) -> str:
        """Get Android Appium template."""
        return '''import pytest
from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy

class Test{{ test_name | title }}:
    """{{ test_description }} - Android"""

    @pytest.fixture
    def driver(self):
        """Setup Appium driver."""
        options = AppiumOptions()
        options.set_capability("platformName", "Android")
        options.set_capability("automationName", "{{ automation_name }}")
        {% if device_name %}
        options.set_capability("deviceName", "{{ device_name }}")
        {% endif %}
        {% if udid %}
        options.set_capability("udid", "{{ udid }}")
        {% endif %}
        {% if app_package %}
        options.set_capability("appPackage", "{{ app_package }}")
        {% endif %}
        {% if app_activity %}
        options.set_capability("appActivity", "{{ app_activity }}")
        {% endif %}
        options.set_capability("autoGrantPermissions", True)

        driver = webdriver.Remote("http://localhost:4723/wd/hub", options=options)
        yield driver
        driver.quit()

    def test_{{ test_name | lower }}(self, driver):
        """{{ test_description }}"""
        {% if app_package and app_activity %}
        # App is already launched from capabilities
        {% else %}
        # Launch app if needed
        {% endif %}

        {% for step in steps %}
        # {{ step.description }}
        {% if step.action == "tap" %}
        element = driver.find_element(AppiumBy.ID, "{{ step.id }}")
        element.click()
        {% elif step.action == "send_keys" %}
        element = driver.find_element(AppiumBy.ID, "{{ step.id }}")
        element.send_keys("{{ step.value }}")
        {% elif step.action == "swipe" %}
        driver.execute_script("mobile: swipe", {"direction": "{{ step.direction }}"})
        {% elif step.action == "wait" %}
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(AppiumBy.ID, "{{ step.id }}").is_displayed()
        )
        {% endif %}

        {% endfor %}

        # Assertions
        {% for assertion in assertions %}
        # {{ assertion }}
        {% if "element" in assertion %}
        element = driver.find_element(AppiumBy.ID, "{{ assertion.id }}")
        assert element.is_displayed()
        {% elif "text" in assertion %}
        element = driver.find_element(AppiumBy.XPATH, "//*[@text='{{ assertion.text }}']")
        assert element is not None
        {% endif %}
        {% endfor %}
'''

    def _get_ios_template(self) -> str:
        """Get iOS Appium template."""
        return '''import pytest
from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy

class Test{{ test_name | title }}:
    """{{ test_description }} - iOS"""

    @pytest.fixture
    def driver(self):
        """Setup Appium driver."""
        options = AppiumOptions()
        options.set_capability("platformName", "iOS")
        options.set_capability("automationName", "XCUITest")
        options.set_capability("deviceName", "{{ device_name or 'iPhone' }}")
        {% if udid %}
        options.set_capability("udid", "{{ udid }}")
        {% endif %}
        {% if app_package %}
        options.set_capability("bundleId", "{{ app_package }}")
        {% endif %}
        options.set_capability("autoAcceptAlerts", True)

        driver = webdriver.Remote("http://localhost:4723/wd/hub", options=options)
        yield driver
        driver.quit()

    def test_{{ test_name | lower }}(self, driver):
        """{{ test_description }}"""
        {% if app_package %}
        # Bundle ID is set in capabilities
        pass
        {% endif %}

        {% for step in steps %}
        # {{ step.description }}
        {% if step.action == "tap" %}
        element = driver.find_element(AppiumBy.ID, "{{ step.id }}")
        element.click()
        {% elif step.action == "send_keys" %}
        element = driver.find_element(AppiumBy.ID, "{{ step.id }}")
        element.send_keys("{{ step.value }}")
        {% elif step.action == "swipe" %}
        driver.execute_script("mobile: swipe", {"direction": "{{ step.direction }}"})
        {% elif step.action == "wait" %}
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(AppiumBy.ID, "{{ step.id }}").is_displayed()
        )
        {% endif %}

        {% endfor %}

        # Assertions
        {% for assertion in assertions %}
        # {{ assertion }}
        {% if "element" in assertion %}
        element = driver.find_element(AppiumBy.ID, "{{ assertion.id }}")
        assert element.is_displayed()
        {% endif %}
        {% endfor %}
'''


def get_appium_generator() -> AppiumTestGenerator:
    """Get or create Appium test generator instance."""
    return AppiumTestGenerator()
