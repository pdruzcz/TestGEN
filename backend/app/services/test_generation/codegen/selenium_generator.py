"""Selenium WebDriver code generator — Story 1.40.

Generuje pliki testowe Selenium WebDriver (.py / .java / .cs) z test case'ow:
- Page Object Model (POM) — jedna klasa per strona z lokatorami i metodami
- Explicit waits (WebDriverWait + expected_conditions) — brak implicit waits/time.sleep
- Asserty po akcjach (obecnosc elementu, tekst, URL)
- ChromeDriver setup (headless, window size, timeouts) + teardown (driver.quit)
- 3 jezyki: Python (default), Java, C# — okreslone w CodeGenConfig.language
- Szablony Jinja2: selenium/TestPage.py.j2, TestPage.java.j2, TestPage.cs.j2
- Walidacja skladniowa (py_compile / strukturalna)

AC: 1-10
"""

import logging
import py_compile
import re
import tempfile
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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "selenium"

# ════════════════════════════════════════════════════════════════════════
# Mapowania skladni per jezyk
# ════════════════════════════════════════════════════════════════════════

# Typy lokatorow Selenium per jezyk
LOCATOR_SYNTAX: dict[str, dict[str, str]] = {
    "python": {
        "id": 'By.ID, "{value}"',
        "css": 'By.CSS_SELECTOR, "{value}"',
        "xpath": 'By.XPATH, "{value}"',
        "name": 'By.NAME, "{value}"',
        "class_name": 'By.CLASS_NAME, "{value}"',
        "tag_name": 'By.TAG_NAME, "{value}"',
        "link_text": 'By.LINK_TEXT, "{value}"',
    },
    "java": {
        "id": 'By.id("{value}")',
        "css": 'By.cssSelector("{value}")',
        "xpath": 'By.xpath("{value}")',
        "name": 'By.name("{value}")',
        "class_name": 'By.className("{value}")',
        "tag_name": 'By.tagName("{value}")',
        "link_text": 'By.linkText("{value}")',
    },
    "csharp": {
        "id": 'By.Id("{value}")',
        "css": 'By.CssSelector("{value}")',
        "xpath": 'By.XPath("{value}")',
        "name": 'By.Name("{value}")',
        "class_name": 'By.ClassName("{value}")',
        "tag_name": 'By.TagName("{value}")',
        "link_text": 'By.LinkText("{value}")',
    },
}

# Importy Selenium per jezyk
IMPORTS_PER_LANGUAGE: dict[str, list[str]] = {
    "python": [
        "from selenium import webdriver",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
    ],
    "java": [
        "import org.openqa.selenium.*;",
        "import org.openqa.selenium.chrome.*;",
        "import org.openqa.selenium.support.ui.*;",
        "import org.openqa.selenium.support.ui.ExpectedConditions;",
        "import org.junit.jupiter.api.*;",
        "import static org.junit.jupiter.api.Assertions.*;",
    ],
    "csharp": [
        "using OpenQA.Selenium;",
        "using OpenQA.Selenium.Chrome;",
        "using OpenQA.Selenium.Support.UI;",
    ],
}

# Konfiguracja drivera per jezyk
DRIVER_SETUP: dict[str, dict[str, str]] = {
    "python": {
        "options_class": "webdriver.ChromeOptions()",
        "add_argument": 'options.add_argument("{arg}")',
        "driver_init": "self.driver = webdriver.Chrome(options=options)",
        "wait_init": "self.wait = WebDriverWait(self.driver, {timeout})",
        "page_load_timeout": "self.driver.set_page_load_timeout({timeout})",
    },
    "java": {
        "options_class": "new ChromeOptions()",
        "add_argument": 'options.addArguments("{arg}")',
        "driver_init": "this.driver = new ChromeDriver(options)",
        "wait_init": "this.wait = new WebDriverWait(this.driver, Duration.ofSeconds({timeout}))",
        "page_load_timeout": "this.driver.manage().timeouts().pageLoadTimeout(Duration.ofSeconds({timeout}))",
    },
    "csharp": {
        "options_class": "new ChromeOptions()",
        "add_argument": 'options.AddArgument("{arg}")',
        "driver_init": "this.driver = new ChromeDriver(options)",
        "wait_init": "this.wait = new WebDriverWait(this.driver, TimeSpan.FromSeconds({timeout}))",
        "page_load_timeout": "this.driver.Manage().Timeouts().PageLoad = TimeSpan.FromSeconds({timeout})",
    },
}

TEARDOWN_SYNTAX: dict[str, dict[str, str]] = {
    "python": {
        "method_def": "def teardown_method(self):",
        "quit": "self.driver.quit()",
    },
    "java": {
        "method_def": "@AfterEach",
        "method_sig": "void tearDown() {",
        "quit": "this.driver.quit();",
    },
    "csharp": {
        "method_def": "[TearDown]",
        "method_sig": "public void TearDown() {",
        "quit": "this.driver.Quit();",
    },
}

# Asercje Selenium — sprawdzanie stanu strony po akcjach
ASSERT_TEMPLATES: dict[str, dict[str, str]] = {
    "python": {
        "element_visible": 'assert self.wait.until(EC.visibility_of_element_located({locator})), "Element {name} nie jest widoczny"',
        "text_equals": 'assert {element}.text == "{expected}", "Oczekiwano: {expected}, otrzymano: " + {element}.text',
        "text_contains": 'assert "{expected}" in {element}.text, "Tekst {expected} nie znaleziony"',
        "url_contains": 'assert "{expected}" in self.driver.current_url, "URL nie zawiera {expected}"',
        "element_present": 'assert self.wait.until(EC.presence_of_element_located({locator})), "Element {name} nie istnieje"',
    },
    "java": {
        "element_visible": 'assertTrue(wait.until(ExpectedConditions.visibilityOfElementLocated({locator})).isDisplayed(), "Element {name} nie jest widoczny");',
        "text_equals": 'assertEquals("{expected}", {element}.getText());',
        "text_contains": 'assertTrue({element}.getText().contains("{expected}"));',
        "url_contains": 'assertTrue(driver.getCurrentUrl().contains("{expected}"));',
        "element_present": 'assertNotNull(wait.until(ExpectedConditions.presenceOfElementLocated({locator})), "Element {name} nie istnieje");',
    },
    "csharp": {
        "element_visible": 'Assert.True(wait.Until(ExpectedConditions.ElementIsVisible({locator})).Displayed, "Element {name} nie jest widoczny");',
        "text_equals": 'Assert.Equal("{expected}", {element}.Text);',
        "text_contains": 'Assert.Contains("{expected}", {element}.Text);',
        "url_contains": 'Assert.Contains("{expected}", driver.Url);',
        "element_present": "Assert.NotNull(wait.Until(ExpectedConditions.ElementExists({locator})));",
    },
}

