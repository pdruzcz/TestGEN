"""DOM/HTML source extractor for GUI analysis — Story 1.51-zakończenie (FR69/FR18).

Parses HTML views/templates (and optionally an axe-core ``a11y.json`` dump) into
:class:`DetectedComponent` instances carrying **real locator attributes**
(``data-testid``, ``id``, ``aria-label``, ``role``, ``name``) — the contract
:class:`~app.services.generators.self_healing.SelfHealingService` reads via
``GUIElementView.from_component``.

This is the GUI-source sibling of the screenshot pipeline
(:class:`~app.services.analysis.gui.component_detector.ComponentDetector`).
HTML analysed as GUI arrives **only** through the GUI/DOM upload channel
(origin-based routing, Story 1.51-zakańczenie A1): ``.html`` routed as
documentation still goes to the E2 ``HTMLParser`` and ``.html`` in a code bundle
stays code — neither reaches this extractor.

Uses BeautifulSoup with the stdlib ``html.parser``. ``lxml`` is intentionally
avoided (not a backend dependency) so no new install is required.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.models import DetectedComponent

logger = logging.getLogger(__name__)

# Interactive / landmark selectors — anything a locator could target. A single
# element can match several selectors (e.g. ``button`` + ``[data-testid]``);
# see :meth:`DOMComponentExtractor.extract` for deduplication.
INTERACTIVE_SELECTOR = "a, button, input, select, textarea, form, label, [role], [data-testid], [aria-label], [onclick]"

_TAG_TYPE_MAP: dict[str, GUIComponentType] = {
    "a": GUIComponentType.LINK,
    "button": GUIComponentType.BUTTON,
    "input": GUIComponentType.INPUT,
    "select": GUIComponentType.DROPDOWN,
    "textarea": GUIComponentType.INPUT,
    "form": GUIComponentType.FORM,
    "label": GUIComponentType.UNKNOWN,
    "table": GUIComponentType.TABLE,
}

# ARIA / implicit-HTML roles → GUIComponentType (explicit ``role`` wins over tag).
_ROLE_TYPE_MAP: dict[str, GUIComponentType] = {
    "button": GUIComponentType.BUTTON,
    "link": GUIComponentType.LINK,
    "textbox": GUIComponentType.INPUT,
    "checkbox": GUIComponentType.CHECKBOX,
    "radio": GUIComponentType.RADIO,
    "menu": GUIComponentType.MENU,
    "menuitem": GUIComponentType.MENU,
    "tab": GUIComponentType.TAB,
    "combobox": GUIComponentType.DROPDOWN,
    "listbox": GUIComponentType.DROPDOWN,
    "dialog": GUIComponentType.MODAL,
    "table": GUIComponentType.TABLE,
    "form": GUIComponentType.FORM,
}

_IMPLICIT_ROLE: dict[str, str] = {
    "a": "link",
    "button": "button",
    "input": "textbox",
    "select": "combobox",
    "textarea": "textbox",
}

# Implicit role of an ``<input>`` depends on its ``type`` attribute.
_INPUT_IMPLICIT_ROLE: dict[str, str] = {
    "checkbox": "checkbox",
    "radio": "radio",
    "submit": "button",
    "button": "button",
    "reset": "button",
}


def parse_a11y_json(raw: str | bytes | None) -> dict[str, Any] | None:
    """Best-effort parse of an a11y.json (axe-core) dump.

    Returns the parsed object/list, or ``None`` on empty/invalid input so callers
    can treat it as "no a11y data" without exception handling.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict | list) else None


