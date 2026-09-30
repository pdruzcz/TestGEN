"""Language patterns for requirement extraction — Epic 2.

This module defines regex patterns and linguistic rules for identifying
requirement sentences in Polish technical documentation.
"""

from __future__ import annotations

import re


# Requirement sentence patterns - these indicate a sentence is likely a requirement
REQUIREMENT_PATTERNS = [
    # Modal verbs indicating requirements
    r"system\s+(powinien|musi|ma|wymagane jest)",
    r"aplikacja\s+(powinien|musi|ma)",
    r"użytkownik\s+(może|powinien|musi|ma|ma możliwość)",
    r"(powinien|musi|wymagane jest|niezbędne jest)\s+(być|zawierać|obsługiwać|umożliwiać)",
    # Requirement keywords
    r"wymaganiem\s+jest",
    r"wymaga\s+(wymogania|warunków)",
    r"zgodnie\s+z\s+wymaganiami?",
    r"spełniać\s+wymaganie",
    r"implementacja\s+(wymagania|funkcjonalności)",
]

# Requirement ID patterns - these indicate explicit requirement identifiers
REQUIREMENT_ID_PATTERNS = [
    r"FR-\d+",  # Functional Requirement
    r"REQ-\d+",  # Requirement
    r"NF-\d+",  # Non-Functional
    r"NFR-\d+",  # Non-Functional Requirement
    r"WYM-\d+",  # Wymaganie
    r"UC-\d+",  # Use Case
    r"R-\d+",  # Requirement
    r"ID-\d+",  # ID
    r"\d+\.\d+\.\d+",  # IEEE 830 style: 1.2.3
]

# Non-functional requirement keywords
NON_FUNCTIONAL_KEYWORDS = [
    "wydajność",
    "wydajności",
    "bezpieczeństwo",
    "bezpieczeństwa",
    "szybkość",
    "opóźnienie",
    "dostępność",
    "dostępności",
    "skalowalność",
    "niezawodność",
    "niezawodności",
    "utrzymanie",
    "utrzymania",
    " czas\s+odpowiedzi",
    "przepustowość",
    "pamięć",
    "zużycie\s+pamięci",
    "procesor",
    "obciążenie",
    "czas\s+reakcji",
    "latency",
    "throughput",
    "ssl",
    "tls",
    "szyfrowani",
    "autentykacj",
    "uprawnien",
]

# Priority indicators
PRIORITY_PATTERNS = {
    "critical": [
        r"krytyczny",
        r"krytyczna",
        r"krytyczne",
        r"musi",
        r"niezbędny",
        r"niezbędna",
        r"niezbędne",
        r"wymagany",
        r"wymagana",
        r"wymagane",
        r"obowiązkowy",
        r"obowiązkowa",
        r"obowiązkowe",
        r"bez\s+wych",
        r"zawsze",
    ],
    "high": [
        r"wysoki\s+priorytet",
        r"wysoka",
        r"wysoki",
        r"ważny",
        r"ważna",
        r"ważne",
        r"niezwykle\s+ważny",
        r"kluczowy",
        r"istotny",
        r"preferowany",
    ],
    "medium": [
        r"średni\s+priorytet",
        r"średnia",
        r"średni",
        r"powinien",
        r"zalecany",
        r"zalecana",
        r"zalecane",
        r"optymalny",
    ],
    "low": [
        r"niski\s+priorytet",
        r"niska",
        r"niski",
        r"opcjonalny",
        r"opcjonalna",
        r"opcjonalne",
        r"dodatkowy",
        r"dodatkowa",
        r"dodatkowe",
        r"może",
        r"mógłby",
        r"jeśli\s+to\s+możliwe",
    ],
}

# Section titles that likely contain requirements
REQUIREMENT_SECTION_PATTERNS = [
    r"wymagania\s+funkcjonalne",
    r"wymagania\s+niefunkcjonalne",
    r"wymagania",
    r"functional\s+requirements",
    r"non-functional\s+requirements",
    r"wymagania\s+interfejsu",
    r"wymagania\s+danych",
    r"wymagania\s+bezpieczeństwa",
    r"zakres\s+wymagań",
    r"spezifikacja\s+wymagań",
]

# Sentence starters that often indicate requirements
REQUIREMENT_STARTERS = [
    "system musi",
    "system powinien",
    "system ma",
    "aplikacja musi",
    "aplikacja powinien",
    "użytkownik musi",
    "użytkownik może",
    "użytkownik powinien",
    "wymagane jest",
    "wymagane są",
    "należy",
    "zaleca się",
    "należy zaimplementować",
    "oprogram ma za zadanie",
    "funkcja pozwala",
    "funkcja umożliwia",
]

# Negative patterns - sentence NOT containing requirement
NON_REQUIREMENT_PATTERNS = [
    r"^(np\.|np\s|e\.g\.|dla\s+przykład)",
    r"^przykładowo",
    r"^uwaga\s*:",
    r"^nota\s*:",
    r"patrz\s+(punkt|sekcja|rozdział)",
    r"^zobacz\s+też",
    r"jak\s+widać",
    r"ilustracj",
    r"rysunek\s+pokazuje",
]