# Rozszerzenia plikow per jezyk
FILE_EXTENSIONS: dict[str, str] = {
    "python": ".py",
    "java": ".java",
    "csharp": ".cs",
}


@register_generator("selenium")
class SeleniumCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego Selenium WebDriver (Python/Java/C#).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "selenium".

    Generuje testy GUI z Page Object Model, explicit waits,
    asercjami po akcjach i konfiguracja ChromeDriver.
    """

    FRAMEWORK = "selenium"
    LANGUAGE = "python"
    FILE_EXTENSION = ".py"

    def __init__(self, config: CodeGenConfig | None = None):
        super().__init__(config)
        self._jinja_env: Environment | None = None

    # ── Wlasciwosc: Jinja2 environment (lazy) ──

    @property
    def jinja_env(self) -> Environment:
        """Jinja2 environment — inicjalizowane leniwie."""
        if self._jinja_env is None:
            templates_dir = self.config.templates_dir or TEMPLATES_DIR
            if not templates_dir.exists():
                logger.warning("Katalog szablonow Selenium nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── Wlasciwosc: jezyk z configu ──

    def _get_language(self, config: CodeGenConfig | None = None) -> str:
        """Pobierz jezyk generowania: "python", "java" lub "csharp"."""
        cfg = config or self.config
        language = cfg.language.lower()
        # Normalizuj "c#", "cs" -> "csharp"
        if language in ("c#", "cs", "csharp"):
            return "csharp"
        if language in ("java",):
            return "java"
        return "python"

    # ════════════════════════════════════════════════════════════════
    # 1.3 generate_test_file — glowna metoda
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy Selenium WebDriver z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (typ e2e/system)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem Selenium
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        language = self._get_language(cfg)
        first_tc = test_cases[0]

        # Nazwa modulu
        module_name = self._extract_module_name(first_tc)

        # 1.4 Importy Selenium
        imports = self._build_imports(test_cases, cfg, language)

        # Ekstrahuj elementy GUI i user flow
        ui_elements = self._extract_ui_elements(test_cases)
        user_flows = self._extract_user_flows(test_cases)

        # 1.5 Generuj Page Object Model
        page_objects = self._build_page_objects(ui_elements, user_flows, language)

        # 1.8 Generuj metody testowe
        test_methods = self._build_test_methods(test_cases, page_objects, user_flows, language)

        # 3.1 Konfiguracja przegladarki
        driver_setup = self._generate_driver_setup(language)
        teardown = self._generate_teardown(language)

        # Wybierz szablon
        template_name = self._get_template_name(language)
        file_ext = FILE_EXTENSIONS.get(language, ".py")

        # Renderuj szablon (Task 4)
        context = {
            "module_name": module_name,
            "imports": imports,
            "page_objects": page_objects,
            "test_class_name": self._make_class_name(module_name, language),
            "driver_setup": driver_setup,
            "teardown": teardown,
            "test_methods": test_methods,
            "language": language,
            "config": cfg,
        }

        try:
            template = self.jinja_env.get_template(template_name)
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu Selenium: %s", exc)
            content = self._fallback_render(context, language)

        # Walidacja kompilacji (Task 5)
        file_path = self._build_file_path(module_name, file_ext)
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=language,
            module_name=module_name,
            test_functions=test_methods,
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
        """Generuj bazowy plik setup Selenium (np. webdriver config).

        Args:
            project_context: kontekst projektu

        Returns:
            Zawartosc bazowego pliku setup
        """
        return "# Bazowy plik setup Selenium — rozszerz w konkretnych testach\n"

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
        """Generuj pojedyncza asercje Selenium.

        Args:
            expected: oczekiwana wartosc
            actual: rzeczywista wartosc / element
            comparison_type: typ porownania
            message: komunikat przy bledzie

        Returns:
            Kod asercji jako string
        """
        language = self._get_language()
        templates = ASSERT_TEMPLATES.get(language, ASSERT_TEMPLATES["python"])

        if comparison_type == "element_visible":
            return templates["element_visible"].format(
                locator=actual,
                name=expected,
            )
        elif comparison_type == "text_equals":
            return templates["text_equals"].format(
                element=actual,
                expected=expected,
            )
        elif comparison_type == "text_contains":
            return templates["text_contains"].format(
                element=actual,
                expected=expected,
            )
        elif comparison_type == "url_contains":
            return templates["url_contains"].format(
                expected=expected,
            )
        elif comparison_type == "element_present":
            return templates["element_present"].format(
                locator=actual,
                name=expected,
            )
        else:
            # Fallback
            if language == "python":
                return f'assert {actual} == "{expected}"'
            elif language == "java":
                return f'assertEquals("{expected}", {actual});'
            else:
                return f'Assert.Equal("{expected}", {actual});'

    # ════════════════════════════════════════════════════════════════
    # Task 5: validate_syntax
    # ════════════════════════════════════════════════════════════════

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu Selenium.

        Dla Python: py_compile. Dla Java/C#: walidacja strukturalna.

        Args:
            code: kod do walidacji

        Returns:
            CompilationResult z wynikiem walidacji
        """
        if not code.strip():
            return CompilationResult(
                success=False,
                code=code,
                error_message="Pusty kod",
                framework=self.FRAMEWORK,
            )

        language = self._get_language()
        warnings: list[str] = []

        # 5.4 Walidacja specyficzna: Selenium
        selenium_markers = {
            "python": ["webdriver", "By.", "WebDriverWait", "driver.quit()"],
            "java": ["WebDriver", "By.", "WebDriverWait", "driver.quit()"],
            "csharp": ["IWebDriver", "By.", "WebDriverWait", "driver.Quit()"],
        }
        markers = selenium_markers.get(language, selenium_markers["python"])
        for marker in markers:
            if marker not in code:
                warnings.append(f"Brak elementu Selenium: {marker}")

        # Wybierz metode walidacji per jezyk
        if language == "python":
            return self._validate_python_syntax(code, warnings)
        else:
            return self._validate_structural(code, language, warnings)

    def _validate_python_syntax(self, code: str, warnings: list[str]) -> CompilationResult:
        """Waliduj skladnie Python przez py_compile."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
                tmp_path = f.name
                f.write(code)

            py_compile.compile(tmp_path, doraise=True)
            return CompilationResult(
                success=True,
                code=code,
                file_path=tmp_path,
                framework=self.FRAMEWORK,
                warnings=warnings,
            )
        except py_compile.PyCompileError as exc:
            error_msg = str(exc)
            line, col = self._parse_compile_error(error_msg)
            return CompilationResult(
                success=False,
                code=code,
                file_path=tmp_path,
                error_message=error_msg,
                error_line=line,
                error_column=col,
                framework=self.FRAMEWORK,
                warnings=warnings,
            )
        finally:
            if tmp_path:
                import contextlib

                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)

    def _validate_structural(self, code: str, language: str, warnings: list[str]) -> CompilationResult:
        """Walidacja strukturalna kodu Java/C#."""
        errors: list[str] = []

        # Sprawdz balans nawiasow klamrowych
        open_braces = code.count("{")
        close_braces = code.count("}")
        if open_braces != close_braces:
            errors.append(f"Niezbalansowane nawiasy klamrowe: {{ = {open_braces}, }} = {close_braces}")

        # Sprawdz balans nawiasow okraglych
        open_parens = code.count("(")
        close_parens = code.count(")")
        if open_parens != close_parens:
            errors.append(f"Niezbalansowane nawiasy okragle: ( = {open_parens}, ) = {close_parens}")

        # Sprawdz obecnosc klas / metod
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

        # Sprawdz sredniki (Java/C# wymagaja)
        if language in ("java", "csharp") and ";" not in code:
            errors.append("Brak srednikow w kodzie — prawdopodobnie niepoprawna skladnia")

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
        """Buduj liste importow Selenium per jezyk."""
        imports = list(IMPORTS_PER_LANGUAGE.get(language, IMPORTS_PER_LANGUAGE["python"]))

        # Importy z test case (dodatkowe)
        for tc in test_cases:
            tc_imports = tc.get("imports") or tc.get("usings")
            if isinstance(tc_imports, list):
                for imp in tc_imports:
                    if imp and imp not in imports:
                        imports.append(imp)
            elif isinstance(tc_imports, str) and tc_imports.strip():
                for imp in tc_imports.strip().split("\n"):
                    imp = imp.strip()
                    if imp and imp not in imports:
                        imports.append(imp)

        # Java wymaga Duration
        if language == "java":
            duration_import = "import java.time.Duration;"
            if duration_import not in imports:
                imports.append(duration_import)

        return imports

    # ── Ekstrakcja elementow GUI ──

    def _extract_ui_elements(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ekstrahuj elementy GUI z test case'ow.

        Kazdy element ma: name, locator_type, locator_value, element_type, page_name.
        """
        elements: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tc in test_cases:
            # Elementy z ui_elements field
            ui_elems = tc.get("ui_elements")
            if isinstance(ui_elems, list):
                for elem in ui_elems:
                    if isinstance(elem, dict):
                        key = f"{elem.get('name', '')}:{elem.get('locator_value', '')}"
                        if key not in seen:
                            seen.add(key)
                            elements.append(self._normalize_ui_element(elem))
            elif isinstance(ui_elems, dict):
                elem = self._normalize_ui_element(ui_elems)
                key = f"{elem.get('name', '')}:{elem.get('locator_value', '')}"
                if key not in seen:
                    seen.add(key)
                    elements.append(elem)

            # Elementy z krokow (fallback)
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
        }

    def _extract_user_flows(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ekstrahuj user flows z test case'ow.

        Kazdy flow ma: name, url, steps (lista akcji POM).
        """
        flows: list[dict[str, Any]] = []

        for tc in test_cases:
            # user_flow field
            user_flow = tc.get("user_flow")
            if isinstance(user_flow, dict):
                flows.append(self._normalize_user_flow(user_flow, tc))
            elif isinstance(user_flow, list):
                for flow in user_flow:
                    if isinstance(flow, dict):
                        flows.append(self._normalize_user_flow(flow, tc))
            else:
                # Fallback — buduj flow z steps
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

        # Buduj kroki z formatu step -> POM action
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

    # ── 1.5 _generate_page_object / _build_page_objects ──

    def _build_page_objects(
        self,
        ui_elements: list[dict[str, Any]],
        user_flows: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, Any]]:
        """Buduj klasy Page Object Model z elementow GUI.

        Grupuje elementy po page_name — jedna klasa POM per strona.
        """
        if not ui_elements:
            # Fallback — generuj jedna strone z elementami z flow
            return self._build_page_objects_from_flows(user_flows, language)

        # Grupuj po page_name
        pages: dict[str, list[dict[str, Any]]] = {}
        for elem in ui_elements:
            page = elem.get("page_name", "MainPage")
            if page not in pages:
                pages[page] = []
            pages[page].append(elem)

        page_objects: list[dict[str, Any]] = []
        for page_name, elements in pages.items():
            pom = self._generate_page_object(page_name, elements, language)
            page_objects.append(pom)

        return page_objects

    def _build_page_objects_from_flows(
        self,
        user_flows: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, Any]]:
        """Fallback: buduj POM z elementow w user flows."""
        pages: dict[str, list[dict[str, Any]]] = {}

        for flow in user_flows:
            flow_name = flow.get("name", "MainPage")
            page_name = self._make_class_name(flow_name, language) + "Page"

            steps = flow.get("steps", [])
            for step in steps:
                if isinstance(step, dict):
                    elem = step.get("element")
                    if isinstance(elem, dict) and elem.get("name"):
                        if page_name not in pages:
                            pages[page_name] = []
                        pages[page_name].append(self._normalize_ui_element(elem))

        if not pages:
            # Ostateczny fallback — jedna pusta strona
            pages["MainPage"] = []

        page_objects: list[dict[str, Any]] = []
        for page_name, elements in pages.items():
            pom = self._generate_page_object(page_name, elements or [], language)
            page_objects.append(pom)

        return page_objects

    def _generate_page_object(
        self,
        page_name: str,
        elements: list[dict[str, Any]],
        language: str,
    ) -> dict[str, Any]:
        """Generuj pojedyncza klase POM z lokatorami i metodami interakcji."""
        base_name = self._make_class_name(page_name, language)
        class_name = base_name if base_name.endswith("Page") else base_name + "Page"

        # Lokatory
        locators = [self._generate_locator(elem, language) for elem in elements]

        # 1.7 Metody interakcji POM
        methods = self._generate_interaction_methods(elements, language)

        return {
            "class_name": class_name,
            "page_name": page_name,
            "elements": elements,
            "locators": locators,
            "methods": methods,
            "language": language,
        }

    # ── 1.6 _generate_locator ──

    def _generate_locator(self, element: dict[str, Any], language: str) -> dict[str, Any]:
        """Mapuj element GUI na lokator Selenium: By.ID, By.CSS_SELECTOR, By.XPATH."""
        locator_type = element.get("locator_type", "css")
        locator_value = element.get("locator_value", "")
        element_name = element.get("name", "element")

        # Mapuj typy: css_selector -> css, xpath -> xpath, id -> id
        locator_type = self._normalize_locator_type(locator_type)

        syntax_map = LOCATOR_SYNTAX.get(language, LOCATOR_SYNTAX["python"])
        template = syntax_map.get(locator_type, syntax_map["css"])

        locator_code = template.format(value=locator_value)

        # Nazwa zmiennej elementu
        var_name = self._normalize_element_name(element_name, language)

        return {
            "name": var_name,
            "type": locator_type,
            "value": locator_value,
            "code": locator_code,
        }

    @staticmethod
    def _normalize_locator_type(locator_type: str) -> str:
        """Normalizuj typ lokatora."""
        mapping = {
            "css": "css",
            "css_selector": "css",
            "cssselector": "css",
            "xpath": "xpath",
            "id": "id",
            "name": "name",
            "class": "class_name",
            "class_name": "class_name",
            "tag": "tag_name",
            "tag_name": "tag_name",
            "link_text": "link_text",
        }
        return mapping.get(locator_type.lower(), "css")

    # ── 1.7 _generate_interaction_methods ──

    def _generate_interaction_methods(
        self,
        elements: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, Any]]:
        """Tworzenie metod POM: click_{element}(), fill_{field}(), get_{text}(), is_visible()."""
        methods: list[dict[str, Any]] = []
        seen: set[str] = set()

        for elem in elements:
            elem_name = elem.get("name", "element")
            elem_type = elem.get("element_type", "generic").lower()
            var_name = self._normalize_element_name(elem_name, language)

            # Metoda click
            click_method = self._make_click_method(var_name, elem_name, language)
            if click_method["name"] not in seen:
                seen.add(click_method["name"])
                methods.append(click_method)

            # Metoda fill dla pol tekstowych
            if elem_type in ("input", "textarea", "text_field", "textbox", "field"):
                fill_method = self._make_fill_method(var_name, elem_name, language)
                if fill_method["name"] not in seen:
                    seen.add(fill_method["name"])
                    methods.append(fill_method)

            # Metoda get_text
            text_method = self._make_get_text_method(var_name, elem_name, language)
            if text_method["name"] not in seen:
                seen.add(text_method["name"])
                methods.append(text_method)

            # Metoda is_visible
            visible_method = self._make_is_visible_method(var_name, elem_name, language)
            if visible_method["name"] not in seen:
                seen.add(visible_method["name"])
                methods.append(visible_method)

        return methods

    def _make_click_method(self, var_name: str, elem_name: str, language: str) -> dict[str, Any]:
        """Generuj metode click_{element}()."""
        safe_name = self._normalize_element_name(elem_name, language)
        method_name = f"click_{safe_name}"
        return self._build_pom_method(
            method_name=method_name,
            var_name=var_name,
            language=language,
            actions=["click"],
            has_params=False,
        )

    def _make_fill_method(self, var_name: str, elem_name: str, language: str) -> dict[str, Any]:
        """Generuj metode fill_{field}()."""
        safe_name = self._normalize_element_name(elem_name, language)
        method_name = f"fill_{safe_name}"
        return self._build_pom_method(
            method_name=method_name,
            var_name=var_name,
            language=language,
            actions=["clear", "send_keys"],
            has_params=True,
            param_name="value",
        )

    def _make_get_text_method(self, var_name: str, elem_name: str, language: str) -> dict[str, Any]:
        """Generuj metode get_{text}()."""
        safe_name = self._normalize_element_name(elem_name, language)
        method_name = f"get_{safe_name}_text"
        return self._build_pom_method(
            method_name=method_name,
            var_name=var_name,
            language=language,
            actions=["get_text"],
            has_params=False,
        )

    def _make_is_visible_method(self, var_name: str, elem_name: str, language: str) -> dict[str, Any]:
        """Generuj metode is_visible()."""
        safe_name = self._normalize_element_name(elem_name, language)
        method_name = f"is_{safe_name}_visible"
        return self._build_pom_method(
            method_name=method_name,
            var_name=var_name,
            language=language,
            actions=["is_displayed"],
            has_params=False,
        )

    def _build_pom_method(
        self,
        method_name: str,
        var_name: str,
        language: str,
        actions: list[str],
        has_params: bool,
        param_name: str = "",
    ) -> dict[str, Any]:
        """Buduj specyfikacje metody POM per jezyk."""
        # Kod metody per jezyk
        action_code = self._render_pom_actions(var_name, actions, language, param_name)

        if language == "python":
            params = f", {param_name}" if has_params else ""
            return {
                "name": method_name,
                "params": params,
                "element": var_name,
                "actions": action_code,
                "returns": "element"
                if "click" in actions or "send_keys" in actions
                else ("text" if "get_text" in actions else "bool"),
            }
        elif language == "java":
            params = f", String {param_name}" if has_params else ""
            return_type = "void" if "click" in actions else ("String" if "get_text" in actions else "boolean")
            return {
                "name": method_name,
                "params": params,
                "element": var_name,
                "actions": action_code,
                "returns": return_type,
            }
        else:  # csharp
            params = f", string {param_name}" if has_params else ""
            return_type = "void" if "click" in actions else ("string" if "get_text" in actions else "bool")
            return {
                "name": method_name,
                "params": params,
                "element": var_name,
                "actions": action_code,
                "returns": return_type,
            }

    def _render_pom_actions(
        self,
        var_name: str,
        actions: list[str],
        language: str,
        param_name: str,
    ) -> list[dict[str, str]]:
        """Renderuj kod akcji POM per jezyk."""
        action_code: list[dict[str, str]] = []

        for action in actions:
            if language == "python":
                if action == "click":
                    action_code.append(
                        {"code": f"element = self.wait.until(EC.element_to_be_clickable(self._{var_name}))"}
                    )
                    action_code.append({"code": "element.click()"})
                elif action == "clear":
                    action_code.append(
                        {"code": f"element = self.wait.until(EC.presence_of_element_located(self._{var_name}))"}
                    )
                    action_code.append({"code": "element.clear()"})
                elif action == "send_keys":
                    action_code.append({"code": f"element.send_keys({param_name})"})
                elif action == "get_text":
                    action_code.append(
                        {"code": f"element = self.wait.until(EC.presence_of_element_located(self._{var_name}))"}
                    )
                    action_code.append({"code": "return element.text"})
                elif action == "is_displayed":
                    action_code.append(
                        {"code": f"element = self.wait.until(EC.visibility_of_element_located(self._{var_name}))"}
                    )
                    action_code.append({"code": "return element.is_displayed()"})
            elif language == "java":
                if action == "click":
                    action_code.append(
                        {
                            "code": f"WebElement element = wait.until(ExpectedConditions.elementToBeClickable(this.{var_name}));"
                        }
                    )
                    action_code.append({"code": "element.click();"})
                elif action == "clear":
                    action_code.append(
                        {
                            "code": f"WebElement element = wait.until(ExpectedConditions.presenceOfElementLocated(this.{var_name}));"
                        }
                    )
                    action_code.append({"code": "element.clear();"})
                elif action == "send_keys":
                    action_code.append({"code": f"element.sendKeys({param_name});"})
                elif action == "get_text":
                    action_code.append(
                        {
                            "code": f"WebElement element = wait.until(ExpectedConditions.presenceOfElementLocated(this.{var_name}));"
                        }
                    )
                    action_code.append({"code": "return element.getText();"})
                elif action == "is_displayed":
                    action_code.append(
                        {
                            "code": f"WebElement element = wait.until(ExpectedConditions.visibilityOfElementLocated(this.{var_name}));"
                        }
                    )
                    action_code.append({"code": "return element.isDisplayed();"})
            else:  # csharp
                if action == "click":
                    action_code.append(
                        {"code": f"var element = wait.Until(ExpectedConditions.ElementToBeClickable(this.{var_name}));"}
                    )
                    action_code.append({"code": "element.Click();"})
                elif action == "clear":
                    action_code.append(
                        {"code": f"var element = wait.Until(ExpectedConditions.ElementExists(this.{var_name}));"}
                    )
                    action_code.append({"code": "element.Clear();"})
                elif action == "send_keys":
                    action_code.append({"code": f"element.SendKeys({param_name});"})
                elif action == "get_text":
                    action_code.append(
                        {"code": f"var element = wait.Until(ExpectedConditions.ElementExists(this.{var_name}));"}
                    )
                    action_code.append({"code": "return element.Text;"})
                elif action == "is_displayed":
                    action_code.append(
                        {"code": f"var element = wait.Until(ExpectedConditions.ElementIsVisible(this.{var_name}));"}
                    )
                    action_code.append({"code": "return element.Displayed;"})

        return action_code

    # ── 1.8 _generate_test_method / _build_test_methods ──

    def _build_test_methods(
        self,
        test_cases: list[dict[str, Any]],
        page_objects: list[dict[str, Any]],
        user_flows: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, Any]]:
        """Generuj metody testowe: init driver -> navigate -> POM interactions -> asserts -> cleanup."""
        methods: list[dict[str, Any]] = []

        for i, tc in enumerate(test_cases):
            flow = user_flows[i] if i < len(user_flows) else None
            method = self._generate_test_method(tc, page_objects, flow, language)
            methods.append(method)

        return methods

    def _generate_test_method(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
        user_flow: dict[str, Any] | None,
        language: str,
    ) -> dict[str, Any]:
        """Generuj specyfikacje pojedynczego testu Selenium."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed_test"
        method_name = self._normalize_test_method_name(scenario, language)

        # URL do nawigacji
        url = ""
        if user_flow:
            url = user_flow.get("url", "")

        # 1.9 Mapowanie krokow user flow na sekwencje POM wywolan
        pom_calls = self._map_user_flow_to_pom(test_case, user_flow, page_objects, language)

        # 1.11 Asserty po akcjach
        assertions = self._generate_asserts_after_action(test_case, page_objects, language)

        # 1.10 Explicit waits
        waits = self._generate_explicit_waits(test_case, page_objects, language)

        return {
            "name": method_name,
            "url": url,
            "pom_calls": pom_calls,
            "assertions": assertions,
            "waits": waits,
            "scenario": scenario,
            "language": language,
        }

    # ── 1.9 _map_user_flow_to_pom ──

    def _map_user_flow_to_pom(
        self,
        test_case: dict[str, Any],
        user_flow: dict[str, Any] | None,
        page_objects: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, str]]:
        """Mapowanie krokow user flow na sekwencje wywolan POM methods."""
        pom_calls: list[dict[str, str]] = []

        steps = []
        if user_flow:
            steps = user_flow.get("steps", [])
        if not steps:
            steps = test_case.get("steps", [])

        if not isinstance(steps, list):
            return pom_calls

        # Buduj mape element -> POM class
        element_to_pom = self._build_element_to_pom_map(page_objects)

        for step in steps:
            if isinstance(step, dict):
                action = step.get("action", "")
                value = step.get("value", "")
                target = step.get("target", "")
                elem = step.get("element") or step.get("ui_element")

                if isinstance(elem, dict):
                    elem_name = elem.get("name", "")
                    pom_class, method_call = self._resolve_pom_call(
                        elem_name,
                        action,
                        value,
                        target,
                        element_to_pom,
                        language,
                    )
                    pom_calls.append(
                        {
                            "pom_class": pom_class,
                            "call": method_call,
                            "action": action,
                            "value": value,
                        }
                    )
                elif action and isinstance(action, str):
                    # Generuj kod akcji bezposrednio
                    pom_calls.append(
                        {
                            "pom_class": "",
                            "call": self._render_direct_action(action, value, language),
                            "action": action,
                            "value": value,
                        }
                    )

        return pom_calls

    def _build_element_to_pom_map(
        self,
        page_objects: list[dict[str, Any]],
    ) -> dict[str, tuple[str, list[dict[str, Any]]]]:
        """Buduj mape element_name -> (pom_class_name, methods)."""
        mapping: dict[str, tuple[str, list[dict[str, Any]]]] = {}
        for pom in page_objects:
            for method in pom.get("methods", []):
                mapping[method["name"]] = (pom["class_name"], pom.get("methods", []))
            for elem in pom.get("elements", []):
                name = elem.get("name", "")
                if name:
                    mapping[name] = (pom["class_name"], pom.get("methods", []))
        return mapping

    def _resolve_pom_call(
        self,
        elem_name: str,
        action: str,
        value: str,
        target: str,
        element_to_pom: dict[str, tuple[str, list[dict[str, Any]]]],
        language: str,
    ) -> tuple[str, str]:
        """Rozwiaz element na wywolanie metody POM."""
        safe_name = self._normalize_element_name(elem_name, language)
        pom_class = ""
        method_call = ""

        # Znajdz POM class dla elementu
        if elem_name in element_to_pom:
            pom_class, _methods = element_to_pom[elem_name]
            pom_var = self._normalize_element_name(pom_class.replace("Page", "").lower(), language)
        else:
            pom_var = safe_name

        # Mapuj akcje na metode POM
        action_lower = action.lower() if action else ""
        if any(kw in action_lower for kw in ("click", "press", "tap", "submit")):
            method_call = f"{pom_var}_page.click_{safe_name}()"
        elif any(kw in action_lower for kw in ("fill", "type", "enter", "input", "write")):
            val = value if value is not None else (target or "")
            method_call = f'{pom_var}_page.fill_{safe_name}("{val}")'
        elif any(kw in action_lower for kw in ("navigate", "go", "open", "visit")):
            method_call = f'self.driver.get("{value or target}")'
        elif any(kw in action_lower for kw in ("wait", "sleep")):
            method_call = self._render_explicit_wait_code(safe_name, language)
        elif any(kw in action_lower for kw in ("check", "assert", "verify")):
            method_call = f"{pom_var}_page.is_{safe_name}_visible()"
        else:
            method_call = action if action and "driver" not in action else f"# {action or 'akcja'} — {elem_name}"

        return pom_class, method_call

    @staticmethod
    def _render_direct_action(action: str, value: str, language: str) -> str:
        """Renderuj bezposrednia akcje bez POM."""
        if ("driver.get" in action or "navigate" in action) and value:
            if language == "python":
                return f'self.driver.get("{value}")'
            elif language == "java":
                return f'driver.get("{value}");'
            else:
                return f'driver.Url = "{value}";'
        return action

    # ── 1.10 _generate_explicit_wait ──

    def _generate_explicit_waits(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, str]]:
        """Generuj explicit waits (WebDriverWait + expected_conditions)."""
        waits: list[dict[str, str]] = []

        # Sprawdz czy test case ma explicit wait requirements
        wait_elements = test_case.get("wait_for") or test_case.get("explicit_waits")
        if not wait_elements:
            return waits

        if isinstance(wait_elements, list):
            for wait_spec in wait_elements:
                if isinstance(wait_spec, dict):
                    wait_code = self._render_explicit_wait_code(
                        wait_spec.get("element", ""),
                        language,
                        wait_spec.get("condition", "presence"),
                        wait_spec.get("timeout", 10),
                    )
                    waits.append({"code": wait_code})

        return waits

    def _render_explicit_wait_code(
        self,
        element_name: str,
        language: str,
        condition: str = "presence",
        timeout: int = 10,
    ) -> str:
        """Renderuj kod WebDriverWait per jezyk."""
        safe_name = self._normalize_element_name(element_name, language)

        if language == "python":
            wait_map = {
                "clickable": f"self.wait.until(EC.element_to_be_clickable(self._{safe_name}))",
                "visible": f"self.wait.until(EC.visibility_of_element_located(self._{safe_name}))",
                "text": f'self.wait.until(EC.text_to_be_present_in_element(self._{safe_name}, "expected_text"))',
            }
            return wait_map.get(condition, f"self.wait.until(EC.presence_of_element_located(self._{safe_name}))")
        elif language == "java":
            wait_map = {
                "clickable": f"wait.until(ExpectedConditions.elementToBeClickable(this.{safe_name}));",
                "visible": f"wait.until(ExpectedConditions.visibilityOfElementLocated(this.{safe_name}));",
            }
            return wait_map.get(
                condition, f"wait.until(ExpectedConditions.presenceOfElementLocated(this.{safe_name}));"
            )
        else:  # csharp
            wait_map = {
                "clickable": f"wait.Until(ExpectedConditions.ElementToBeClickable(this.{safe_name}));",
                "visible": f"wait.Until(ExpectedConditions.ElementIsVisible(this.{safe_name}));",
            }
            return wait_map.get(condition, f"wait.Until(ExpectedConditions.ElementExists(this.{safe_name}));")

    # ── 1.11 _generate_assert_after_action ──

    def _generate_asserts_after_action(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, str]]:
        """Dodawanie assert sprawdzajacego stan strony po kazdej akcji."""
        assertions: list[dict[str, str]] = []

        # Asercje z expected_result
        expected = test_case.get("expected_result")
        if expected:
            assertion_code = self.generate_assertion(
                expected=str(expected),
                actual="result",
                comparison_type=test_case.get("comparison_type", "equals"),
            )
            assertions.append({"code": assertion_code})

        # Asercje z explicit assertions list
        raw_assertions = test_case.get("assertions")
        if isinstance(raw_assertions, list):
            for a in raw_assertions:
                if isinstance(a, dict):
                    a_type = a.get("type") or a.get("assertion_type", "text_equals")
                    a_element = a.get("element") or a.get("actual", "element")
                    a_expected = a.get("expected") or a.get("value", "")
                    assertion_code = self.generate_assertion(
                        expected=str(a_expected),
                        actual=a_element,
                        comparison_type=a_type,
                    )
                    assertions.append({"code": assertion_code})

        # Asercja: sprawdz URL po nawigacji
        url = test_case.get("url") or test_case.get("target_url")
        if url:
            url_assert = self.generate_assertion(
                expected=url,
                actual="self.driver.current_url",
                comparison_type="url_contains",
            )
            assertions.append({"code": url_assert})

        return assertions

    # ── Task 3: Konfiguracja przegladarki ──

    def _generate_driver_setup(self, language: str) -> dict[str, Any]:
        """Generuj konfiguracje ChromeDriver z opcjami."""
        setup_syntax = DRIVER_SETUP.get(language, DRIVER_SETUP["python"])

        options_lines: list[str] = []
        options_lines.append(setup_syntax["options_class"])
        options_lines.append(setup_syntax["add_argument"].format(arg="--headless"))
        options_lines.append(setup_syntax["add_argument"].format(arg="--window-size=1920,1080"))

        driver_init = setup_syntax["driver_init"]
        wait_init = setup_syntax["wait_init"].format(timeout=10)

        return {
            "options_lines": options_lines,
            "driver_init": driver_init,
            "wait_init": wait_init,
            "language": language,
        }

    def _generate_teardown(self, language: str) -> dict[str, Any]:
        """Generuj teardown z driver.quit()."""
        td_syntax = TEARDOWN_SYNTAX.get(language, TEARDOWN_SYNTAX["python"])
        return {
            "method_def": td_syntax["method_def"],
            "method_sig": td_syntax.get("method_sig", ""),
            "quit": td_syntax["quit"],
            "language": language,
        }

    # ── Task 4: Szablony Jinja2 helpers ──

    @staticmethod
    def _get_template_name(language: str) -> str:
        """Wybor szablonu na podstawie jezyka."""
        mapping = {
            "python": "TestPage.py.j2",
            "java": "TestPage.java.j2",
            "csharp": "TestPage.cs.j2",
        }
        return mapping.get(language, "TestPage.py.j2")

    @staticmethod
    def _build_file_path(module_name: str, extension: str) -> str:
        """Generuj sciezke pliku testowego."""
        return f"tests/selenium/{module_name}/{module_name}Test{extension}"

    # ── Nazewnictwo ──

    @staticmethod
    def _extract_module_name(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe modulu z test case."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        # Normalizuj
        result = re.sub(r"[^\w]", "_", scenario)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "unnamed"

    @staticmethod
    def _make_class_name(name: str, language: str) -> str:
        """Utworz nazwe klasy PascalCase."""
        if not name:
            return "Unnamed"
        # Usun rozszerzenie
        name = re.sub(r"\.\w+$", "", name)
        # Zamien separatory na spacje
        name = re.sub(r"[-_]+", " ", name)
        # PascalCase — zachowaj wielkosc liter wewnatrz slow
        parts = name.split()
        return "".join((p[0].upper() + p[1:]) if p else "" for p in parts if p)

    @staticmethod
    def _normalize_element_name(name: str, language: str) -> str:
        """Normalizuj nazwe elementu na snake_case (Python) lub camelCase (Java/C#)."""
        if not name:
            return "element"
        # Zamien spacje i mysliniki na podkreslenia
        result = re.sub(r"[\s\-]+", "_", name.lower())
        result = re.sub(r"[^a-z0-9_]", "", result)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "element"

    @staticmethod
    def _normalize_test_method_name(scenario: str, language: str) -> str:
        """Normalizuj nazwe metody testowej per jezyk."""
        # Normalizuj
        result = re.sub(r"[^\w]", "_", scenario.lower())
        result = re.sub(r"_+", "_", result).strip("_")

        if language == "python":
            if not result.startswith("test_"):
                result = f"test_{result}"
            if len(result) > 60:
                result = result[:60].rstrip("_")
        elif language == "java":
            # camelCase
            parts = result.split("_")
            result = parts[0] + "".join(p.capitalize() for p in parts[1:])
            if len(result) > 60:
                result = result[:60]
        else:  # csharp
            # PascalCase
            parts = result.split("_")
            result = "".join(p.capitalize() for p in parts if p)
            if len(result) > 60:
                result = result[:60]

        return result or "test_unnamed"

    # ── Fallback renderowanie ──

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy Selenium."""
        language = self._get_language(config)
        ext = FILE_EXTENSIONS.get(language, ".py")
        return TestCodeFile(
            content="# Brak test case'ow do wygenerowania\n",
            file_path=f"tests/selenium/empty/emptyTest{ext}",
            framework=self.FRAMEWORK,
            language=language,
            module_name="empty",
        )

    def _fallback_render(self, context: dict[str, Any], language: str) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        if language == "python":
            return self._fallback_render_python(context)
        elif language == "java":
            return self._fallback_render_java(context)
        else:
            return self._fallback_render_csharp(context)

    def _fallback_render_python(self, context: dict[str, Any]) -> str:
        """Fallback renderowanie Python."""
        lines: list[str] = []
        lines.extend(IMPORTS_PER_LANGUAGE["python"])
        lines.append("")

        # Page Objects
        for pom in context.get("page_objects", []):
            lines.append(f"class {pom['class_name']}:")
            lines.append(f'    """Page Object Model: {pom["page_name"]}"""')
            lines.append("")
            lines.append("    def __init__(self, driver):")
            lines.append("        self.driver = driver")
            lines.append("        self.wait = WebDriverWait(driver, 10)")
            lines.append("")
            for locator in pom.get("locators", []):
                lines.append(f"    _{locator['name']} = ({locator['code']})")
            lines.append("")
            for method in pom.get("methods", []):
                lines.append(f"    def {method['name']}(self{method.get('params', '')}):")
                for action in method.get("actions", []):
                    lines.append(f"        {action['code']}")
                lines.append("")
            lines.append("")

        # Test class
        class_name = context.get("test_class_name", "TestSuite")
        lines.append(f"class {class_name}:")
        lines.append("")

        # Setup
        lines.append("    def setup_method(self):")
        lines.append("        options = webdriver.ChromeOptions()")
        lines.append('        options.add_argument("--headless")')
        lines.append('        options.add_argument("--window-size=1920,1080")')
        lines.append("        self.driver = webdriver.Chrome(options=options)")
        lines.append("        self.wait = WebDriverWait(self.driver, 10)")
        lines.append("")

        # Teardown
        lines.append("    def teardown_method(self):")
        lines.append("        self.driver.quit()")
        lines.append("")

        # Test methods
        for method in context.get("test_methods", []):
            lines.append(f"    def {method['name']}(self):")
            if method.get("url"):
                lines.append(f'        self.driver.get("{method["url"]}")')
            for pom_call in method.get("pom_calls", []):
                if pom_call.get("call"):
                    lines.append(f"        {pom_call['call']}")
            for assertion in method.get("assertions", []):
                if assertion.get("code"):
                    lines.append(f"        {assertion['code']}")
            if not method.get("pom_calls") and not method.get("assertions"):
                lines.append("        pass  # TODO: dodaj kroki testowe")
            lines.append("")

        return "\n".join(lines)

    def _fallback_render_java(self, context: dict[str, Any]) -> str:
        """Fallback renderowanie Java."""
        lines: list[str] = []
        lines.extend(IMPORTS_PER_LANGUAGE["java"])
        lines.append("import java.time.Duration;")
        lines.append("")

        # Page Objects
        for pom in context.get("page_objects", []):
            lines.append(f"public class {pom['class_name']} {{")
            lines.append("    private WebDriver driver;")
            lines.append("    private WebDriverWait wait;")
            lines.append("")
            for locator in pom.get("locators", []):
                lines.append(f"    private By {locator['name']} = {locator['code']};")
            lines.append("")
            lines.append(f"    public {pom['class_name']}(WebDriver driver) {{")
            lines.append("        this.driver = driver;")
            lines.append("        this.wait = new WebDriverWait(driver, Duration.ofSeconds(10));")
            lines.append("    }")
            lines.append("")
            for method in pom.get("methods", []):
                return_type = method.get("returns", "void")
                lines.append(f"    public {return_type} {method['name']}({method.get('params', '').lstrip(', ')}) {{")
                for action in method.get("actions", []):
                    lines.append(f"        {action['code']}")
                lines.append("    }")
                lines.append("")
            lines.append("}")
            lines.append("")

        # Test class
        class_name = context.get("test_class_name", "TestSuite")
        lines.append(f"public class {class_name} {{")
        lines.append("    private WebDriver driver;")
        lines.append("    private WebDriverWait wait;")
        lines.append("")
        lines.append("    @BeforeEach")
        lines.append("    void setUp() {")
        lines.append("        ChromeOptions options = new ChromeOptions();")
        lines.append('        options.addArguments("--headless");')
        lines.append('        options.addArguments("--window-size=1920,1080");')
        lines.append("        this.driver = new ChromeDriver(options);")
        lines.append("        this.wait = new WebDriverWait(driver, Duration.ofSeconds(10));")
        lines.append("    }")
        lines.append("")
        lines.append("    @AfterEach")
        lines.append("    void tearDown() {")
        lines.append("        this.driver.quit();")
        lines.append("    }")

        for method in context.get("test_methods", []):
            lines.append("")
            lines.append("    @Test")
            lines.append(f"    void {method['name']}() {{")
            if method.get("url"):
                lines.append(f'        driver.get("{method["url"]}");')
            for pom_call in method.get("pom_calls", []):
                if pom_call.get("call"):
                    lines.append(f"        {pom_call['call']}")
            for assertion in method.get("assertions", []):
                if assertion.get("code"):
                    lines.append(f"        {assertion['code']}")
            if not method.get("pom_calls") and not method.get("assertions"):
                lines.append("        // TODO: dodaj kroki testowe")
            lines.append("    }")

        lines.append("}")
        return "\n".join(lines)

    def _fallback_render_csharp(self, context: dict[str, Any]) -> str:
        """Fallback renderowanie C#."""
        lines: list[str] = []
        lines.extend(IMPORTS_PER_LANGUAGE["csharp"])
        lines.append("using System;")
        lines.append("using NUnit.Framework;")
        lines.append("")

        # Page Objects
        for pom in context.get("page_objects", []):
            lines.append(f"public class {pom['class_name']} {{")
            lines.append("    private IWebDriver driver;")
            lines.append("    private WebDriverWait wait;")
            lines.append("")
            for locator in pom.get("locators", []):
                lines.append(f"    private By {locator['name']} = {locator['code']};")
            lines.append("")
            lines.append(f"    public {pom['class_name']}(IWebDriver driver) {{")
            lines.append("        this.driver = driver;")
            lines.append("        this.wait = new WebDriverWait(driver, TimeSpan.FromSeconds(10));")
            lines.append("    }")
            lines.append("")
            for method in pom.get("methods", []):
                return_type = method.get("returns", "void")
                lines.append(f"    public {return_type} {method['name']}({method.get('params', '').lstrip(', ')}) {{")
                for action in method.get("actions", []):
                    lines.append(f"        {action['code']}")
                lines.append("    }")
                lines.append("")
            lines.append("}")
            lines.append("")

        # Test class
        class_name = context.get("test_class_name", "TestSuite")
        lines.append("[TestFixture]")
        lines.append(f"public class {class_name} {{")
        lines.append("    private IWebDriver driver;")
        lines.append("    private WebDriverWait wait;")
        lines.append("")
        lines.append("    [SetUp]")
        lines.append("    public void SetUp() {")
        lines.append("        var options = new ChromeOptions();")
        lines.append('        options.AddArgument("--headless");')
        lines.append('        options.AddArgument("--window-size=1920,1080");')
        lines.append("        this.driver = new ChromeDriver(options);")
        lines.append("        this.wait = new WebDriverWait(driver, TimeSpan.FromSeconds(10));")
        lines.append("    }")
        lines.append("")
        lines.append("    [TearDown]")
        lines.append("    public void TearDown() {")
        lines.append("        this.driver.Quit();")
        lines.append("    }")

        for method in context.get("test_methods", []):
            lines.append("")
            lines.append("    [Test]")
            lines.append(f"    public void {method['name']}() {{")
            if method.get("url"):
                lines.append(f'        driver.Url = "{method["url"]}";')
            for pom_call in method.get("pom_calls", []):
                if pom_call.get("call"):
                    lines.append(f"        {pom_call['call']}")
            for assertion in method.get("assertions", []):
                if assertion.get("code"):
                    lines.append(f"        {assertion['code']}")
            if not method.get("pom_calls") and not method.get("assertions"):
                lines.append("        // TODO: dodaj kroki testowe")
            lines.append("    }")

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _parse_compile_error(error_msg: str) -> tuple[int | None, int | None]:
        """Parsuj linie i kolumne z komunikatu bledu."""
        line_match = re.search(r"line\s+(\d+)", error_msg)
        col_match = re.search(r"column\s+(\d+)", error_msg)
        line = int(line_match.group(1)) if line_match else None
        col = int(col_match.group(1)) if col_match else None
        return line, col
