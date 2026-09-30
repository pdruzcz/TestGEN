"""CVSS v3.1 calculator — Epic 4, Story 4.8.

Pure implementation of the CVSS v3.1 Base Score formula plus a set of default
vectors per vulnerability class (keyed by CWE). No database or network access,
so every helper is directly unit-testable. The formula follows the official
FIRST specification (https://www.first.org/cvss/v3.1/specification-document).
"""

import math
from dataclasses import dataclass

# Metric value tables (CVSS v3.1 specification, section 7.4).
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
# Privileges Required depends on Scope: (unchanged, changed).
_PR = {"N": (0.85, 0.85), "L": (0.62, 0.68), "H": (0.27, 0.50)}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.00}


@dataclass(frozen=True)
class CVSSVector:
    """The eight CVSS v3.1 base metrics, each stored as its single-letter code."""

    attack_vector: str = "N"  # AV: N/A/L/P
    attack_complexity: str = "L"  # AC: L/H
    privileges_required: str = "N"  # PR: N/L/H
    user_interaction: str = "N"  # UI: N/R
    scope: str = "U"  # S: U/C
    confidentiality: str = "N"  # C: H/L/N
    integrity: str = "N"  # I: H/L/N
    availability: str = "N"  # A: H/L/N

    def to_string(self) -> str:
        return (
            f"CVSS:3.1/AV:{self.attack_vector}/AC:{self.attack_complexity}"
            f"/PR:{self.privileges_required}/UI:{self.user_interaction}"
            f"/S:{self.scope}/C:{self.confidentiality}/I:{self.integrity}"
            f"/A:{self.availability}"
        )


def _roundup(value: float) -> float:
    """CVSS v3.1 roundup: smallest 1-decimal number >= value (spec appendix A)."""
    int_input = round(value * 100000)
    if int_input % 10000 == 0:
        return int_input / 100000.0
    return (math.floor(int_input / 10000) + 1) / 10.0


def calculate_cvss_base_score(vector: CVSSVector) -> float:
    """Compute the CVSS v3.1 Base Score (0.0-10.0) for the given vector."""
    scope_changed = vector.scope == "C"

    iss = 1 - (
        (1 - _CIA[vector.confidentiality])
        * (1 - _CIA[vector.integrity])
        * (1 - _CIA[vector.availability])
    )

    impact = (
        7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if scope_changed else 6.42 * iss
    )

    pr = _PR[vector.privileges_required][1 if scope_changed else 0]
    exploitability = (
        8.22 * _AV[vector.attack_vector] * _AC[vector.attack_complexity] * pr * _UI[vector.user_interaction]
    )

    if impact <= 0:
        return 0.0

    if scope_changed:
        return _roundup(min(1.08 * (impact + exploitability), 10))
    return _roundup(min(impact + exploitability, 10))


def cvss_severity(score: float) -> str:
    """Map a CVSS Base Score to its qualitative severity rating."""
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "info"


# Default vectors per vulnerability class, keyed by CWE. Values reflect the
# canonical CVSS profile for each class (see the NVD reference scores).
DEFAULT_CVSS_VECTORS: dict[str, CVSSVector] = {
    # SQL Injection — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H (9.8)
    "CWE-89": CVSSVector("N", "L", "N", "N", "U", "H", "H", "H"),
    # OS Command Injection — 9.8
    "CWE-78": CVSSVector("N", "L", "N", "N", "U", "H", "H", "H"),
    # Code Injection — 9.8
    "CWE-94": CVSSVector("N", "L", "N", "N", "U", "H", "H", "H"),
    # Deserialization of Untrusted Data — 9.8
    "CWE-502": CVSSVector("N", "L", "N", "N", "U", "H", "H", "H"),
    # SSRF — 9.1
    "CWE-918": CVSSVector("N", "L", "N", "N", "U", "H", "H", "N"),
    # XSS — AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N (6.1)
    "CWE-79": CVSSVector("N", "L", "N", "R", "C", "L", "L", "N"),
    # CSRF — AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N (6.5)
    "CWE-352": CVSSVector("N", "L", "N", "R", "U", "N", "H", "N"),
    # Path Traversal — 7.5
    "CWE-22": CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"),
    # XXE — 7.5
    "CWE-611": CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"),
    # Hardcoded Credentials / secrets — 7.5
    "CWE-798": CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"),
    "CWE-259": CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"),
    # Weak Crypto — 5.9
    "CWE-327": CVSSVector("N", "H", "N", "N", "U", "H", "N", "N"),
    # IDOR — 6.5 (authenticated)
    "CWE-639": CVSSVector("N", "L", "L", "N", "U", "H", "N", "N"),
    # Missing Authorization — 8.1
    "CWE-862": CVSSVector("N", "L", "N", "N", "U", "H", "H", "N"),
    # Information Exposure — 5.3
    "CWE-200": CVSSVector("N", "L", "N", "N", "U", "L", "N", "N"),
    # Improper Access Control / exposed resource — 7.5
    "CWE-668": CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"),
    # Unpinned base image — 5.3 (supply-chain integrity)
    "CWE-1104": CVSSVector("N", "L", "N", "N", "U", "N", "L", "N"),
}

# Fallback vectors when the CWE is unknown — chosen so the computed CVSS lands in
# the band matching the finding's own severity label.
_SEVERITY_FALLBACK_VECTORS: dict[str, CVSSVector] = {
    "critical": CVSSVector("N", "L", "N", "N", "U", "H", "H", "H"),
    "high": CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"),
    "medium": CVSSVector("N", "L", "N", "R", "U", "L", "L", "N"),
    "low": CVSSVector("N", "H", "L", "N", "U", "L", "N", "N"),
    "info": CVSSVector("N", "H", "L", "N", "U", "N", "N", "N"),
}


def default_vector_for(cwe_id: str | None, severity: str | None = None) -> CVSSVector:
    """Pick a default CVSS vector by CWE, falling back to the severity band."""
    if cwe_id:
        vector = DEFAULT_CVSS_VECTORS.get(cwe_id.upper())
        if vector is not None:
            return vector
    return _SEVERITY_FALLBACK_VECTORS.get((severity or "medium").lower(), _SEVERITY_FALLBACK_VECTORS["medium"])
