"""Slug generation utility — handles Polish diacritics and special characters."""

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_VALIDATE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_DIACRITICS_MAP = str.maketrans(
    "ąćęłńóśźżàáâãäåèéêëìíîïòóôõöùúûüýÿñçðø",
    "acelnoszzaaaaaaeeeeiiiiooooouuuuyyncdo",
)


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug with diacritics support."""
    text = text.lower().translate(_DIACRITICS_MAP)
    text = _SLUG_RE.sub("-", text)
    return text.strip("-")


def is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_VALIDATE_RE.match(slug))
