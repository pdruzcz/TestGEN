"""Unit tests for the CVSS v3.1 calculator — Story 4.8.

Validates the base-score formula against the canonical NVD reference scores and
the qualitative severity mapping.
"""

import pytest

from app.services.security_scan.cvss_calculator import (
    CVSSVector,
    calculate_cvss_base_score,
    cvss_severity,
    default_vector_for,
)


class TestBaseScoreFormula:
    @pytest.mark.parametrize(
        ("vector", "expected"),
        [
            # SQLi — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
            (CVSSVector("N", "L", "N", "N", "U", "H", "H", "H"), 9.8),
            # XSS — AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N
            (CVSSVector("N", "L", "N", "R", "C", "L", "L", "N"), 6.1),
            # CSRF — AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N
            (CVSSVector("N", "L", "N", "R", "U", "N", "H", "N"), 6.5),
            # Hardcoded secret — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N
            (CVSSVector("N", "L", "N", "N", "U", "H", "N", "N"), 7.5),
            # No impact → 0.0
            (CVSSVector("N", "L", "N", "N", "U", "N", "N", "N"), 0.0),
        ],
    )
    def test_reference_scores(self, vector: CVSSVector, expected: float):
        assert calculate_cvss_base_score(vector) == expected

    def test_score_within_range(self):
        score = calculate_cvss_base_score(CVSSVector("N", "L", "L", "N", "C", "H", "H", "H"))
        assert 0.0 <= score <= 10.0


class TestSeverityMapping:
    @pytest.mark.parametrize(
        ("score", "label"),
        [
            (9.8, "critical"),
            (9.0, "critical"),
            (8.9, "high"),
            (7.0, "high"),
            (6.9, "medium"),
            (4.0, "medium"),
            (3.9, "low"),
            (0.1, "low"),
            (0.0, "info"),
        ],
    )
    def test_cvss_severity(self, score: float, label: str):
        assert cvss_severity(score) == label


class TestDefaultVectors:
    def test_known_cwe_returns_sqli_vector(self):
        vector = default_vector_for("CWE-89")
        assert calculate_cvss_base_score(vector) == 9.8

    def test_unknown_cwe_falls_back_to_severity_band(self):
        vector = default_vector_for("CWE-99999", "critical")
        assert cvss_severity(calculate_cvss_base_score(vector)) == "critical"

    def test_no_cwe_uses_severity(self):
        vector = default_vector_for(None, "low")
        assert calculate_cvss_base_score(vector) < 7.0

    def test_to_string_roundtrip_format(self):
        assert default_vector_for("CWE-89").to_string().startswith("CVSS:3.1/AV:N")
