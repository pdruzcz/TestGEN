"""Tests for SelfHealingService — Epic 1, Story 1.51 (native + LLM + hybrid)."""

import uuid
from types import SimpleNamespace

import pytest

from app.models.healing_report import HealingStatus, LocatorStrategy
from app.services.generators.self_healing import (
    GUIElementView,
    HealCandidate,
    NativeMatcher,
    ParsedLocator,
    SelfHealingService,
    _bbox_iou,
    _build_replacement,
    _element_similarity,
    _parse_llm_candidate,
    _replace_locator_in_code,
    extract_signal,
    parse_locators,
)


# ── fixtures / helpers ───────────────────────────────────────────────────────
def _el(label=None, **attrs):
    bbox = attrs.pop("bbox", None)
    ctype = attrs.pop("ctype", "button")
    return GUIElementView(
        component_id=uuid.uuid4(),
        component_type=ctype,
        label=label,
        attributes=attrs,
        bbox=bbox,
    )


def _comp(label=None, **attrs):
    bbox = attrs.pop("bbox", None)
    ctype = attrs.pop("component_type", "button")
    return SimpleNamespace(
        id=uuid.uuid4(),
        component_type=ctype,
        label=label,
        attributes=attrs,
        bbox=bbox,
    )


def _tcode(code, framework="selenium"):
    return SimpleNamespace(id=uuid.uuid4(), code=code, framework=framework, test_case_id=uuid.uuid4())


def _loc(strategy, selector, raw=None):
    return ParsedLocator(raw=raw or selector, strategy=strategy, selector=selector, start=0, end=len(selector))


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def first(self):
        return self._rows[0] if self._rows else None


class _ExecResult:
    def __init__(self, rows):
        self._scalars = _Scalars(rows)

    def scalars(self):
        return self._scalars


