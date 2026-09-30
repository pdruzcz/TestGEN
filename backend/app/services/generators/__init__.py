"""
Test generation services - Stories 1.29, 1.30, 1.32, 1.33, 1.34, 1.35, 1.40, 1.41, 1.42

Template-based and LLM-powered test generation with scenario generation, classification, and template engine.
"""

from app.services.generators.appium_generator import (
    AppiumTestGenerator,
    AppiumTestSpec,
    AppType,
    MobilePlatform,
    get_appium_generator,
)
from app.services.generators.llm_test_generator import (
    LLMGeneratedTest,
    LLMTestFramework,
    LLMTestGenerator,
    LLMTestScenario,
    LLMTestSuite,
    LLMTestType,
    get_llm_test_generator,
)
from app.services.generators.native_test_generator import (
    GeneratedTestCase,
    NativeTestGenerator,
    TestFramework,
    TestSuite,
    TestType,
    get_native_test_generator,
)
from app.services.generators.negative_scenarios import (
    NegativeScenario,
    NegativeScenarioGenerator,
    NegativeScenarioSuite,
    NegativeScenarioType,
    get_negative_scenario_generator,
)
from app.services.generators.playwright_generator import (
    PlaywrightTestGenerator,
    PlaywrightTestSpec,
    get_playwright_generator,
)
from app.services.generators.positive_scenarios import (
    PositiveScenario,
    PositiveScenarioGenerator,
    PositiveScenarioSuite,
    ScenarioComplexity,
    get_positive_scenario_generator,
)
from app.services.generators.regression_generator import (
    ChangeType,
    CodeChange,
    DiffParser,
    GeneratedRegressionTest,
    RegressionTestGenerator,
    RegressionTestSpec,
    RiskLevel,
    get_regression_generator,
)
from app.services.generators.selenium_generator import (
    SeleniumTestGenerator,
    SeleniumTestSpec,
    get_selenium_generator,
)
from app.services.generators.self_healing import (
    NativeMatcher,
    SelfHealingService,
)
from app.services.generators.template_engine import (
    RenderedTemplate,
    TemplateCategory,
    TemplateContext,
    TemplateEngine,
    TemplateLoader,
    get_template_engine,
)
from app.services.generators.test_classifier import (
    TestCategory,
    TestClassification,
    TestClassifier,
    TestComplexity,
    TestLayer,
    get_test_classifier,
)

__all__ = [  # noqa: RUF022 - intentionally grouped by story with comments
    # Native test generator (1.29)
    "NativeTestGenerator",
    "TestFramework",
    "TestType",
    "GeneratedTestCase",
    "TestSuite",
    "get_native_test_generator",
    # LLM test generator (1.30)
    "LLMTestGenerator",
    "LLMTestFramework",
    "LLMTestType",
    "LLMTestScenario",
    "LLMGeneratedTest",
    "LLMTestSuite",
    "get_llm_test_generator",
    # Positive scenarios (1.32)
    "PositiveScenarioGenerator",
    "PositiveScenario",
    "PositiveScenarioSuite",
    "ScenarioComplexity",
    "get_positive_scenario_generator",
    # Negative scenarios (1.33)
    "NegativeScenarioGenerator",
    "NegativeScenario",
    "NegativeScenarioSuite",
    "NegativeScenarioType",
    "get_negative_scenario_generator",
    # Test classifier (1.34)
    "TestClassifier",
    "TestClassification",
    "TestLayer",
    "TestCategory",
    "TestComplexity",
    "get_test_classifier",
    # Template engine (1.35)
    "TemplateEngine",
    "TemplateContext",
    "RenderedTemplate",
    "TemplateCategory",
    "TemplateLoader",
    "get_template_engine",
    # Selenium generator (1.40)
    "SeleniumTestGenerator",
    "SeleniumTestSpec",
    "get_selenium_generator",
    # Playwright generator (1.41)
    "PlaywrightTestGenerator",
    "PlaywrightTestSpec",
    "get_playwright_generator",
    # Appium generator (1.42)
    "AppiumTestGenerator",
    "AppiumTestSpec",
    "MobilePlatform",
    "AppType",
    "get_appium_generator",
    # Regression generator (1.44)
    "RegressionTestGenerator",
    "RegressionTestSpec",
    "ChangeType",
    "RiskLevel",
    "CodeChange",
    "GeneratedRegressionTest",
    "DiffParser",
    "get_regression_generator",
    # Self-healing (1.51)
    "NativeMatcher",
    "SelfHealingService",
]
