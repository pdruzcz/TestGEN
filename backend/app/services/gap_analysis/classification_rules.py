"""Classification rules for gap analysis — Epic 5, Story 5.2.

Defines thresholds, exclusion patterns, and severity mappings used by
GapClassifier to categorise findings.
"""

from __future__ import annotations

import re

# ── Confidence thresholds ────────────────────────────────────────────────────

MISSING_THRESHOLD = 30.0      # below this → missing (no match)
DIVERGENT_THRESHOLD = 70.0    # 30-70 → different (partial/divergent match)
GOOD_MATCH_THRESHOLD = 70.0   # above this → matched (not a gap)

# ── Exclusion patterns for "extra" detection ────────────────────────────────
# Entities matching these patterns are not flagged as extra code.

EXCLUDE_PATTERNS = re.compile(
    r"^(test_|__|conftest|setup|teardown|main$|_main|pytest_|"
    r"setUp|tearDown|before|after)"
)

# Common getter/setter/minor methods to skip as "extra"
MINOR_ENTITY_PATTERNS = re.compile(
    r"^(get_|set_|is_|has_|can_|_get|_set|_is|_has|_can)"
)

# ── Severity mapping ─────────────────────────────────────────────────────────
# gap_type → default severity; overridden by priority for missing.

SEVERITY_MAP: dict[str, str] = {
    "missing": "warning",       # bumped to critical if priority=high
    "different": "warning",
    "extra": "info",
    "inconsistent": "critical",
}

# Priority → severity override for missing gaps
PRIORITY_SEVERITY: dict[str, str] = {
    "high": "critical",
    "medium": "warning",
    "low": "warning",
}

# ── Inconsistent detection ───────────────────────────────────────────────────
# A code entity mapped to multiple requirements with conflicting signals
# is flagged as inconsistent. We detect this when:
# 1. The same entity is the best match for 2+ requirements
# 2. The score spread between best and worst exceeds this threshold
INCONSISTENT_SCORE_SPREAD = 40.0

# Contradiction indicator terms (pairs that suggest conflicting requirements)
CONTRADICTION_INDICATORS = [
    ("must", "must not"),
    ("required", "optional"),
    ("always", "never"),
    ("include", "exclude"),
    ("enable", "disable"),
    ("allow", "deny"),
    ("accept", "reject"),
]
