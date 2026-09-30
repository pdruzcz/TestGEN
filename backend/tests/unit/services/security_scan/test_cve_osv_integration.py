"""OSV.dev and GitHub Advisory response parsing — Story 4.12, Tasks 3 & 4.

Asserts the pure ``_parse_osv`` / ``_parse_github`` extract package, ecosystem,
CVE alias, affected/fixed versions and severity without network access.
"""

from app.models.security_finding import Severity
from app.services.security_scan.cve_pipeline import CVEPipeline

_OSV_PAYLOAD = {
    "vulns": [
        {
            "id": "GHSA-aaaa-bbbb-cccc",
            "aliases": ["CVE-2024-3000"],
            "summary": "ReDoS in parser",
            "published": "2024-04-01T00:00:00Z",
            "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L baseScore:7.5"}],
            "database_specific": {"severity": "HIGH"},
            "affected": [
                {
                    "package": {"ecosystem": "PyPI", "name": "parserlib"},
                    "versions": ["1.0.0", "1.1.0"],
                    "ranges": [
                        {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "1.2.0"}]}
                    ],
                }
            ],
        }
    ]
}


def test_parse_osv_extracts_package_and_fix():
    records = CVEPipeline._parse_osv(_OSV_PAYLOAD, "PyPI")
    assert len(records) == 1
    rec = records[0]
    assert rec.cve_id == "CVE-2024-3000"
    assert rec.package_name == "parserlib"
    assert rec.ecosystem == "pypi"
    assert rec.fixed_version == "1.2.0"
    assert "1.0.0" in rec.affected_versions
    assert rec.severity == Severity.HIGH
    assert rec.source_db == "osv"


def test_parse_osv_falls_back_to_osv_id_without_cve_alias():
    payload = {
        "vulns": [
            {
                "id": "OSV-2024-9",
                "summary": "x",
                "affected": [{"package": {"ecosystem": "npm", "name": "leftpad"}}],
            }
        ]
    }
    records = CVEPipeline._parse_osv(payload, "npm")
    assert records[0].cve_id == "OSV-2024-9"
    assert records[0].ecosystem == "npm"


def test_parse_osv_empty():
    assert CVEPipeline._parse_osv({}, "PyPI") == []


_GITHUB_PAYLOAD = [
    {
        "ghsa_id": "GHSA-zzzz",
        "cve_id": "CVE-2024-4000",
        "summary": "SSRF in fetcher",
        "severity": "critical",
        "cvss": {"score": 9.1},
        "published_at": "2024-03-01T00:00:00Z",
        "vulnerabilities": [
            {
                "package": {"ecosystem": "pip", "name": "fetcher"},
                "vulnerable_version_range": "< 2.0.0",
                "first_patched_version": {"identifier": "2.0.0"},
            }
        ],
    }
]


def test_parse_github_extracts_package_and_patch():
    records = CVEPipeline._parse_github(_GITHUB_PAYLOAD)
    assert len(records) == 1
    rec = records[0]
    assert rec.cve_id == "CVE-2024-4000"
    assert rec.package_name == "fetcher"
    assert rec.ecosystem == "pypi"  # pip normalized
    assert rec.cvss_score == 9.1
    assert rec.severity == Severity.CRITICAL
    assert rec.fixed_version == "2.0.0"
    assert rec.source_db == "github"


def test_parse_github_falls_back_to_ghsa_id():
    payload = [
        {
            "ghsa_id": "GHSA-only",
            "summary": "x",
            "vulnerabilities": [{"package": {"ecosystem": "npm", "name": "p"}}],
        }
    ]
    records = CVEPipeline._parse_github(payload)
    assert records[0].cve_id == "GHSA-only"
