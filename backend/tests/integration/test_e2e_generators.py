"""Tests for E2E test generators - Stories 1.40-1.42"""

from app.services.generators.appium_generator import (
    AppiumTestGenerator,
    AppiumTestSpec,
    AppType,
    MobilePlatform,
    get_appium_generator,
)
from app.services.generators.playwright_generator import (
    PlaywrightTestGenerator,
    PlaywrightTestSpec,
    get_playwright_generator,
)
from app.services.generators.selenium_generator import (
    SeleniumTestGenerator,
    SeleniumTestSpec,
    get_selenium_generator,
)


class TestSeleniumGenerator:
    """Test Selenium generator (Story 1.40)."""

    def test_generator_initialization(self):
        generator = SeleniumTestGenerator()
        assert generator is not None

    def test_generate_basic_test(self):
        generator = SeleniumTestGenerator()
        spec = SeleniumTestSpec(
            test_name="test_user_login",
            description="Test user login flow",
            browser="chrome",
            url="https://example.com/login",
            steps=[
                {
                    "action": "type",
                    "locator": "id",
                    "selector": "username",
                    "value": "user",
                    "description": "Type username",
                },
                {
                    "action": "type",
                    "locator": "id",
                    "selector": "password",
                    "value": "pass",
                    "description": "Type password",
                },
                {"action": "click", "locator": "id", "selector": "submit", "description": "Click submit"},
            ],
            assertions=["Login successful"],
        )

        result = generator.generate_test(spec)
        assert "test_user_login" in result
        assert "selenium" in result.lower()
        assert "webdriver" in result.lower()


class TestPlaywrightGenerator:
    """Test Playwright generator (Story 1.41)."""

    def test_generator_initialization(self):
        generator = PlaywrightTestGenerator()
        assert generator is not None

    def test_generate_basic_test(self):
        generator = PlaywrightTestGenerator()
        spec = PlaywrightTestSpec(
            test_name="test_user_registration",
            description="Test user registration",
            browser="chromium",
            url="https://example.com/register",
            steps=[
                {"action": "fill", "selector": "#email", "value": "user@example.com", "description": "Fill email"},
                {"action": "fill", "selector": "#password", "value": "SecurePass123", "description": "Fill password"},
                {"action": "click", "selector": "#submit", "description": "Click submit"},
            ],
            assertions=["page loaded successfully"],
        )

        result = generator.generate_test(spec)
        assert "test_user_registration" in result
        assert "playwright" in result.lower()


class TestAppiumGenerator:
    """Test Appium generator (Story 1.42)."""

    def test_generator_initialization(self):
        generator = AppiumTestGenerator()
        assert generator is not None

    def test_generate_android_test(self):
        generator = AppiumTestGenerator()
        spec = AppiumTestSpec(
            test_name="test_mobile_login",
            description="Test mobile login",
            platform=MobilePlatform.ANDROID,
            app_type=AppType.NATIVE,
            app_package="com.example.app",
            app_activity=".MainActivity",
            steps=[
                {"action": "wait", "id": "login_button", "description": "Wait for login button"},
                {"action": "tap", "id": "login_button", "description": "Tap login button"},
            ],
            assertions=["Login successful"],
        )

        result = generator.generate_test(spec)
        assert "test_mobile_login" in result
        assert "android" in result.lower()
        assert "appium" in result.lower()

    def test_generate_ios_test(self):
        generator = AppiumTestGenerator()
        spec = AppiumTestSpec(
            test_name="test_ios_login",
            description="Test iOS login",
            platform=MobilePlatform.IOS,
            app_type=AppType.NATIVE,
            app_package="com.example.app",
            device_name="iPhone 14",
            steps=[{"action": "tap", "id": "login", "description": "Tap login"}],
        )

        result = generator.generate_test(spec)
        assert "test_ios_login" in result
        assert "ios" in result.lower()
        assert "appium" in result.lower()


def test_get_e2e_generators():
    """Test getting E2E generator instances."""
    selenium_gen = get_selenium_generator()
    playwright_gen = get_playwright_generator()
    appium_gen = get_appium_generator()

    assert isinstance(selenium_gen, SeleniumTestGenerator)
    assert isinstance(playwright_gen, PlaywrightTestGenerator)
    assert isinstance(appium_gen, AppiumTestGenerator)
