"""Golden dataset for HTML/DOM GUI sourcing — Story 1.51-zakańczenie (FR69).

Story 3.14-style golden test for the DOM extraction path (Testy #12): a realistic
login form (``.html`` + axe-core ``a11y.json`` + ground-truth ``.truth.json``)
must yield ≥90% locator-attribute coverage, and the before/after pair must heal
green via the self-healing locator ladder — all on real fixture data, no
manually injected attributes.
"""

import json
import uuid
from pathlib import Path

from app.models.healing_report import LocatorStrategy
from app.services.analysis.gui.dom_extractor import DOMComponentExtractor
from app.services.generators.self_healing import GUIElementView, NativeMatcher, ParsedLocator

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "dom"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _views(html: str) -> list[GUIElementView]:
    return [
        GUIElementView(
            component_id=uuid.uuid4(),
            component_type=c.component_type,
            label=c.label,
            attributes=c.attributes,
            bbox=None,
        )
        for c in DOMComponentExtractor().extract(html)
    ]


def _matches(comps, expected: dict) -> bool:
    tag = expected["tag"]
    if "attr" in expected:
        return any(
            c.attributes.get("tag") == tag and c.attributes.get(expected["attr"]) == expected["value"] for c in comps
        )
    if "label" in expected:
        return any(c.attributes.get("tag") == tag and c.label == expected["label"] for c in comps)
    return False


class TestGoldenDom:
    def test_attribute_coverage_at_least_90_percent(self):
        html = _read("login_form.html")
        a11y = json.loads(_read("login_form.a11y.json"))
        comps = DOMComponentExtractor().extract(html, a11y_json=a11y)

        truth = json.loads(_read("login_form.truth.json"))["elements"]
        covered = sum(1 for t in truth if _matches(comps, t))
        ratio = covered / len(truth)
        assert ratio >= 0.90, f"attribute coverage {ratio:.0%} < 90% ({covered}/{len(truth)})"

        # a11y merge enriched the form (matched by aria-label) with a semantic role.
        forms = [c for c in comps if c.attributes.get("tag") == "form"]
        assert forms and forms[0].attributes.get("role") == "form"

    def test_healing_before_after_green_on_real_fixture(self):
        before = _views(_read("login_form.html"))
        after = _views(_read("login_form_after.html"))

        # The test targets the legacy id-based locator from version A.
        loc = ParsedLocator(
            raw="#login-btn",
            strategy=LocatorStrategy.ID,
            selector="#login-btn",
            start=0,
            end=9,
        )
        candidate = NativeMatcher.match(loc, before, after)
        assert candidate is not None, "healing found no candidate for #login-btn"
        assert candidate.new_strategy == LocatorStrategy.DATA_TESTID
        assert candidate.new_locator == "[data-testid='login-submit']"
