"""Unit tests for document text cleaning (Story 2.2 — AC#2/#3).

Covers Polish character normalization, de-hyphenation, and artifact removal
performed by ``DocumentPreprocessor``. There was no dedicated cleaner test
file before this story.
"""

import pytest

from app.services.analysis.document.preprocessing import DocumentPreprocessor


@pytest.fixture()
def cleaner() -> DocumentPreprocessor:
    return DocumentPreprocessor()


class TestPolishNormalization:
    def test_fixes_known_substitutes(self, cleaner):
        from app.services.analysis.document.preprocessing import POLISH_CHARS_MAP

        for bad, good in POLISH_CHARS_MAP.items():
            assert cleaner._normalize_polish_chars(bad) == good

    def test_preserves_already_correct_polish(self, cleaner):
        text = "Zażółć gęślą jaźń"
        assert cleaner._normalize_polish_chars(text) == text

    def test_counts_fixes(self, cleaner):
        from app.services.analysis.document.preprocessing import POLISH_CHARS_MAP

        sample = list(POLISH_CHARS_MAP.items())[:3]
        cleaner._normalize_polish_chars("".join(bad for bad, _ in sample))
        assert cleaner.stats.polish_char_issues_fixed == 3


class TestDeHyphenation:
    def test_joins_word_split_across_line(self, cleaner):
        assert cleaner._fix_hyphenation("wymaga-\nnia") == "wymagania"

    def test_joins_with_surrounding_whitespace(self, cleaner):
        assert cleaner._fix_hyphenation("wymaga-  \n  nia") == "wymagania"

    def test_preserves_inline_hyphen(self, cleaner):
        assert cleaner._fix_hyphenation("czerwono-niebieski") == "czerwono-niebieski"

    def test_no_match_without_newline(self, cleaner):
        assert cleaner._fix_hyphenation("wymaga-nia") == "wymaga-nia"


class TestArtifactRemoval:
    def test_strips_standalone_page_number(self, cleaner):
        assert cleaner._remove_artifacts_from_line("12") == ""
        assert cleaner.stats.artifact_count == 1

    def test_strips_strona_page_marker(self, cleaner):
        assert cleaner._remove_artifacts_from_line("Strona 42") == ""

    def test_strips_copyright_footer(self, cleaner):
        assert cleaner._remove_artifacts_from_line("© 2024 Acme Sp. z o.o.") == ""

    def test_strips_separator_line(self, cleaner):
        assert cleaner._remove_artifacts_from_line("--------------------") == ""

    def test_preserves_real_content(self, cleaner):
        assert cleaner._remove_artifacts_from_line("System musi wysyłać e-mail") == ("System musi wysyłać e-mail")


class TestCleanSectionContent:
    def test_removes_artifact_lines_and_normalizes(self, cleaner):
        from app.services.analysis.document.preprocessing import POLISH_CHARS_MAP

        bad = next(iter(POLISH_CHARS_MAP))  # a known mojibake stand-in
        good = POLISH_CHARS_MAP[bad]
        content = f"Tekst{bad}\n12\nWłaściwa treść dokumentu"
        cleaned = cleaner._clean_section_content(content)
        assert "12" not in cleaned
        assert f"Tekst{good}" in cleaned
        assert "Właściwa treść dokumentu" in cleaned

    def test_empty_content_returns_empty(self, cleaner):
        assert cleaner._clean_section_content("") == ""

    def test_collapses_excessive_blank_lines(self, cleaner):
        cleaned = cleaner._clean_section_content("A\n\n\n\n\nB")
        assert "\n\n\n" not in cleaned
