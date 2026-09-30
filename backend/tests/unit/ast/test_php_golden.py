"""Golden-data accuracy tests for the PHP AST adapter (Story 1.52 / FR12).

Parses each fixture under ``tests/fixtures/golden/php/`` and compares the
extracted structure against the empirically-verified ground truth in
``expected.json``. Accuracy must stay above 95%.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.analysis.ast.adapters.php_parser import PhpAdapter

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "golden" / "php"
_ACCURACY_THRESHOLD = 0.95


def _load_expected() -> dict:
    with open(_FIXTURE_DIR / "expected.json", encoding="utf-8") as f:
        return json.load(f)


def _php_fixtures() -> list[Path]:
    return sorted(_FIXTURE_DIR.glob("*.php"))


@pytest.fixture(scope="module")
def parser():
    return PhpAdapter()


@pytest.fixture(scope="module")
def expected():
    return _load_expected()


@pytest.mark.parametrize("fixture_path", _php_fixtures(), ids=lambda p: p.name)
def test_golden_accuracy_per_fixture(parser, expected, fixture_path):
    """Every fixture must match its ground-truth class/method/function/import sets exactly."""
    code = fixture_path.read_text(encoding="utf-8")
    tree = parser.parse(code)

    actual = {
        "classes": [
            {"name": c.name, "type": c.type, "bases": c.bases, "methods": [m.name for m in c.methods]}
            for c in tree.classes
        ],
        "functions": [f.name for f in tree.functions],
        "imports": [i.module for i in tree.imports],
    }

    truth = expected[fixture_path.name]
    assert actual == truth


def test_golden_overall_accuracy(parser, expected):
    """Aggregate field-level accuracy across all fixtures must exceed 95%."""
    matches = 0
    total = 0

    for fixture_path in _php_fixtures():
        code = fixture_path.read_text(encoding="utf-8")
        tree = parser.parse(code)
        truth = expected[fixture_path.name]

        # Compare class names, class types, method names, function names, import modules.
        actual_class_names = {c.name for c in tree.classes}
        truth_class_names = {c["name"] for c in truth["classes"]}
        actual_class_types = {f"{c.name}:{c.type}" for c in tree.classes}
        truth_class_types = {f"{c['name']}:{c['type']}" for c in truth["classes"]}
        actual_methods = {m.name for c in tree.classes for m in c.methods}
        truth_methods = {m for c in truth["classes"] for m in c["methods"]}
        actual_functions = {f.name for f in tree.functions}
        truth_functions = set(truth["functions"])
        actual_imports = {i.module for i in tree.imports}
        truth_imports = set(truth["imports"])

        for actual_set, truth_set in [
            (actual_class_names, truth_class_names),
            (actual_class_types, truth_class_types),
            (actual_methods, truth_methods),
            (actual_functions, truth_functions),
            (actual_imports, truth_imports),
        ]:
            total += len(truth_set)
            matches += len(actual_set & truth_set)

    accuracy = matches / total if total else 1.0
    assert accuracy >= _ACCURACY_THRESHOLD, f"PHP golden accuracy {accuracy:.2%} < {_ACCURACY_THRESHOLD:.0%}"


def test_golden_fixture_count():
    """FR12 golden dataset: exactly 5 PHP samples covering POPO, controller, test, trait, enum."""
    names = {p.name for p in _php_fixtures()}
    assert len(names) == 5
    assert names == {
        "POPO.php",
        "LaravelController.php",
        "PHPUnitTest.php",
        "InterfaceWithTrait.php",
        "Enum.php",
    }
