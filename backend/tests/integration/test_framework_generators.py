"""Tests for framework-specific test generators - Stories 1.36-1.39

Tests for pytest, junit, nunit, mocha/jest generators.
"""

import pytest
from app.models.test_case import TestFramework, TestType
from app.services.generators.native_test_generator import NativeTestGenerator


class TestPytestGenerator:
    """Test pytest-specific generator (Story 1.36)."""

    def test_pytest_template_loaded(self):
        """Verify pytest template is available."""
        generator = NativeTestGenerator()
        assert TestFramework.PYTEST in generator.templates


class TestJUnitGenerator:
    """Test junit-specific generator (Story 1.37)."""

    def test_junit_template_loaded(self):
        """Verify junit template is available."""
        generator = NativeTestGenerator()
        assert TestFramework.JUNIT in generator.templates


class TestNUnitGenerator:
    """Test nunit-specific generator (Story 1.38)."""

    def test_nunit_in_framework_enum(self):
        """Verify nunit is supported."""
        assert TestFramework.NUNIT == "nunit"


class TestMochaJestGenerator:
    """Test mocha/jest generator (Story 1.39)."""

    def test_mocha_template_loaded(self):
        """Verify mocha template is available."""
        generator = NativeTestGenerator()
        assert TestFramework.MOCHA in generator.templates

    def test_jest_in_framework_enum(self):
        """Verify jest is supported."""
        assert TestFramework.JEST == "jest"
