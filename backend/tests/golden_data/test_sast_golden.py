"""Golden SAST regression tests — Epic 4, Story 4.1.

Run the native SAST engine over the frozen vulnerable samples and assert it
still detects every expected vulnerability type. Guards against rule
regressions silently dropping detections.
"""

import json
from pathlib import Path

import pytest

from app.services.security_scan.sast_engine import SASTEngine

_SAST_DIR = Path(__file__).parent / "security" / "sast"
_GROUND_TRUTH = json.loads((_SAST_DIR / "sast_ground_truth.json").read_text(encoding="utf-8"))


@pytest.mark.golden
@pytest.mark.parametrize("sample", _GROUND_TRUTH["samples"], ids=lambda s: s["file"])
def test_sast_detects_expected_types(sample):
    engine = SASTEngine()
    code = (_SAST_DIR / sample["file"]).read_text(encoding="utf-8")
    findings = engine.scan_code(code, sample["language"], sample["file"])

    detected = {f.vulnerability_type for f in findings}
    missing = set(sample["expected_types"]) - detected
    assert not missing, f"{sample['file']}: missing detections {missing}"
    assert len(findings) >= sample["min_findings"]


@pytest.mark.golden
@pytest.mark.parametrize("sample", _GROUND_TRUTH["samples"], ids=lambda s: s["file"])
def test_sast_findings_carry_metadata(sample):
    engine = SASTEngine()
    code = (_SAST_DIR / sample["file"]).read_text(encoding="utf-8")
    findings = engine.scan_code(code, sample["language"], sample["file"])

    for f in findings:
        assert f.severity in ("critical", "high", "medium", "low", "info")
        assert 0.1 <= f.confidence <= 0.99
        assert f.line_start and f.line_start >= 1
        assert f.file_path == sample["file"]