# Pattern for splitting text into sentences
SENTENCE_SPLIT_PATTERN = re.compile(
    r"""
    (?<=[.!?])\s+      # Sentence ending followed by whitespace
    (?=[A-ZĄĆĘŁŃÓŚŹŻ])     # Next sentence starts with capital letter
    |
    (?<=[.!?])\s*\n\s*   # Sentence ending followed by newline
    (?=[A-ZĄĆĘŁŃÓŚŹŻ])     # Next sentence starts with capital letter
    """,
    re.VERBOSE,
)


def compile_patterns() -> dict[str, re.Pattern]:
    """Compile all regex patterns for efficient matching.

    Returns:
        Dictionary mapping pattern names to compiled regex objects
    """
    return {
        "requirement_patterns": [re.compile(p, re.IGNORECASE) for p in REQUIREMENT_PATTERNS],
        "requirement_ids": [re.compile(p, re.IGNORECASE) for p in REQUIREMENT_ID_PATTERNS],
        "non_functional": NON_FUNCTIONAL_KEYWORDS,
        "requirement_sections": [re.compile(p, re.IGNORECASE) for p in REQUIREMENT_SECTION_PATTERNS],
        "requirement_starters": REQUIREMENT_STARTERS,
        "non_requirement": [re.compile(p, re.IGNORECASE) for p in NON_REQUIREMENT_PATTERNS],
    }


# Pre-compiled patterns for performance
COMPILED_PATTERNS = compile_patterns()


def is_requirement_section(title: str) -> bool:
    """Check if a section title suggests it contains requirements.

    Args:
        title: Section title to check

    Returns:
        True if title suggests requirement section
    """
    title_lower = title.lower().strip()
    for pattern in COMPILED_PATTERNS["requirement_sections"]:
        if pattern.search(title_lower):
            return True
    return False


def extract_requirement_id(text: str) -> str | None:
    """Extract requirement ID from text if present.

    Args:
        text: Text to search for requirement ID

    Returns:
        Requirement ID if found, None otherwise
    """
    for pattern in COMPILED_PATTERNS["requirement_ids"]:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def detect_priority(text: str) -> str | None:
    """Detect priority level from requirement text.

    Args:
        text: Requirement text to analyze

    Returns:
        Priority level (critical, high, medium, low) or None
    """
    text_lower = text.lower()

    # Check in order of specificity (critical first)
    for priority, patterns in PRIORITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return priority

    return None


def is_non_functional(text: str) -> bool:
    """Check if requirement is non-functional based on keywords.

    Args:
        text: Requirement text to analyze

    Returns:
        True if appears to be non-functional requirement
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in COMPILED_PATTERNS["non_functional"])


def matches_requirement_pattern(text: str) -> bool:
    """Check if text matches any requirement pattern.

    Args:
        text: Text to check

    Returns:
        True if matches any requirement pattern
    """
    text_lower = text.lower()
    for pattern in COMPILED_PATTERNS["requirement_patterns"]:
        if pattern.search(text_lower):
            return True
    return False


def starts_with_requirement_starter(text: str) -> bool:
    """Check if sentence starts with a requirement phrase.

    Args:
        text: Sentence to check

    Returns:
        True if starts with requirement phrase
    """
    text_lower = text.lower().strip()
    for starter in COMPILED_PATTERNS["requirement_starters"]:
        if text_lower.startswith(starter.lower()):
            return True
    return False


def is_non_requirement(text: str) -> bool:
    """Check if text matches non-requirement patterns.

    Args:
        text: Text to check

    Returns:
        True if matches exclusion pattern
    """
    text_lower = text.lower().strip()
    for pattern in COMPILED_PATTERNS["non_requirement"]:
        if pattern.match(text_lower):
            return True
    return False


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using regex pattern.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    # Simple sentence splitting
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])', text)
    # Clean up
    return [s.strip() for s in sentences if s.strip()]


def calculate_requirement_confidence(
    text: str,
    has_id: bool,
    in_requirement_section: bool,
) -> float:
    """Calculate confidence score for requirement extraction.

    Args:
        text: Requirement text
        has_id: Whether text contains requirement ID
        in_requirement_section: Whether from requirement section

    Returns:
        Confidence score 0-100
    """
    score = 50.0  # Base score

    # Boost for explicit requirement ID
    if has_id:
        score += 30.0

    # Boost for requirement section
    if in_requirement_section:
        score += 15.0

    # Pattern matching
    if matches_requirement_pattern(text):
        score += 15.0

    # Starter phrase
    if starts_with_requirement_starter(text):
        score += 10.0

    # Penalty if matches non-requirement pattern
    if is_non_requirement(text):
        score -= 20.0

    # Length check (too short or too long)
    if len(text) < 10:
        score -= 20.0
    elif len(text) > 500:
        score -= 10.0

    return max(0.0, min(100.0, score))
