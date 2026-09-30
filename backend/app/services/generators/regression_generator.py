"""Regression test generator from code diff - Story 1.44

Generates regression tests based on code changes:
- Diff parsing (unified, git diff)
- Change detection (added, modified, deleted functions)
- Impact analysis (what might break)
- Regression test generation
- Test prioritization by risk
- Change coverage tracking
"""

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.services.generators.template_engine import (
    TemplateContext,
    TemplateEngine,
    TestFramework,
    get_template_engine,
)

logger = logging.getLogger(__name__)


class ChangeType(StrEnum):
    """Type of code change."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    REFACTORED = "refactored"


class RiskLevel(StrEnum):
    """Risk level of change."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CodeChange:
    """Represents a single code change."""
    file_path: str
    change_type: ChangeType
    function_name: str | None = None
    class_name: str | None = None
    old_lines: list[str] = field(default_factory=list)
    new_lines: list[str] = field(default_factory=list)
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class RegressionTestSpec:
    """Specification for regression test generation."""
    changes: list[CodeChange]
    language: str
    framework: TestFramework = TestFramework.PYTEST
    include_edge_cases: bool = True
    include_integration_tests: bool = True


@dataclass
class GeneratedRegressionTest:
    """Generated regression test."""
    test_name: str
    test_code: str
    risk_level: RiskLevel
    description: str
    covered_changes: list[str]  # References to CodeChanges


class DiffParser:
    """Parse diff output into structured changes."""

    def parse_unified_diff(self, diff_text: str) -> list[CodeChange]:
        """Parse unified diff format."""
        changes = []
        current_file = None
        current_hunk = None

        for line in diff_text.split("\n"):
            # File header
            if line.startswith("+++"):
                current_file = line[4:].strip()
                continue
            if line.startswith("---"):
                continue

            # Hunk header
            hunk_match = re.match(r"^@@\s+-(\d+),?(\d+)?\s+\+(\d+),?(\d+)?\s+@@", line)
            if hunk_match:
                if current_hunk and current_hunk["old_lines"]:
                    changes.append(self._hunk_to_change(current_file, current_hunk))
                current_hunk = {
                    "old_start": int(hunk_match.group(1)),
                    "new_start": int(hunk_match.group(3)),
                    "old_lines": [],
                    "new_lines": [],
                }
                continue

            # Content lines
            if current_hunk:
                if line.startswith("-") and not line.startswith("---"):
                    current_hunk["old_lines"].append(line[1:])
                elif line.startswith("+") and not line.startswith("+++"):
                    current_hunk["new_lines"].append(line[1:])

        # Last hunk
        if current_hunk and current_hunk["old_lines"]:
            changes.append(self._hunk_to_change(current_file, current_hunk))

        return changes

    def _hunk_to_change(self, file_path: str | None, hunk: dict) -> CodeChange:
        """Convert hunk to CodeChange."""
        old_lines = hunk["old_lines"]
        new_lines = hunk["new_lines"]

        # Detect change type
        if old_lines and not new_lines:
            change_type = ChangeType.DELETED
        elif new_lines and not old_lines:
            change_type = ChangeType.ADDED
        else:
            change_type = ChangeType.MODIFIED

        # Try to extract function name
        function_name = self._extract_function_name(old_lines + new_lines)

        return CodeChange(
            file_path=file_path or "unknown",
            change_type=change_type,
            function_name=function_name,
            old_lines=old_lines,
            new_lines=new_lines,
            line_start=hunk["old_start"],
        )

    def _extract_function_name(self, lines: list[str]) -> str | None:
        """Extract function name from lines."""
        # Simple heuristic: look for function definitions
        for line in lines:
            # Python: def name(
            if m := re.match(r"def\s+(\w+)\s*\(", line):
                return m.group(1)
            # JavaScript/TypeScript: function name(
            if m := re.match(r"function\s+(\w+)\s*\(", line):
                return m.group(1)
            # Java/C#: public/private/protected type name(
            if m := re.match(r"(?:public|private|protected)?\s*(?:static\s+)?\w+\s+(\w+)\s*\(", line):
                return m.group(1)
        return None


