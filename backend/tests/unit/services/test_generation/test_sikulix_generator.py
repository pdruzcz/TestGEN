"""Unit tests for Story 3.13 — SikuliX (image-based) code generator."""

import io

import pytest

from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry
from app.services.test_generation.codegen.sikulix_generator import SikuliXCodeGenerator
from app.services.test_generation.pattern_cropper import (
    CroppedPattern,
    crop_all_components,
    crop_element,
)


@pytest.fixture
def generator():
    return SikuliXCodeGenerator(CodeGenConfig(framework="sikulix"))


class TestFactoryRegistration:
    def test_sikulix_registered_in_registry(self):
        registry = CodeGenRegistry.get_instance()
        assert registry.is_supported("sikulix")
        gen = registry.get_generator("sikulix")
        assert isinstance(gen, SikuliXCodeGenerator)

    def test_supported_frameworks_include_sikulix(self):
        assert "sikulix" in CodeGenRegistry.get_instance().supported_frameworks()


class TestSimilarity:
    def test_button_low_threshold(self, generator):
        assert generator._calculate_similarity({"component_type": "button"}) == 0.7

    def test_modal_high_threshold(self, generator):
        assert generator._calculate_similarity({"component_type": "modal"}) == 0.9

    def test_unknown_type_default(self, generator):
        assert generator._calculate_similarity({"component_type": "weird"}) == 0.8

    def test_none_component_default(self, generator):
        assert generator._calculate_similarity(None) == 0.8

    def test_low_ocr_confidence_bumps_threshold(self, generator):
        # input baza 0.75 + 0.05 (confidence < 0.5) = 0.8
        sim = generator._calculate_similarity({"component_type": "input", "confidence": 0.3})
        assert sim == 0.8

    def test_clamped_to_max(self, generator):
        sim = generator._calculate_similarity({"component_type": "modal", "confidence": 0.1})
        assert sim == 0.9


class TestPatternStatement:
    def test_pattern_statement_format(self, generator):
        stmt = generator._pattern_statement("button_ok.png", 0.8)
        assert stmt == 'Pattern("images/button_ok.png").similar(0.8)'

    def test_pattern_image_name(self, generator):
        name = generator._pattern_image_name(
            {"component_type": "button", "label": "Login Submit"}, {}
        )
        assert name == "button_login_submit.png"

    def test_pattern_image_name_strips_diacritics(self, generator):
        # Znaki diakrytyczne sa usuwane (sanityzacja do [a-z0-9_]).
        name = generator._pattern_image_name(
            {"component_type": "button", "label": "Zaloguj się"}, {}
        )
        assert name == "button_zaloguj_si.png"

    def test_pattern_image_name_explicit(self, generator):
        name = generator._pattern_image_name({"pattern_image": "custom.png"}, {})
        assert name == "custom.png"


class TestStepMapping:
    def test_click(self, generator):
        op, meta = generator._map_step_to_operation(
            {"action": "click", "component": {"component_type": "button", "label": "OK"}}
        )
        assert op == 'self.s.click(Pattern("images/button_ok.png").similar(0.7))'
        assert meta["name"] == "button_ok.png"

    def test_type(self, generator):
        op, _ = generator._map_step_to_operation(
            {"action": "type", "value": "admin", "component": {"component_type": "input", "label": "Login"}}
        )
        assert op == 'self.s.type(Pattern("images/input_login.png").similar(0.75), "admin")'

    def test_wait(self, generator):
        op, _ = generator._map_step_to_operation(
            {"action": "wait", "component": {"component_type": "modal", "label": "Dialog"}}
        )
        assert op == 'self.s.wait(Pattern("images/modal_dialog.png").similar(0.9), 10)'

    def test_assert_exists(self, generator):
        op, _ = generator._map_step_to_operation(
            {"action": "assert_exists", "component": {"component_type": "label", "label": "Sukces"}}
        )
        assert op.startswith("assert exists(")
        assert "is not None" in op

    def test_assert_vanish(self, generator):
        op, _ = generator._map_step_to_operation(
            {"action": "assert_vanish", "component": {"component_type": "icon", "label": "Loading"}}
        )
        assert op.startswith("self.s.waitVanish(")

    def test_unknown_action_comment(self, generator):
        op, meta = generator._map_step_to_operation({"action": "frobnicate"})
        assert op.startswith("# nieobslugiwana akcja")
        assert meta is None


