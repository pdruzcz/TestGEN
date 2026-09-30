"""Codegen package — framework-specific test code generators."""

import app.services.test_generation.codegen.appium_generator
import app.services.test_generation.codegen.cypress_generator
import app.services.test_generation.codegen.database_generator
import app.services.test_generation.codegen.junit_generator

# Rejestracja generatorow (import wczytuje klasy z @register_generator)
import app.services.test_generation.codegen.mocha_jest_generator
import app.services.test_generation.codegen.nunit_generator
import app.services.test_generation.codegen.phpunit_generator  # phpunit + pest (Story 1.55)
import app.services.test_generation.codegen.playwright_generator
import app.services.test_generation.codegen.pytest_generator
import app.services.test_generation.codegen.selenium_generator
import app.services.test_generation.codegen.sikulix_generator
import app.services.test_generation.codegen.xunit_generators  # noqa: F401 — import rejestruje unittest/testng/mstest (Story 1.57)
from app.services.test_generation.codegen.base import (
    BaseTestCodeGenerator,
    CodeGenConfig,
    CodeGenFramework,
    CodeGenRegistry,
    CompilationResult,
    TestCodeFile,
    register_generator,
)

__all__ = [
    "BaseTestCodeGenerator",
    "CodeGenConfig",
    "CodeGenFramework",
    "CodeGenRegistry",
    "CompilationResult",
    "TestCodeFile",
    "register_generator",
]
