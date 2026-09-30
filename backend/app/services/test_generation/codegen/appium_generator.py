"""Appium mobile code generator — Story 1.42.

Generuje pliki testowe Appium (.py) z test case'ow:
- AppiumBy lokatory: ACCESSIBILITY_ID, XPATH, ID, CLASS_NAME
- Desired capabilities: Android (UiAutomator2) / iOS (XCUITest)
- Gesty mobilne: tap, swipe, scroll, pinch — TouchAction / ActionChains
- Context switching: webview vs native — driver.contexts / driver.switch_to.context()
- Explicit waits (WebDriverWait + expected_conditions) — brak time.sleep()
- Szablony Jinja2: appium/test_mobile.py.j2, appium/conftest.py.j2
- Walidacja skladniowa (py_compile)

AC: 1-11
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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "appium"

# ════════════════════════════════════════════════════════════════════════
# Mapowania skladni Appium (Python only)
# ════════════════════════════════════════════════════════════════════════

# Typy lokatorow Appium
LOCATOR_SYNTAX: dict[str, str] = {
    "accessibility_id": 'AppiumBy.ACCESSIBILITY_ID, "{value}"',
    "id": 'AppiumBy.ID, "{value}"',
    "xpath": 'AppiumBy.XPATH, "{value}"',
    "class_name": 'AppiumBy.CLASS_NAME, "{value}"',
    "css": 'AppiumBy.CSS_SELECTOR, "{value}"',
    "name": 'AppiumBy.NAME, "{value}"',
    "uiautomator": 'AppiumBy.ANDROID_UIAUTOMATOR, "{value}"',
    "ios_class_chain": 'AppiumBy.IOS_CLASS_CHAIN, "{value}"',
    "ios_predicate": 'AppiumBy.IOS_PREDICATE, "{value}"',
}

# Importy Appium
APPIUM_IMPORTS: list[str] = [
    "from appium import webdriver",
    "from appium.webdriver.common.appiumby import AppiumBy",
    "from appium.webdriver.common.touch_action import TouchAction",
    "from selenium.webdriver.support.ui import WebDriverWait",
    "from selenium.webdriver.support import expected_conditions as EC",
]

# Desired capabilities per platforma
DESIRED_CAPABILITIES: dict[str, dict[str, str]] = {
    "android": {
        "platformName": "Android",
        "deviceName": "emulator-5554",
        "automationName": "UiAutomator2",
        "app": "/path/to/app.apk",
    },
    "ios": {
        "platformName": "iOS",
        "deviceName": "iPhone Simulator",
        "automationName": "XCUITest",
        "app": "/path/to/app.ipa",
        "platformVersion": "17.0",
        "udid": "auto",
    },
}

# Asercje mobilne
ASSERT_TEMPLATES: dict[str, str] = {
    "element_visible": 'assert self.wait.until(EC.visibility_of_element_located({locator})), "Element {name} nie jest widoczny"',
    "text_equals": 'assert {element}.text == "{expected}", "Oczekiwano: {expected}, otrzymano: " + {element}.text',
    "text_contains": 'assert "{expected}" in {element}.text, "Tekst {expected} nie znaleziony"',
    "element_present": 'assert self.wait.until(EC.presence_of_element_located({locator})), "Element {name} nie istnieje"',
    "element_enabled": 'assert {element}.is_enabled(), "Element {name} nie jest aktywny"',
    "element_selected": 'assert {element}.is_selected(), "Element {name} nie jest zaznaczony"',
}

# Gesty — szablony kodu
GESTURE_TEMPLATES: dict[str, str] = {
    "tap": "TouchAction(self.driver).tap({params}).perform()",
    "swipe": "TouchAction(self.driver).press(x={start_x}, y={start_y}).wait({duration}).move_to(x={end_x}, y={end_y}).release().perform()",
    "scroll": "TouchAction(self.driver).press(x={start_x}, y={start_y}).wait({duration}).move_to(x={end_x}, y={end_y}).release().perform()",
    "pinch": "TouchAction(self.driver).press(x={center_x}, y={center_y}).move_to(x={center_x}, y={center_y}+{offset}).release().perform()",
    "zoom": "TouchAction(self.driver).press(x={center_x}, y={center_y}).move_to(x={center_x}, y={center_y}-{offset}).release().perform()",
}

# Domyślne parametry gestów
DEFAULT_GESTURE_PARAMS: dict[str, dict[str, int]] = {
    "tap": {},
    "swipe": {"start_x": 500, "start_y": 1500, "end_x": 500, "end_y": 500, "duration": 500},
    "scroll": {"start_x": 500, "start_y": 1500, "end_x": 500, "end_y": 500, "duration": 500},
    "pinch": {"center_x": 500, "center_y": 500, "offset": 100},
    "zoom": {"center_x": 500, "center_y": 500, "offset": 100},
}


@register_generator("appium")
class AppiumCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego Appium (mobile — Python).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "appium".

    Generuje testy mobilne z AppiumBy lokatorami, desired capabilities,
    gestami (TouchAction), context switching (webview/native),
    explicit waits i asercjami.
    """

    FRAMEWORK = "appium"
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
                logger.warning("Katalog szablonow Appium nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── Platforma z configu ──

    def _get_platform(self, config: CodeGenConfig | None = None) -> str:
        """Pobierz platforme: "android" lub "ios"."""
        cfg = config or self.config
        platform = "android"
        project_ctx = cfg.project_context or {}
        if isinstance(project_ctx, dict):
            platform = project_ctx.get("platform", "android")
        if platform.lower() in ("ios", "iphone", "ipad"):
            return "ios"
        return "android"

    # ════════════════════════════════════════════════════════════════
    # 1.3 generate_test_file — glowna metoda
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy Appium z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (typ e2e/system)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem Appium
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        first_tc = test_cases[0]
        platform = self._get_platform(cfg)

        # Nazwa modulu
        module_name = self._extract_module_name(first_tc)

        # 1.4 Importy Appium
        imports = self._build_imports(test_cases, cfg)

        # Ekstrahuj elementy GUI i user flow
        ui_elements = self._extract_ui_elements(test_cases)
        user_flows = self._extract_user_flows(test_cases)

        # Gesty z test case'ow
        has_gestures = self._detect_gestures(test_cases)

        # 1.5 Generuj Page Object Model (ekrany)
        page_objects = self._build_page_objects(ui_elements, user_flows)

        # 1.8 Generuj metody testowe
        test_methods = self._build_test_methods(test_cases, page_objects, user_flows)

        # 2.5 Desired capabilities i driver setup
        desired_caps = self._generate_desired_capabilities(platform, first_tc)
        driver_setup = self._generate_driver_setup(platform, desired_caps)

        # Context switching
        has_webview = self._detect_webview(test_cases)

        # Renderuj szablon
        context = {
            "module_name": module_name,
            "imports": imports,
            "page_objects": page_objects,
            "test_class_name": self._make_class_name(module_name),
            "desired_caps": desired_caps,
            "driver_setup": driver_setup,
            "test_methods": test_methods,
            "platform": platform,
            "has_webview": has_webview,
            "has_gestures": has_gestures,
            "config": cfg,
        }

        try:
            template = self.jinja_env.get_template("test_mobile.py.j2")
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu Appium: %s", exc)
            content = self._fallback_render(context)

        # Walidacja kompilacji (Task 6)
        file_path = self._build_file_path(module_name, platform)
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=module_name,
            test_functions=test_methods,
            imports=imports,
            compilation_result=compilation_result,
        )

    # ════════════════════════════════════════════════════════════════
    # generate_setup — conftest.py
    # ════════════════════════════════════════════════════════════════

    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj plik conftest.py z capabilities.

        Args:
            project_context: kontekst projektu (zawiera "platform")

        Returns:
            Zawartosc pliku conftest.py
        """
        platform = "android"
        if project_context and isinstance(project_context, dict):
            platform = project_context.get("platform", "android")
            if platform.lower() in ("ios", "iphone", "ipad"):
                platform = "ios"

        caps = DESIRED_CAPABILITIES.get(platform, DESIRED_CAPABILITIES["android"])

        context = {
            "platform": platform,
            "platform_default": platform.capitalize(),
            "desired_caps": caps,
            "device_name": caps.get("deviceName", "emulator-5554"),
            "app_path_default": caps.get("app", "/path/to/app.apk"),
        }

        try:
            template = self.jinja_env.get_template("conftest.py.j2")
            return template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania conftest.py.j2: %s", exc)
            return self._fallback_render_conftest(platform, caps)

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
        """Generuj pojedyncza asercje Appium.

        Args:
            expected: oczekiwana wartosc
            actual: rzeczywista wartosc / element
            comparison_type: typ porownania
            message: komunikat przy bledzie

        Returns:
            Kod asercji jako string
        """
        if comparison_type == "element_visible":
            return ASSERT_TEMPLATES["element_visible"].format(
                locator=actual,
                name=expected,
            )
        elif comparison_type == "text_equals":
            return ASSERT_TEMPLATES["text_equals"].format(
                element=actual,
                expected=expected,
            )
        elif comparison_type == "text_contains":
            return ASSERT_TEMPLATES["text_contains"].format(
                element=actual,
                expected=expected,
            )
        elif comparison_type == "element_present":
            return ASSERT_TEMPLATES["element_present"].format(
                locator=actual,
                name=expected,
            )
        elif comparison_type == "element_enabled":
            return ASSERT_TEMPLATES["element_enabled"].format(
                element=actual,
                name=expected,
            )
        elif comparison_type == "element_selected":
            return ASSERT_TEMPLATES["element_selected"].format(
                element=actual,
                name=expected,
            )
        else:
            assertion = f'assert {actual} == "{expected}"'
            if message:
                assertion += f', "{message}"'
            return assertion

    # ════════════════════════════════════════════════════════════════
    # Task 6: validate_syntax
    # ════════════════════════════════════════════════════════════════

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu Appium (py_compile).

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

        warnings: list[str] = []

        # Walidacja specyficzna: Appium
        appium_markers = ["from appium import webdriver", "AppiumBy", "desired_caps", "driver.quit()"]
        for marker in appium_markers:
            if marker not in code:
                warnings.append(f"Brak elementu Appium: {marker}")

        return self._validate_python_syntax(code, warnings)

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

    # ════════════════════════════════════════════════════════════════
    # Metody prywatne — Task 1: Core generator
    # ════════════════════════════════════════════════════════════════

    # ── 1.4 _build_imports ──

    def _build_imports(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[str]:
        """Buduj liste importow Appium."""
        imports = list(APPIUM_IMPORTS)

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

        # TouchAction potrzebne dla gestow
        has_gestures = self._detect_gestures(test_cases)
        if has_gestures:
            ta_import = "from appium.webdriver.common.touch_action import TouchAction"
            if ta_import not in imports:
                imports.append(ta_import)

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
            "locator_type": elem.get("locator_type") or elem.get("strategy", "accessibility_id"),
            "locator_value": elem.get("locator_value") or elem.get("selector") or elem.get("value", ""),
            "element_type": elem.get("element_type") or elem.get("type", "generic"),
            "page_name": elem.get("page_name") or elem.get("screen", "MainScreen"),
        }

    def _extract_user_flows(self, test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ekstrahuj user flows z test case'ow.

        Kazdy flow ma: name, url, steps (lista akcji).
        """
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
                            "gesture": step.get("gesture", ""),
                        }
                    )
                elif isinstance(step, str):
                    pom_steps.append({"action": step, "element": {}, "value": "", "target": "", "gesture": ""})

        return {
            "name": scenario,
            "url": tc.get("url") or tc.get("target_url", ""),
            "steps": pom_steps,
        }

    # ── 1.5 _build_page_objects ──

    def _build_page_objects(
        self,
        ui_elements: list[dict[str, Any]],
        user_flows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Buduj klasy Page Object Model (ekrany) z elementow GUI.

        Grupuje elementy po page_name/screen — jedna klasa per ekran.
        """
        if not ui_elements:
            return self._build_page_objects_from_flows(user_flows)

        # Grupuj po page_name
        pages: dict[str, list[dict[str, Any]]] = {}
        for elem in ui_elements:
            page = elem.get("page_name", "MainScreen")
            if page not in pages:
                pages[page] = []
            pages[page].append(elem)

        if not pages:
            pages["MainScreen"] = []

        page_objects: list[dict[str, Any]] = []
        for page_name, elements in pages.items():
            pom = self._generate_page_object(page_name, elements or [])
            page_objects.append(pom)

        return page_objects

    def _build_page_objects_from_flows(
        self,
        user_flows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fallback: buduj POM z elementow w user flows."""
        pages: dict[str, list[dict[str, Any]]] = {}

        for flow in user_flows:
            flow_name = flow.get("name", "MainScreen")
            page_name = self._make_class_name(flow_name) + "Screen"

            steps = flow.get("steps", [])
            for step in steps:
                if isinstance(step, dict):
                    elem = step.get("element")
                    if isinstance(elem, dict) and elem.get("name"):
                        if page_name not in pages:
                            pages[page_name] = []
                        pages[page_name].append(self._normalize_ui_element(elem))

        if not pages:
            pages["MainScreen"] = []

        return [self._generate_page_object(name, elems) for name, elems in pages.items()]

    def _generate_page_object(
        self,
        page_name: str,
        elements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generuj pojedyncza klase POM (ekran) z lokatorami i metodami."""
        base_name = self._make_class_name(page_name)
        class_name = base_name if base_name.endswith("Screen") else base_name + "Screen"

        # Lokatory
        locators = [self._generate_locator(elem) for elem in elements]

        # Metody interakcji
        methods = self._generate_interaction_methods(elements)

        return {
            "class_name": class_name,
            "page_name": page_name,
            "elements": elements,
            "locators": locators,
            "methods": methods,
        }

    # ── 1.5 _generate_locator ──

    def _generate_locator(self, element: dict[str, Any]) -> dict[str, Any]:
        """Mapuj element GUI na lokator Appium: AppiumBy.ACCESSIBILITY_ID, AppiumBy.XPATH, AppiumBy.ID."""
        locator_type = element.get("locator_type", "accessibility_id")
        locator_value = element.get("locator_value", "")
        element_name = element.get("name", "element")

        # Normalizuj typy
        locator_type = self._normalize_locator_type(locator_type)

        template = LOCATOR_SYNTAX.get(locator_type, LOCATOR_SYNTAX["accessibility_id"])
        locator_code = template.format(value=locator_value)

        var_name = self._normalize_element_name(element_name)

        return {
            "name": var_name,
            "type": locator_type,
            "value": locator_value,
            "code": locator_code,
        }

    @staticmethod
    def _normalize_locator_type(locator_type: str) -> str:
        """Normalizuj typ lokatora dla Appium."""
        mapping = {
            "accessibility_id": "accessibility_id",
            "accessibility": "accessibility_id",
            "content_desc": "accessibility_id",
            "id": "id",
            "resource_id": "id",
            "xpath": "xpath",
            "class_name": "class_name",
            "classname": "class_name",
            "class": "class_name",
            "css": "css",
            "css_selector": "css",
            "name": "name",
            "uiautomator": "uiautomator",
            "android_uiautomator": "uiautomator",
            "ios_class_chain": "ios_class_chain",
            "ios_predicate": "ios_predicate",
        }
        return mapping.get(locator_type.lower(), "accessibility_id")

    # ── 1.7 _generate_interaction_methods ──

    def _generate_interaction_methods(
        self,
        elements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Tworzenie metod POM: click_{element}(), fill_{field}(), get_{text}(), is_visible()."""
        methods: list[dict[str, Any]] = []
        seen: set[str] = set()

        for elem in elements:
            elem_name = elem.get("name", "element")
            elem_type = elem.get("element_type", "generic").lower()
            var_name = self._normalize_element_name(elem_name)

            # Metoda click / tap
            click_method = self._make_tap_method(var_name, elem_name)
            if click_method["name"] not in seen:
                seen.add(click_method["name"])
                methods.append(click_method)

            # Metoda fill dla pol tekstowych
            if elem_type in ("input", "textarea", "text_field", "textbox", "field", "edittext"):
                fill_method = self._make_fill_method(var_name, elem_name)
                if fill_method["name"] not in seen:
                    seen.add(fill_method["name"])
                    methods.append(fill_method)

            # Metoda get_text
            text_method = self._make_get_text_method(var_name, elem_name)
            if text_method["name"] not in seen:
                seen.add(text_method["name"])
                methods.append(text_method)

            # Metoda is_visible
            visible_method = self._make_is_visible_method(var_name, elem_name)
            if visible_method["name"] not in seen:
                seen.add(visible_method["name"])
                methods.append(visible_method)

        return methods

    def _make_tap_method(self, var_name: str, elem_name: str) -> dict[str, Any]:
        """Generuj metode tap_{element}()."""
        safe_name = self._normalize_element_name(elem_name)
        return {
            "name": f"tap_{safe_name}",
            "params": "",
            "element": var_name,
            "actions": [
                {"code": f"element = self.wait.until(EC.element_to_be_clickable(self._{var_name}))"},
                {"code": "element.click()"},
            ],
            "returns": "element",
        }

    def _make_fill_method(self, var_name: str, elem_name: str) -> dict[str, Any]:
        """Generuj metode fill_{field}()."""
        safe_name = self._normalize_element_name(elem_name)
        return {
            "name": f"fill_{safe_name}",
            "params": ", value",
            "element": var_name,
            "actions": [
                {"code": f"element = self.wait.until(EC.presence_of_element_located(self._{var_name}))"},
                {"code": "element.clear()"},
                {"code": "element.send_keys(value)"},
            ],
            "returns": "element",
        }

    def _make_get_text_method(self, var_name: str, elem_name: str) -> dict[str, Any]:
        """Generuj metode get_{text}()."""
        safe_name = self._normalize_element_name(elem_name)
        return {
            "name": f"get_{safe_name}_text",
            "params": "",
            "element": var_name,
            "actions": [
                {"code": f"element = self.wait.until(EC.presence_of_element_located(self._{var_name}))"},
                {"code": "return element.text"},
            ],
            "returns": "text",
        }

    def _make_is_visible_method(self, var_name: str, elem_name: str) -> dict[str, Any]:
        """Generuj metode is_visible()."""
        safe_name = self._normalize_element_name(elem_name)
        return {
            "name": f"is_{safe_name}_visible",
            "params": "",
            "element": var_name,
            "actions": [
                {"code": f"element = self.wait.until(EC.visibility_of_element_located(self._{var_name}))"},
                {"code": "return element.is_displayed()"},
            ],
            "returns": "bool",
        }

    # ── 1.8 _build_test_methods ──

    def _build_test_methods(
        self,
        test_cases: list[dict[str, Any]],
        page_objects: list[dict[str, Any]],
        user_flows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generuj metody testowe: init driver -> navigate -> interakcje -> asserty -> cleanup."""
        methods: list[dict[str, Any]] = []

        for i, tc in enumerate(test_cases):
            flow = user_flows[i] if i < len(user_flows) else None
            method = self._generate_test_method(tc, page_objects, flow)
            methods.append(method)

        return methods

    def _generate_test_method(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
        user_flow: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Generuj specyfikacje pojedynczego testu Appium."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed_test"
        method_name = self._normalize_test_method_name(scenario)

        # Mapowanie krokow na sekwencje akcji
        steps = self._build_test_steps(test_case, page_objects, user_flow)

        # Asserty po akcjach
        assertions = self._generate_asserts_after_action(test_case, page_objects)

        # Explicit waits
        waits = self._generate_explicit_waits(test_case, page_objects)

        return {
            "name": method_name,
            "url": user_flow.get("url", "") if user_flow else "",
            "steps": steps,
            "assertions": assertions,
            "waits": waits,
            "scenario": scenario,
        }

    def _build_test_steps(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
        user_flow: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        """Buduj kroki testowe z akcjami, gestami i asercjami."""
        steps_code: list[dict[str, str]] = []

        raw_steps = []
        if user_flow:
            raw_steps = user_flow.get("steps", [])
        if not raw_steps:
            raw_steps = test_case.get("steps", [])

        if not isinstance(raw_steps, list):
            return steps_code

        element_to_pom = self._build_element_to_pom_map(page_objects)

        for step in raw_steps:
            if not isinstance(step, dict):
                continue

            action = step.get("action", "")
            value = step.get("value", "")
            target = step.get("target", "")
            gesture = step.get("gesture", "")
            elem = step.get("element") or step.get("ui_element")

            # Gesty mobilne
            if gesture:
                gesture_code = self._generate_gesture(gesture, step)
                steps_code.append(
                    {
                        "description": f"Gest: {gesture}",
                        "gesture_code": gesture_code,
                        "action_code": "",
                        "assertion_code": "",
                    }
                )
                continue

            # Standardowa akcja POM
            if isinstance(elem, dict):
                elem_name = elem.get("name", "")
                action_code = self._resolve_action(elem_name, action, value, target, element_to_pom)
            elif action and isinstance(action, str):
                action_code = self._render_direct_action(action, value)
            else:
                action_code = f"# {action or 'akcja'}"

            steps_code.append(
                {
                    "description": action or "krok",
                    "gesture_code": "",
                    "action_code": action_code,
                    "assertion_code": "",
                }
            )

        return steps_code

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

    def _resolve_action(
        self,
        elem_name: str,
        action: str,
        value: str,
        target: str,
        element_to_pom: dict[str, tuple[str, list[dict[str, Any]]]],
    ) -> str:
        """Rozwiaz element na akcje."""
        safe_name = self._normalize_element_name(elem_name)

        if elem_name in element_to_pom:
            pom_class, _methods = element_to_pom[elem_name]
            pom_var = self._normalize_element_name(pom_class.replace("Screen", "").lower())
        else:
            pom_var = safe_name

        action_lower = action.lower() if action else ""
        if any(kw in action_lower for kw in ("click", "press", "tap", "submit")):
            return f"{pom_var}_screen.tap_{safe_name}()"
        elif any(kw in action_lower for kw in ("fill", "type", "enter", "input", "write")):
            val = value if value is not None else (target or "")
            return f'{pom_var}_screen.fill_{safe_name}("{val}")'
        elif any(kw in action_lower for kw in ("navigate", "go", "open", "visit")):
            return f'self.driver.get("{value or target}")'
        elif any(kw in action_lower for kw in ("wait", "sleep")):
            return self._render_explicit_wait_code(safe_name)
        elif any(kw in action_lower for kw in ("check", "assert", "verify")):
            return f"{pom_var}_screen.is_{safe_name}_visible()"
        else:
            return f"# {action or 'akcja'} — {elem_name}"

    @staticmethod
    def _render_direct_action(action: str, value: str) -> str:
        """Renderuj bezposrednia akcje bez POM."""
        if ("driver.get" in action or "navigate" in action) and value:
            return f'self.driver.get("{value}")'
        return action

    # ── Task 2: Desired capabilities i platformy ──

    def _generate_desired_capabilities(
        self,
        platform: str,
        test_case: dict[str, Any],
    ) -> dict[str, str]:
        """Tworzenie dict z desired capabilities dla platformy.

        Args:
            platform: "android" lub "ios"
            test_case: pierwszy test case z ewentualnymi nadpisaniami

        Returns:
            Dict z desired capabilities
        """
        base_caps = dict(DESIRED_CAPABILITIES.get(platform, DESIRED_CAPABILITIES["android"]))

        # Nadpisania z test case (setup_steps, desired_caps)
        tc_caps = test_case.get("desired_caps") or test_case.get("capabilities")
        if isinstance(tc_caps, dict):
            base_caps.update(tc_caps)

        return base_caps

    def _generate_driver_setup(
        self,
        platform: str,
        desired_caps: dict[str, str],
    ) -> dict[str, Any]:
        """Generuj konfiguracje drivera Appium.

        Args:
            platform: "android" lub "ios"
            desired_caps: desired capabilities

        Returns:
            Dict z konfiguracja drivera
        """
        caps_lines: list[str] = []
        caps_lines.append("desired_caps = {")
        for key, value in desired_caps.items():
            caps_lines.append(f'    "{key}": "{value}",')
        caps_lines.append("}")

        return {
            "platform": platform,
            "caps_lines": caps_lines,
            "hub_url": "http://localhost:4723/wd/hub",
        }

    # ── Task 3: Context switching (webview/native) ──

    def _detect_webview(self, test_cases: list[dict[str, Any]]) -> bool:
        """Detekcja czy test case zawiera elementy webview."""
        for tc in test_cases:
            # Sprawdz webview_elements
            webview = tc.get("webview_elements")
            if webview:
                return True
            # Sprawdz kroki z kontekstem
            steps = tc.get("steps", [])
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        context_type = step.get("context", "")
                        if context_type and "webview" in context_type.lower():
                            return True
        return False

    def _generate_context_switch_code(self, context_type: str) -> str:
        """Generuj kod switchowania kontekstu.

        Args:
            context_type: "webview" lub "native"

        Returns:
            Kod switchowania kontekstu
        """
        if context_type == "webview":
            return (
                "contexts = self.driver.contexts\n"
                '        webview = [c for c in contexts if "WEBVIEW" in c]\n'
                "        if webview:\n"
                "            self.driver.switch_to.context(webview[0])"
            )
        else:
            return 'self.driver.switch_to.context("NATIVE_APP")'

    # ── Task 4: Gesty mobilne ──

    def _detect_gestures(self, test_cases: list[dict[str, Any]]) -> bool:
        """Detekcja czy test case zawiera gesty."""
        for tc in test_cases:
            gestures = tc.get("gestures")
            if gestures:
                return True
            steps = tc.get("steps", [])
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        gesture = step.get("gesture", "")
                        if gesture:
                            return True
            user_flow = tc.get("user_flow", {})
            if isinstance(user_flow, dict):
                steps = user_flow.get("steps", [])
                if isinstance(steps, list):
                    for step in steps:
                        if isinstance(step, dict):
                            gesture = step.get("gesture", "")
                            if gesture:
                                return True
        return False

    def _generate_gesture(self, gesture_type: str, step: dict[str, Any]) -> str:
        """Generuj kod gestu mobilnego: tap, swipe, scroll, pinch.

        Args:
            gesture_type: typ gestu (tap, swipe, scroll, pinch, zoom)
            step: dane kroku z parametrami gestu

        Returns:
            Kod gestu jako string
        """
        gesture_lower = gesture_type.lower()

        if gesture_lower == "tap":
            return self._generate_tap(step)
        elif gesture_lower == "swipe":
            return self._generate_swipe(step)
        elif gesture_lower == "scroll":
            return self._generate_scroll(step)
        elif gesture_lower in ("pinch", "zoom"):
            return self._generate_pinch(gesture_lower, step)
        else:
            return f"# Nieobsługiwany gest: {gesture_type}"

    def _generate_tap(self, step: dict[str, Any]) -> str:
        """Generuj kod gestu tap."""
        element = step.get("element")
        if isinstance(element, dict) and element.get("name"):
            var_name = self._normalize_element_name(element["name"])
            return f"element = self.wait.until(EC.element_to_be_clickable(self._{var_name}))\n        element.click()"
        elif step.get("x") and step.get("y"):
            return f"TouchAction(self.driver).tap(x={step['x']}, y={step['y']}).perform()"
        else:
            return "TouchAction(self.driver).tap(element).perform()"

    def _generate_swipe(self, step: dict[str, Any]) -> str:
        """Generuj kod gestu swipe z koordynatami."""
        defaults = DEFAULT_GESTURE_PARAMS["swipe"]
        start_x = step.get("start_x", defaults["start_x"])
        start_y = step.get("start_y", defaults["start_y"])
        end_x = step.get("end_x", defaults["end_x"])
        end_y = step.get("end_y", defaults["end_y"])
        duration = step.get("duration", defaults["duration"])

        return (
            f"TouchAction(self.driver)\\\n"
            f"        .press(x={start_x}, y={start_y})\\\n"
            f"        .wait({duration})\\\n"
            f"        .move_to(x={end_x}, y={end_y})\\\n"
            f"        .release()\\\n"
            f"        .perform()"
        )

    def _generate_scroll(self, step: dict[str, Any]) -> str:
        """Generuj kod gestu scroll."""
        # Scroll to element lub scroll z koordynatami
        element = step.get("target_element") or step.get("scroll_to")
        if element:
            return (
                f'target = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, "{element}")\n'
                f"        self.driver.execute_script('mobile: scroll', "
                f"{{'element': target.id, 'toVisible': True}})"
            )

        # Fallback: scroll z koordynatami (identyczny ze swipe)
        return self._generate_swipe(step)

    def _generate_pinch(self, gesture: str, step: dict[str, Any]) -> str:
        """Generuj kod gestu pinch/zoom."""
        defaults = DEFAULT_GESTURE_PARAMS.get(gesture, DEFAULT_GESTURE_PARAMS["pinch"])
        center_x = step.get("center_x", defaults["center_x"])
        center_y = step.get("center_y", defaults["center_y"])
        offset = step.get("offset", defaults["offset"])

        direction = "+" if gesture == "pinch" else "-"
        return (
            f"TouchAction(self.driver)\\\n"
            f"        .press(x={center_x}, y={center_y})\\\n"
            f"        .move_to(x={center_x}, y={center_y}{direction}{offset})\\\n"
            f"        .release()\\\n"
            f"        .perform()"
        )

    # ── 1.10 _generate_explicit_waits ──

    def _generate_explicit_waits(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Generuj explicit waits (WebDriverWait + expected_conditions)."""
        waits: list[dict[str, str]] = []

        wait_elements = test_case.get("wait_for") or test_case.get("explicit_waits")
        if not wait_elements:
            return waits

        if isinstance(wait_elements, list):
            for wait_spec in wait_elements:
                if isinstance(wait_spec, dict):
                    wait_code = self._render_explicit_wait_code(
                        wait_spec.get("element", ""),
                        wait_spec.get("condition", "presence"),
                        wait_spec.get("timeout", 10),
                    )
                    waits.append({"code": wait_code})

        return waits

    def _render_explicit_wait_code(
        self,
        element_name: str,
        condition: str = "presence",
        timeout: int = 10,
    ) -> str:
        """Renderuj kod WebDriverWait."""
        safe_name = self._normalize_element_name(element_name)

        wait_map = {
            "clickable": f"self.wait.until(EC.element_to_be_clickable(self._{safe_name}))",
            "visible": f"self.wait.until(EC.visibility_of_element_located(self._{safe_name}))",
            "text": f'self.wait.until(EC.text_to_be_present_in_element(self._{safe_name}, "expected_text"))',
        }
        return wait_map.get(condition, f"self.wait.until(EC.presence_of_element_located(self._{safe_name}))")

    # ── 1.11 _generate_asserts_after_action ──

    def _generate_asserts_after_action(
        self,
        test_case: dict[str, Any],
        page_objects: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Dodawanie assert sprawdzajacego stan ekranu po akcji."""
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

        return assertions

    # ── Nazewnictwo ──

    @staticmethod
    def _extract_module_name(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe modulu z test case."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        result = re.sub(r"[^\w]", "_", scenario)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "unnamed"

    @staticmethod
    def _make_class_name(name: str) -> str:
        """Utworz nazwe klasy PascalCase."""
        if not name:
            return "Unnamed"
        name = re.sub(r"\.\w+$", "", name)
        name = re.sub(r"[-_]+", " ", name)
        parts = name.split()
        return "".join((p[0].upper() + p[1:]) if p else "" for p in parts if p)

    @staticmethod
    def _normalize_element_name(name: str) -> str:
        """Normalizuj nazwe elementu na snake_case."""
        if not name:
            return "element"
        result = re.sub(r"[\s\-]+", "_", name.lower())
        result = re.sub(r"[^a-z0-9_]", "", result)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "element"

    @staticmethod
    def _normalize_test_method_name(scenario: str) -> str:
        """Normalizuj nazwe metody testowej (Python — test_ prefix)."""
        result = re.sub(r"[^\w]", "_", scenario.lower())
        result = re.sub(r"_+", "_", result).strip("_")

        if not result.startswith("test_"):
            result = f"test_{result}"
        if len(result) > 60:
            result = result[:60].rstrip("_")

        return result or "test_unnamed"

    # ── Sciezka pliku ──

    @staticmethod
    def _build_file_path(module_name: str, platform: str) -> str:
        """Generuj sciezke pliku testowego: tests/mobile/{platform}/{test_name}.py."""
        return f"tests/mobile/{platform}/{module_name}.py"

    # ── Fallback renderowanie ──

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy Appium."""
        platform = self._get_platform(config)
        return TestCodeFile(
            content="# Brak test case'ow do wygenerowania\n",
            file_path=f"tests/mobile/{platform}/empty.py",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    def _fallback_render(self, context: dict[str, Any]) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        lines: list[str] = []

        # Importy
        lines.extend(APPIUM_IMPORTS)
        lines.append("")

        # Page Objects (ekrany)
        for pom in context.get("page_objects", []):
            lines.append(f"class {pom['class_name']}:")
            lines.append(f'    """Ekran: {pom["page_name"]}"""')
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

        # Klasa testowa
        class_name = context.get("test_class_name", "TestMobile")
        platform = context.get("platform", "android")
        lines.append(f"class {class_name}:")
        lines.append(f'    """Testy mobilne — platforma {platform}"""')
        lines.append("")

        # Setup — desired capabilities
        lines.append("    def setup_method(self):")
        driver_setup = context.get("driver_setup", {})
        for cap_line in driver_setup.get("caps_lines", []):
            lines.append(f"        {cap_line}")
        lines.append(
            f'        self.driver = webdriver.Remote("{driver_setup.get("hub_url", "http://localhost:4723/wd/hub")}", desired_caps)'
        )
        lines.append("        self.wait = WebDriverWait(self.driver, 10)")
        lines.append("")

        # Context switching helpers
        if context.get("has_webview"):
            lines.append("    def _switch_to_webview(self):")
            lines.append("        contexts = self.driver.contexts")
            lines.append('        webview = [c for c in contexts if "WEBVIEW" in c]')
            lines.append("        if webview:")
            lines.append("            self.driver.switch_to.context(webview[0])")
            lines.append("")
            lines.append("    def _switch_to_native(self):")
            lines.append('        self.driver.switch_to.context("NATIVE_APP")')
            lines.append("")

        # Teardown
        lines.append("    def teardown_method(self):")
        lines.append("        self.driver.quit()")
        lines.append("")

        # Metody testowe
        for method in context.get("test_methods", []):
            lines.append(f"    def {method['name']}(self):")
            if method.get("url"):
                lines.append(f'        self.driver.get("{method["url"]})')
            for wait in method.get("waits", []):
                if wait.get("code"):
                    lines.append(f"        {wait['code']}")
            for step in method.get("steps", []):
                if step.get("gesture_code"):
                    for gesture_line in step["gesture_code"].split("\n"):
                        lines.append(f"        {gesture_line.strip()}" if gesture_line.strip() else "")
                elif step.get("action_code"):
                    lines.append(f"        {step['action_code']}")
            for assertion in method.get("assertions", []):
                if assertion.get("code"):
                    lines.append(f"        {assertion['code']}")
            if not method.get("steps") and not method.get("assertions"):
                lines.append("        pass  # TODO: dodaj kroki testowe i asercje")
            lines.append("")

        return "\n".join(lines)

    def _fallback_render_conftest(self, platform: str, caps: dict[str, str]) -> str:
        """Fallback renderowanie conftest.py."""
        lines: list[str] = []
        lines.append("import pytest")
        lines.append("from appium import webdriver")
        lines.append("")
        lines.append("")
        lines.append("def pytest_addoption(parser):")
        lines.append(f'    parser.addoption("--platform", default="{platform.capitalize()}")')
        lines.append(f'    parser.addoption("--app-path", default="{caps.get("app", "/path/to/app.apk")}")')
        lines.append("")
        lines.append("")
        lines.append("@pytest.fixture")
        lines.append("def driver(request):")
        lines.append("    platform = request.config.getoption('--platform')")
        lines.append("    app_path = request.config.getoption('--app-path')")
        lines.append("")
        lines.append("    caps = {")
        lines.append('        "platformName": platform,')
        lines.append(f'        "deviceName": "{caps.get("deviceName", "emulator-5554")}",')
        lines.append('        "automationName": "UiAutomator2" if platform == "Android" else "XCUITest",')
        lines.append('        "app": app_path,')
        lines.append("    }")
        lines.append('    driver = webdriver.Remote("http://localhost:4723/wd/hub", caps)')
        lines.append("    yield driver")
        lines.append("    driver.quit()")

        return "\n".join(lines)

    # ── Parse compile error ──

    @staticmethod
    def _parse_compile_error(error_msg: str) -> tuple[int | None, int | None]:
        """Parsuj linie i kolumne z komunikatu bledu."""
        line_match = re.search(r"line\s+(\d+)", error_msg)
        col_match = re.search(r"column\s+(\d+)", error_msg)
        line = int(line_match.group(1)) if line_match else None
        col = int(col_match.group(1)) if col_match else None
        return line, col
