"""Playwright code generator — Story 1.41.

Generuje pliki testowe Playwright (.spec.ts / .py / .java / .cs) z test case'ow:
- Semantyczne selektory: getByRole, getByText, getByPlaceholder, getByTestId
- Auto-waiting (brak explicit waits — Playwright wbudowane)
- test.describe / test() / expect() struktura
- Network interceptors: page.route() z mockowaniem API
- Trace: test.use({ trace: 'on-first-retry' })
- 4 jezyki: TypeScript (default), Python, Java, C#
- Walidacja selektorow: preferencja semantycznych nad XPath
- Walidacja skladniowa (strukturalna)

AC: 1-12
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.test_generation.codegen.base import (
    BaseTestCodeGenerator,
    CodeGenConfig,
    CompilationResult,
    TestCodeFile,
    register_generator,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "playwright"

# ════════════════════════════════════════════════════════════════════════
# Mapowania skladni per jezyk
# ════════════════════════════════════════════════════════════════════════

# Importy Playwright per jezyk
IMPORTS_PER_LANGUAGE: dict[str, list[str]] = {
    "typescript": [
        "import { test, expect } from '@playwright/test';",
    ],
    "python": [
        "from playwright.sync_api import sync_playwright, expect",
    ],
    "java": [
        "import com.microsoft.playwright.*;",
        "import com.microsoft.playwright.options.*;",
        "import org.junit.jupiter.api.*;",
        "import static org.junit.jupiter.api.Assertions.*;",
    ],
    "csharp": [
        "using Microsoft.Playwright;",
        "using NUnit.Framework;",
        "using System.Threading.Tasks;",
    ],
}

# Rozszerzenia plikow per jezyk
FILE_EXTENSIONS: dict[str, str] = {
    "typescript": ".spec.ts",
    "python": ".py",
    "java": ".java",
    "csharp": ".cs",
}

# Expectation templates per language
EXPECT_TEMPLATES: dict[str, dict[str, str]] = {
    "typescript": {
        "toBeVisible": "await expect({locator}).toBeVisible();",
        "toHaveText": "await expect({locator}).toHaveText({expected});",
        "toContainText": "await expect({locator}).toContainText({expected});",
        "toHaveURL": "await expect(page).toHaveURL({expected});",
        "toBeEnabled": "await expect({locator}).toBeEnabled();",
    },
    "python": {
        "toBeVisible": "expect({locator}).to_be_visible()",
        "toHaveText": "expect({locator}).to_have_text({expected})",
        "toContainText": "expect({locator}).to_contain_text({expected})",
        "toHaveURL": "expect(page).to_have_url({expected})",
        "toBeEnabled": "expect({locator}).to_be_enabled()",
    },
    "java": {
        "toBeVisible": "assertThat({locator}).isVisible();",
        "toHaveText": "assertThat({locator}).hasText({expected});",
        "toContainText": "assertThat({locator}).containsText({expected});",
        "toHaveURL": "assertThat(page).hasURL({expected});",
        "toBeEnabled": "assertThat({locator}).isEnabled();",
    },
    "csharp": {
        "toBeVisible": "await Expect({locator}).ToBeVisibleAsync();",
        "toHaveText": "await Expect({locator}).ToHaveTextAsync({expected});",
        "toContainText": "await Expect({locator}).ToContainTextAsync({expected});",
        "toHaveURL": "await Expect(Page).ToHaveURLAsync({expected});",
        "toBeEnabled": "await Expect({locator}).ToBeEnabledAsync();",
    },
}

# Kategoria selektora (semantyczne, css, xpath)
SELECTOR_CATEGORIES = {
    "role": "semantic",
    "text": "semantic",
    "placeholder": "semantic",
    "label": "semantic",
    "alt": "semantic",
    "title": "semantic",
    "testId": "semantic",
    "testid": "semantic",
    "css": "css",
    "id": "css",
    "class": "css",
    "name": "css",
    "xpath": "xpath",
}


@register_generator("playwright")
class PlaywrightCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego Playwright (TypeScript/Python/Java/C#).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "playwright".

    Filozofia Playwright: auto-waiting, semantyczne selektory,
    network interceptors, trace na first-retry.
    """

    FRAMEWORK = "playwright"
    LANGUAGE = "typescript"
    FILE_EXTENSION = ".spec.ts"

    def __init__(self, config: CodeGenConfig | None = None):
        if config is None:
            config = CodeGenConfig(
                framework="playwright",
                language="typescript",
                file_extension=".spec.ts",
            )
        super().__init__(config)
        self._jinja_env: Environment | None = None

    # ── Wlasciwosc: Jinja2 environment (lazy) ──

    @property
    def jinja_env(self) -> Environment:
        """Jinja2 environment — inicjalizowane leniwie."""
        if self._jinja_env is None:
            templates_dir = self.config.templates_dir or TEMPLATES_DIR
            if not templates_dir.exists():
                logger.warning("Katalog szablonow Playwright nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── Wlasciwosc: jezyk z configu ──

    def _get_language(self, config: CodeGenConfig | None = None) -> str:
        """Pobierz jezyk generowania."""
        cfg = config or self.config
        language = cfg.language.lower()
        if language in ("c#", "cs", "csharp"):
            return "csharp"
        if language in ("java",):
            return "java"
        if language in ("python", "py"):
            return "python"
        if language in ("typescript", "ts", "javascript", "js"):
            return "typescript"
        # Default dla Playwright = typescript
        return "typescript"

    # ════════════════════════════════════════════════════════════════
    # 1.3 generate_test_file — glowna metoda
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy Playwright z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (typ e2e/system)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem Playwright
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        language = self._get_language(cfg)
        first_tc = test_cases[0]

        # Nazwa modulu / feature
        module_name = self._extract_module_name(first_tc)
        feature_name = self._make_feature_name(module_name)

        # 1.4 Importy Playwright
        imports = self._build_imports(test_cases, cfg, language)

        # 1.10 Trace config
        trace_config = self._generate_trace_config(language)

        # Task 2: Network interceptors
        route_mocks = self._extract_route_mocks(test_cases)

        # Ekstrahuj elementy GUI i user flow
        ui_elements = self._extract_ui_elements(test_cases)
        user_flows = self._extract_user_flows(test_cases)

        # Task 3: Walidacja selektorow
        selector_validation = self._validate_selectors(ui_elements)
        selector_warnings = [
            f"Selektor XPath dla '{c['element']}': preferuj getByRole/getByText nad XPath"
            for c in selector_validation
            if c["category"] == "xpath"
        ]

        # Generuj test cases per language
        generated_test_cases = []
        for i, tc in enumerate(test_cases):
            flow = user_flows[i] if i < len(user_flows) else None
            tc_data = self._generate_test_case(tc, flow, language)
            generated_test_cases.append(tc_data)

        # Renderuj kod
        file_ext = FILE_EXTENSIONS.get(language, ".spec.ts")
        file_path = self._build_file_path(module_name, file_ext)

        # Proboj szablon, fallback na string building
        content = self._render_code(
            feature_name=feature_name,
            imports=imports,
            trace_config=trace_config,
            route_mocks=route_mocks,
            test_cases=generated_test_cases,
            language=language,
        )

        # Walidacja kompilacji (Task 6)
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)
            if selector_warnings:
                if compilation_result.warnings is None:
                    compilation_result.warnings = []
                compilation_result.warnings.extend(selector_warnings)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=language,
            module_name=module_name,
            test_functions=generated_test_cases,
            imports=imports,
            compilation_result=compilation_result,
        )

    # ════════════════════════════════════════════════════════════════
    # generate_setup
    # ════════════════════════════════════════════════════════════════

    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj bazowy plik setup Playwright."""
        return "// Bazowy plik setup Playwright — rozszerz w konkretnych testach\n"

    # ════════════════════════════════════════════════════════════════
    # generate_assertion
    # ════════════════════════════════════════════════════════════════

    def generate_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        message: str | None = None,
    ) -> str:
        """Generuj pojedyncza asercje Playwright."""
        language = self._get_language()
        templates = EXPECT_TEMPLATES.get(language, EXPECT_TEMPLATES["typescript"])

        if comparison_type in ("text_equals", "text_contains"):
            key = "toHaveText" if comparison_type == "text_equals" else "toContainText"
            return templates[key].format(locator=actual, expected=f'"{expected}"')
        elif comparison_type == "element_visible":
            return templates["toBeVisible"].format(locator=actual)
        elif comparison_type == "url_contains":
            return templates["toHaveURL"].format(expected=f'"{expected}"')
        else:
            return templates["toBeVisible"].format(locator=actual)

    # ════════════════════════════════════════════════════════════════
    # Task 6: validate_syntax
    # ════════════════════════════════════════════════════════════════

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu Playwright (strukturalna)."""
        if not code.strip():
            return CompilationResult(
                success=False,
                code=code,
                error_message="Pusty kod",
                framework=self.FRAMEWORK,
            )

        language = self._get_language()
        warnings: list[str] = []
        errors: list[str] = []

        # Walidacja specyficzna Playwright
        playwright_markers = {
            "typescript": ["test(", "expect(", "page."],
            "python": ["test_", "expect(", "page."],
            "java": ["@Test", "assertThat", "page."],
            "csharp": ["[Test]", "Expect(", "Page."],
        }
        markers = playwright_markers.get(language, playwright_markers["typescript"])
        for marker in markers:
            if marker not in code:
                warnings.append(f"Brak elementu Playwright: {marker}")

        # Sprawdz balans nawiasow
        open_braces = code.count("{")
        close_braces = code.count("}")
        if open_braces != close_braces:
            errors.append(f"Niezbalansowane nawiasy klamrowe: {{ = {open_braces}, }} = {close_braces}")

        open_parens = code.count("(")
        close_parens = code.count(")")
        if open_parens != close_parens:
            errors.append(f"Niezbalansowane nawiasy okragle: ( = {open_parens}, ) = {close_parens}")

        # Language-specific checks
        if language == "java":
            if "class " not in code:
                errors.append("Brak definicji klasy w kodzie Java")
            if "import " not in code:
                errors.append("Brak importow w kodzie Java")
        elif language == "csharp":
            if "class " not in code:
                errors.append("Brak definicji klasy w kodzie C#")
            if "using " not in code:
                errors.append("Brak dyrektyw using w kodzie C#")

        if errors:
            return CompilationResult(
                success=False,
                code=code,
                error_message="; ".join(errors),
                error_line=1,
                framework=self.FRAMEWORK,
                warnings=warnings,
            )

        return CompilationResult(
            success=True,
            code=code,
            framework=self.FRAMEWORK,
            warnings=warnings,
        )

    # ════════════════════════════════════════════════════════════════
    # Metody prywatne — Task 1: Core generator
    # ════════════════════════════════════════════════════════════════

    # ── 1.4 _build_imports ──

    def _build_imports(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
        language: str,
    ) -> list[str]:
        """Buduj liste importow Playwright per jezyk."""
        imports = list(IMPORTS_PER_LANGUAGE.get(language, IMPORTS_PER_LANGUAGE["typescript"]))

        # Importy z test case (dodatkowe)
        for tc in test_cases:
            tc_imports = tc.get("imports") or tc.get("usings")
            if isinstance(tc_imports, list):
                for imp in tc_imports:
                    if imp and imp not in imports:
                        imports.append(imp)

        return imports

    # ── 1.5 _generate_describe_block ──

    def _generate_describe_block(
        self,
        feature_name: str,
        test_cases_code: list[str],
        trace_config: str,
        route_mocks_code: str,
        language: str,
    ) -> str:
        """Tworzenie test.describe block."""
        if language == "typescript":
            parts = [f"test.describe('{feature_name}', () => {{"]
            if trace_config:
                parts.append(f"  {trace_config}")
            parts.append("")
            if route_mocks_code:
                parts.append(route_mocks_code)
                parts.append("")
            for tc_code in test_cases_code:
                parts.append(tc_code)
                parts.append("")
            parts.append("});")
            return "\n".join(parts)
        elif language == "python":
            parts = [f"# {feature_name}"]
            for tc_code in test_cases_code:
                parts.append(tc_code)
                parts.append("")
            return "\n".join(parts)
        elif language == "java":
            class_name = self._make_class_name(feature_name, language)
            parts = [f"public class {class_name} {{"]
            if route_mocks_code:
                parts.append(route_mocks_code)
            for tc_code in test_cases_code:
                parts.append(tc_code)
            parts.append("}")
            return "\n".join(parts)
        else:  # csharp
            class_name = self._make_class_name(feature_name, language)
            parts = ["[TestFixture]"]
            parts.append(f"public class {class_name} {{")
            for tc_code in test_cases_code:
                parts.append(tc_code)
            parts.append("}")
            return "\n".join(parts)

    # ── 1.6 _generate_test_case ──

    def _generate_test_case(
        self,
        test_case: dict[str, Any],
        user_flow: dict[str, Any] | None,
        language: str,
    ) -> dict[str, Any]:
        """Tworzenie pojedynczego test() z akcjami i expectations."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed_test"
        description = scenario

        url = ""
        if user_flow:
            url = user_flow.get("url", "")
        if not url:
            url = test_case.get("url") or test_case.get("target_url", "")

        # Mapowanie krokow na akcje Playwright
        steps = self._map_user_flow_to_actions(test_case, user_flow, language)

        # Expectations po akcjach
        expectations = self._generate_expectations(test_case, language)

        return {
            "description": description,
            "url": url,
            "steps": steps,
            "expectations": expectations,
            "scenario": scenario,
            "language": language,
        }

    # ── 1.7 _generate_locator ──

    def _generate_locator(self, element: dict[str, Any], language: str) -> dict[str, Any]:
        """Mapuj element GUI na selektor Playwright.

        Preferencja: getByRole > getByText > getByPlaceholder > getByTestId > locator() > XPath
        """
        locator_type = element.get("locator_type", "css").lower()
        locator_value = element.get("locator_value", "")
        element_name = element.get("name", "element")

        if language == "typescript":
            locator_code = self._generate_ts_locator(locator_type, locator_value, element)
        elif language == "python":
            locator_code = self._generate_py_locator(locator_type, locator_value, element)
        elif language == "java":
            locator_code = self._generate_java_locator(locator_type, locator_value, element)
        else:  # csharp
            locator_code = self._generate_csharp_locator(locator_type, locator_value, element)

        var_name = self._normalize_element_name(element_name, language)
        return {
            "name": var_name,
            "type": locator_type,
            "value": locator_value,
            "code": locator_code,
        }

    def _generate_ts_locator(self, locator_type: str, value: str, element: dict) -> str:
        """Selektor TypeScript Playwright."""
        if locator_type == "role":
            role_name = element.get("role_name", value)
            name_option = f", name: '{role_name}'" if element.get("role_name") else ""
            return f"page.getByRole('{value}'{name_option})"
        elif locator_type == "text":
            return f"page.getByText('{value}')"
        elif locator_type == "placeholder":
            return f"page.getByPlaceholder('{value}')"
        elif locator_type in ("testid", "testId"):
            return f"page.getByTestId('{value}')"
        elif locator_type == "label":
            return f"page.getByLabel('{value}')"
        elif locator_type == "alt":
            return f"page.getByAltText('{value}')"
        elif locator_type == "title":
            return f"page.getByTitle('{value}')"
        elif locator_type in ("css", "id", "class", "name"):
            if locator_type == "id":
                return f"page.locator('#{value}')"
            elif locator_type == "name":
                return f"page.locator('[name=\"{value}\"]')"
            else:
                return f"page.locator('{value}')"
        elif locator_type == "xpath":
            return f"page.locator('xpath={value}')"
        else:
            return f"page.locator('{value}')"

    def _generate_py_locator(self, locator_type: str, value: str, element: dict) -> str:
        """Selektor Python Playwright."""
        if locator_type == "role":
            role_name = element.get("role_name", value)
            name_opt = f', name="{role_name}"' if element.get("role_name") else ""
            return f'page.get_by_role("{value}"{name_opt})'
        elif locator_type == "text":
            return f'page.get_by_text("{value}")'
        elif locator_type == "placeholder":
            return f'page.get_by_placeholder("{value}")'
        elif locator_type in ("testid", "testId"):
            return f'page.get_by_test_id("{value}")'
        elif locator_type in ("css", "id", "class", "name"):
            if locator_type == "id":
                return f'page.locator("#{value}")'
            elif locator_type == "name":
                return f"page.locator('[name=\"{value}\"]')"
            return f'page.locator("{value}")'
        elif locator_type == "xpath":
            return f'page.locator("xpath={value}")'
        else:
            return f'page.locator("{value}")'

    def _generate_java_locator(self, locator_type: str, value: str, element: dict) -> str:
        """Selektor Java Playwright."""
        if locator_type == "role":
            role_name = element.get("role_name", value)
            name_opt = f'.setName("{role_name}")' if element.get("role_name") else ""
            return f"page.getByRole(AriaRole.{value.upper()}{name_opt})"
        elif locator_type == "text":
            return f'page.getByText("{value}")'
        elif locator_type == "placeholder":
            return f'page.getByPlaceholder("{value}")'
        elif locator_type in ("testid", "testId"):
            return f'page.getByTestId("{value}")'
        elif locator_type == "xpath":
            return f'page.locator("xpath={value}")'
        else:
            return f'page.locator("{value}")'

    def _generate_csharp_locator(self, locator_type: str, value: str, element: dict) -> str:
        """Selektor C# Playwright."""
        if locator_type == "role":
            role_name = element.get("role_name", value)
            name_opt = f', new() {{ Name = "{role_name}" }}' if element.get("role_name") else ""
            return f"Page.GetByRole(AriaRole.{value.capitalize()}{name_opt})"
        elif locator_type == "text":
            return f'Page.GetByText("{value}")'
        elif locator_type == "placeholder":
            return f'Page.GetByPlaceholder("{value}")'
        elif locator_type in ("testid", "testId"):
            return f'Page.GetByTestId("{value}")'
        elif locator_type == "xpath":
            return f'Page.Locator("xpath={value}")'
        else:
            return f'Page.Locator("{value}")'

    # ── 1.8 _map_user_flow_to_actions ──

    def _map_user_flow_to_actions(
        self,
        test_case: dict[str, Any],
        user_flow: dict[str, Any] | None,
        language: str,
    ) -> list[dict[str, str]]:
        """Mapowanie krokow user flow na sekwencje akcji Playwright z expectations."""
        actions: list[dict[str, str]] = []

        steps = []
        if user_flow:
            steps = user_flow.get("steps", [])
        if not steps:
            steps = test_case.get("steps", [])

        if not isinstance(steps, list):
            return actions

        ui_elements = self._extract_ui_elements([test_case])

        for step in steps:
            if isinstance(step, dict):
                action_name = step.get("action", "")
                value = step.get("value", "")
                elem = step.get("element") or step.get("ui_element")

                if isinstance(elem, dict):
                    elem_name = elem.get("name", "")
                    # Znajdz element UI dla lokatora
                    ui_elem = next(
                        (e for e in ui_elements if e.get("name") == elem_name),
                        elem,
                    )
                    locator = self._generate_locator(
                        self._normalize_ui_element(ui_elem) if isinstance(ui_elem, dict) else elem,
                        language,
                    )
                    action_code = self._render_action(action_name, locator, value, language)
                    expectation_code = self._generate_step_expectation(locator, action_name, language)
                    actions.append(
                        {
                            "action": action_code,
                            "expectation": expectation_code,
                            "description": step.get("description", f"{action_name} {elem_name}"),
                        }
                    )
                elif action_name and isinstance(action_name, str):
                    # Direct action (np. navigate)
                    action_code = self._render_direct_action(action_name, value, language)
                    actions.append(
                        {
                            "action": action_code,
                            "expectation": "",
                            "description": action_name,
                        }
                    )

        return actions

    def _render_action(self, action_name: str, locator: dict[str, Any], value: str, language: str) -> str:
        """Renderuj kod akcji Playwright."""
        locator_code = locator["code"]
        action_lower = action_name.lower() if action_name else ""

        if language == "typescript":
            if any(kw in action_lower for kw in ("fill", "type", "enter", "input")):
                return f"await {locator_code}.fill('{value}');"
            elif any(kw in action_lower for kw in ("click", "press", "tap", "submit")):
                return f"await {locator_code}.click();"
            elif any(kw in action_lower for kw in ("check", "assert", "verify")):
                return f"await expect({locator_code}).toBeVisible();"
            elif any(kw in action_lower for kw in ("select", "choose")):
                return f"await {locator_code}.selectOption('{value}');"
            else:
                return f"await {locator_code}.click();"

        elif language == "python":
            if any(kw in action_lower for kw in ("fill", "type", "enter", "input")):
                return f'{locator_code}.fill("{value}")'
            elif any(kw in action_lower for kw in ("click", "press", "tap", "submit")):
                return f"{locator_code}.click()"
            elif any(kw in action_lower for kw in ("check", "assert", "verify")):
                return f"expect({locator_code}).to_be_visible()"
            else:
                return f"{locator_code}.click()"

        elif language == "java":
            if any(kw in action_lower for kw in ("fill", "type", "enter", "input")):
                return f'{locator_code}.fill("{value}");'
            elif any(kw in action_lower for kw in ("click", "press", "tap", "submit")):
                return f"{locator_code}.click();"
            else:
                return f"{locator_code}.click();"

        else:  # csharp
            if any(kw in action_lower for kw in ("fill", "type", "enter", "input")):
                return f'await {locator_code}.FillAsync("{value}");'
            elif any(kw in action_lower for kw in ("click", "press", "tap", "submit")):
                return f"await {locator_code}.ClickAsync();"
            else:
                return f"await {locator_code}.ClickAsync();"

    @staticmethod
    def _render_direct_action(action: str, value: str, language: str) -> str:
        """Renderuj bezposrednia akcje bez lokatora."""
        action_lower = action.lower() if action else ""
        if any(kw in action_lower for kw in ("navigate", "go", "open", "visit")):
            url = value or "about:blank"
            goto_map = {
                "typescript": f"await page.goto('{url}');",
                "python": f'page.goto("{url}")',
                "java": f'page.navigate("{url}");',
                "csharp": f'await Page.GotoAsync("{url}");',
            }
            return goto_map.get(language, f'await Page.GotoAsync("{url}");')
        return action

    # ── 1.9 _generate_expectation / _generate_expectations ──

    def _generate_expectations(self, test_case: dict[str, Any], language: str) -> list[dict[str, str]]:
        """Tworzenie expectations z test case."""
        expectations: list[dict[str, str]] = []
        templates = EXPECT_TEMPLATES.get(language, EXPECT_TEMPLATES["typescript"])

        # Z expected_result
        expected = test_case.get("expected_result")
        if expected:
            expectations.append(
                {
                    "code": templates["toContainText"].format(locator="page", expected=f"'{expected}'"),
                    "description": f"Oczekiwany wynik: {expected}",
                }
            )

        # Z assertions list
        raw_assertions = test_case.get("assertions")
        if isinstance(raw_assertions, list):
            for a in raw_assertions:
                if isinstance(a, dict):
                    a_type = a.get("type") or a.get("assertion_type", "text_contains")
                    a_element = a.get("element") or a.get("actual", "page")
                    a_expected = a.get("expected") or a.get("value", "")

                    # Mapuj na expectation Playwright
                    if a_type == "text_contains":
                        expectations.append(
                            {
                                "code": templates["toContainText"].format(
                                    locator=f"page.getByText('{a_expected}')",
                                    expected=f"'{a_expected}'",
                                ),
                                "description": f"Tekst zawiera: {a_expected}",
                            }
                        )
                    elif a_type == "text_equals":
                        expectations.append(
                            {
                                "code": templates["toHaveText"].format(
                                    locator=f"page.getByText('{a_expected}')",
                                    expected=f"'{a_expected}'",
                                ),
                                "description": f"Tekst rowny: {a_expected}",
                            }
                        )
                    elif a_type == "element_visible":
                        expectations.append(
                            {
                                "code": templates["toBeVisible"].format(locator=f"page.locator('.{a_element}')"),
                                "description": f"Element widoczny: {a_element}",
                            }
                        )

        # URL expectation
        url = test_case.get("url") or test_case.get("target_url")
        if url:
            expectations.append(
                {
                    "code": templates["toHaveURL"].format(expected=f"'{url}'"),
                    "description": f"URL zawiera: {url}",
                }
            )

        return expectations

    def _generate_step_expectation(self, locator: dict[str, Any], action_name: str, language: str) -> str:
        """Tworzenie expectation po akcji (każdy krok = akcja + expectation)."""
        templates = EXPECT_TEMPLATES.get(language, EXPECT_TEMPLATES["typescript"])
        locator_code = locator["code"]
        return templates["toBeVisible"].format(locator=locator_code)

    # ── 1.10 _generate_trace_config ──

    @staticmethod
    def _generate_trace_config(language: str) -> str:
        """Dodawanie trace config do pliku testowego."""
        trace_map = {
            "typescript": "test.use({ trace: 'on-first-retry' });",
            "python": "# trace: on-first-retry",
            "java": "// trace: on-first-retry",
            "csharp": "// trace: on-first-retry",
        }
        return trace_map.get(language, "// trace: on-first-retry")

    # ════════════════════════════════════════════════════════════════
    # Task 2: Network interceptors
    # ════════════════════════════════════════════════════════════════

    def _extract_route_mocks(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ekstrahuj API mocki z test case'ow."""
        mocks: list[dict[str, Any]] = []

        for tc in test_cases:
            api_mocks = tc.get("api_mocks")
            if isinstance(api_mocks, list):
                for mock in api_mocks:
                    if isinstance(mock, dict):
                        mocks.append(self._normalize_route_mock(mock))
            elif isinstance(api_mocks, dict):
                mocks.append(self._normalize_route_mock(api_mocks))

        return mocks

    @staticmethod
    def _normalize_route_mock(mock: dict[str, Any]) -> dict[str, Any]:
        """Normalizuj specyfikacje mocka."""
        return {
            "url": mock.get("url", "**/api/*"),
            "method": mock.get("method", "GET").upper(),
            "status": mock.get("status", 200),
            "body": mock.get("body", {}),
            "headers": mock.get("headers", {"Content-Type": "application/json"}),
        }

    def _generate_route_mock_code(self, mock: dict[str, Any], language: str) -> str:
        """Generuj kod page.route() per language."""
        url = mock["url"]
        status = mock["status"]
        body = json.dumps(mock["body"], ensure_ascii=False)

        mock_map = {
            "typescript": (
                f"    await page.route('{url}', async route => {{\n"
                f"      await route.fulfill({{\n"
                f"        status: {status},\n"
                f"        contentType: 'application/json',\n"
                f"        body: JSON.stringify({body}),\n"
                f"      }});\n"
                f"    }});"
            ),
            "python": (
                f'    page.route("{url}", lambda route: route.fulfill(\n'
                f"        status={status},\n"
                f'        content_type="application/json",\n'
                f"        body=json.dumps({body}),\n"
                f"    ))"
            ),
            "java": (
                f'    page.route("{url}", route -> route.fulfill(new Route.FulfillOptions()\n'
                f"        .setStatus({status})\n"
                f'        .setContentType("application/json")\n'
                f'        .setBody("{body}")));'
            ),
            "csharp": (
                f'    await Page.RouteAsync("{url}", async route => {{\n'
                f"      await route.FulfillAsync(new() {{\n"
                f"        Status = {status},\n"
                f'        ContentType = "application/json",\n'
                f"        Body = JsonSerializer.Serialize({body}),\n"
                f"      }});\n"
                f"    }});"
            ),
        }
        return mock_map.get(language, f'    await page.route("{url}", ...);')

    # ════════════════════════════════════════════════════════════════
    # Task 3: Walidacja selektorow
    # ════════════════════════════════════════════════════════════════

    def _validate_selectors(self, ui_elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sprawdzenie selektorow — preferencja semantycznych nad XPath."""
        classified: list[dict[str, Any]] = []
        for elem in ui_elements:
            locator_type = elem.get("locator_type", "css").lower()
            category = SELECTOR_CATEGORIES.get(locator_type, "css")
            classified.append(
                {
                    "element": elem.get("name", "unknown"),
                    "locator_type": locator_type,
                    "category": category,
                }
            )
        return classified

    # ════════════════════════════════════════════════════════════════
    # Ekstrakcja danych (wspolne z Selenium wzorzec)
    # ════════════════════════════════════════════════════════════════

    def _extract_ui_elements(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ekstrahuj elementy GUI z test case'ow."""
        elements: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tc in test_cases:
            ui_elems = tc.get("ui_elements")
            if isinstance(ui_elems, list):
                for elem in ui_elems:
                    if isinstance(elem, dict):
                        key = f"{elem.get('name', '')}:{elem.get('locator_value', '')}"
                        if key not in seen:
                            seen.add(key)
                            elements.append(self._normalize_ui_element(elem))

            # Fallback: elementy z krokow
            steps = tc.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        elem = step.get("element") or step.get("ui_element")
                        if isinstance(elem, dict):
                            key = f"{elem.get('name', '')}:{elem.get('locator_value', '')}"
                            if key not in seen:
                                seen.add(key)
                                elements.append(self._normalize_ui_element(elem))

        return elements

    @staticmethod
    def _normalize_ui_element(elem: dict[str, Any]) -> dict[str, Any]:
        """Normalizuj element UI do standardowego formatu."""
        return {
            "name": elem.get("name", "element"),
            "locator_type": elem.get("locator_type") or elem.get("strategy", "css"),
            "locator_value": elem.get("locator_value") or elem.get("selector") or elem.get("value", ""),
            "element_type": elem.get("element_type") or elem.get("type", "generic"),
            "page_name": elem.get("page_name", "MainPage"),
            "role_name": elem.get("role_name"),
        }

    def _extract_user_flows(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ekstrahuj user flows z test case'ow."""
        flows: list[dict[str, Any]] = []

        for tc in test_cases:
            user_flow = tc.get("user_flow")
            if isinstance(user_flow, dict):
                flows.append(self._normalize_user_flow(user_flow, tc))
            elif isinstance(user_flow, list):
                for flow in user_flow:
                    if isinstance(flow, dict):
                        flows.append(self._normalize_user_flow(flow, tc))
            else:
                flow = self._build_flow_from_steps(tc)
                if flow:
                    flows.append(flow)

        return flows

    @staticmethod
    def _normalize_user_flow(flow: dict[str, Any], tc: dict[str, Any]) -> dict[str, Any]:
        """Normalizuj user flow."""
        return {
            "name": flow.get("name") or tc.get("scenario_name") or tc.get("title", "unnamed_flow"),
            "url": flow.get("url") or tc.get("url") or tc.get("target_url", ""),
            "steps": flow.get("steps") or tc.get("steps") or [],
        }

    @staticmethod
    def _build_flow_from_steps(tc: dict[str, Any]) -> dict[str, Any] | None:
        """Buduj user flow z krokow test case."""
        steps = tc.get("steps")
        if not steps:
            return None

        scenario = tc.get("scenario_name") or tc.get("title", "unnamed_flow")

        pom_steps: list[dict[str, Any]] = []
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    pom_steps.append(
                        {
                            "action": step.get("action") or step.get("code", ""),
                            "element": step.get("element") or step.get("ui_element", {}),
                            "value": step.get("value", ""),
                            "target": step.get("target", ""),
                        }
                    )
                elif isinstance(step, str):
                    pom_steps.append({"action": step, "element": {}, "value": "", "target": ""})

        return {
            "name": scenario,
            "url": tc.get("url") or tc.get("target_url", ""),
            "steps": pom_steps,
        }

    # ════════════════════════════════════════════════════════════════
    # Renderowanie kodu (fallback — string building)
    # ════════════════════════════════════════════════════════════════

    def _render_code(
        self,
        feature_name: str,
        imports: list[str],
        trace_config: str,
        route_mocks: list[dict[str, Any]],
        test_cases: list[dict[str, Any]],
        language: str,
    ) -> str:
        """Renderuj kod Playwright per language (fallback)."""
        if language == "typescript":
            return self._render_typescript(feature_name, imports, trace_config, route_mocks, test_cases)
        elif language == "python":
            return self._render_python(feature_name, imports, trace_config, route_mocks, test_cases)
        elif language == "java":
            return self._render_java(feature_name, imports, trace_config, route_mocks, test_cases)
        else:
            return self._render_csharp(feature_name, imports, trace_config, route_mocks, test_cases)

    def _render_typescript(
        self,
        feature_name: str,
        imports: list[str],
        trace_config: str,
        route_mocks: list[dict[str, Any]],
        test_cases: list[dict[str, Any]],
    ) -> str:
        """Renderuj TypeScript Playwright test."""
        lines: list[str] = []
        lines.extend(imports)
        lines.append("")
        lines.append(f"test.describe('{feature_name}', () => {{")
        lines.append(f"  {trace_config}")
        lines.append("")

        # Route mocks — beforeEach
        if route_mocks:
            lines.append("  test.beforeEach(async ({ page }) => {")
            for mock in route_mocks:
                lines.append(self._generate_route_mock_code(mock, "typescript"))
            lines.append("  });")
            lines.append("")

        # Test cases
        for tc in test_cases:
            desc = tc.get("description", "unnamed test")
            url = tc.get("url", "")
            lines.append(f"  test('{desc}', async ({{ page }}) => {{")

            if url:
                lines.append(f"    await page.goto('{url}');")

            for step in tc.get("steps", []):
                if step.get("action"):
                    lines.append(f"    // {step.get('description', '')}")
                    lines.append(f"    {step['action']}")
                if step.get("expectation"):
                    lines.append(f"    {step['expectation']}")

            for exp in tc.get("expectations", []):
                if exp.get("code"):
                    lines.append(f"    {exp['code']}")

            lines.append("  });")
            lines.append("")

        lines.append("});")
        return "\n".join(lines)

    def _render_python(
        self,
        feature_name: str,
        imports: list[str],
        trace_config: str,
        route_mocks: list[dict[str, Any]],
        test_cases: list[dict[str, Any]],
    ) -> str:
        """Renderuj Python Playwright test."""
        lines: list[str] = []
        lines.extend(imports)
        if route_mocks:
            lines.append("import json")
        lines.append("")
        lines.append(f"# {feature_name}")
        if trace_config:
            lines.append(trace_config)
        lines.append("")

        for tc in test_cases:
            desc = tc.get("description", "unnamed test")
            safe_name = self._normalize_test_method_name(desc, "python")
            url = tc.get("url", "")

            lines.append(f"def {safe_name}(page):")
            # Route mocks — setup przed nawigacja
            for mock in route_mocks:
                lines.append(self._generate_route_mock_code(mock, "python"))
            if url:
                lines.append(f'    page.goto("{url}")')

            for step in tc.get("steps", []):
                if step.get("action"):
                    lines.append(f"    # {step.get('description', '')}")
                    lines.append(f"    {step['action']}")
                if step.get("expectation"):
                    lines.append(f"    {step['expectation']}")

            for exp in tc.get("expectations", []):
                if exp.get("code"):
                    lines.append(f"    {exp['code']}")

            lines.append("")

        return "\n".join(lines)

    def _render_java(
        self,
        feature_name: str,
        imports: list[str],
        trace_config: str,
        route_mocks: list[dict[str, Any]],
        test_cases: list[dict[str, Any]],
    ) -> str:
        """Renderuj Java Playwright test (JUnit 5)."""
        lines: list[str] = []
        lines.extend(imports)
        lines.append("import com.microsoft.playwright.junit.UsePlaywright;")
        lines.append("import org.junit.jupiter.api.Test;")
        lines.append("")

        class_name = self._make_class_name(feature_name, "java")
        lines.append(f"public class {class_name} {{")
        lines.append("")

        # Route mocks
        if route_mocks:
            lines.append("  @BeforeEach")
            lines.append("  void setupMocks(Page page) {")
            for mock in route_mocks:
                lines.append(self._generate_route_mock_code(mock, "java"))
            lines.append("  }")
            lines.append("")

        for tc in test_cases:
            desc = tc.get("description", "unnamed test")
            safe_name = self._normalize_test_method_name(desc, "java")
            url = tc.get("url", "")

            lines.append("  @Test")
            lines.append(f"  void {safe_name}(Page page) {{")
            if url:
                lines.append(f'    page.navigate("{url}");')

            for step in tc.get("steps", []):
                if step.get("action"):
                    lines.append(f"    {step['action']}")
                if step.get("expectation"):
                    lines.append(f"    {step['expectation']}")

            for exp in tc.get("expectations", []):
                if exp.get("code"):
                    lines.append(f"    {exp['code']}")

            lines.append("  }")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    def _render_csharp(
        self,
        feature_name: str,
        imports: list[str],
        trace_config: str,
        route_mocks: list[dict[str, Any]],
        test_cases: list[dict[str, Any]],
    ) -> str:
        """Renderuj C# Playwright test (NUnit)."""
        lines: list[str] = []
        lines.extend(imports)
        lines.append("using System.Text.Json;")
        lines.append("")

        class_name = self._make_class_name(feature_name, "csharp")
        lines.append("[TestFixture]")
        lines.append(f"public class {class_name} : PageTest {{")
        lines.append("")

        # Route mocks
        if route_mocks:
            lines.append("  [SetUp]")
            lines.append("  public async Task SetupMocks() {")
            for mock in route_mocks:
                lines.append(self._generate_route_mock_code(mock, "csharp"))
            lines.append("  }")
            lines.append("")

        for tc in test_cases:
            desc = tc.get("description", "unnamed test")
            safe_name = self._normalize_test_method_name(desc, "csharp")
            url = tc.get("url", "")

            lines.append("  [Test]")
            lines.append(f"  public async Task {safe_name}() {{")
            if url:
                lines.append(f'    await Page.GotoAsync("{url}");')

            for step in tc.get("steps", []):
                if step.get("action"):
                    lines.append(f"    {step['action']}")
                if step.get("expectation"):
                    lines.append(f"    {step['expectation']}")

            for exp in tc.get("expectations", []):
                if exp.get("code"):
                    lines.append(f"    {exp['code']}")

            lines.append("  }")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    # ════════════════════════════════════════════════════════════════
    # Helpers — nazewnictwo
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_module_name(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe modulu z test case."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        result = re.sub(r"[^\w]", "_", scenario)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "unnamed"

    @staticmethod
    def _make_feature_name(module_name: str) -> str:
        """Utworz czytelna nazwe feature z module_name."""
        return module_name.replace("_", " ")

    @staticmethod
    def _make_class_name(name: str, language: str) -> str:
        """Utworz nazwe klasy PascalCase."""
        if not name:
            return "Unnamed"
        name = re.sub(r"\.\w+$", "", name)
        name = re.sub(r"[-_]+", " ", name)
        parts = name.split()
        return "".join((p[0].upper() + p[1:]) if p else "" for p in parts if p)

    @staticmethod
    def _normalize_element_name(name: str, language: str) -> str:
        """Normalizuj nazwe elementu na snake_case (Python) lub camelCase."""
        if not name:
            return "element"
        result = re.sub(r"[\s\-]+", "_", name.lower())
        result = re.sub(r"[^a-z0-9_]", "", result)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "element"

    @staticmethod
    def _normalize_test_method_name(scenario: str, language: str) -> str:
        """Normalizuj nazwe metody testowej per jezyk."""
        result = re.sub(r"[^\w]", "_", scenario.lower())
        result = re.sub(r"_+", "_", result).strip("_")

        if language == "python":
            if not result.startswith("test_"):
                result = f"test_{result}"
            if len(result) > 60:
                result = result[:60].rstrip("_")
        elif language == "java":
            parts = result.split("_")
            result = parts[0] + "".join(p.capitalize() for p in parts[1:])
            if len(result) > 60:
                result = result[:60]
        elif language == "csharp":
            parts = result.split("_")
            result = "".join(p.capitalize() for p in parts if p)
            if len(result) > 60:
                result = result[:60]
        else:  # typescript — descriptive name
            if len(result) > 60:
                result = result[:60].rstrip("_")

        return result or "test_unnamed"

    @staticmethod
    def _build_file_path(module_name: str, extension: str) -> str:
        """Generuj sciezke pliku testowego: e2e/{feature_name}.spec.ts."""
        return f"e2e/{module_name}/{module_name}{extension}"

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy Playwright."""
        language = self._get_language(config)
        ext = FILE_EXTENSIONS.get(language, ".spec.ts")
        return TestCodeFile(
            content="// Brak test case'ow do wygenerowania\n",
            file_path=f"e2e/empty/empty{ext}",
            framework=self.FRAMEWORK,
            language=language,
            module_name="empty",
        )
