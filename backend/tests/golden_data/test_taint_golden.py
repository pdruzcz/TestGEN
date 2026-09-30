"""Golden taint-analysis regression tests — Epic 4, Story 4.3.

Run the taint analyzer over the frozen samples and assert it still recovers every
expected source -> sink flow (recall guard, AC4). The inadequate-sanitizer sample
also verifies AC3 reporting.
"""

import json
from pathlib import Path

import pytest

from app.services.security_scan.taint_analyzer import TaintAnalyzer

_TAINT_DIR = Path(__file__).parent / "security" / "taint"
_GROUND_TRUTH = json.loads((_TAINT_DIR / "taint_ground_truth.json").read_text(encoding="utf-8"))


@pytest.mark.golden
@pytest.mark.parametrize("sample", _GROUND_TRUTH["samples"], ids=lambda s: s["file"])
def test_taint_detects_expected_flows(sample):
    analyzer = TaintAnalyzer()
    code = (_TAINT_DIR / sample["file"]).read_text(encoding="utf-8")
    paths = analyzer.analyze_code(code, sample["language"], sample["file"])

    detected_types = {p.vulnerability_type for p in paths}
    missing = set(sample["expected_types"]) - detected_types
    assert not missing, f"{sample['file']}: missing flows {missing}"
    assert len(paths) >= sample["min_paths"]

    detected_sinks = {p.sink_type for p in paths}
    assert set(sample["expected_sink_types"]) <= detected_sinks


@pytest.mark.golden
@pytest.mark.parametrize("sample", _GROUND_TRUTH["samples"], ids=lambda s: s["file"])
def test_taint_paths_carry_metadata(sample):
    analyzer = TaintAnalyzer()
    code = (_TAINT_DIR / sample["file"]).read_text(encoding="utf-8")
    paths = analyzer.analyze_code(code, sample["language"], sample["file"])

    for p in paths:
        assert p.severity in ("critical", "high", "medium", "low", "info")
        assert p.steps, "taint path must carry at least one step"
        assert p.steps[0].node_type == "source"
        assert p.steps[-1].node_type == "sink"
        assert p.line_start and p.line_start >= 1


@pytest.mark.golden
def test_inadequate_sanitizer_sample_is_flagged():
    analyzer = TaintAnalyzer()
    sample = next(s for s in _GROUND_TRUTH["samples"] if s["sanitized"])
    code = (_TAINT_DIR / sample["file"]).read_text(encoding="utf-8")
    paths = analyzer.analyze_code(code, sample["language"], sample["file"])
    assert any(p.sanitizer_name and not p.sanitizer_adequate for p in paths)
