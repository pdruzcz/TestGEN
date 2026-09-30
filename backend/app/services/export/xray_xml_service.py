"""Generator XML zgodnego z Jira Xray Generic Import — Story 6.8, AC3 (FR46).

Struktura: <testCases><testCase> z elementami summary/description/priority/
testType, krokami (<steps><step><action>/<result>), etykietami (<labels>)
i polami niestandardowymi (<customFields>).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.services.export.tms_common import (
    PRIORITY_TO_TMS,
    TYPE_TO_XRAY,
    XRAY_TYPE_DEFAULT,
    as_text,
    mapped_value,
)


def _sub(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = text
    return element


def render(
    rows: list[dict[str, Any]],
    field_mapping: dict[str, str] | None = None,
) -> bytes:
    """Renderuje test case'y do XML Xray Generic Import."""
    root = ET.Element("testCases")

    for row in rows:
        tc = ET.SubElement(root, "testCase")

        summary = mapped_value(row, "summary", "title", field_mapping)
        description = mapped_value(row, "description", "description", field_mapping)
        priority = str(mapped_value(row, "priority", "priority", field_mapping))
        test_type = str(row.get("type", ""))

        _sub(tc, "summary", as_text(summary))
        _sub(tc, "description", as_text(description))
        _sub(tc, "priority", PRIORITY_TO_TMS.get(priority, as_text(priority)))
        _sub(tc, "testType", TYPE_TO_XRAY.get(test_type, XRAY_TYPE_DEFAULT))

        preconditions = as_text(
            mapped_value(row, "preconditions", "preconditions", field_mapping)
        )
        if preconditions:
            _sub(tc, "preconditions", preconditions)

        # Kroki testowe — oczekiwany rezultat na ostatnim kroku (AC3)
        steps_value = mapped_value(row, "steps", "steps", field_mapping)
        steps = steps_value if isinstance(steps_value, list) else [as_text(steps_value)]
        steps = [step for step in steps if step]
        expected = as_text(
            mapped_value(row, "expected_result", "expected_result", field_mapping)
        )
        steps_el = ET.SubElement(tc, "steps")
        for index, action in enumerate(steps, start=1):
            step_el = ET.SubElement(steps_el, "step", index=str(index))
            _sub(step_el, "action", str(action))
            _sub(step_el, "data")
            _sub(step_el, "result", expected if index == len(steps) else "")
        if not steps and expected:
            step_el = ET.SubElement(steps_el, "step", index="1")
            _sub(step_el, "action", as_text(description) or as_text(summary))
            _sub(step_el, "data")
            _sub(step_el, "result", expected)

        # Etykiety (AC3)
        labels_value = mapped_value(row, "labels", "tags", field_mapping)
        labels = labels_value if isinstance(labels_value, list) else []
        if labels:
            labels_el = ET.SubElement(tc, "labels")
            for label in labels:
                _sub(labels_el, "label", str(label))

        # Pola niestandardowe (AC3)
        custom_el = ET.SubElement(tc, "customFields")
        for name, key in (
            ("TestGEN ID", "id"),
            ("Moduł", "module"),
            ("Framework", "framework"),
            ("Status", "status"),
        ):
            value = as_text(row.get(key, ""))
            if value:
                ET.SubElement(custom_el, "customField", name=name, value=value)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
