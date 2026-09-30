"""Golden config-scan regression tests — Epic 4, Story 4.5.

Run the config scanner over the frozen insecure samples and assert it still
recovers every expected misconfiguration rule across Docker / Kubernetes /
Terraform (recall guard).
"""

import json
from pathlib import Path

import pytest

from app.services.security_scan.config_scanner import ConfigScanner

_CONFIG_DIR = Path(__file__).parent / "security" / "config"
_GROUND_TRUTH = json.loads(
    (_CONFIG_DIR / "config_ground_truth.json").read_text(encoding="utf-8")
)


@pytest.mark.golden
@pytest.mark.parametrize("sample", _GROUND_TRUTH["samples"], ids=lambda s: s["file"])
def test_config_detects_expected_rules(sample):
    scanner = ConfigScanner()
    content = (_CONFIG_DIR / sample["file"]).read_text(encoding="utf-8")
    findings = scanner.scan_content(content, sample["file"])

    detected = {f.rule_id for f in findings}
    missing = set(sample["expected_rules"]) - detected
    assert not missing, f"{sample['file']}: missing rules {missing}"
    assert all(f.config_type == sample["config_type"] for f in findings)