class DOMComponentExtractor:
    """Extract interactive HTML elements with locator attributes for self-healing."""

    INTERACTIVE = INTERACTIVE_SELECTOR

    def extract(self, html: str, a11y_json: dict[str, Any] | None = None) -> list[DetectedComponent]:
        """Return one :class:`DetectedComponent` per interactive HTML element.

        ``bbox`` is always ``None`` (HTML carries no geometry); merging with a
        screenshot's CV geometry happens in the analysis task. ``a11y_json``
        optionally supplies semantic ``role``/``name`` from an axe-core dump.
        """
        if not html or not html.strip():
            return []
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:  # pragma: no cover - defensive, bs4 is lenient
            logger.warning("DOM parse failed: %s", exc)
            return []

        comps: list[DetectedComponent] = []
        seen: set[tuple[str, str]] = set()
        for el in soup.select(self.INTERACTIVE):
            if not isinstance(el, Tag):
                continue
            attrs = self._element_attributes(el)
            if not attrs:
                continue
            key = self._dedup_key(el, attrs)
            if key in seen:
                continue
            seen.add(key)
            comps.append(
                DetectedComponent(
                    component_type=self._map_type(el, attrs),
                    label=attrs.get("text") or attrs.get("aria-label") or attrs.get("name"),
                    bbox=None,
                    confidence=1.0,
                    attributes=attrs,
                )
            )

        if a11y_json:
            self._merge_a11y(comps, a11y_json)
        return comps

    # -- helpers ------------------------------------------------------------
    def _effective_role(self, el: Tag) -> str | None:
        """Effective ARIA role: explicit ``role`` wins, else implicit (input-type aware)."""
        explicit = el.get("role")
        if explicit:
            return explicit
        tag = el.name or ""
        if tag == "input":
            itype = (el.get("type") or "text").lower()
            return _INPUT_IMPLICIT_ROLE.get(itype, "textbox")
        return _IMPLICIT_ROLE.get(tag)

    def _element_attributes(self, el: Tag) -> dict[str, str]:
        """Build the locator-attribute dict, dropping empty values."""
        text = (el.get_text(strip=True) or "")[:200]
        attrs = {
            "id": el.get("id"),
            "data-testid": el.get("data-testid"),
            "aria-label": el.get("aria-label"),
            "aria-labelledby": el.get("aria-labelledby"),
            "name": el.get("name"),
            "role": self._effective_role(el),
            "text": text or None,
            "tag": el.name,
        }
        return {k: v for k, v in attrs.items() if v}

    def _map_type(self, el: Tag, attrs: dict[str, str]) -> GUIComponentType:
        """Map to GUIComponentType via the (effective) role, else the tag fallback."""
        role = attrs.get("role")
        if role and role in _ROLE_TYPE_MAP:
            return _ROLE_TYPE_MAP[role]
        return _TAG_TYPE_MAP.get(el.name or "", GUIComponentType.UNKNOWN)

    def _dedup_key(self, el: Tag, attrs: dict[str, str]) -> tuple[str, str]:
        """Stable identity so a multi-selector match emits one component."""
        primary = (
            attrs.get("id")
            or attrs.get("data-testid")
            or attrs.get("name")
            or attrs.get("aria-label")
            or attrs.get("text")
            or ""
        )
        return (el.name or "", primary)

    def _merge_a11y(self, comps: list[DetectedComponent], a11y_json: dict[str, Any]) -> None:
        """Merge semantic ``role``/``name`` from an axe-core accessibility dump.

        Accepts ``{"nodes": [...]}`` or a bare list of node objects. Matching is
        best-effort: by ``data-testid`` first, then by ``name`` ↔ component label.
        """
        nodes = a11y_json.get("nodes") if isinstance(a11y_json, dict) else a11y_json
        if not isinstance(nodes, list):
            return
        by_testid: dict[str, DetectedComponent] = {
            c.attributes["data-testid"]: c for c in comps if c.attributes.get("data-testid")
        }
        for node in nodes:
            if not isinstance(node, dict):
                continue
            role = node.get("role")
            name = node.get("name")
            if not (role or name):
                continue
            tid = node.get("data-testid")
            target = by_testid.get(tid) if tid else None
            if target is None and name:
                # An a11y node "name" is frequently the element's aria-label.
                target = next(
                    (c for c in comps if c.attributes.get("aria-label") == name),
                    None,
                )
            if target is None and name:
                target = next((c for c in comps if c.label and c.label == name), None)
            if target is None:
                continue
            if role:
                target.attributes["role"] = role
            if name and not target.attributes.get("text"):
                target.attributes["text"] = name
                if not target.label:
                    target.label = name