class TestGenerateTestFile:
    def test_generates_script_with_class_and_flow(self, generator):
        tc = {
            "title": "Login Flow",
            "steps": [
                {"action": "click", "component": {"component_type": "button", "label": "Login"}},
                {"action": "type", "value": "haslo", "component": {"component_type": "input", "label": "Password"}},
                {"action": "assert_exists", "component": {"component_type": "label", "label": "Dashboard"}},
            ],
        }
        result = generator.generate_test_file([tc])
        assert result.framework == "sikulix"
        assert result.language == "python"
        assert "from sikuli import *" in result.content
        assert "class LoginFlow" in result.content
        assert "def testFlow(self):" in result.content
        assert "self.s.click(" in result.content
        assert result.file_path == "tests/sikuli/login_flow/login_flow.py"
        # patterny zebrane w fixtures (dedup po nazwie)
        names = {p["name"] for p in result.fixtures}
        assert "button_login.png" in names
        assert "input_password.png" in names

    def test_empty_test_cases(self, generator):
        result = generator.generate_test_file([])
        assert "from sikuli import *" in result.content
        assert result.module_name == "empty"

    def test_dedupes_patterns(self, generator):
        tc = {
            "title": "Powtórka",
            "steps": [
                {"action": "click", "component": {"component_type": "button", "label": "OK"}},
                {"action": "assert_exists", "component": {"component_type": "button", "label": "OK"}},
            ],
        }
        result = generator.generate_test_file([tc])
        names = [p["name"] for p in result.fixtures]
        assert names.count("button_ok.png") == 1


class TestValidateSyntax:
    def test_valid_script(self, generator):
        tc = {"title": "Test", "steps": [{"action": "click", "component": {"component_type": "button", "label": "X"}}]}
        result = generator.generate_test_file([tc])
        assert result.compilation_result is not None
        assert result.compilation_result.success is True

    def test_empty_code_fails(self, generator):
        res = generator.validate_syntax("")
        assert res.success is False

    def test_missing_import_fails(self, generator):
        res = generator.validate_syntax("class Foo:\n    def testFlow(self):\n        pass\n")
        assert res.success is False
        assert "import" in res.error_message


class TestAssertionHelper:
    def test_exists_assertion(self, generator):
        out = generator.generate_assertion("success.png", "", "exists", "Brak sukcesu")
        assert out.startswith("assert exists(")
        assert "Brak sukcesu" in out

    def test_vanish_assertion(self, generator):
        out = generator.generate_assertion("spinner.png", "", "vanish")
        assert out.startswith("self.s.waitVanish(")


def _png_bytes(width: int = 100, height: int = 80) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPatternCropper:
    @pytest.fixture(autouse=True)
    def _require_pillow(self):
        pytest.importorskip("PIL", reason="Pillow nie jest zainstalowany w tym srodowisku")

    def test_crop_element_returns_png(self):
        data = _png_bytes(200, 200)
        cropped = crop_element(data, {"x": 10, "y": 10, "w": 50, "h": 40})
        from PIL import Image

        img = Image.open(io.BytesIO(cropped))
        assert img.size == (50, 40)

    def test_crop_element_x1y1x2y2_format(self):
        data = _png_bytes(200, 200)
        cropped = crop_element(data, {"x": 0, "y": 0, "x2": 30, "y2": 20})
        from PIL import Image

        img = Image.open(io.BytesIO(cropped))
        assert img.size == (30, 20)

    def test_crop_clamps_to_image_bounds(self):
        data = _png_bytes(100, 100)
        cropped = crop_element(data, {"x": 90, "y": 90, "w": 50, "h": 50})
        from PIL import Image

        img = Image.open(io.BytesIO(cropped))
        assert img.size == (10, 10)

    def test_crop_invalid_bbox_raises(self):
        data = _png_bytes(100, 100)
        with pytest.raises(ValueError):
            crop_element(data, {"x": 0, "y": 0, "w": 0, "h": 0})

    def test_crop_all_components(self):
        data = _png_bytes(300, 300)
        components = [
            {"component_type": "button", "label": "Login", "bbox": {"x": 0, "y": 0, "w": 40, "h": 20}},
            {"component_type": "input", "label": "User", "bbox": {"x": 50, "y": 50, "w": 60, "h": 25}},
            {"component_type": "icon", "label": "skip", "bbox": "not-a-dict"},
        ]
        patterns = crop_all_components(data, components)
        assert len(patterns) == 2
        assert all(isinstance(p, CroppedPattern) for p in patterns)
        assert patterns[0].name == "button_login.png"
        assert patterns[1].name == "input_user.png"