class FakeSession:
    def __init__(self, result_sets):
        self._sets = list(result_sets)
        self.added = []
        self.flushed = False

    async def execute(self, _stmt):
        return _ExecResult(self._sets.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True


# ── parse_locators ────────────────────────────────────────────────────────────
class TestParseLocators:
    def test_selenium_css_id_xpath(self):
        code = (
            'driver.find_element(By.CSS_SELECTOR, "#login")\n'
            'driver.find_element(By.ID, "user")\n'
            'driver.find_element(By.XPATH, "//button")'
        )
        locs = parse_locators(code)
        strategies = [(loc.strategy, loc.selector) for loc in locs]
        assert (LocatorStrategy.CSS, "#login") in strategies
        assert (LocatorStrategy.ID, "user") in strategies
        assert (LocatorStrategy.XPATH, "//button") in strategies

    def test_playwright_role_and_locator(self):
        code = "page.get_by_role('button', name='Login')\npage.locator(\"#login\")"
        locs = parse_locators(code)
        roles = [loc for loc in locs if loc.strategy == LocatorStrategy.ROLE_NAME]
        assert roles and "Login" in roles[0].selector
        ids = [loc for loc in locs if loc.strategy == LocatorStrategy.ID]
        assert ids and ids[0].selector == "#login"

    def test_dedup_repeated_wait_pattern(self):
        code = 'EC.presence_of_element_located((By.ID, "x"))\ndriver.find_element(By.ID, "x")'
        locs = parse_locators(code)
        # two distinct spans -> both kept (different positions), but same selector
        assert all(loc.selector == "x" for loc in locs)
        assert len({loc.start for loc in locs}) == len(locs)


# ── extract_signal ────────────────────────────────────────────────────────────
class TestExtractSignal:
    def test_id_strategy_uses_raw_selector(self):
        sig = extract_signal(_loc(LocatorStrategy.ID, "login-btn"))
        assert sig.id_value == "login-btn"

    def test_data_testid(self):
        sig = extract_signal(_loc(LocatorStrategy.CSS, "[data-testid='login']"))
        assert sig.testid == "login"

    def test_role_text(self):
        sig = extract_signal(_loc(LocatorStrategy.ROLE_NAME, "role=button[name='Submit']"))
        assert sig.text == "Submit"


# ── NativeMatcher.target_exists (anti false-positive) ─────────────────────────
class TestTargetExists:
    def test_id_still_present(self):
        loc = _loc(LocatorStrategy.ID, "login-btn")
        elements = [_el(label="Login", id="login-btn")]
        assert NativeMatcher.target_exists(loc, elements) is True

    def test_id_removed(self):
        loc = _loc(LocatorStrategy.ID, "login-btn")
        elements = [_el(label="Login", **{"data-testid": "x"})]  # no id
        assert NativeMatcher.target_exists(loc, elements) is False

    def test_role_text_present(self):
        loc = _loc(LocatorStrategy.ROLE_NAME, "role=button[name='Login']")
        elements = [_el(label="Login")]
        assert NativeMatcher.target_exists(loc, elements) is True


# ── NativeMatcher.match (bridge) ──────────────────────────────────────────────
class TestNativeMatch:
    def test_bridge_heal_changed_id_to_testid(self):
        loc = _loc(LocatorStrategy.ID, "login-btn")
        elements_a = [_el(label="Login", id="login-btn")]
        elements_b = [_el(label="Login", **{"data-testid": "login-submit"})]
        cand = NativeMatcher.match(loc, elements_a, elements_b)
        assert cand is not None
        assert cand.confidence >= 0.8
        assert cand.new_strategy == LocatorStrategy.DATA_TESTID

    def test_no_candidate_when_unrelated(self):
        loc = _loc(LocatorStrategy.ID, "login-btn")
        elements_a = [_el(label="Login", id="login-btn")]
        elements_b = [_el(label="Completely Different Thing")]
        assert NativeMatcher.match(loc, elements_a, elements_b) is None

    def test_direct_fallback_when_original_unknown(self):
        loc = _loc(LocatorStrategy.CSS, "[data-testid='gone']")
        elements_a = []  # can't resolve original
        elements_b = [_el(label="Login")]
        # label similarity to the testid token is weak -> None
        assert NativeMatcher.match(loc, elements_a, elements_b) is None


# ── _build_replacement / similarity / bbox ────────────────────────────────────
class TestHelpers:
    def test_build_replacement_prefers_testid(self):
        s, _v = _build_replacement(_el(label="Login", **{"data-testid": "x", "id": "y"}))
        assert s == LocatorStrategy.DATA_TESTID

    def test_build_replacement_role_when_no_testid(self):
        s, _v = _build_replacement(_el(label="Login", **{"role": "button"}))
        assert s == LocatorStrategy.ROLE_NAME

    def test_element_similarity_same_control(self):
        a = _el(label="Login", ctype="button")
        b = _el(label="Login", ctype="button")
        assert _element_similarity(a, b) > 0.85

    def test_bbox_iou_identical(self):
        box = {"x": 0, "y": 0, "width": 10, "height": 10}
        assert _bbox_iou(box, box) == pytest.approx(1.0)

    def test_bbox_iou_disjoint(self):
        a = {"x": 0, "y": 0, "width": 5, "height": 5}
        b = {"x": 100, "y": 100, "width": 5, "height": 5}
        assert _bbox_iou(a, b) == 0.0


# ── merge (hybrid) ────────────────────────────────────────────────────────────
class TestMerge:
    def test_agreement_boosts_to_hybrid(self):
        nat = HealCandidate("a", LocatorStrategy.ID, 0.8, "native")
        llm = HealCandidate("a", LocatorStrategy.ID, 0.85, "llm")
        out = SelfHealingService._merge(nat, llm)
        assert out.method == "hybrid"
        assert out.confidence > 0.85

    def test_disagreement_keeps_native_on_tie(self):
        nat = HealCandidate("a", LocatorStrategy.ID, 0.8, "native")
        llm = HealCandidate("b", LocatorStrategy.CSS, 0.82, "llm")
        out = SelfHealingService._merge(nat, llm)
        # llm only 0.02 higher, not >+0.05 -> native preferred
        assert out.method == "native"

    def test_disagreement_llm_wins_when_clearly_higher(self):
        nat = HealCandidate("a", LocatorStrategy.ID, 0.6, "native")
        llm = HealCandidate("b", LocatorStrategy.CSS, 0.95, "llm")
        out = SelfHealingService._merge(nat, llm)
        assert out.method == "llm"

    def test_both_none(self):
        assert SelfHealingService._merge(None, None) is None

    def test_native_only(self):
        nat = HealCandidate("a", LocatorStrategy.ID, 0.9, "native")
        assert SelfHealingService._merge(nat, None) is nat


# ── _parse_llm_candidate ──────────────────────────────────────────────────────
class TestParseLLMCandidate:
    def test_clean_json(self):
        c = _parse_llm_candidate('{"new_locator": "#x", "new_strategy": "id", "confidence": 0.9}')
        assert c is not None and c.confidence == 0.9

    def test_fenced_json(self):
        c = _parse_llm_candidate(
            '```json\n{"new_locator": "[data-testid=\'y\']", "new_strategy": "data-testid", "confidence": 0.8}\n```'
        )
        assert c is not None and c.new_strategy == LocatorStrategy.DATA_TESTID

    def test_invalid_strategy_rejected(self):
        assert _parse_llm_candidate('{"new_locator": "x", "new_strategy": "voodoo", "confidence": 0.5}') is None

    def test_garbage_returns_none(self):
        assert _parse_llm_candidate("no json here") is None


# ── _replace_locator_in_code ──────────────────────────────────────────────────
class TestReplaceLocator:
    def test_replaces_first_occurrence(self):
        out = _replace_locator_in_code("By.ID, 'old'", "old", "new")
        assert "new" in out and "old" not in out


# ── heal() orchestration ──────────────────────────────────────────────────────
class TestHealOrchestration:
    async def test_heal_changed_locator(self):
        code = 'driver.find_element(By.ID, "login-btn")'
        elements_a = [_comp(label="Login", **{"id": "login-btn"})]
        elements_b = [_comp(label="Login", **{"data-testid": "login-submit"})]
        session = FakeSession([elements_a, elements_b, [_tcode(code)]])
        svc = SelfHealingService(session, llm_gateway=None)

        report = await svc.heal(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), str(uuid.uuid4()))

        assert report.status == HealingStatus.HEALED
        assert len(report.items) == 1
        item = report.items[0]
        assert item.status == HealingStatus.HEALED
        assert item.confidence >= 0.8
        assert item.new_strategy == LocatorStrategy.DATA_TESTID
        assert report.stats["healed"] == 1
        assert report.stats["healthy"] == 0
        assert report.stats["total"] == 1
        assert session.flushed is True

    async def test_anti_false_positive_healthy_locator(self):
        code = 'driver.find_element(By.ID, "login-btn")'
        elements_a = [_comp(label="Login", **{"id": "login-btn"})]
        elements_b = [_comp(label="Login", **{"id": "login-btn"})]  # unchanged
        session = FakeSession([elements_a, elements_b, [_tcode(code)]])
        svc = SelfHealingService(session)

        report = await svc.heal(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), str(uuid.uuid4()))

        assert report.items == []
        assert report.status == HealingStatus.HEALED
        assert report.stats["healthy"] == 1
        assert report.stats["total"] == 1

    async def test_failed_when_no_candidate(self):
        code = 'driver.find_element(By.ID, "login-btn")'
        elements_a = [_comp(label="Login", **{"id": "login-btn"})]
        elements_b = [_comp(label="Totally Different Control")]
        session = FakeSession([elements_a, elements_b, [_tcode(code)]])
        svc = SelfHealingService(session)

        report = await svc.heal(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), str(uuid.uuid4()))

        assert report.status == HealingStatus.FAILED
        assert report.stats["failed"] == 1
        assert report.items[0].status == HealingStatus.FAILED


# ── apply_decision ────────────────────────────────────────────────────────────
class TestApplyDecision:
    async def test_accept_applies_to_testcode(self):
        tc = _tcode('driver.find_element(By.ID, "old-id")')
        session = FakeSession([[tc]])
        svc = SelfHealingService(session)
        item = SimpleNamespace(
            test_code_id=tc.id,
            old_locator="old-id",
            new_locator="[data-testid='new']",
            status=HealingStatus.NEEDS_REVIEW,
        )
        out_item, applied = await svc.apply_decision(item, "accept")
        assert applied is True
        assert out_item.status == HealingStatus.HEALED
        assert "old-id" not in tc.code

    async def test_reject_does_not_apply(self):
        tc = _tcode('driver.find_element(By.ID, "old-id")')
        session = FakeSession([[tc]])
        svc = SelfHealingService(session)
        item = SimpleNamespace(
            test_code_id=tc.id,
            old_locator="old-id",
            new_locator="[data-testid='new']",
            status=HealingStatus.NEEDS_REVIEW,
        )
        out_item, applied = await svc.apply_decision(item, "reject")
        assert applied is False
        assert out_item.status == HealingStatus.REJECTED
        assert "old-id" in tc.code  # unchanged
