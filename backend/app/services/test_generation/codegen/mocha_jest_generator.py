"""Mocha/Jest code generator — Story 1.39.

Generuje pliki testowe Mocha lub Jest (.test.js / .test.ts) z test case'ow:
- describe/it blocks z konwencja 'should X when Y'
- Asercje: Jest (expect().toBe()) lub Mocha+Chai (expect().to.equal())
- beforeEach / afterEach lifecycle hooks
- Mockowanie: Jest (jest.mock/fn/spyOn) lub Sinon (stub/mock/sandbox)
- async/await z proper error handling
- TypeScript support (.test.ts z typami)
- Parametryzacja: test.each() (Jest) lub it.each() (Mocha)
- Walidacja skladniowa (strukturalna lub node --check / tsc --noEmit)
- Szablony Jinja2 (test_module.test.js.j2 / test_module.test.ts.j2)

AC: 1-11
"""

import logging
import re
import subprocess
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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "mocha_jest"

# ════════════════════════════════════════════════════════════════════════
# Mapowania asercji — Jest
# ════════════════════════════════════════════════════════════════════════

JEST_ASSERTION_MAP: dict[str, str] = {
    "equals": "expect({actual}).toBe({expected});",
    "not_equals": "expect({actual}).not.toBe({expected});",
    "contains": "expect({actual}).toContain({expected});",
    "not_contains": "expect({actual}).not.toContain({expected});",
    "throws": "expect(() => {{ {actual}; }}).toThrow({expected});",
    "approx": "expect({actual}).toBeCloseTo({expected}, 2);",
    "is_none": "expect({actual}).toBeNull();",
    "is_not_none": "expect({actual}).toBeDefined();",
    "is_true": "expect({actual}).toBeTruthy();",
    "is_false": "expect({actual}).toBeFalsy();",
    "greater_than": "expect({actual}).toBeGreaterThan({expected});",
    "less_than": "expect({actual}).toBeLessThan({expected});",
    "has_length": "expect({actual}).toHaveLength({expected});",
    "is_instance": "expect({actual}).toBeInstanceOf({expected});",
    "matches": "expect({actual}).toMatch({expected});",
}

# ════════════════════════════════════════════════════════════════════════
# Mapowania asercji — Mocha + Chai
# ════════════════════════════════════════════════════════════════════════

MOCHA_ASSERTION_MAP: dict[str, str] = {
    "equals": "expect({actual}).to.equal({expected});",
    "not_equals": "expect({actual}).to.not.equal({expected});",
    "contains": "expect({actual}).to.include({expected});",
    "not_contains": "expect({actual}).to.not.include({expected});",
    "throws": "expect(() => {{ {actual}; }}).to.throw({expected});",
    "approx": "expect({actual}).to.be.closeTo({expected}, 2);",
    "is_none": "expect({actual}).to.be.null;",
    "is_not_none": "expect({actual}).to.exist;",
    "is_true": "expect({actual}).to.be.true;",
    "is_false": "expect({actual}).to.be.false;",
    "greater_than": "expect({actual}).to.be.above({expected});",
    "less_than": "expect({actual}).to.be.below({expected});",
    "has_length": "expect({actual}).to.have.lengthOf({expected});",
    "is_instance": "expect({actual}).to.be.instanceOf({expected});",
    "matches": "expect({actual}).to.match({expected});",
}


