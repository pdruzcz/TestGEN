"""Unit tests for GUI user-flow reconstruction — Story 3.9.

These exercise the pure-Python matching + action inference without ``scipy`` /
``numpy`` (greedy fallback path) and the LLM prompt helpers.
"""

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.flow_reconstructor import (
    ACTION_BUTTON_CLICK,
    ACTION_INPUT_FILL,
    ACTION_NAVIGATION,
    ACTION_UNKNOWN,
    ComponentMatch,
    GUIFlowReconstructor,
    ScreenAnalysis,
    UserAction,
    _label_similarity,
    _levenshtein,
    best_action,
    detect_actions,
    match_components,
)
from app.services.analysis.gui.llm_prompt import build_flow_prompt, parse_flow_response
from app.services.analysis.gui.models import BBox, DetectedComponent


def _comp(ctype, x, y, w=80, h=30, label=None):
    return DetectedComponent(
        component_type=ctype,
        bbox=BBox(x=x, y=y, width=w, height=h),
        confidence=0.9,
        label=label,
    )


class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("zaloguj", "zaloguj") == 0

    def test_empty(self):
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3

    def test_substitution(self):
        assert _levenshtein("kot", "kox") == 1


class TestLabelSimilarity:
    def test_identical_labels(self):
        assert _label_similarity("Zaloguj", "zaloguj") == 1.0

    def test_disjoint(self):
        assert _label_similarity("Zaloguj", "Wyloguj") < 1.0

    def test_missing_label(self):
        assert _label_similarity(None, "x") == 0.0
        assert _label_similarity(None, None) == 0.0


class TestMatchComponents:
    def test_matches_same_position_and_type(self):
        a = [_comp(GUIComponentType.BUTTON, 10, 10, label="Dalej")]
        b = [_comp(GUIComponentType.BUTTON, 10, 10, label="Dalej")]
        matches = match_components(a, b)
        assert len(matches) == 1
        assert matches[0].confidence >= 0.6

    def test_empty_inputs(self):
        assert match_components([], []) == []

    def test_no_match_when_far_apart_and_different(self):
        a = [_comp(GUIComponentType.BUTTON, 0, 0, label="Dalej")]
        b = [_comp(GUIComponentType.INPUT, 900, 900, label="Email")]
        assert match_components(a, b) == []


class TestDetectActions:
    def test_button_disappears_is_click(self):
        a = [_comp(GUIComponentType.BUTTON, 10, 10, label="Zaloguj")]
        b = [_comp(GUIComponentType.INPUT, 500, 500, label="Pole")]
        actions = detect_actions(a, b, matches=[])
        assert any(act.action_type == ACTION_BUTTON_CLICK for act in actions)

    def test_input_label_change_is_fill(self):
        a = [_comp(GUIComponentType.INPUT, 10, 10, label="")]
        b = [_comp(GUIComponentType.INPUT, 10, 10, label="jan@x.pl")]
        matches = [ComponentMatch(index_a=0, index_b=0, confidence=0.9)]
        actions = detect_actions(a, b, matches=matches)
        assert any(act.action_type == ACTION_INPUT_FILL for act in actions)

    def test_high_pixel_diff_is_navigation(self):
        actions = detect_actions([], [], matches=[], pixel_diff_ratio=0.8)
        assert any(act.action_type == ACTION_NAVIGATION for act in actions)


class TestBestAction:
    def test_empty_is_unknown(self):
        assert best_action([]).action_type == ACTION_UNKNOWN

    def test_navigation_wins_over_click(self):
        actions = [
            UserAction(ACTION_BUTTON_CLICK, "x", 0.9, "click"),
            UserAction(ACTION_NAVIGATION, None, 0.5, "nav"),
        ]
        assert best_action(actions).action_type == ACTION_NAVIGATION


class TestReconstructor:
    def test_single_screen_warns(self):
        screens = [ScreenAnalysis(screenshot_id="s1", sequence=0, components=[])]
        result = GUIFlowReconstructor().reconstruct(screens)
        assert result.steps == []
        assert result.warnings

    def test_two_screens_one_step(self):
        s1 = ScreenAnalysis(
            screenshot_id="s1",
            sequence=0,
            components=[_comp(GUIComponentType.BUTTON, 10, 10, label="Dalej")],
        )
        s2 = ScreenAnalysis(
            screenshot_id="s2",
            sequence=1,
            components=[_comp(GUIComponentType.INPUT, 500, 500, label="Email")],
        )
        result = GUIFlowReconstructor().reconstruct(screens=[s2, s1], name="Logowanie")
        assert result.name == "Logowanie"
        assert len(result.steps) == 1
        step = result.steps[0]
        assert step.source_screenshot_id == "s1"
        assert step.next_screenshot_id == "s2"


class TestLLMPrompt:
    def test_build_prompt_contains_screens(self):
        screens = ["Ekran 0: button:Dalej"]

        class _S:
            sequence = 1
            action_type = "button_click"
            target_element = "Dalej"

        prompt = build_flow_prompt(screens, [_S()])
        assert "Ekran 0" in prompt
        assert "krok 1" in prompt

    def test_parse_valid_json(self):
        out = parse_flow_response('{"1": "Kliknięcie Dalej", "2": "Wpisanie email"}')
        assert out == {1: "Kliknięcie Dalej", 2: "Wpisanie email"}

    def test_parse_with_markdown_fence(self):
        out = parse_flow_response('```json\n{"1": "akcja"}\n```')
        assert out == {1: "akcja"}

    def test_parse_garbage_returns_empty(self):
        assert parse_flow_response("brak json") == {}
        assert parse_flow_response("") == {}
