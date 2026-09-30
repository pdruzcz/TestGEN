"""Unit tests for the DOM/HTML source extractor — Story 1.51-zakończenie (FR69/FR18).

The extractor is the GUI-source sibling of :class:`ComponentDetector`: it turns
HTML views/templates into :class:`DetectedComponent` carrying the real locator
attributes (``data-testid``, ``id``, ``aria-label``, ``role``, ``name``) that
``SelfHealingService`` reads. Pure Python + BeautifulSoup stdlib parser — no
``cv2``/``lxml`` dependency.
"""

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.dom_extractor import (
    DOMComponentExtractor,
    parse_a11y_json,
)


def _attrs(html: str, **kw):
    return {c.attributes.get("tag"): c for c in DOMComponentExtractor().extract(html, **kw)}


class TestContractKeys:
    """Story Testy backend #1 + #2 — locator contract keys are produced."""

    def test_data_testid_extracted(self):
        comps = DOMComponentExtractor().extract('<button data-testid="login-submit">Zaloguj</button>')
        assert len(comps) == 1
        assert comps[0].attributes["data-testid"] == "login-submit"
        assert comps[0].attributes["tag"] == "button"

    def test_all_locator_keys_present(self):
        comps = DOMComponentExtractor().extract(
            '<input id="email" name="email" aria-label="Adres e-mail" data-testid="email-input" />'
        )
        assert len(comps) == 1
        attrs = comps[0].attributes
        for key in ("id", "name", "aria-label", "data-testid", "tag"):
            assert key in attrs, f"missing contract key: {key}"
        assert attrs["id"] == "email"
        assert attrs["name"] == "email"
        assert attrs["aria-label"] == "Adres e-mail"

    def test_implicit_role_for_button(self):
        comps = DOMComponentExtractor().extract("<button>X</button>")
        assert comps[0].attributes["role"] == "button"

    def test_explicit_role_overrides_implicit(self):
        comps = DOMComponentExtractor().extract('<div role="menu">Plik</div>')
        assert comps[0].attributes["role"] == "menu"


class TestTypeMapping:
    def test_button_tag_maps_to_button(self):
        assert _attrs("<button>OK</button>")["button"].component_type == GUIComponentType.BUTTON

    def test_anchor_maps_to_link(self):
        assert _attrs('<a href="/">Home</a>')["a"].component_type == GUIComponentType.LINK

    def test_input_checkbox(self):
        comps = DOMComponentExtractor().extract('<input type="checkbox" name="agree" />')
        assert comps[0].component_type == GUIComponentType.CHECKBOX

    def test_input_submit_is_button(self):
        comps = DOMComponentExtractor().extract('<input type="submit" value="Wyślij" />')
        assert comps[0].component_type == GUIComponentType.BUTTON

    def test_select_maps_to_dropdown(self):
        assert _attrs("<select><option>a</option></select>")["select"].component_type == GUIComponentType.DROPDOWN

    def test_role_menuitem_maps_to_menu(self):
        comps = DOMComponentExtractor().extract('<li role="menuitem">Otwórz</li>')
        assert comps[0].component_type == GUIComponentType.MENU


class TestLabelFallback:
    def test_label_prefers_text(self):
        comps = DOMComponentExtractor().extract('<button data-testid="x" aria-label="Akceptuj">Zatwierdź</button>')
        assert comps[0].label == "Zatwierdź"

    def test_label_falls_back_to_aria(self):
        comps = DOMComponentExtractor().extract('<button aria-label="Zamknij"></button>')
        assert comps[0].label == "Zamknij"

    def test_label_falls_back_to_name(self):
        comps = DOMComponentExtractor().extract('<input name="username" />')
        assert comps[0].label == "username"


class TestDedup:
    def test_double_matched_element_not_duplicated(self):
        # Matches both `button` and `[data-testid]` selectors — must emit once.
        comps = DOMComponentExtractor().extract('<button data-testid="save">Zapisz</button>')
        assert len(comps) == 1


class TestA11yMerge:
    """Story Testy backend #5 — axe-core a11y dump adds semantic role/name."""

    def test_a11y_merges_role_by_testid(self):
        html = '<div data-testid="panel"></div>'
        a11y = {"nodes": [{"data-testid": "panel", "role": "region", "name": "Panel główny"}]}
        comps = DOMComponentExtractor().extract(html, a11y_json=a11y)
        assert comps[0].attributes["role"] == "region"
        assert comps[0].attributes["text"] == "Panel główny"

    def test_a11y_merges_name_by_label(self):
        html = "<button>Zaloguj</button>"
        a11y = {"nodes": [{"role": "button", "name": "Zaloguj"}]}
        comps = DOMComponentExtractor().extract(html, a11y_json=a11y)
        assert comps[0].attributes["role"] == "button"

    def test_parse_a11y_json_handles_bad_input(self):
        assert parse_a11y_json(None) is None
        assert parse_a11y_json("not json") is None
        assert parse_a11y_json('{"nodes": []}') == {"nodes": []}


class TestGracefulDegrade:
    """Story Testy backend #7 — no interactive elements → empty, no exception."""

    def test_static_html_yields_no_components(self):
        comps = DOMComponentExtractor().extract("<html><body><h1>Tytuł</h1><p>Tekst bez interakcji.</p></body></html>")
        assert comps == []

    def test_empty_html_yields_empty(self):
        assert DOMComponentExtractor().extract("") == []
        assert DOMComponentExtractor().extract("   ") == []

    def test_malformed_html_does_not_raise(self):
        # Unclosed tags / garbage must not crash the parser.
        comps = DOMComponentExtractor().extract("<button><div")
        assert isinstance(comps, list)


class TestBboxNone:
    """DOM sources carry no geometry — bbox must be None (merge adds it later)."""

    def test_bbox_is_none(self):
        comps = DOMComponentExtractor().extract("<button>X</button>")
        assert comps[0].bbox is None
        assert comps[0].confidence == 1.0
