"""Unit tests for the visual-regression engine — Epic 3, Story 3.10.

Covers the pure-Python paths (semantic diff, change classification, status
derivation) plus the graceful-degradation behaviour of the optional pixel-diff /
diff-image stages, and the Playwright / Cypress test-code generation.
"""

from app.models.gui_screenshot import GUIComponentType
from app.models.visual_regression import ComparisonStatus
from app.services.analysis.gui.models import BBox, DetectedComponent
from app.services.analysis.gui.visual_regression import (
    CHANGE_ADDED,
    CHANGE_MOVED,
    CHANGE_REMOVED,
    CHANGE_TEXT,
    SEVERITY_BREAKING,
    SEVERITY_VISUAL,
    VisualRegressionEngine,
    classify_status,
    compute_component_delta,
    compute_pixel_diff,
    generate_diff_image,
)
from app.services.test_generation.visual_regression_codegen import (
    generate_visual_regression_code,
)


def _comp(ctype, x, y, w=20, h=10, label=None):
    return DetectedComponent(
        component_type=ctype,
        bbox=BBox(x=x, y=y, width=w, height=h),
        confidence=0.9,
        label=label,
    )


class TestComputePixelDiff:
    def test_returns_zero_when_image_missing(self):
        pct, warning = compute_pixel_diff(None, None)
        assert pct == 0.0
        assert warning is not None

    def test_warns_when_numpy_missing(self, monkeypatch):
        # Force the no-numpy degrade path regardless of whether numpy is
        # installed (it is present under the imaging dep group, used by the
        # golden-regression CI stage). compute_pixel_diff imports numpy lazily,
        # so blocking __import__ exercises the ImportError branch.
        import builtins

        real_import = builtins.__import__

        def _block_numpy(name, *args, **kwargs):
            if name == "numpy":
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_numpy)
        pct, warning = compute_pixel_diff(object(), object())
        assert pct == 0.0
        assert warning is not None


class TestComputeComponentDelta:
    def test_detects_added_and_removed(self):
        baseline = [_comp(GUIComponentType.BUTTON, 0, 0, label="OK")]
        comparison = [_comp(GUIComponentType.INPUT, 100, 100, label="Email")]
        deltas = compute_component_delta(baseline, comparison)
        change_types = {d.change_type for d in deltas}
        assert CHANGE_REMOVED in change_types
        assert CHANGE_ADDED in change_types

    def test_removed_button_is_breaking(self):
        baseline = [_comp(GUIComponentType.BUTTON, 0, 0, label="Wyślij")]
        deltas = compute_component_delta(baseline, [])
        removed = [d for d in deltas if d.change_type == CHANGE_REMOVED]
        assert removed and removed[0].severity == SEVERITY_BREAKING

    def test_text_change_detected(self):
        baseline = [_comp(GUIComponentType.LINK, 0, 0, label="Zaloguj")]
        comparison = [_comp(GUIComponentType.LINK, 0, 0, label="Wyloguj")]
        deltas = compute_component_delta(baseline, comparison)
        assert any(d.change_type == CHANGE_TEXT for d in deltas)

    def test_moderate_move_is_visual(self):
        baseline = [_comp(GUIComponentType.LINK, 0, 0, label="Menu")]
        comparison = [_comp(GUIComponentType.LINK, 10, 0, label="Menu")]
        deltas = compute_component_delta(baseline, comparison)
        moved = [d for d in deltas if d.change_type == CHANGE_MOVED]
        assert moved and moved[0].severity == SEVERITY_VISUAL

    def test_identical_components_no_delta(self):
        baseline = [_comp(GUIComponentType.LINK, 0, 0, label="Menu")]
        comparison = [_comp(GUIComponentType.LINK, 0, 0, label="Menu")]
        assert compute_component_delta(baseline, comparison) == []


class TestClassifyStatus:
    def test_match_when_no_changes(self):
        assert classify_status(0.0, [], 0.02) == ComparisonStatus.MATCH

    def test_major_when_breaking(self):
        baseline = [_comp(GUIComponentType.BUTTON, 0, 0, label="Wyślij")]
        deltas = compute_component_delta(baseline, [])
        assert classify_status(1.0, deltas, 0.02) == ComparisonStatus.MAJOR_DIFF

    def test_major_when_high_pixel_diff(self):
        assert classify_status(35.0, [], 0.02) == ComparisonStatus.MAJOR_DIFF

    def test_minor_diff_when_deltas_present(self):
        baseline = [_comp(GUIComponentType.LINK, 0, 0, label="Menu")]
        comparison = [_comp(GUIComponentType.LINK, 10, 0, label="Menu")]
        deltas = compute_component_delta(baseline, comparison)
        assert classify_status(1.0, deltas, 0.02) == ComparisonStatus.MINOR_DIFF


class TestGenerateDiffImage:
    def test_returns_none_without_baseline(self):
        image, warning = generate_diff_image(None, [])
        assert image is None
        assert warning is None

    def test_warns_when_cv2_missing(self):
        image, warning = generate_diff_image(object(), [])
        assert image is None
        assert warning is not None


class TestVisualRegressionEngine:
    def test_compare_semantic_only(self):
        engine = VisualRegressionEngine()
        baseline = [_comp(GUIComponentType.BUTTON, 0, 0, label="Wyślij")]
        comparison = []
        result = engine.compare(None, None, baseline, comparison)
        assert result.status == ComparisonStatus.MAJOR_DIFF
        assert any(d.change_type == CHANGE_REMOVED for d in result.deltas)
        assert result.warnings  # pixel diff skipped warning

    def test_semantic_diff_payload_shape(self):
        engine = VisualRegressionEngine()
        baseline = [_comp(GUIComponentType.LINK, 0, 0, label="Zaloguj")]
        comparison = [_comp(GUIComponentType.LINK, 0, 0, label="Wyloguj")]
        result = engine.compare(None, None, baseline, comparison)
        payload = result.semantic_diff_payload()
        assert payload and "change_type" in payload[0] and "severity" in payload[0]


class TestCodeGeneration:
    def _result(self):
        engine = VisualRegressionEngine()
        baseline = [_comp(GUIComponentType.LINK, 0, 0, label="Zaloguj")]
        comparison = [_comp(GUIComponentType.LINK, 0, 0, label="Wyloguj")]
        return engine.compare(None, None, baseline, comparison)

    def test_playwright_output(self):
        code = generate_visual_regression_code(self._result(), "playwright", "login", "/login", 0.02)
        assert "@playwright/test" in code
        assert "toHaveScreenshot" in code
        assert "maxDiffPixelRatio: 0.02" in code

    def test_cypress_output(self):
        code = generate_visual_regression_code(self._result(), "cypress", "login", "/login", 0.02)
        assert "matchImageSnapshot" in code
        assert "failureThreshold: 0.02" in code

    def test_empty_changes_still_generates_guard_test(self):
        engine = VisualRegressionEngine()
        same = [_comp(GUIComponentType.LINK, 0, 0, label="Menu")]
        result = engine.compare(None, None, same, list(same))
        code = generate_visual_regression_code(result, "playwright", "home")
        assert "toHaveScreenshot" in code

    def test_unknown_framework_raises(self):
        try:
            generate_visual_regression_code(self._result(), "selenium")
        except ValueError as exc:
            assert "selenium" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected ValueError for unknown framework")
