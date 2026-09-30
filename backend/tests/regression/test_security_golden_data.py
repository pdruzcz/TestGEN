"""Security golden-data regression suite — Epic 4, Story 4.14 (AC4).

Runs the native security scanners over the curated golden corpus under
``tests/golden_data/security/`` and asserts the aggregate quality metrics stay
above their regression thresholds:

| Metric              | Threshold | Source                                        |
|---------------------|-----------|-----------------------------------------------|
| SAST detection rate | >= 90%    | vulnerable_code/* (one expected type / file)  |
| SAST FP rate        | < 30%     | vulnerable_code/safe_code/*                   |
| Taint recall        | >= 75%    | vulnerable_code/taint_paths/*                 |
| Config detection    | >= 90%    | misconfigurations/*                           |
| CVE detection       | >= 80%    | cve/* (package+version parse, offline)        |

The thresholds double as the CI regression alert: if a rule change silently
drops detections (or starts flagging the safe samples) the matching test fails,
failing the pipeline. Everything runs offline against the native engines — no
LLM, DB or network — so it is safe to gate every build on.
"""

import json
from pathlib import Path

import pytest

from app.services.security_scan.config_scanner import ConfigScanner
from app.services.security_scan.dependency_scanner import DependencyScanner
from app.services.security_scan.sast_engine import SASTEngine
from app.services.security_scan.taint_analyzer import TaintAnalyzer

_SECURITY_ROOT = Path(__file__).parent.parent / "golden_data" / "security"
_VULN_CODE = _SECURITY_ROOT / "vulnerable_code"
_MISCONFIG = _SECURITY_ROOT / "misconfigurations"
_CVE = _SECURITY_ROOT / "cve"

# Regression thresholds (AC4).
SAST_DETECTION_THRESHOLD = 0.90
SAST_FP_THRESHOLD = 0.30
TAINT_RECALL_THRESHOLD = 0.75
CONFIG_DETECTION_THRESHOLD = 0.90
CVE_DETECTION_THRESHOLD = 0.80

# Categories whose samples carry exactly one expected vulnerability type each.
_SAST_CATEGORIES = ("sqli", "xss", "csrf", "authz", "secrets", "command_injection")


def _load_manifest(directory: Path) -> dict:
    return json.loads((directory / "manifest.json").read_text(encoding="utf-8"))


def _sast_samples() -> list[tuple[Path, dict]]:
    samples: list[tuple[Path, dict]] = []
    for category in _SAST_CATEGORIES:
        manifest = _load_manifest(_VULN_CODE / category)
        for sample in manifest["samples"]:
            samples.append((_VULN_CODE / category / sample["file"], sample))
    return samples


pytestmark = pytest.mark.golden_data


def test_sast_detection_rate():
    """SAST must detect the expected vulnerability type in >= 90% of samples."""
    engine = SASTEngine()
    samples = _sast_samples()
    detected = 0
    misses: list[str] = []
    for path, sample in samples:
        code = path.read_text(encoding="utf-8")
        findings = engine.scan_code(code, sample["language"], sample["file"])
        types = {f.vulnerability_type for f in findings}
        if sample["vulnerability_type"] in types:
            detected += 1
        else:
            misses.append(f"{sample['file']} (got {sorted(types)})")

    rate = detected / len(samples)
    assert rate >= SAST_DETECTION_THRESHOLD, (
        f"SAST detection rate {rate:.0%} < {SAST_DETECTION_THRESHOLD:.0%}; misses: {misses}"
    )


def test_sast_false_positive_rate():
    """Safe-by-construction samples must stay below the 30% FP threshold."""
    engine = SASTEngine()
    manifest = _load_manifest(_VULN_CODE / "safe_code")
    samples = manifest["samples"]
    false_positives = 0
    offenders: list[str] = []
    for sample in samples:
        code = (_VULN_CODE / "safe_code" / sample["file"]).read_text(encoding="utf-8")
        findings = engine.scan_code(code, sample["language"], sample["file"])
        if findings:
            false_positives += 1
            offenders.append(f"{sample['file']} ({[f.vulnerability_type for f in findings]})")

    fp_rate = false_positives / len(samples)
    assert fp_rate < SAST_FP_THRESHOLD, f"SAST FP rate {fp_rate:.0%} >= {SAST_FP_THRESHOLD:.0%}; offenders: {offenders}"


