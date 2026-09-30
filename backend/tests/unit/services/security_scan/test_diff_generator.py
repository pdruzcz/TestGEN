"""Unit tests for the unified diff generator — Story 4.9."""

from app.services.security_scan.diff_generator import generate_unified_diff


class TestGenerateUnifiedDiff:
    def test_identical_returns_empty(self):
        assert generate_unified_diff("same", "same") == ""

    def test_produces_unified_diff_markers(self):
        diff = generate_unified_diff(
            'query("SELECT * FROM u WHERE id = " + id)',
            'query("SELECT * FROM u WHERE id = ?", [id])',
            file_path="app/db.py",
        )
        assert diff.startswith("--- a/app/db.py")
        assert "+++ b/app/db.py" in diff
        assert "@@" in diff
        assert any(line.startswith("-") and "WHERE" in line for line in diff.splitlines())
        assert any(line.startswith("+") and "WHERE" in line for line in diff.splitlines())

    def test_default_label_when_no_path(self):
        diff = generate_unified_diff("a", "b")
        assert "a/code" in diff
        assert "b/code" in diff

    def test_line_start_shifts_hunk_header(self):
        diff = generate_unified_diff("a", "b", line_start=42)
        hunk = next(line for line in diff.splitlines() if line.startswith("@@"))
        # Original was @@ -1 +1 @@; with line_start=42 the offset is +41.
        assert "-42" in hunk
        assert "+42" in hunk

    def test_no_trailing_newline_inputs_diff_cleanly(self):
        diff = generate_unified_diff("foo", "bar", file_path="x.py")
        assert "-foo" in diff
        assert "+bar" in diff
