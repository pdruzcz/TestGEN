"""Unit tests for Story 3-13-domknięcie — SikuliX pipeline linkage (AC2).

TestStep↔GUIComponent linkage resolution is the pure, DB-free core of the
pipeline. These tests exercise ``index_components`` + ``resolve_step_component``
without any database or MinIO — the integration of fetch→crop→PNG is covered in
``tests/integration/test_sikulix_pipeline.py`` (image-gated).
"""

from app.services.test_generation.sikulix_pipeline import (
    index_components,
    resolve_step_component,
)

_BBOX = {"x": 0, "y": 0, "w": 40, "h": 20}


def _db_components() -> list[dict]:
    return [
        {
            "id": "c1",
            "component_type": "input",
            "label": "User",
            "bbox": {"x": 0, "y": 0, "w": 60, "h": 25},
            "confidence": 0.9,
            "storage_key": "tenant/proj/gui/shot_a.png",
        },
        {
            "id": "c2",
            "component_type": "button",
            "label": "Login Submit",
            "bbox": _BBOX,
            "confidence": 0.95,
            "storage_key": "tenant/proj/gui/shot_b.png",
        },
        {
            "id": "c3",
            "component_type": "button",
            "label": "Zaloguj się",
            "bbox": _BBOX,
            "confidence": 0.8,
            "storage_key": "tenant/proj/gui/shot_c.png",
        },
    ]


class TestIndexComponents:
    def test_indexes_by_id_and_label(self):
        by_id, by_label = index_components(_db_components())
        assert "c1" in by_id
        assert by_id["c1"]["component_type"] == "input"
        # label klucz sanityzowany (lower, diakrytyki/whitespace -> "_")
        assert "login_submit" in by_label
        assert "zaloguj_si" in by_label

    def test_skips_components_without_id(self):
        comps = [{"component_type": "button", "label": "OK", "bbox": _BBOX}]
        by_id, by_label = index_components(comps)
        assert by_id == {}
        assert "ok" in by_label


class TestResolveStepComponent:
    def test_explicit_component_with_bbox_is_kept(self):
        step = {
            "action": "click",
            "component": {"component_type": "button", "label": "OK", "bbox": _BBOX},
        }
        resolved = resolve_step_component(step, {}, {})
        assert resolved is not None
        assert resolved["component_type"] == "button"
        assert isinstance(resolved["bbox"], dict)

    def test_explicit_component_without_bbox_falls_through(self):
        # Inline component bez bbox nie jest użyteczny dla cropu → spróbuj innych ścieżek.
        step = {
            "action": "click",
            "component": {"component_type": "button"},
            "component_id": "c1",
        }
        by_id, _ = index_components(_db_components())
        resolved = resolve_step_component(step, by_id, {})
        assert resolved["component_type"] == "input"
        assert resolved["storage_key"] == "tenant/proj/gui/shot_a.png"

    def test_component_id_resolves_to_db_component(self):
        by_id, by_label = index_components(_db_components())
        step = {"action": "type", "component_id": "c1", "value": "admin"}
        resolved = resolve_step_component(step, by_id, by_label)
        assert resolved["component_type"] == "input"
        assert resolved["label"] == "User"
        assert resolved["bbox"] == {"x": 0, "y": 0, "w": 60, "h": 25}
        assert resolved["storage_key"] == "tenant/proj/gui/shot_a.png"

    def test_component_id_accepts_uuid_string(self):
        by_id, _ = index_components(_db_components())
        step = {"action": "click", "component_id": "c2"}
        resolved = resolve_step_component(step, by_id, {})
        assert resolved["label"] == "Login Submit"

    def test_label_match_via_target(self):
        _, by_label = index_components(_db_components())
        step = {"action": "click", "target": "Login Submit"}
        resolved = resolve_step_component(step, {}, by_label)
        assert resolved["component_type"] == "button"
        assert resolved["storage_key"] == "tenant/proj/gui/shot_b.png"

    def test_label_match_via_target_element_key(self):
        _, by_label = index_components(_db_components())
        step = {"action": "click", "target_element": "Login Submit"}
        resolved = resolve_step_component(step, {}, by_label)
        assert resolved is not None

    def test_label_match_strips_diacritics_and_whitespace(self):
        _, by_label = index_components(_db_components())
        step = {"action": "click", "target": "Zaloguj się"}
        resolved = resolve_step_component(step, {}, by_label)
        assert resolved is not None
        assert resolved["storage_key"] == "tenant/proj/gui/shot_c.png"

    def test_unknown_component_id_falls_through_to_label(self):
        by_id, by_label = index_components(_db_components())
        step = {"action": "click", "component_id": "nope", "target": "User"}
        resolved = resolve_step_component(step, by_id, by_label)
        assert resolved["component_type"] == "input"

    def test_no_match_returns_none(self):
        by_id, by_label = index_components(_db_components())
        step = {"action": "click", "target": "Nieistniejący"}
        assert resolve_step_component(step, by_id, by_label) is None

    def test_empty_step_returns_none(self):
        assert resolve_step_component({}, {}, {}) is None
