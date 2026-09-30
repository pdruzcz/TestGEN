"""Unit tests for OCRService + orchestrator graceful degradation — Story 3.8, AC6."""

import builtins

from app.services.analysis.gui.models import BBox, DetectedComponent, TextBlock
from app.services.analysis.gui.ocr_service import OCRService
from app.services.analysis.gui.orchestrator import GUIAnalyzerOrchestrator


def _block_imports(monkeypatch, names):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in names:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


class TestOCRServiceDegradation:
    def test_no_engines_returns_warnings(self, monkeypatch):
        _block_imports(monkeypatch, {"pytesseract", "easyocr"})
        blocks, warnings = OCRService().extract_text(object())
        assert blocks == []
        assert any("Tesseract" in w for w in warnings)
        assert any("EasyOCR" in w for w in warnings)


class _StubOCR:
    def extract_text(self, image):
        return [TextBlock("OK", BBox(0, 0, 10, 10), 0.9)], []


class _StubDetector:
    def detect_components(self, image, text_blocks):
        from app.models.gui_screenshot import GUIComponentType

        return [
            DetectedComponent(GUIComponentType.BUTTON, BBox(0, 0, 100, 40), 0.8, label="OK")
        ], []


class _StubLayout:
    def analyze(self, components, text_blocks, image_size):
        from app.services.analysis.gui.models import LayoutTreeNode

        return LayoutTreeNode(type="screen"), []


class TestOrchestrator:
    def test_no_decoder_returns_partial(self, monkeypatch):
        _block_imports(monkeypatch, {"cv2", "numpy", "PIL"})
        out = GUIAnalyzerOrchestrator().analyze(b"not-an-image")
        assert out.components == []
        assert out.text_blocks == []
        assert any("dekod" in w.lower() for w in out.warnings)
        assert out.processing_time_ms >= 0

    def test_pipeline_with_stubs(self, monkeypatch):
        # Make decode succeed by faking it.
        monkeypatch.setattr(
            "app.services.analysis.gui.orchestrator.decode_image",
            lambda data: (object(), (800, 600), None),
        )
        orch = GUIAnalyzerOrchestrator(
            ocr_service=_StubOCR(),
            component_detector=_StubDetector(),
            layout_analyzer=_StubLayout(),
        )
        out = orch.analyze(b"img")
        assert len(out.text_blocks) == 1
        assert len(out.components) == 1
        assert out.layout_tree is not None
        assert out.layout_tree.type == "screen"
