"""Golden dependency-parser regression tests — Epic 4, Story 4.4.

Run the dependency scanner's parsers over the frozen manifests and assert it still
recovers every expected package and version across the five supported ecosystems
(parser stability guard).
"""

import json
from pathlib import Path

import pytest

from app.services.security_scan.dependency_scanner import DependencyScanner

_DEP_DIR = Path(__file__).parent / "security" / "dependency"
_GROUND_TRUTH = json.loads(
    (_DEP_DIR / "dependency_ground_truth.json").read_text(encoding="utf-8")
)


@pytest.mark.golden
@pytest.mark.parametrize("sample", _GROUND_TRUTH["samples"], ids=lambda s: s["file"])
def test_parser_recovers_expected_packages(sample):
    scanner = DependencyScanner()
    content = (_DEP_DIR / sample["file"]).read_text(encoding="utf-8")
    deps = scanner.parse_file(sample["file"], content)

    parsed = {d.name: d for d in deps}
    for pkg in sample["expected_packages"]:
        assert pkg in parsed, f"{sample['file']}: missing package {pkg}"
        assert parsed[pkg].ecosystem == sample["ecosystem"]

    for pkg, version in sample["expected_versions"].items():
        assert parsed[pkg].version == version, (
            f"{sample['file']}: {pkg} version {parsed[pkg].version} != {version}"
        )