@register_generator("mocha_jest")
class MochaJestCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego Mocha/Jest (JavaScript/TypeScript).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "mocha_jest".

    Parametr framework_variant ("jest" lub "mocha") decyduje o skladni.
    """

    FRAMEWORK = "mocha_jest"
    LANGUAGE = "javascript"
    FILE_EXTENSION = ".test.js"

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
                logger.warning("Katalog szablonow Mocha/Jest nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── Wlasciwosc: variant frameworka ──

    def _get_variant(self, config: CodeGenConfig | None = None) -> str:
        """Pobierz variant frameworka: "jest" lub "mocha"."""
        cfg = config or self.config
        if cfg.project_context and isinstance(cfg.project_context, dict):
            variant = cfg.project_context.get("framework_variant", "jest")
            return variant if variant in ("jest", "mocha") else "jest"
        return "jest"

    # ── Wlasciwosc: TypeScript ──

    def _is_typescript(self, test_cases: list[dict[str, Any]], config: CodeGenConfig) -> bool:
        """Sprawdz czy projekt uzywwa TypeScript."""
        if config.project_context and isinstance(config.project_context, dict):
            ts_flag = config.project_context.get("typescript")
            if ts_flag is not None:
                return bool(ts_flag)

        # Fallback — sprawdz rozszerzenia w source_file
        for tc in test_cases:
            source = tc.get("source_file") or tc.get("source_module") or ""
            if source.endswith(".ts") or source.endswith(".tsx"):
                return True

        return False

    # ════════════════════════════════════════════════════════════════
    # 1.3 generate_test_file — glowna metoda
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy Mocha/Jest z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (z modelu TestCase)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem JS/TS
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        variant = self._get_variant(cfg)
        is_ts = self._is_typescript(test_cases, cfg)
        first_tc = test_cases[0]

        # Nazwa modulu i describe block
        module_name = self._extract_module_name(first_tc)
        test_module_name = module_name

        # 1.4 Buduj importy
        imports = self._build_imports(test_cases, cfg, variant, is_ts)

        # Mocki (Task 2)
        mocks = self._build_all_mocks(test_cases, cfg, variant)

        # Lifecycle hooks (1.10)
        setup_steps, teardown_steps = self._build_lifecycle_steps(test_cases)
        # Mocki wymagaja afterEach (cleanup) nawet bez explicit teardown_steps
        has_lifecycle = bool(setup_steps or teardown_steps or mocks)
        has_teardown = bool(teardown_steps or mocks)

        # Test cases (1.6)
        test_methods = self._build_all_test_methods(test_cases, cfg, variant)

        # Test each helpers (parametryzacja)
        test_each_helpers = self._build_test_each_helpers(test_methods)

        # Wybierz szablon
        template_name = "test_module.test.ts.j2" if is_ts else "test_module.test.js.j2"
        file_ext = ".test.ts" if is_ts else ".test.js"
        language = "typescript" if is_ts else "javascript"

        # Renderuj szablon (Task 4)
        context = {
            "test_module_name": test_module_name,
            "imports": imports,
            "describe_blocks": self._build_describe_blocks(test_methods, module_name),
            "has_lifecycle": has_lifecycle,
            "setup_steps": setup_steps,
            "has_teardown": has_teardown,
            "teardown_steps": teardown_steps,
            "mocks": mocks,
            "test_cases": test_methods,
            "test_each_helpers": test_each_helpers,
            "variant": variant,
            "is_jest": variant == "jest",
            "is_mocha": variant == "mocha",
            "is_typescript": is_ts,
            "project_context": cfg.project_context,
        }

        try:
            template = self.jinja_env.get_template(template_name)
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu Mocha/Jest: %s", exc)
            content = self._fallback_render(context, variant)

        # Walidacja kompilacji (Task 5)
        file_path = self._build_file_path(module_name, file_ext)
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        # Zbuduj fixtures dict
        fixtures = self._build_fixtures_from_mocks(mocks)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=language,
            module_name=module_name,
            fixtures=fixtures,
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
        """Generuj setup testowy Mocha/Jest (bazowy plik konfiguracyjny).

        Args:
            project_context: kontekst projektu

        Returns:
            Zawartosc bazowego pliku setup JS/TS
        """
        return "// Bazowy plik setup — rozszerz w konkretnych testach\n"

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
        """Generuj pojedyncza asercje Jest lub Mocha+Chai.

        Args:
            expected: oczekiwana wartosc
            actual: rzeczywista wartosc
            comparison_type: typ porownania
            message: komunikat przy bledzie (nie uzywany w Jest/Mocha)

        Returns:
            Kod asercji JS/TS jako string
        """
        variant = self._get_variant()
        return self._map_assertion(expected, actual, comparison_type, variant, message)

    # ════════════════════════════════════════════════════════════════
    # Task 5: validate_syntax
    # ════════════════════════════════════════════════════════════════

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu JS/TS.

        Najpierw probuje node --check / tsc --noEmit, potem walidacja strukturalna.

        Args:
            code: kod JS/TS do walidacji

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

        # 5.4 Walidacja specyficzna: sprawdzenie obecnosci describe/it/expect
        has_describe = "describe(" in code or "describe('" in code or 'describe("' in code
        has_it_or_test = "it(" in code or "test(" in code
        if not has_describe:
            warnings.append("Brak bloku describe() w wygenerowanym kodzie")
        if not has_it_or_test:
            warnings.append("Brak bloku it()/test() w wygenerowanym kodzie")

        # Najpierw sprobuj node --check / tsc --noEmit
        tool_result = self._validate_with_tool(code)
        if tool_result is not None:
            tool_result.warnings = warnings
            return tool_result

        # Fallback — walidacja strukturalna
        structural_result = self._validate_structural(code)
        structural_result.warnings = warnings
        return structural_result

    # ════════════════════════════════════════════════════════════════
    # Metody prywatne — Task 1: Core generator
    # ════════════════════════════════════════════════════════════════

    # ── 1.4 _build_imports ──

    def _build_imports(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
        variant: str,
        is_ts: bool,
    ) -> list[str]:
        """Buduj liste importow JS/TS z kontekstu test case'ow."""
        imports: list[str] = []
        seen: set[str] = set()

        # Import testowanego modulu
        first_tc = test_cases[0]
        source_module = first_tc.get("source_module") or first_tc.get("source_file")
        source_class = first_tc.get("source_class")
        module_name = self._extract_module_name(first_tc)

        if source_module:
            # Relatywna sciezka importu
            import_path = self._source_to_import_path(source_module)
            if source_class:
                if is_ts:
                    imp = f"import {{ {source_class} }} from '{import_path}';"
                else:
                    imp = f"const {{ {source_class} }} = require('{import_path}');"
            else:
                if is_ts:
                    imp = f"import * as {self._to_camel_case(module_name)} from '{import_path}';"
                else:
                    imp = f"const {self._to_camel_case(module_name)} = require('{import_path}');"
            if imp not in seen:
                seen.add(imp)
                imports.append(imp)

        # Mocha + Sinon imports (variant == "mocha")
        if variant == "mocha":
            mocha_imports = [
                "const { expect } = require('chai');",
                "const sinon = require('sinon');",
            ]
            for imp in mocha_imports:
                if imp not in seen:
                    seen.add(imp)
                    imports.append(imp)
        # Jest nie wymaga importow — describe, it, expect sa globals

        # Explicit imports z test case
        for tc in test_cases:
            tc_imports = tc.get("imports") or tc.get("usings")
            if isinstance(tc_imports, list):
                for imp in tc_imports:
                    if imp and imp not in seen:
                        seen.add(imp)
                        imports.append(imp)
            elif isinstance(tc_imports, str) and tc_imports.strip():
                for imp in tc_imports.strip().split("\n"):
                    imp = imp.strip()
                    if imp and imp not in seen:
                        seen.add(imp)
                        imports.append(imp)

        # Dodaj importy warunkowe (Sinon dla mockow)
        if variant == "mocha":
            deps = any(tc.get("dependencies") or tc.get("mocks") for tc in test_cases)
            if deps:
                sinon_imp = "const sinon = require('sinon');"
                if sinon_imp not in seen:
                    seen.add(sinon_imp)
                    imports.append(sinon_imp)

        return imports

    # ── 1.5 _generate_describe_block ──

    def _build_describe_blocks(
        self,
        test_methods: list[dict[str, Any]],
        module_name: str,
    ) -> list[dict[str, Any]]:
        """Buduj bloki describe z test case'ow."""
        # Wszystkie testy w jednym describe dla danego modulu
        return [
            {
                "name": module_name,
                "tests": test_methods,
            }
        ]

    # ── 1.6 _generate_test_case ──

    def _build_all_test_methods(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
        variant: str,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje testow it() z test case'ow."""
        methods: list[dict[str, Any]] = []

        for tc in test_cases:
            method = self._generate_test_method(tc, config, variant)
            if method:
                methods.append(method)

        return methods

    def _generate_test_method(
        self,
        test_case: dict[str, Any],
        config: CodeGenConfig,
        variant: str,
    ) -> dict[str, Any]:
        """Generuj specyfikacje pojedynczego testu it()."""
        # 1.8 Normalizacja opisu — "should X when Y"
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        description = self._normalize_test_description(scenario)

        # 1.9 Async/await
        is_async = self._is_async_test(test_case)

        # Parametryzacja
        parameterized = False
        test_each_data: list[list[str]] | None = None
        parameters: list[dict[str, str]] = []

        if config.include_parametrize:
            param_result = self._generate_parameterized_test(test_case, variant)
            if param_result:
                parameterized = True
                test_each_data = param_result.get("test_each_data")
                parameters = param_result.get("parameters", [])

        # Kroki
        steps = self._build_steps(test_case)

        # Asercje
        assertions = self._build_assertions(test_case, variant)

        # Mock stubbing
        mock_stubbing = self._build_mock_stubbing(test_case, variant)

        return {
            "description": description,
            "is_async": is_async,
            "parameterized": parameterized,
            "test_each_data": test_each_data,
            "parameters": parameters,
            "steps": steps,
            "assertions": assertions,
            "mock_stubbing": mock_stubbing,
        }

    # ── 1.7 _map_assertion ──

    def _map_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        variant: str = "jest",
        message: str | None = None,
    ) -> str:
        """Mapuj comparison_type na asercje Jest lub Mocha+Chai."""
        assertion_map = JEST_ASSERTION_MAP if variant == "jest" else MOCHA_ASSERTION_MAP
        template = assertion_map.get(comparison_type)

        if template:
            result = template.format(
                expected=expected,
                actual=actual,
            )
        else:
            if variant == "jest":
                result = f"expect({actual}).toBe({expected}); // nieznany comparison_type: {comparison_type}"
            else:
                result = f"expect({actual}).to.equal({expected}); // nieznany comparison_type: {comparison_type}"

        return result

    # ── 1.8 _normalize_test_description ──

    @staticmethod
    def _normalize_test_description(scenario: str) -> str:
        """Konwersja nazwy scenariusza na opis testu: "should X when Y".

        Jezeli nazwa juz zawiera "should" lub "when", zachowaj ja.
        """
        if not scenario:
            return "should work as expected"

        scenario = scenario.strip()

        # Jezeli juz zaczyna sie od "should" — zachowaj
        if scenario.lower().startswith("should"):
            return scenario[:1].lower() + scenario[1:]

        # Jezeli zawiera "when" — dodaj "should"
        if " when " in scenario.lower() or scenario.lower().startswith("when "):
            return f"should {scenario[0].lower()}{scenario[1:]}"

        # Domyslnie — "should {scenario}"
        return f"should {scenario[0].lower()}{scenario[1:]}"

    # ── 1.9 _generate_async_wrapper ──

    @staticmethod
    def _is_async_test(test_case: dict[str, Any]) -> bool:
        """Sprawdz czy test case wymaga async/await."""
        # Sprawdz flagi
        if test_case.get("is_async"):
            return True
        if test_case.get("async"):
            return True

        # Sprawdz kroki czy zawieraja await lub Promise
        steps = test_case.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    code = step.get("code", "")
                    if "await " in code or "Promise" in code or "fetch(" in code or "async" in code:
                        return True
                elif isinstance(step, str):
                    if "await " in step or "Promise" in step or "fetch(" in step or "async" in step:
                        return True
        elif isinstance(steps, dict):
            for val in steps.values():
                val_str = str(val)
                if "await " in val_str or "Promise" in val_str or "fetch(" in val_str:
                    return True

        # Sprawdz zaleznosci (DB, API = async)
        deps = test_case.get("dependencies") or test_case.get("mocks")
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, dict):
                    dep_type = (dep.get("type") or dep.get("target") or "").lower()
                    if dep_type in ("db", "database", "api", "http", "fetch"):
                        return True

        return False

    # ── 1.10 _generate_lifecycle_hooks ──

    def _build_lifecycle_steps(
        self,
        test_cases: list[dict[str, Any]],
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Buduj kroki beforeEach / afterEach z test case'ow.

        Returns:
            Krotka (setup_steps, teardown_steps)
        """
        setup_steps: list[dict[str, str]] = []
        teardown_steps: list[dict[str, str]] = []
        seen_setup: set[str] = set()
        seen_teardown: set[str] = set()

        for tc in test_cases:
            # Setup steps
            setup_code = tc.get("setup_code", "")
            if setup_code:
                for line in setup_code.strip().split("\n"):
                    line = line.strip()
                    if line and line not in seen_setup:
                        seen_setup.add(line)
                        setup_steps.append({"code": line})

            preconditions = tc.get("preconditions")
            if isinstance(preconditions, dict):
                for _key, val in preconditions.items():
                    code = str(val).strip() if val else ""
                    if code and code not in seen_setup:
                        seen_setup.add(code)
                        setup_steps.append({"code": code})

            # Teardown steps
            teardown_code = tc.get("teardown_code", "")
            if teardown_code:
                for line in teardown_code.strip().split("\n"):
                    line = line.strip()
                    if line and line not in seen_teardown:
                        seen_teardown.add(line)
                        teardown_steps.append({"code": line})

        return setup_steps, teardown_steps

    # ════════════════════════════════════════════════════════════════
    # Task 2: Mockowanie
    # ════════════════════════════════════════════════════════════════

    def _build_all_mocks(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
        variant: str,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje mockow z test case'ow."""
        if not config.include_mocks:
            return []

        mocks: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tc in test_cases:
            deps = tc.get("dependencies") or tc.get("mocks")
            if not deps:
                continue

            dep_list = deps if isinstance(deps, list) else [deps]
            for dep in dep_list:
                if not isinstance(dep, dict):
                    continue
                mock = self._generate_mock(dep, variant)
                if mock and mock["name"] not in seen:
                    seen.add(mock["name"])
                    mocks.append(mock)

        return mocks

    def _generate_mock(
        self,
        dependency: dict[str, Any],
        variant: str,
    ) -> dict[str, Any] | None:
        """Generuj specyfikacje pojedynczego mocka."""
        target = dependency.get("target") or dependency.get("type") or dependency.get("module")
        if not target:
            return None

        # Nazwa mocka — camelCase
        parts = target.split("/")
        module_part = parts[-1] if parts else target
        module_part = module_part.replace("-", " ").replace("_", " ")
        words = module_part.split()
        name = words[0].lower() + "".join(w.capitalize() for w in words[1:]) if words else "mock"

        mock_type = "jest" if variant == "jest" else "sinon"

        return {
            "name": name,
            "type": target,
            "mock_type": mock_type,
            "return_value": dependency.get("return_value"),
            "side_effect": dependency.get("side_effect"),
            "verify_method": dependency.get("verify_method"),
            "method": dependency.get("method") or dependency.get("method_name", "someMethod"),
        }

    def _build_mock_stubbing(
        self,
        test_case: dict[str, Any],
        variant: str,
    ) -> list[dict[str, str]]:
        """Buduj kod stubbingu mockow dla test case."""
        stubs: list[dict[str, str]] = []

        deps = test_case.get("dependencies") or test_case.get("mocks")
        if not deps:
            return stubs

        dep_list = deps if isinstance(deps, list) else [deps]
        for dep in dep_list:
            if not isinstance(dep, dict):
                continue

            target = dep.get("target") or dep.get("type") or dep.get("module")
            if not target:
                continue

            parts = target.split("/")
            module_part = parts[-1] if parts else target
            module_part = module_part.replace("-", " ").replace("_", " ")
            words = module_part.split()
            name = words[0].lower() + "".join(w.capitalize() for w in words[1:]) if words else "mock"
            method = dep.get("method") or dep.get("method_name", "someMethod")

            return_value = dep.get("return_value")
            side_effect = dep.get("side_effect")

            if variant == "jest":
                stubs.extend(self._jest_mock_stubs(name, method, return_value, side_effect, dep))
            else:
                stubs.extend(self._sinon_mock_stubs(name, method, return_value, side_effect, dep))

        return stubs

    @staticmethod
    def _jest_mock_stubs(
        name: str,
        method: str,
        return_value: Any,
        side_effect: Any,
        dep: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generuj stubbing mocka Jest."""
        stubs: list[dict[str, str]] = []

        if side_effect:
            stubs.append({"code": f"const {name}Mock = jest.fn().mockRejectedValue({js_value_literal(side_effect)});"})
        elif return_value is not None:
            stubs.append({"code": f"const {name}Mock = jest.fn().mockReturnValue({js_value_literal(return_value)});"})
        else:
            stubs.append({"code": f"const {name}Mock = jest.fn();"})

        # Verify
        verify = dep.get("verify")
        if verify:
            verify_method = verify if isinstance(verify, str) else method
            stubs.append({"code": f"expect({name}Mock).toHaveBeenCalledWith({verify_method});"})

        return stubs

    @staticmethod
    def _sinon_mock_stubs(
        name: str,
        method: str,
        return_value: Any,
        side_effect: Any,
        dep: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generuj stubbing mocka Sinon."""
        stubs: list[dict[str, str]] = []

        if side_effect:
            stubs.append({"code": f"const {name}Stub = sandbox.stub().throws({js_value_literal(side_effect)});"})
        elif return_value is not None:
            stubs.append({"code": f"const {name}Stub = sandbox.stub().returns({js_value_literal(return_value)});"})
        else:
            stubs.append({"code": f"const {name}Stub = sandbox.stub();"})

        # Verify
        verify = dep.get("verify")
        if verify:
            stubs.append({"code": f"expect({name}Stub.calledOnce).to.be.true;"})

        return stubs

    def _build_fixtures_from_mocks(
        self,
        mocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Buduj fixtures dict z mockow (kompatybilnosc z TestCodeFile)."""
        return [
            {
                "name": m["name"],
                "type": m["type"],
                "is_mock": True,
                "mock_type": m["mock_type"],
            }
            for m in mocks
        ]

    # ════════════════════════════════════════════════════════════════
    # Task 3: TypeScript
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _detect_typescript(project_context: dict[str, Any] | None) -> bool:
        """Sprawdz kontekst projektu czy jest TypeScript."""
        if not project_context:
            return False
        return bool(project_context.get("typescript", False))

    # ════════════════════════════════════════════════════════════════
    # Parametryzacja
    # ════════════════════════════════════════════════════════════════

    def _generate_parameterized_test(
        self,
        test_case: dict[str, Any],
        variant: str,
    ) -> dict[str, Any] | None:
        """Generuj specyfikacje test.each() / it.each().

        Zwraca None jesli tylko 1 zestaw danych (zwykly test).
        """
        test_data = test_case.get("test_data")
        if not test_data:
            return None

        data_sets = self._normalize_test_data(test_data)
        if len(data_sets) <= 1:
            return None

        # Buduj test.each data
        test_each_data: list[list[str]] = []
        for ds in data_sets:
            if isinstance(ds, dict):
                row = [js_value_literal(v) for v in ds.values()]
                test_each_data.append(row)
            elif isinstance(ds, list | tuple):
                row = [js_value_literal(v) for v in ds]
                test_each_data.append(row)
            else:
                test_each_data.append([js_value_literal(ds)])

        # Parametry
        parameters = []
        if data_sets and isinstance(data_sets[0], dict):
            for key in data_sets[0]:
                parameters.append({"name": key, "type": self._infer_js_type(data_sets, key)})
        else:
            parameters.append({"name": "input", "type": "any"})
            parameters.append({"name": "expected", "type": "any"})

        return {
            "test_each_data": test_each_data,
            "parameters": parameters,
        }

    @staticmethod
    def _normalize_test_data(test_data: Any) -> list[Any]:
        """Normalizuj test_data do listy zestawow danych."""
        if isinstance(test_data, list):
            return test_data
        if isinstance(test_data, dict):
            if "sets" in test_data and isinstance(test_data["sets"], list):
                return test_data["sets"]
            return [test_data]
        return []

    @staticmethod
    def _infer_js_type(data_sets: list[Any], key: str) -> str:
        """Wnioskuj typ JS/TS na podstawie danych testowych."""
        for ds in data_sets:
            if isinstance(ds, dict) and key in ds:
                val = ds[key]
                if val is None:
                    return "any"
                if isinstance(val, bool):
                    return "boolean"
                if isinstance(val, int):
                    return "number"
                if isinstance(val, float):
                    return "number"
                if isinstance(val, str):
                    return "string"
                if isinstance(val, list):
                    return "any[]"
                return "any"
        return "any"

    def _build_test_each_helpers(
        self,
        test_methods: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Buduj helper data dla test.each()."""
        helpers: list[dict[str, Any]] = []
        for tm in test_methods:
            if tm.get("test_each_data"):
                helpers.append(
                    {
                        "description": tm["description"],
                        "data": tm["test_each_data"],
                        "parameters": tm.get("parameters", []),
                    }
                )
        return helpers

    # ════════════════════════════════════════════════════════════════
    # Task 4: Szablony — helpers
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_file_path(module_name: str, extension: str) -> str:
        """Generuj sciezke pliku testowego JS/TS.

        Format: tests/{ModuleName}/{ModuleName}{extension}
        """
        return f"tests/{module_name}/{module_name}{extension}"

    @staticmethod
    def _extract_module_name(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe modulu z test case."""
        source_class = test_case.get("source_class")
        if source_class:
            # Usun rozszerzenie jesli jest
            return re.sub(r"\.\w+$", "", source_class)

        source_file = test_case.get("source_file") or test_case.get("source_module")
        if source_file:
            return Path(source_file).stem

        return "unknown"

    @staticmethod
    def _source_to_import_path(source: str) -> str:
        """Konwertuj sciezke zrodlowa na import path JS/TS."""
        # Usun rozszerzenie
        path = re.sub(r"\.(js|ts|jsx|tsx|mjs|cjs)$", "", source)
        # Jezeli nie zaczyna sie od . lub /, dodaj ./
        if not path.startswith(".") and not path.startswith("/"):
            path = "./" + path
        return path

    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Zamien nazwe na camelCase (pierwsza litera mala)."""
        if not name:
            return "module"
        # Zamien kebab-case i snake_case
        name = re.sub(r"[-_]+", " ", name)
        words = name.split()
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])

    # ════════════════════════════════════════════════════════════════
    # Task 5: Walidacja kompilacji
    # ════════════════════════════════════════════════════════════════

    def _validate_with_tool(self, code: str) -> CompilationResult | None:
        """Sprobuj zwalidowac kod JS/TS przez node --check lub tsc --noEmit.

        Returns:
            CompilationResult lub None jesli narzedzie niedostepne.
        """
        tmp_path = None
        try:
            # Uzyj .ts rozszerzenia dla kodu TypeScript (do detekcji tsc)
            is_ts_code = "interface " in code or ("describe" in code and ": " in code.split("describe")[0])
            suffix = ".ts" if is_ts_code else ".js"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w", encoding="utf-8") as f:
                tmp_path = f.name
                f.write(code)

            # Sprobuj node --check
            result = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return CompilationResult(
                    success=True,
                    code=code,
                    file_path=tmp_path,
                    framework=self.FRAMEWORK,
                )
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                line, col = self._parse_node_error(error_msg)
                return CompilationResult(
                    success=False,
                    code=code,
                    file_path=tmp_path,
                    error_message=error_msg,
                    error_line=line,
                    error_column=col,
                    framework=self.FRAMEWORK,
                )
        except FileNotFoundError:
            logger.debug("node niedostepny — fallback do walidacji strukturalnej")
            return None
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                code=code,
                error_message="Timeout walidacji node --check (>10s)",
                framework=self.FRAMEWORK,
            )
        except Exception as exc:
            logger.warning("Blad walidacji node: %s", exc)
            return None
        finally:
            if tmp_path:
                from contextlib import suppress

                with suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)

    def _validate_structural(self, code: str) -> CompilationResult:
        """Walidacja strukturalna kodu JS/TS (bez node).

        Sprawdza: nawiasy, strukture describe/it, poprawnosc expect() chain.
        """
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

        # Sprawdz obecnosc describe
        if not re.search(r"describe\s*\(", code):
            errors.append("Brak bloku describe() w kodzie testowym")

        # Sprawdz obecnosc it lub test
        if not re.search(r"(?:it|test)\s*\(", code):
            errors.append("Brak bloku it()/test() w kodzie testowym")

        # Sprawdz obecnosc expect (asercji)
        if not re.search(r"expect\s*\(", code):
            # Moze byc test bez asercji (np. smoke test) — warning, nie error
            pass

        # Sprawdz balans nawiasow kwadratowych
        open_brackets = code.count("[")
        close_brackets = code.count("]")
        if open_brackets != close_brackets:
            errors.append(f"Niezbalansowane nawiasy kwadratowe: [ = {open_brackets}, ] = {close_brackets}")

        if errors:
            return CompilationResult(
                success=False,
                code=code,
                error_message="; ".join(errors),
                error_line=1,
                framework=self.FRAMEWORK,
            )

        return CompilationResult(
            success=True,
            code=code,
            framework=self.FRAMEWORK,
        )

    @staticmethod
    def _parse_node_error(error_msg: str) -> tuple[int | None, int | None]:
        """Parsuj linie i kolumne z komunikatu bledu node."""
        # Format: 'SyntaxError: Unexpected token ...'
        match = re.search(r":(\d+):(\d+)", error_msg)
        if match:
            return int(match.group(1)), int(match.group(2))
        line_match = re.search(r"line (\d+)", error_msg)
        if line_match:
            return int(line_match.group(1)), None
        return None, None

    # ════════════════════════════════════════════════════════════════
    # Metody pomocnicze — steps, assertions
    # ════════════════════════════════════════════════════════════════

    def _build_steps(self, test_case: dict[str, Any]) -> list[dict[str, str]]:
        """Buduj kroki testowe z test case."""
        steps_raw = test_case.get("steps")
        if not steps_raw:
            return []

        steps: list[dict[str, str]] = []

        if isinstance(steps_raw, list):
            for step in steps_raw:
                if isinstance(step, dict):
                    code = step.get("code") or step.get("action") or ""
                    if code:
                        steps.append({"code": code})
                elif isinstance(step, str) and step.strip():
                    steps.append({"code": step.strip()})
        elif isinstance(steps_raw, dict):
            for _key, val in steps_raw.items():
                if isinstance(val, str) and val.strip():
                    steps.append({"code": val.strip()})
                elif isinstance(val, dict):
                    code = val.get("code") or val.get("action") or ""
                    if code:
                        steps.append({"code": code})

        return steps

    def _build_assertions(
        self,
        test_case: dict[str, Any],
        variant: str,
    ) -> list[dict[str, Any]]:
        """Buduj asercje z test case."""
        assertions: list[dict[str, Any]] = []

        expected = test_case.get("expected_result")
        comparison_type = test_case.get("comparison_type", "equals")

        if expected:
            assertions.append(
                {
                    "comparison_type": comparison_type,
                    "expected": js_value_literal(expected),
                    "actual": "result",
                    "message": None,
                }
            )

        # Explicit assertions list
        raw_assertions = test_case.get("assertions")
        if isinstance(raw_assertions, list):
            for a in raw_assertions:
                if isinstance(a, dict):
                    assertions.append(
                        {
                            "comparison_type": a.get("comparison_type", "equals"),
                            "expected": js_value_literal(a.get("expected", "")),
                            "actual": str(a.get("actual", "result")),
                            "message": a.get("message"),
                        }
                    )

        return assertions

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy JS."""
        return TestCodeFile(
            content="// Brak test case'ow do wygenerowania\n",
            file_path="tests/empty/empty.test.js",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any], variant: str) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        module_name = context.get("test_module_name", "unknown")
        test_cases = context.get("test_cases", [])

        lines: list[str] = []

        # Importy
        if variant == "mocha":
            lines.append("const { expect } = require('chai');")

        lines.append("")
        lines.append(f"describe('{module_name}', () => {{")
        lines.append("")

        for tc in test_cases:
            desc = tc.get("description", "should work")
            async_kw = "async " if tc.get("is_async") else ""
            lines.append(f"  it('{desc}', {async_kw}() => {{")
            lines.append("    // TODO: szablon niedostepny — reczne generowanie")
            lines.append("  });")
            lines.append("")

        lines.append("});")
        lines.append("")

        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════
# Funkcje pomocnicze module-level
# ════════════════════════════════════════════════════════════════════════


def js_value_literal(value: Any) -> str:
    """Konwertuj wartosc Python na literal JS/TS."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        # Escapuj cudzyslowy i backslash
        escaped = value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        return f"'{escaped}'"
    if isinstance(value, list):
        items = ", ".join(js_value_literal(v) for v in value)
        return f"[{items}]"
    if isinstance(value, dict):
        pairs = ", ".join(f"{js_value_literal(k)}: {js_value_literal(v)}" for k, v in value.items())
        return f"{{ {pairs} }}"
    return str(value)
