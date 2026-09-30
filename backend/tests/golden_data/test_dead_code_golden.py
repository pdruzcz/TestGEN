"""Golden regression for the dead code detector — Epic 5, Story 5.10 (AC5).

Each sample in ``tests/golden_data/dead_code/`` embeds source files plus
the exact expected findings: deliberately dead definitions that MUST be
reported and exclusions (entry points / tests) that MUST NOT be.
Runs in the CI golden-regression stage (``pytest tests/golden_data/ -m golden``).
"""

import json
from pathlib import Path

import pytest

from app.services.analysis.ast.adapters.python_parser import PythonAdapter
from app.services.gap_analysis.error_detectors.dead_code_detector import (
    DeadCodeDetector,
    ParsedFile,
)

pytestmark = pytest.mark.golden

GOLDEN_DIR = Path(__file__).parent / "dead_code"
SAMPLES = sorted(GOLDEN_DIR.glob("*.json"))

PARSERS = {"python": PythonAdapter}


@pytest.mark.parametrize(
    "sample_path",
    SAMPLES,
    ids=[p.stem for p in SAMPLES],
)
def test_dead_code_golden(sample_path: Path):
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    parser = PARSERS[sample["language"]]()

    parsed_files = [
        ParsedFile(
            tree=parser.parse(f["content"], f["path"]),
            file_path=f["path"],
            content=f["content"],
        )
        for f in sample["files"]
    ]
    findings = DeadCodeDetector().detect_project(parsed_files)

    expected = sample["expected"]["dead_code"]
    excluded = sample["expected"]["excluded"]

    # exactly the expected dead definitions — no more, no less (AC5)
    reported = {(f.file_path, f.context["function"]) for f in findings}
    want = {(e["file"], e["name"]) for e in expected}
    assert reported == want, f"reported={sorted(reported)} want={sorted(want)}"

    # each finding carries location + "0 wywołań" + fingerprint (AC1/AC4)
    for f in findings:
        assert f.rule_id == "DEAD_CODE"
        assert f.line_start and f.file_path
        assert "0 wywołań" in f.message
        fp = f.context["fingerprint"]
        assert fp.startswith(f"{f.file_path}:{f.context['function']}:")
        assert len(fp.rsplit(":", 1)[1]) == 8

    # exclusions never appear (AC2/AC5)
    reported_names = {f.context["function"] for f in findings}
    for e in excluded:
        assert e["name"] not in reported_names, f"excluded {e['name']} was reported"


def test_golden_samples_exist():
    """Guard: the dead_code golden set is non-empty (regression suite)."""
    assert len(SAMPLES) >= 1
    langs = {json.loads(p.read_text(encoding="utf-8"))["language"] for p in SAMPLES}
    assert "python" in langs