def test_taint_recall():
    """Taint analyzer must recover >= 75% of the ground-truth source->sink flows."""
    analyzer = TaintAnalyzer()
    manifest = _load_manifest(_VULN_CODE / "taint_paths")
    samples = manifest["samples"]
    recovered = 0
    misses: list[str] = []
    for sample in samples:
        code = (_VULN_CODE / "taint_paths" / sample["file"]).read_text(encoding="utf-8")
        paths = analyzer.analyze_code(code, sample["language"], sample["file"])
        sinks = {p.sink_type for p in paths}
        expected_sinks = set(sample["expected_sink_types"])
        if len(paths) >= sample["min_paths"] and expected_sinks <= sinks:
            recovered += 1
        else:
            misses.append(f"{sample['file']} (paths={len(paths)}, sinks={sorted(sinks)})")

    recall = recovered / len(samples)
    assert recall >= TAINT_RECALL_THRESHOLD, (
        f"Taint recall {recall:.0%} < {TAINT_RECALL_THRESHOLD:.0%}; misses: {misses}"
    )


def test_taint_inadequate_sanitizer_flagged():
    """The sanitized-but-still-vulnerable sample must be flagged as inadequate."""
    analyzer = TaintAnalyzer()
    manifest = _load_manifest(_VULN_CODE / "taint_paths")
    sample = next(s for s in manifest["samples"] if s["sanitized"])
    code = (_VULN_CODE / "taint_paths" / sample["file"]).read_text(encoding="utf-8")
    paths = analyzer.analyze_code(code, sample["language"], sample["file"])
    assert any(p.sanitizer_name and not p.sanitizer_adequate for p in paths)


def test_config_scan_detection():
    """Config scanner must recover the expected rule in >= 90% of misconfig samples."""
    scanner = ConfigScanner()
    samples: list[tuple[str, dict]] = []
    for config_type in ("docker", "kubernetes", "terraform"):
        manifest = _load_manifest(_MISCONFIG / config_type)
        for sample in manifest["samples"]:
            samples.append((config_type, sample))

    detected = 0
    misses: list[str] = []
    for config_type, sample in samples:
        content = (_MISCONFIG / config_type / sample["file"]).read_text(encoding="utf-8")
        findings = scanner.scan_content(content, sample["file"])
        rules = {f.rule_id for f in findings}
        if set(sample["expected_rules"]) <= rules:
            detected += 1
        else:
            misses.append(f"{config_type}/{sample['file']} (got {sorted(rules)})")

    rate = detected / len(samples)
    assert rate >= CONFIG_DETECTION_THRESHOLD, (
        f"Config detection rate {rate:.0%} < {CONFIG_DETECTION_THRESHOLD:.0%}; misses: {misses}"
    )


def test_dependency_scan_cve():
    """Dependency parsers must recover every known-vulnerable package per ecosystem."""
    scanner = DependencyScanner()
    ground_truth = json.loads((_CVE / "cve_ground_truth.json").read_text(encoding="utf-8"))
    samples = ground_truth["samples"]
    recovered = 0
    misses: list[str] = []
    for sample in samples:
        content = (_CVE / sample["file"]).read_text(encoding="utf-8")
        filename = sample["file"].rsplit("/", 1)[-1]
        deps = {d.name: d for d in scanner.parse_file(filename, content)}
        expected = set(sample["expected_packages"])
        versions_ok = all(
            name in deps and deps[name].version == version for name, version in sample["expected_versions"].items()
        )
        if expected <= set(deps) and versions_ok:
            recovered += 1
        else:
            misses.append(f"{sample['file']} (got {sorted(deps)})")

    rate = recovered / len(samples)
    assert rate >= CVE_DETECTION_THRESHOLD, (
        f"CVE detection rate {rate:.0%} < {CVE_DETECTION_THRESHOLD:.0%}; misses: {misses}"
    )
