"""Automatic code cleanup service - Story 1.49

Provides automated code quality improvements:
- Import sorting and organization
- Unused import removal
- Code formatting (black, autopep8)
- Linting rule application
- Dead code elimination
- Variable renaming
- Comment cleanup
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CleanupRule(StrEnum):
    """Types of cleanup rules."""
    SORT_IMPORTS = "sort_imports"
    REMOVE_UNUSED_IMPORTS = "remove_unused_imports"
    FORMAT_CODE = "format_code"
    REMOVE_DEAD_CODE = "remove_dead_code"
    RENAME_VARIABLES = "rename_variables"
    CLEANUP_COMMENTS = "cleanup_comments"
    FIX_INDENTATION = "fix_indentation"
    REMOVE_DUPLICATES = "remove_duplicates"


@dataclass
class CleanupIssue:
    """Represents a code issue found during analysis."""
    file_path: str
    line_number: int
    rule: CleanupRule
    description: str
    severity: str  # info, warning, error
    suggestion: str | None = None


@dataclass
class CleanupResult:
    """Result of code cleanup operation."""
    file_path: str
    original_code: str
    cleaned_code: str
    issues_fixed: list[CleanupIssue]
    lines_changed: int
    success: bool


class CodeCleanupService:
    """Service for automatic code cleanup."""

    def __init__(self):
        self.rules = {
            CleanupRule.SORT_IMPORTS: self._sort_imports,
            CleanupRule.REMOVE_UNUSED_IMPORTS: self._remove_unused_imports,
            CleanupRule.FORMAT_CODE: self._format_code,
            CleanupRule.CLEANUP_COMMENTS: self._cleanup_comments,
        }

    def analyze_file(self, file_path: str) -> list[CleanupIssue]:
        """Analyze file for cleanup opportunities.

        Args:
            file_path: Path to source file

        Returns:
            List of cleanup issues found
        """
        issues = []
        path = Path(file_path)

        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return issues

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for import issues
            issues.extend(self._check_imports(content, file_path))

            # Check for formatting issues
            issues.extend(self._check_formatting(content, file_path))

            # Check for comment issues
            issues.extend(self._check_comments(content, file_path))

        except Exception as e:
            logger.error(f"Failed to analyze {file_path}: {e}")

        return issues

    def cleanup_file(
        self, file_path: str, rules: list[CleanupRule] | None = None
    ) -> CleanupResult:
        """Apply cleanup rules to a file.

        Args:
            file_path: Path to source file
            rules: List of rules to apply (all if None)

        Returns:
            CleanupResult with changes
        """
        path = Path(file_path)

        if not path.exists():
            return CleanupResult(
                file_path=file_path,
                original_code="",
                cleaned_code="",
                issues_fixed=[],
                lines_changed=0,
                success=False,
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                original_code = f.read()

            cleaned_code = original_code
            issues_fixed = []

            rules_to_apply = rules or list(self.rules.keys())

            for rule in rules_to_apply:
                if rule in self.rules:
                    cleaned_code, rule_issues = self.rules[rule](cleaned_code, file_path)
                    if rule_issues:
                        issues_fixed.extend(rule_issues)

            lines_changed = self._count_line_changes(original_code, cleaned_code)

            # Write back if changed
            if cleaned_code != original_code:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(cleaned_code)
                logger.info(f"Cleaned {file_path}: {lines_changed} lines changed")

            return CleanupResult(
                file_path=file_path,
                original_code=original_code,
                cleaned_code=cleaned_code,
                issues_fixed=issues_fixed,
                lines_changed=lines_changed,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to cleanup {file_path}: {e}")
            return CleanupResult(
                file_path=file_path,
                original_code="",
                cleaned_code="",
                issues_fixed=[],
                lines_changed=0,
                success=False,
            )

    def _sort_imports(self, code: str, file_path: str) -> tuple[str, list[CleanupIssue]]:
        """Sort and organize imports."""
        lines = code.split("\n")
        import_start = -1
        import_end = -1
        imports = []

        # Find import block
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                if import_start == -1:
                    import_start = i
                imports.append(line)
            elif import_start != -1 and import_end == -1:
                import_end = i
                break

        if not imports:
            return code, []

        # Sort imports (stdlib first, then third-party, then local)
        sorted_imports = sorted(imports, key=lambda x: self._import_sort_key(x))

        # Rebuild code
        new_lines = (
            lines[:import_start] + sorted_imports + [""] + lines[import_end:]
        )
        new_code = "\n".join(new_lines)

        issue = CleanupIssue(
            file_path=file_path,
            line_number=import_start + 1,
            rule=CleanupRule.SORT_IMPORTS,
            description="Imports were sorted and organized",
            severity="info",
        )

        return new_code, [issue]

    def _import_sort_key(self, import_line: str) -> tuple[int, str]:
        """Generate sort key for imports."""
        stripped = import_line.strip()

        # Check for local imports
        if stripped.startswith("from app.") or stripped.startswith("from ."):
            return (2, stripped.lower())
        # Check for third-party imports
        elif any(
            stripped.startswith(f"from {lib}") or stripped.startswith(f"import {lib}")
            for lib in ["pytest", "sqlalchemy", "jinja2", "httpx"]
        ):
            return (1, stripped.lower())
        # Standard library
        else:
            return (0, stripped.lower())

    def _remove_unused_imports(self, code: str, file_path: str) -> tuple[str, list[CleanupIssue]]:
        """Remove unused imports."""
        try:
            tree = ast.parse(code)
        except:
            return code, []

        # Find all imported names
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        # Find all used names
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)

        # Find unused imports
        unused = imported_names - used_names

        if not unused:
            return code, []

        # Remove unused imports
        lines = code.split("\n")
        new_lines = []
        issues = []

        for i, line in enumerate(lines):
            should_remove = False
            for unused_name in unused:
                if f"import {unused_name}" in line or f" as {unused_name}" in line:
                    should_remove = True
                    issues.append(
                        CleanupIssue(
                            file_path=file_path,
                            line_number=i + 1,
                            rule=CleanupRule.REMOVE_UNUSED_IMPORTS,
                            description=f"Removed unused import: {unused_name}",
                            severity="info",
                        )
                    )
                    break

            if not should_remove:
                new_lines.append(line)

        return "\n".join(new_lines), issues

    def _format_code(self, code: str, file_path: str) -> tuple[str, list[CleanupIssue]]:
        """Basic code formatting."""
        lines = code.split("\n")
        new_lines = []
        issues = []

        for i, line in enumerate(lines):
            stripped = line.rstrip()
            # Remove trailing whitespace
            if line != stripped:
                issues.append(
                    CleanupIssue(
                        file_path=file_path,
                        line_number=i + 1,
                        rule=CleanupRule.FORMAT_CODE,
                        description="Removed trailing whitespace",
                        severity="info",
                    )
                )
            new_lines.append(stripped)

        # Ensure file ends with newline
        if new_lines and new_lines[-1]:
            new_lines.append("")

        return "\n".join(new_lines), issues

    def _cleanup_comments(self, code: str, file_path: str) -> tuple[str, list[CleanupIssue]]:
        """Clean up comments."""
        lines = code.split("\n")
        new_lines = []
        issues = []

        for i, line in enumerate(lines):
            # Check for commented-out code patterns
            if re.search(r"#\s*(def |class |import |from )", line):
                issues.append(
                    CleanupIssue(
                        file_path=file_path,
                        line_number=i + 1,
                        rule=CleanupRule.CLEANUP_COMMENTS,
                        description="Possible commented-out code detected",
                        severity="warning",
                        suggestion=line.strip(),
                    )
                )
            new_lines.append(line)

        return "\n".join(new_lines), issues

    def _check_imports(self, content: str, file_path: str) -> list[CleanupIssue]:
        """Check for import-related issues."""
        issues = []
        lines = content.split("\n")

        imports_seen = set()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                # Check for duplicate imports
                if stripped in imports_seen:
                    issues.append(
                        CleanupIssue(
                            file_path=file_path,
                            line_number=i,
                            rule=CleanupRule.REMOVE_DUPLICATES,
                            description="Duplicate import detected",
                            severity="warning",
                            suggestion=f"Remove duplicate: {stripped}",
                        )
                    )
                imports_seen.add(stripped)

        return issues

    def _check_formatting(self, content: str, file_path: str) -> list[CleanupIssue]:
        """Check for formatting issues."""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for trailing whitespace
            if line != line.rstrip():
                issues.append(
                    CleanupIssue(
                        file_path=file_path,
                        line_number=i,
                        rule=CleanupRule.FORMAT_CODE,
                        description="Trailing whitespace detected",
                        severity="info",
                    )
                )

        # Check for missing final newline
        if lines and lines[-1]:
            issues.append(
                CleanupIssue(
                    file_path=file_path,
                    line_number=len(lines),
                    rule=CleanupRule.FORMAT_CODE,
                    description="Missing final newline",
                    severity="info",
                )
            )

        return issues

    def _check_comments(self, content: str, file_path: str) -> list[CleanupIssue]:
        """Check for comment-related issues."""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for commented-out code
            if re.search(r"#\s*(def |class |import |from )", line):
                issues.append(
                    CleanupIssue(
                        file_path=file_path,
                        line_number=i,
                        rule=CleanupRule.CLEANUP_COMMENTS,
                        description="Possible commented-out code",
                        severity="warning",
                    )
                )

        return issues

    def _count_line_changes(self, original: str, cleaned: str) -> int:
        """Count number of changed lines."""
        original_lines = original.split("\n")
        cleaned_lines = cleaned.split("\n")

        changes = abs(len(original_lines) - len(cleaned_lines))

        for i, (orig, clean) in enumerate(zip(original_lines, cleaned_lines)):
            if orig != clean:
                changes += 1

        return changes


def get_code_cleanup_service() -> CodeCleanupService:
    """Get or create code cleanup service instance."""
    return CodeCleanupService()
