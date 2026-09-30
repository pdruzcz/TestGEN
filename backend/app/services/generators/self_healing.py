"""Self-healing service for broken UI-test locators — Epic 1, Story 1.51 (FR69).

Dual-path (native heuristics + LLM reconstruction) consistent with the 1.11
engine framework:

* **Native** — parse locators out of generated ``TestCode`` (Selenium ``By.*``
  / Playwright ``locator`` / ``get_by_role``), then fuzzy-match the broken
  target against the GUI components detected in the new version (label
  similarity via ``difflib``, type compatibility, attribute-key matches).
* **LLM** — ask the gateway to reconstruct a selector from component
  semantics when the native match is weak.
* **Hybrid** — when native and LLM agree, confidence is boosted.

The pure matching logic (``LocatorParser``, ``NativeMatcher``) is deliberately
decoupled from the DB so it stays unit-testable; ``SelfHealingService`` only
owns the async orchestration (load GUI elements + test codes, build the
``HealingReport`` / ``HealingItem`` graph, persist).

Anti false-positive: a locator whose target still resolves in ``version_b`` is
counted as ``healthy`` and never modified.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.models.analysis_result import AnalysisResult
from app.models.gui_screenshot import GUIComponent
from app.models.healing_report import (
    HealingItem,
    HealingReport,
    HealingStatus,
    LocatorStrategy,
)
from app.models.test_case import TestCase
from app.models.test_code import TestCode
from app.services.analysis.llm_gateway import LLMGateway, LLMMessage, LLMProvider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.gui_screenshot import GUIComponent as GUIComponentT

logger = logging.getLogger(__name__)

# Frameworks whose generated code carries healable UI locators.
UI_FRAMEWORKS = ("selenium", "playwright", "cypress", "appium")

# Confidence at/above which a heal is auto-applied (configurable per call).
DEFAULT_CONFIDENCE_THRESHOLD = 0.8


# ── Selenium By-strategy → LocatorStrategy ────────────────────────────────────
_BY_TO_STRATEGY: dict[str, LocatorStrategy] = {
    "CSS_SELECTOR": LocatorStrategy.CSS,
    "ID": LocatorStrategy.ID,
    "XPATH": LocatorStrategy.XPATH,
    "NAME": LocatorStrategy.CSS,
    "CLASS_NAME": LocatorStrategy.CSS,
    "TAG_NAME": LocatorStrategy.CSS,
    "LINK_TEXT": LocatorStrategy.ROLE_NAME,
    "PARTIAL_LINK_TEXT": LocatorStrategy.ROLE_NAME,
}


@dataclass(frozen=True)
class ParsedLocator:
    """One locator occurrence found inside generated test code."""

    raw: str  # exact text span from the source
    strategy: LocatorStrategy
    selector: str  # raw selector value
    start: int
    end: int


@dataclass(frozen=True)
class LocatorSignal:
    """Normalized matching signals extracted from a locator."""

    testid: str | None = None
    id_value: str | None = None
    aria: str | None = None
    text: str | None = None  # link text / role name / visible label


@dataclass
class GUIElementView:
    """DB-agnostic view of a detected GUI component (for matching)."""

    component_id: uuid.UUID
    component_type: str
    label: str | None
    attributes: dict = field(default_factory=dict)
    bbox: dict | None = None

    @classmethod
    def from_component(cls, comp: GUIComponentT) -> GUIElementView:
        return cls(
            component_id=comp.id,
            component_type=comp.component_type.value
            if hasattr(comp.component_type, "value")
            else str(comp.component_type),
            label=comp.label,
            attributes=comp.attributes or {},
            bbox=comp.bbox,
        )


@dataclass
class HealCandidate:
    """A proposed replacement for a broken locator."""

    new_locator: str
    new_strategy: LocatorStrategy
    confidence: float
    method: str  # native | llm | hybrid
    element_id: uuid.UUID | None = None


# ── Locator parsing (pure) ────────────────────────────────────────────────────
_SELENIUM_BY_RE = re.compile(r"By\.([A-Z_]+)\s*,\s*(['\"])(.*?)\2")
_PLAYWRIGHT_LOCATOR_RE = re.compile(r"\.locator\(\s*(['\"])(.*?)\1\s*\)")
_PLAYWRIGHT_ROLE_RE = re.compile(r"get_by_role\(\s*(['\"])(\w+)\1\s*,\s*name\s*=\s*(['\"])(.*?)\3\s*\)")
_TESTID_RE = re.compile(r"data-?testid\s*=\s*['\"]?([\w.-]+)['\"]?", re.IGNORECASE)
_ARIA_RE = re.compile(r"aria-?label\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_ID_CSS_RE = re.compile(r"#([\w.-]+)")


def parse_locators(code: str) -> list[ParsedLocator]:
    """Extract UI locators from generated Selenium/Playwright test code."""
    found: list[ParsedLocator] = []

    for m in _SELENIUM_BY_RE.finditer(code):
        by_name, selector = m.group(1), m.group(3)
        strategy = _BY_TO_STRATEGY.get(by_name, LocatorStrategy.CSS)
        found.append(
            ParsedLocator(
                raw=m.group(0),
                strategy=strategy,
                selector=selector,
                start=m.start(),
                end=m.end(),
            )
        )

    for m in _PLAYWRIGHT_ROLE_RE.finditer(code):
        role, name = m.group(2), m.group(4)
        found.append(
            ParsedLocator(
                raw=m.group(0),
                strategy=LocatorStrategy.ROLE_NAME,
                selector=f"role={role}[name='{name}']",
                start=m.start(),
                end=m.end(),
            )
        )

    for m in _PLAYWRIGHT_LOCATOR_RE.finditer(code):
        selector = m.group(2)
        strategy = _classify_selector(selector)
        found.append(
            ParsedLocator(
                raw=m.group(0),
                strategy=strategy,
                selector=selector,
                start=m.start(),
                end=m.end(),
            )
        )

    # De-duplicate by (strategy, selector, start) — Selenium wait patterns repeat.
    seen: set[tuple[str, str, int]] = set()
    unique: list[ParsedLocator] = []
    for loc in found:
        key = (loc.strategy.value, loc.selector, loc.start)
        if key in seen:
            continue
        seen.add(key)
        unique.append(loc)
    return unique


def _classify_selector(selector: str) -> LocatorStrategy:
    if _TESTID_RE.search(selector):
        return LocatorStrategy.DATA_TESTID
    if selector.startswith("//") or selector.startswith("/"):
        return LocatorStrategy.XPATH
    if selector.startswith("#"):
        return LocatorStrategy.ID
    if _ARIA_RE.search(selector):
        return LocatorStrategy.ARIA_LABEL
    return LocatorStrategy.CSS


def extract_signal(loc: ParsedLocator) -> LocatorSignal:
    """Pull normalized matching signals out of a parsed locator."""
    sel = loc.selector
    testid = _TESTID_RE.search(sel)
    aria = _ARIA_RE.search(sel)
    idm = _ID_CSS_RE.search(sel)
    text: str | None = None
    if loc.strategy == LocatorStrategy.ROLE_NAME and "name=" in sel:
        # role=button[name='Login'] → text is the name
        text = sel.split("name=", 1)[1].strip().strip("'\"[]")
    id_value = idm.group(1) if idm else (sel if loc.strategy == LocatorStrategy.ID else None)
    return LocatorSignal(
        testid=testid.group(1) if testid else None,
        id_value=id_value,
        aria=aria.group(1) if aria else None,
        text=text,
    )


# ── Native matcher (pure) ────────────────────────────────────────────────────
def _label_ratio(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _bbox_iou(a: dict | None, b: dict | None) -> float:
    """IoU of two bbox dicts ``{x, y, width, height}``."""
    if not a or not b:
        return 0.0
    try:
        ax1, ay1 = a["x"], a["y"]
        ax2, ay2 = ax1 + a["width"], ay1 + a["height"]
        bx1, by1 = b["x"], b["y"]
        bx2, by2 = bx1 + b["width"], by1 + b["height"]
    except (KeyError, TypeError):
        return 0.0
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (a["width"] * a["height"]) + (b["width"] * b["height"]) - inter
    return inter / union if union > 0 else 0.0


def _element_similarity(a: GUIElementView, b: GUIElementView) -> float:
    """How likely two GUI elements are the same control across versions."""
    label = _label_ratio(a.label, b.label)
    type_bonus = 0.2 if a.component_type == b.component_type else 0.0
    iou = _bbox_iou(a.bbox, b.bbox) if (a.bbox and b.bbox) else 0.0
    if label < 0.3:
        # Without textual correlation only a strong positional match counts.
        return iou * 0.5
    return label * 0.7 + type_bonus + iou * 0.1


class NativeMatcher:
    """Scores GUI elements as replacement candidates for a broken locator.

    Uses the OLD version's elements (``elements_a``) as a bridge: first resolve
    which control the broken locator pointed at, then find its counterpart in
    the new version by label/type/position similarity.  This lets a changed
    ``data-testid`` / ``id`` still heal correctly when the visible control is
    unchanged.
    """

    @staticmethod
    def target_exists(loc: ParsedLocator, elements: list[GUIElementView]) -> bool:
        """True if the locator's target still resolves in the new version."""
        sig = extract_signal(loc)
        for el in elements:
            if sig.testid and el.attributes.get("data-testid") == sig.testid:
                return True
            if sig.id_value and el.attributes.get("id") == sig.id_value:
                return True
            if sig.aria and el.attributes.get("aria-label") == sig.aria:
                return True
            if sig.text and el.label and _label_ratio(sig.text, el.label) >= 0.95:
                return True
        return False

    @staticmethod
    def resolve_original(loc: ParsedLocator, elements_a: list[GUIElementView]) -> tuple[GUIElementView | None, float]:
        """Which element the locator referred to in the old version."""
        sig = extract_signal(loc)
        for el in elements_a:
            if sig.testid and el.attributes.get("data-testid") == sig.testid:
                return el, 1.0
            if sig.id_value and el.attributes.get("id") == sig.id_value:
                return el, 1.0
            if sig.aria and el.attributes.get("aria-label") == sig.aria:
                return el, 1.0
        best: tuple[float, GUIElementView] | None = None
        for el in elements_a:
            r = _label_ratio(sig.text, el.label)
            if best is None or r > best[0]:
                best = (r, el)
        if best and best[0] >= 0.6:
            return best[1], best[0]
        return None, 0.0

    @staticmethod
    def match(
        loc: ParsedLocator,
        elements_a: list[GUIElementView],
        elements_b: list[GUIElementView],
    ) -> HealCandidate | None:
        orig, _orig_conf = NativeMatcher.resolve_original(loc, elements_a)
        if orig is None:
            return NativeMatcher._direct_match(loc, elements_b)

        best: tuple[float, GUIElementView] | None = None
        for el in elements_b:
            score = _element_similarity(orig, el)
            if best is None or score > best[0]:
                best = (score, el)

        if best is None or best[0] < 0.4:
            return None

        score, el = best
        new_strategy, new_locator = _build_replacement(el)
        return HealCandidate(
            new_locator=new_locator,
            new_strategy=new_strategy,
            confidence=round(min(score, 0.99), 3),
            method="native",
            element_id=el.component_id,
        )

    @staticmethod
    def _direct_match(loc: ParsedLocator, elements_b: list[GUIElementView]) -> HealCandidate | None:
        """Fallback when the original target cannot be resolved."""
        sig = extract_signal(loc)
        best: tuple[float, GUIElementView] | None = None
        for el in elements_b:
            score = (
                max(
                    _label_ratio(sig.text, el.label),
                    _label_ratio(sig.id_value, el.label),
                    _label_ratio(sig.testid, el.label),
                    _label_ratio(sig.aria, el.label),
                )
                * 0.9
            )
            if best is None or score > best[0]:
                best = (score, el)
        if best is None or best[0] < 0.4:
            return None
        score, el = best
        new_strategy, new_locator = _build_replacement(el)
        return HealCandidate(
            new_locator=new_locator,
            new_strategy=new_strategy,
            confidence=round(min(score, 0.99), 3),
            method="native",
            element_id=el.component_id,
        )


