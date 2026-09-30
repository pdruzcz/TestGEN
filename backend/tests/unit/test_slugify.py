"""Tests for slugify utility."""

from app.core.slugify import is_valid_slug, slugify


class TestSlugify:
    def test_basic_ascii(self):
        assert slugify("Hello World") == "hello-world"

    def test_polish_diacritics(self):
        assert slugify("Żółć Sp. z o.o.") == "zolc-sp-z-o-o"

    def test_special_characters(self):
        assert slugify("My Company & Partners @ 2026") == "my-company-partners-2026"

    def test_multiple_spaces(self):
        assert slugify("  multiple   spaces  ") == "multiple-spaces"

    def test_dots_and_commas(self):
        assert slugify("Acme, Inc.") == "acme-inc"


class TestIsValidSlug:
    def test_valid_slug(self):
        assert is_valid_slug("acme-corp")

    def test_valid_slug_single_word(self):
        assert is_valid_slug("acme")

    def test_valid_slug_with_numbers(self):
        assert is_valid_slug("company-123")

    def test_invalid_slug_uppercase(self):
        assert not is_valid_slug("Acme-Corp")

    def test_invalid_slug_spaces(self):
        assert not is_valid_slug("acme corp")

    def test_invalid_slug_special_chars(self):
        assert not is_valid_slug("acme&corp")

    def test_invalid_slug_leading_hyphen(self):
        assert not is_valid_slug("-acme")

    def test_invalid_slug_trailing_hyphen(self):
        assert not is_valid_slug("acme-")

    def test_invalid_slug_double_hyphen(self):
        assert not is_valid_slug("acme--corp")
