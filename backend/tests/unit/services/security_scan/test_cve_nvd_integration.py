"""NVD API v2.0 response parsing — Story 4.12, Task 2.

Asserts the pure ``_parse_nvd`` extracts CVE id, English description, CVSS v3.1
base score, published date and affected product (from CPE) without any network.
"""

from app.models.security_finding import Severity
from app.services.security_scan.cve_pipeline import CVEPipeline

_NVD_PAYLOAD = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2024-1000",
                "published": "2024-05-01T10:00:00.000",
                "descriptions": [
                    {"lang": "es", "value": "ignorado"},
                    {"lang": "en", "value": "Buffer overflow in widget."},
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {"cvssData": {"baseScore": 9.8}},
                    ]
                },
                "configurations": [
                    {
                        "nodes": [
                            {
                                "cpeMatch": [
                                    {"criteria": "cpe:2.3:a:acme:widget:1.0:*:*:*:*:*:*:*"},
                                ]
                            }
                        ]
                    }
                ],
            }
        }
    ]
}


def test_parse_nvd_extracts_core_fields():
    records = CVEPipeline._parse_nvd(_NVD_PAYLOAD)
    assert len(records) == 1
    rec = records[0]
    assert rec.cve_id == "CVE-2024-1000"
    assert rec.description == "Buffer overflow in widget."
    assert rec.cvss_score == 9.8
    assert rec.severity == Severity.CRITICAL
    assert rec.package_name == "widget"
    assert rec.source_db == "nvd"
    assert rec.published_date is not None


def test_parse_nvd_handles_missing_metrics_and_cpe():
    payload = {
        "vulnerabilities": [
            {"cve": {"id": "CVE-2024-2000", "descriptions": [{"lang": "en", "value": "x"}]}}
        ]
    }
    records = CVEPipeline._parse_nvd(payload)
    assert len(records) == 1
    assert records[0].cvss_score == 0.0
    assert records[0].severity == Severity.INFO
    # No CPE -> placeholder package, still a record.
    assert records[0].package_name == ""


def test_parse_nvd_skips_entries_without_id():
    payload = {"vulnerabilities": [{"cve": {"descriptions": []}}]}
    assert CVEPipeline._parse_nvd(payload) == []


def test_parse_nvd_empty_payload():
    assert CVEPipeline._parse_nvd({}) == []