class RegressionTestGenerator:
    """Generate regression tests from code changes."""

    def __init__(self):
        self.engine = get_template_engine()
        self.diff_parser = DiffParser()

    def generate_from_diff(self, diff_text: str, language: str = "python") -> list[GeneratedRegressionTest]:
        """Generate regression tests from diff."""
        changes = self.diff_parser.parse_unified_diff(diff_text)

        if not changes:
            logger.warning("No changes detected in diff")
            return []

        # Group changes by risk and generate tests
        tests = []
        for change in changes:
            risk = self._assess_risk(change)
            test = self._generate_regression_test(change, language, risk)
            if test:
                tests.append(test)

        return tests

    def _assess_risk(self, change: CodeChange) -> RiskLevel:
        """Assess risk level of a change."""
        # Deleted functions are high risk
        if change.change_type == ChangeType.DELETED:
            return RiskLevel.HIGH

        # Changes in core logic functions
        if change.function_name and any(
            keyword in change.function_name.lower()
            for keyword in ["process", "calculate", "validate", "execute", "handle"]
        ):
            return RiskLevel.HIGH

        # Auth/security related
        if any(
            keyword in " ".join(change.new_lines).lower()
            for keyword in ["auth", "password", "token", "permission", "security"]
        ):
            return RiskLevel.CRITICAL

        # Database operations
        if any(
            keyword in " ".join(change.new_lines).lower()
            for keyword in ["delete", "update", "insert", "drop", "alter"]
        ):
            return RiskLevel.HIGH

        return RiskLevel.MEDIUM

    def _generate_regression_test(
        self, change: CodeChange, language: str, risk: RiskLevel
    ) -> GeneratedRegressionTest | None:
        """Generate a regression test for a single change."""

        if language.lower() == "python":
            return self._generate_python_regression_test(change, risk)
        elif language.lower() in ["javascript", "typescript"]:
            return self._generate_js_regression_test(change, risk)
        else:
            logger.warning(f"Unsupported language for regression test: {language}")
            return None

    def _generate_python_regression_test(
        self, change: CodeChange, risk: RiskLevel
    ) -> GeneratedRegressionTest:
        """Generate Python regression test."""

        function_name = change.function_name or "changed_function"
        test_name = f"test_regression_{function_name}_{change.change_type.value}"

        context = TemplateContext(
            test_name=test_name,
            test_description=f"Regression test for {change.change_type.value} {function_name}",
            framework=TestFramework.PYTEST,
            extra_vars={
                "change": change,
                "risk_level": risk.value,
                "function_name": function_name,
            },
        )

        template = self._get_python_regression_template()
        result = self.engine.render_string(template, context)

        return GeneratedRegressionTest(
            test_name=test_name,
            test_code=result.content,
            risk_level=risk,
            description=f"Regression test for {change.function_name or 'change'} in {change.file_path}",
            covered_changes=[change.file_path],
        )

    def _get_python_regression_template(self) -> str:
        """Get Python regression test template."""
        return '''import pytest
from unittest.mock import Mock, patch

def test_{{ test_name }}():
    """
    {{ test_description }}
    Risk level: {{ risk_level }}
    """
    {% if change.change_type == "deleted" %}
    # Test that the deleted function is no longer accessible
    with pytest.raises(AttributeError):
        from {{ change.file_path.replace('/', '.').replace('.py', '') }} import {{ function_name }}
    {% elif change.change_type == "modified" %}
    # Test modified function behavior
    {% if risk_level == "critical" %}
    # Critical change - comprehensive testing needed
    {% endif %}
    result = {{ function_name }}()
    assert result is not None
    {% else %}
    # Test new function
    result = {{ function_name }}()
    assert result is not None
    {% endif %}

{% if risk_level == "critical" %}
@pytest.mark.integration
def test_{{ test_name }}_integration():
    """Integration test for critical change."""
    # Test the change in an integration context
    pass
{% endif %}
'''

    def _generate_js_regression_test(
        self, change: CodeChange, risk: RiskLevel
    ) -> GeneratedRegressionTest:
        """Generate JavaScript/TypeScript regression test."""

        function_name = change.function_name or "changedFunction"
        test_name = f"regression{function_name.title()}{change.change_type.value.title()}"

        context = TemplateContext(
            test_name=test_name,
            test_description=f"Regression test for {change.change_type.value} {function_name}",
            framework=TestFramework.JEST,
            extra_vars={
                "change": change,
                "risk_level": risk.value,
                "function_name": function_name,
            },
        )

        template = self._get_js_regression_template()
        result = self.engine.render_string(template, context)

        return GeneratedRegressionTest(
            test_name=test_name,
            test_code=result.content,
            risk_level=risk,
            description=f"Regression test for {change.function_name or 'change'} in {change.file_path}",
            covered_changes=[change.file_path],
        )

    def _get_js_regression_template(self) -> str:
        """Get JavaScript regression test template."""
        return '''describe('{{ test_name | title }}', () => {
  /*
   * {{ test_description }}
   * Risk level: {{ risk_level }}
   */
  {% if change.change_type == "deleted" %}
  it('should not have the deleted function', () => {
    expect(() => {
      const module = require('./{{ change.file_path }}');
      module.{{ function_name }}();
    }).toThrow();
  });
  {% elif change.change_type == "modified" %}
  it('should handle modified function correctly', () => {
    {% if risk_level == "critical" %}
    // Critical change - comprehensive testing needed
    {% endif %}
    const result = {{ function_name }}();
    expect(result).toBeDefined();
  });
  {% else %}
  it('should handle new function correctly', () => {
    const result = {{ function_name }}();
    expect(result).toBeDefined();
  });
  {% endif %}

{% if risk_level == "critical" %}
  it('should work in integration context', () => {
    // Integration test for critical change
  });
{% endif %}
});
'''


def get_regression_generator() -> RegressionTestGenerator:
    """Get or create regression test generator instance."""
    return RegressionTestGenerator()
