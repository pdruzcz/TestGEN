"""Testy jednostkowe generatorów eksportu do TMS — Story 6.8 (FR46)."""

import json
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from app.services.export import (
    generic_json_service,
    testrail_csv_service,
    xray_xml_service,
)
from app.services.export.tms_common import slugify, steps_list
from app.services.export.tms_common import test_case_row as build_row


def _make_tc(**overrides) -> SimpleNamespace:
    base = dict(
        id="11111111-2222-3333-4444-555555555555",
        title="Logowanie użytkownika — ścieżka pozytywna",
        description="Weryfikacja logowania; dane poprawne & aktywne konto",
        preconditions="Użytkownik istnieje w bazie",
        steps={"items": ["Otwórz stronę logowania", "Wpisz dane", "Kliknij Zaloguj"]},
        expected_result="Użytkownik zalogowany, przekierowanie na dashboard",
        priority="CRITICAL",
        type="SECURITY",
        framework="PYTEST",
        status="READY",
        source_class="AuthController",
        source_function="login",
        source_endpoint="/api/login",
        tags=["auth", "smoke"],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture()
def rows() -> list[dict]:
    return [
        build_row(_make_tc()),
        build_row(
            _make_tc(
                id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                title="Walidacja brzegowa pól",
                priority="LOW",
                type="BOUNDARY",
                steps="Krok pierwszy\nKrok drugi",
                tags=None,
                source_class=None,
            )
        ),
    ]


class TestTmsCommon:
    def test_steps_list_variants(self):
        assert steps_list({"items": ["a", "b"]}) == ["a", "b"]
        assert steps_list("x\ny") == ["x", "y"]
        assert steps_list(None) == []

    def test_slugify_polish(self):
        assert slugify("Mój Projekt Żółty!") == "moj-projekt-zolty"
        assert slugify("###") == "projekt"

    def test_row_module_fallback(self, rows):
        assert rows[0]["module"] == "AuthController"
        assert rows[1]["module"] == "login"


class TestTestRailCsv:
    def test_bom_semicolon_and_headers(self, rows):
        data = testrail_csv_service.render(rows)
        text = data.decode("utf-8")
        assert text.startswith("\ufeff")
        header = text.lstrip("\ufeff").splitlines()[0]
        assert header == "Title;Section;Priority;Type;Preconds;Steps;Expected Result;References"

    def test_priority_and_type_mapping(self, rows):
        text = testrail_csv_service.render(rows).decode("utf-8")
        assert "Critical" in text
        assert "Security" in text
        assert "Functional" in text  # BOUNDARY → Functional
        assert "Low" in text

    def test_semicolon_in_value_is_quoted(self):
        row = build_row(_make_tc(title="Tytuł; ze średnikiem"))
        text = testrail_csv_service.render([row]).decode("utf-8")
        assert '"Tytuł; ze średnikiem"' in text

    def test_field_mapping_override(self, rows):
        text = testrail_csv_service.render(
            rows, field_mapping={"section": "source_function"}
        ).decode("utf-8")
        assert ";login;" in text


class TestXrayXml:
    def test_valid_xml_with_steps_and_labels(self, rows):
        data = xray_xml_service.render(rows)
        assert data.startswith(b"<?xml")
        root = ET.fromstring(data)
        assert root.tag == "testCases"
        cases = root.findall("testCase")
        assert len(cases) == 2

        first = cases[0]
        assert first.findtext("summary") == "Logowanie użytkownika — ścieżka pozytywna"
        assert first.findtext("testType") == "Security"
        assert first.findtext("priority") == "Critical"
        steps = first.find("steps").findall("step")
        assert len(steps) == 3
        assert steps[0].findtext("action") == "Otwórz stronę logowania"
        # oczekiwany rezultat na ostatnim kroku
        assert steps[-1].findtext("result").startswith("Użytkownik zalogowany")
        labels = [el.text for el in first.find("labels").findall("label")]
        assert labels == ["auth", "smoke"]

    def test_custom_fields_and_generic_type(self, rows):
        root = ET.fromstring(xray_xml_service.render(rows))
        second = root.findall("testCase")[1]
        assert second.findtext("testType") == "Generic"
        custom = {
            el.get("name"): el.get("value")
            for el in second.find("customFields").findall("customField")
        }
        assert custom["Moduł"] == "login"
        assert custom["Framework"] == "PYTEST"


class TestGenericJson:
    def test_structure_snake_case_utf8(self, rows):
        payload = json.loads(generic_json_service.render(rows).decode("utf-8"))
        assert payload["total"] == 2
        first = payload["test_cases"][0]
        assert set(first.keys()) == {
            "id",
            "title",
            "description",
            "steps",
            "expected_result",
            "priority",
            "type",
            "module",
            "tags",
        }
        assert first["steps"] == [
            "Otwórz stronę logowania",
            "Wpisz dane",
            "Kliknij Zaloguj",
        ]
        assert first["title"] == "Logowanie użytkownika — ścieżka pozytywna"

    def test_pretty_printed(self, rows):
        text = generic_json_service.render(rows).decode("utf-8")
        assert '\n  "test_cases"' in text
