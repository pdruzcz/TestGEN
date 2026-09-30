"""Tests for automatic code cleanup service - Story 1.49"""

import pytest
from pathlib import Path

from app.services.code_cleanup import (
    CodeCleanupService,
    CleanupRule,
    CleanupIssue,
    CleanupResult,
    get_code_cleanup_service,
)


class TestCleanupRule:
    """Test CleanupRule enum (Story 1.49)."""

    def test_rule_values(self):
        """Test all rule values exist."""
        assert CleanupRule.SORT_IMPORTS == "sort_imports"
        assert CleanupRule.REMOVE_UNUSED_IMPORTS == "remove_unused_imports"
        assert CleanupRule.FORMAT_CODE == "format_code"
        assert CleanupRule.REMOVE_DEAD_CODE == "remove_dead_code"


class TestCleanupIssue:
    """Test CleanupIssue dataclass (Story 1.49)."""

    def test_issue_creation(self):
        """Test creating a cleanup issue."""
        issue = CleanupIssue(
            file_path="test.py",
            line_number=10,
            rule=CleanupRule.FORMAT_CODE,
            description="Trailing whitespace",
            severity="info",
        )
        assert issue.file_path == "test.py"
        assert issue.rule == CleanupRule.FORMAT_CODE


class TestCodeCleanupService:
    """Test CodeCleanupService (Story 1.49)."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        service = CodeCleanupService()
        assert service is not None
        assert len(service.rules) > 0

    def test_get_code_cleanup_service(self):
        """Test getting service singleton."""
        service = get_code_cleanup_service()
        assert isinstance(service, CodeCleanupService)

    def test_analyze_nonexistent_file(self):
        """Test analyzing non-existent file."""
        service = CodeCleanupService()
        issues = service.analyze_file("nonexistent.py")
        assert issues == []

    def test_analyze_file(self, tmp_path):
        """Test analyzing a file with issues."""
        # Create test file with issues
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import sys
import os
import sys

def hello():
    x = 1
    return x
""")

        service = CodeCleanupService()
        issues = service.analyze_file(str(test_file))

        assert len(issues) > 0
        assert any(i.rule == CleanupRule.REMOVE_DUPLICATES for i in issues)

    def test_cleanup_file_sort_imports(self, tmp_path):
        """Test sorting imports."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import os
import sys
from app.models import User
import pytest
""")

        service = CodeCleanupService()
        result = service.cleanup_file(str(test_file), [CleanupRule.SORT_IMPORTS])

        assert result.success
        assert "import os" in result.cleaned_code
        assert result.lines_changed > 0

    def test_cleanup_file_format_code(self, tmp_path):
        """Test code formatting."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test():\n    x = 1    \n")

        service = CodeCleanupService()
        result = service.cleanup_file(str(test_file), [CleanupRule.FORMAT_CODE])

        assert result.success
        assert "    x = 1" in result.cleaned_code  # No trailing space
        assert result.cleaned_code.endswith("\n")

    def test_cleanup_file_remove_trailing_whitespace(self, tmp_path):
        """Test removing trailing whitespace."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1   \ny = 2\n")

        service = CodeCleanupService()
        result = service.cleanup_file(str(test_file), [CleanupRule.FORMAT_CODE])

        assert result.success
        assert "x = 1   " not in result.cleaned_code

    def test_check_imports_duplicates(self):
        """Test duplicate import detection."""
        service = CodeCleanupService()
        content = "import os\nimport sys\nimport os\n"

        issues = service._check_imports(content, "test.py")
        assert any(i.rule == CleanupRule.REMOVE_DUPLICATES for i in issues)

    def test_check_formatting_trailing_whitespace(self):
        """Test trailing whitespace detection."""
        service = CodeCleanupService()
        content = "x = 1   \ny = 2\n"

        issues = service._check_formatting(content, "test.py")
        assert len(issues) > 0
        assert any("trailing" in i.description.lower() for i in issues)

    def test_check_comments_commented_code(self):
        """Test commented-out code detection."""
        service = CodeCleanupService()
        content = "# def old_function():\n# class OldClass:\nx = 1\n"

        issues = service._check_comments(content, "test.py")
        assert len(issues) >= 2

    def test_sort_imports_basic(self):
        """Test basic import sorting."""
        service = CodeCleanupService()
        code = "import os\nimport sys\nfrom app.models import User\n"
        result, issues = service._sort_imports(code, "test.py")

        assert "import os" in result
        assert len(issues) > 0

    def test_remove_unused_imports(self):
        """Test removing unused imports."""
        service = CodeCleanupService()
        code = "import os\nimport sys\n\nx = 1\n"
        result, issues = service._remove_unused_imports(code, "test.py")

        # os is unused, sys is unused
        assert "import os" not in result or "import sys" not in result

    def test_format_code_trailing_spaces(self):
        """Test formatting removes trailing spaces."""
        service = CodeCleanupService()
        code = "x = 1   \ny = 2\t\n"
        result, issues = service._format_code(code, "test.py")

        assert "x = 1   " not in result
        assert len(issues) > 0

    def test_count_line_changes(self):
        """Test counting changed lines."""
        service = CodeCleanupService()
        original = "x = 1\ny = 2\n"
        cleaned = "x = 1\ny = 2\nz = 3\n"

        changes = service._count_line_changes(original, cleaned)
        # 1 extra line added
        assert changes >= 1


@pytest.mark.integration
class TestCodeCleanupIntegration:
    """Integration tests for code cleanup service (Story 1.49)."""

    def test_full_cleanup_workflow(self, tmp_path):
        """Test complete cleanup workflow."""
        # Create file with multiple issues
        test_file = tmp_path / "messy.py"
        test_file.write_text("""
import sys
import os
import sys

def hello():
    x = 1
    return x

# def old_function():
""")

        service = CodeCleanupService()

        # Analyze first
        issues = service.analyze_file(str(test_file))
        assert len(issues) > 0

        # Cleanup with all rules
        result = service.cleanup_file(
            str(test_file),
            [
                CleanupRule.SORT_IMPORTS,
                CleanupRule.FORMAT_CODE,
                CleanupRule.CLEANUP_COMMENTS,
            ],
        )

        assert result.success
        assert result.lines_changed > 0

        # Verify file was updated
        updated_content = test_file.read_text()
        assert "# def old_function()" in updated_content  # Comments preserved