def _build_replacement(el: GUIElementView) -> tuple[LocatorStrategy, str]:
    """Choose the most stable locator strategy available for an element."""
    attrs = el.attributes
    if attrs.get("data-testid"):
        return LocatorStrategy.DATA_TESTID, f"[data-testid='{attrs['data-testid']}']"
    if attrs.get("role") and el.label:
        return LocatorStrategy.ROLE_NAME, f"role={attrs['role']}[name='{el.label}']"
    if attrs.get("aria-label"):
        return LocatorStrategy.ARIA_LABEL, f"[aria-label='{attrs['aria-label']}']"
    if attrs.get("id"):
        return LocatorStrategy.ID, f"#{attrs['id']}"
    if el.label:
        return LocatorStrategy.CSS, f"text='{el.label}'"
    return LocatorStrategy.CSS, el.component_type


# ── Service (async orchestration + DB) ────────────────────────────────────────
class SelfHealingService:
    """Identify broken locators between two GUI versions and propose fixes."""

    def __init__(
        self,
        session: AsyncSession,
        llm_gateway: LLMGateway | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.session = session
        self.llm_gateway = llm_gateway
        self.confidence_threshold = confidence_threshold

    # -- data loading -------------------------------------------------------
    async def _load_gui_elements(self, version: str) -> list[GUIElementView]:
        try:
            analysis_id = uuid.UUID(str(version))
        except (ValueError, AttributeError):
            return []
        res = await self.session.execute(select(GUIComponent).where(GUIComponent.analysis_id == analysis_id))
        return [GUIElementView.from_component(c) for c in res.scalars().all()]

    async def _load_ui_test_codes(self, project_id: uuid.UUID) -> list[TestCode]:
        res = await self.session.execute(
            select(TestCode)
            .join(TestCase, TestCode.test_case_id == TestCase.id)
            .join(AnalysisResult, TestCase.analysis_result_id == AnalysisResult.id)
            .where(AnalysisResult.project_id == project_id)
            .where(func.lower(TestCode.framework).in_(UI_FRAMEWORKS))
        )
        return list(res.scalars().all())

    # -- core ---------------------------------------------------------------
    async def _analyze(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        version_a: str,
        version_b: str,
    ) -> tuple[list[HealingItem], dict, HealingStatus]:
        import time

        started = time.monotonic()
        elements_a = await self._load_gui_elements(version_a)
        elements_b = await self._load_gui_elements(version_b)
        test_codes = await self._load_ui_test_codes(project_id)

        items: list[HealingItem] = []
        healthy = 0
        healed = 0
        needs_review = 0
        failed = 0
        confidences: list[float] = []

        for tc in test_codes:
            for loc in parse_locators(tc.code):
                # Anti false-positive: target still resolves -> skip.
                if NativeMatcher.target_exists(loc, elements_b):
                    healthy += 1
                    continue

                candidate = await self._find_replacement(loc, elements_a, elements_b, tc)
                item = self._build_item(tc, tenant_id, loc, candidate)
                items.append(item)

                if candidate is None:
                    failed += 1
                elif candidate.confidence >= self.confidence_threshold:
                    healed += 1
                    confidences.append(candidate.confidence)
                else:
                    needs_review += 1
                    confidences.append(candidate.confidence)

        total = healthy + len(items)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        duration = time.monotonic() - started

        if not items:
            status = HealingStatus.HEALED  # nothing broken
        elif failed == len(items):
            status = HealingStatus.FAILED
        elif needs_review == 0 and failed == 0:
            status = HealingStatus.HEALED
        else:
            status = HealingStatus.NEEDS_REVIEW

        for it in items:
            it.tenant_id = tenant_id

        stats = {
            "total": total,
            "healthy": healthy,
            "healed": healed,
            "needs_review": needs_review,
            "failed": failed,
            "avg_confidence": round(avg_conf, 3),
            "duration_s": round(duration, 3),
        }
        return items, stats, status

    async def heal(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        version_a: str,
        version_b: str,
    ) -> HealingReport:
        """Create + persist a HealingReport for a fresh run (direct / test path)."""
        items, stats, status = await self._analyze(project_id, tenant_id, version_a, version_b)
        report = HealingReport(
            project_id=project_id,
            tenant_id=tenant_id,
            version_a=version_a,
            version_b=version_b,
            status=status,
            stats=stats,
        )
        report.items = items
        self.session.add(report)
        await self.session.flush()
        return report

    async def fill_report(self, report: HealingReport) -> HealingReport:
        """Fill an existing (PENDING) report with analysis results (task path)."""
        items, stats, status = await self._analyze(
            report.project_id, report.tenant_id, report.version_a, report.version_b
        )
        report.items = items
        report.stats = stats
        report.status = status
        return report

    async def _find_replacement(
        self,
        loc: ParsedLocator,
        elements_a: list[GUIElementView],
        elements_b: list[GUIElementView],
        tc: TestCode,
    ) -> HealCandidate | None:
        native = NativeMatcher.match(loc, elements_a, elements_b)
        llm = await self._llm_reconstruct(loc, tc, elements_b)
        return self._merge(native, llm)

    async def _llm_reconstruct(
        self,
        loc: ParsedLocator,
        tc: TestCode,
        elements_b: list[GUIElementView],
    ) -> HealCandidate | None:
        if self.llm_gateway is None:
            return None
        try:
            menu = [
                {
                    "type": e.component_type,
                    "label": e.label,
                    "attributes": e.attributes,
                }
                for e in elements_b[:25]
            ]
            prompt = (
                "A UI test locator no longer resolves after a GUI change. "
                "Pick the single best replacement from the detected components "
                "and return ONLY compact JSON: "
                '{"new_locator": str, "new_strategy": one of '
                "data-testid|role+name|aria-label|id|css|xpath, "
                '"confidence": 0..1}.\n\n'
                f"Broken locator ({loc.strategy.value}): {loc.selector}\n"
                f"Test framework: {tc.framework}\n"
                f"Components in new version:\n{json.dumps(menu, ensure_ascii=False)}"
            )
            resp = await self.llm_gateway.complete(
                provider=LLMProvider.OPENAI,
                messages=[LLMMessage(role="user", content=prompt)],
                max_tokens=256,
                temperature=0.1,
                module="self_healing",
                task_type="locator_reconstruct",
            )
            return _parse_llm_candidate(resp.content)
        except Exception:
            logger.warning("LLM locator reconstruction failed", exc_info=True)
            return None

    @staticmethod
    def _merge(native: HealCandidate | None, llm: HealCandidate | None) -> HealCandidate | None:
        if native is None and llm is None:
            return None
        if native is None:
            return llm
        if llm is None:
            return native
        # Agreement → hybrid boost.
        if llm.new_strategy == native.new_strategy and llm.new_locator == native.new_locator:
            return HealCandidate(
                new_locator=native.new_locator,
                new_strategy=native.new_strategy,
                confidence=round(min(0.99, max(native.confidence, llm.confidence) + 0.05), 3),
                method="hybrid",
                element_id=native.element_id,
            )
        # Disagreement → keep the higher-confidence one, native preferred on tie.
        if llm.confidence > native.confidence + 0.05:
            return llm
        return native

    def _build_item(
        self,
        tc: TestCode,
        tenant_id: uuid.UUID,
        loc: ParsedLocator,
        candidate: HealCandidate | None,
    ) -> HealingItem:
        if candidate is None:
            return HealingItem(
                tenant_id=tenant_id,
                test_code_id=tc.id,
                old_locator=loc.selector,
                old_strategy=loc.strategy,
                new_locator=None,
                new_strategy=None,
                confidence=0.0,
                healing_method="native",
                status=HealingStatus.FAILED,
                diff_preview=None,
            )
        status = (
            HealingStatus.HEALED if candidate.confidence >= self.confidence_threshold else HealingStatus.NEEDS_REVIEW
        )
        diff = f"- {loc.selector}\n+ {candidate.new_locator}"
        return HealingItem(
            tenant_id=tenant_id,
            test_code_id=tc.id,
            old_locator=loc.selector,
            old_strategy=loc.strategy,
            new_locator=candidate.new_locator,
            new_strategy=candidate.new_strategy,
            confidence=candidate.confidence,
            healing_method=candidate.method,
            status=status,
            diff_preview=diff,
        )

    # -- decision flow (accept/reject) --------------------------------------
    async def apply_decision(self, item: HealingItem, action: str) -> tuple[HealingItem, bool]:
        """Apply an accept/reject decision. Returns (item, applied_to_test_code)."""
        if action == "reject":
            item.status = HealingStatus.REJECTED
            return item, False

        # accept
        if item.new_locator is None:
            item.status = HealingStatus.FAILED
            return item, False

        tc_res = await self.session.execute(select(TestCode).where(TestCode.id == item.test_code_id))
        tc = tc_res.scalars().one_or_none()
        applied = False
        if tc is not None:
            tc.code = _replace_locator_in_code(tc.code, item.old_locator, item.new_locator)
            applied = True
        item.status = HealingStatus.HEALED
        return item, applied


def _parse_llm_candidate(raw: str) -> HealCandidate | None:
    """Parse the gateway response into a candidate, tolerating code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # strip an optional language tag line
        text = text.split("\n", 1)[1] if "\n" in text else text
    # Find the JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    try:
        strategy = LocatorStrategy(str(data["new_strategy"]))
    except (KeyError, ValueError):
        return None
    confidence = float(data.get("confidence", 0.0))
    return HealCandidate(
        new_locator=str(data.get("new_locator", "")).strip(),
        new_strategy=strategy,
        confidence=max(0.0, min(1.0, confidence)),
        method="llm",
    )


def _replace_locator_in_code(code: str, old_selector: str, new_locator: str) -> str:
    """Replace the first occurrence of a broken selector value in test code."""
    if not old_selector:
        return code
    return code.replace(old_selector, new_locator, 1)
