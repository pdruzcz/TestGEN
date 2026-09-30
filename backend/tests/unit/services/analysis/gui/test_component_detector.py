"""Unit tests for the pure-Python component classification — Story 3.8, AC4.

These exercise :func:`classify_region` and :class:`ComponentDetector` without any
``cv2`` dependency (graceful degradation, AC6).
"""

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.component_detector import (
    ComponentDetector,
    classify_region,
)
from app.services.analysis.gui.models import BBox, TextBlock


class TestClassifyRegion:
    def test_small_square_is_checkbox(self):
        ctype, conf = classify_region(BBox(x=10, y=10, width=20, height=20))
        assert ctype == GUIComponentType.CHECKBOX
        assert conf > 0.5

    def test_explicit_marker_is_checkbox(self):
        ctype, _ = classify_region(BBox(x=0, y=0, width=200, height=40), is_square_marker=True)
        assert ctype == GUIComponentType.CHECKBOX

    def test_button_keyword(self):
        ctype, conf = classify_region(BBox(x=0, y=0, width=120, height=40), text="Zapisz")
        assert ctype == GUIComponentType.BUTTON
        assert conf >= 0.65

    def test_menu_keyword_wide(self):
        ctype, _ = classify_region(BBox(x=0, y=0, width=400, height=30), text="Plik Edycja Widok")
        assert ctype == GUIComponentType.MENU

    def test_wide_thin_bar_is_menu(self):
        ctype, _ = classify_region(BBox(x=0, y=0, width=600, height=32))
        assert ctype == GUIComponentType.MENU

    def test_empty_wide_short_is_input(self):
        ctype, conf = classify_region(BBox(x=0, y=0, width=180, height=36))
        assert ctype == GUIComponentType.INPUT
        assert conf >= 0.5

    def test_large_region_is_form(self):
        ctype, _ = classify_region(BBox(x=0, y=0, width=400, height=400))
        assert ctype == GUIComponentType.FORM

    def test_unknown_fallback(self):
        ctype, conf = classify_region(BBox(x=0, y=0, width=3, height=300))
        assert ctype == GUIComponentType.UNKNOWN
        assert conf <= 0.3


class TestComponentDetectorDegradation:
    def test_no_cv2_returns_warning(self, monkeypatch):
        # Force the optional cv2 import to fail inside _cv2_regions.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in ("cv2", "numpy"):
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        detector = ComponentDetector()
        components, warnings = detector.detect_components(object(), [TextBlock("X", BBox(0, 0, 1, 1))])
        assert components == []
        assert any("OpenCV" in w for w in warnings)
