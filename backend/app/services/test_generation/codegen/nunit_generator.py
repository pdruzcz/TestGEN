"""NUnit 3 code generator — Story 1.38.

Generuje pliki testowe NUnit 3 (.cs) z test case'ow:
- Klasy testowe z konwencja {TestedClass}Tests
- Metody testowe {MethodName}_{Scenario}_{ExpectedResult}() z [Test]
- [SetUp] / [TearDown] z lifecycle setup/teardown
- [TestCase(params)] / [TestCaseSource] dla parametryzacji
- Moq Mock<T>, Setup/Verify dla mockowania
- Walidacja skladniowa (strukturalna lub dotnet build)
- Szablony Jinja2 (TestClass.cs.j2)

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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "nunit"

# ── Mapowanie comparison_type -> asercje NUnit 3 ──
ASSERTION_MAP: dict[str, str] = {
    "equals": "Assert.AreEqual({expected}, {actual}{message});",
    "not_equals": "Assert.AreNotEqual({expected}, {actual}{message});",
    "contains": "Assert.That({actual}, Does.Contain({expected}){message});",
    "not_contains": "Assert.That({actual}, Does.Not.Contain({expected}){message});",
    "throws": "Assert.Throws<{expected}>(() => {{ {actual}; }});",
    "approx": "Assert.AreEqual({expected}, {actual}, 0.0001{message});",
    "is_none": "Assert.IsNull({actual}{message});",
    "is_not_none": "Assert.IsNotNull({actual}{message});",
    "is_instance": "Assert.IsInstanceOf<{expected}>({actual}{message});",
    "is_true": "Assert.IsTrue({actual}{message});",
    "is_false": "Assert.IsFalse({actual}{message});",
    "greater_than": "Assert.Greater({actual}, {expected}{message});",
    "less_than": "Assert.Less({actual}, {expected}{message});",
    "has_length": "Assert.AreEqual({expected}, {actual}.Length{message});",
}

# ── Domyslne using statements NUnit 3 ──
DEFAULT_NUNIT_USINGS = [
    "using NUnit.Framework;",
]

PARAMETERIZED_USINGS: list[str] = []  # TestCase jest w NUnit.Framework

MOQ_USINGS = [
    "using Moq;",
]


@register_generator("nunit")
class NUnitCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego NUnit 3 (C#).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "nunit".
    """

    FRAMEWORK = "nunit"
    LANGUAGE = "csharp"
    FILE_EXTENSION = ".cs"

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
                logger.warning("Katalog szablonow NUnit nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ════════════════════════════════════════════════════════════════
    # 1.3 Metoda glowna: generate_test_file
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy NUnit 3 z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (z modelu TestCase)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem C#
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        first_tc = test_cases[0]

        # Nazwa klasy testowej i namespace
        tested_class = self._extract_tested_class(first_tc)
        test_class_name = f"{tested_class}Tests"
        namespace = self._build_namespace(first_tc, cfg)
        module_name = tested_class

        # 1.4 Buduj using statements
        usings = self._build_usings(test_cases, cfg)

        # Mocki (Task 3)
        mocks = self._build_all_mocks(test_cases, cfg)

        # Lifecycle methods (1.5)
        setup_steps, teardown_steps = self._build_lifecycle_steps(test_cases)
        has_lifecycle = bool(setup_steps or teardown_steps or mocks)

        # Metody testowe (1.6)
        test_methods = self._build_all_test_methods(test_cases, cfg)

        # TestCaseSource helpers (Task 2)
        test_case_sources = self._build_test_case_sources(test_methods)

        # Mock stubbing per test (Task 3)
        self._enrich_mock_stubbing(test_methods, mocks)

        # Usun self-referencje z usings (namespace == using)
        usings = [u for u in usings if u.strip().rstrip(";").replace("using ", "") != namespace]

        # Renderuj szablon (Task 4)
        context = {
            "namespace": namespace,
            "test_class_name": test_class_name,
            "tested_class": tested_class,
            "tested_class_instance": self._to_camel_case(tested_class),
            "usings": usings,
            "mocks": mocks,
            "has_lifecycle": has_lifecycle,
            "setup_steps": setup_steps,
            "has_teardown": bool(teardown_steps),
            "teardown_steps": teardown_steps,
            "test_methods": test_methods,
            "test_case_sources": test_case_sources,
            "project_context": cfg.project_context,
        }

        try:
            template = self.jinja_env.get_template("TestClass.cs.j2")
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu NUnit: %s", exc)
            content = self._fallback_render(context)

        # Walidacja kompilacji (Task 5)
        file_path = self._build_file_path(namespace, test_class_name)
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        # Zbuduj fixtures dict (kompatybilnosc z TestCodeFile)
        fixtures = self._build_fixtures_from_mocks(mocks)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=module_name,
            fixtures=fixtures,
            test_functions=test_methods,
            imports=usings,
            compilation_result=compilation_result,
        )

    # ════════════════════════════════════════════════════════════════
    # generate_setup
    # ════════════════════════════════════════════════════════════════

    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj setup testowy NUnit (bazowa klasa abstrakcyjna).

        Args:
            project_context: kontekst projektu

        Returns:
            Zawartosc pliku bazowej klasy testowej C#
        """
        return "// Bazowa klasa testowa — rozszerz w konkretnych testach\n"

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
        """Generuj pojedyncza asercje NUnit 3.

        Args:
            expected: oczekiwana wartosc
            actual: rzeczywista wartosc
            comparison_type: typ porownania
            message: komunikat przy bledzie

        Returns:
            Kod asercji C# jako string
        """
        return self._map_assertion(expected, actual, comparison_type, message)

    # ════════════════════════════════════════════════════════════════
    # Task 5: validate_syntax
    # ════════════════════════════════════════════════════════════════

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu C#.

        Najpierw probuje dotnet build (jesli dostepny), potem walidacja strukturalna.

        Args:
            code: kod C# do walidacji

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

        # 5.4 Walidacja specyficzna NUnit: sprawdzenie obecnosci using NUnit.Framework
        if "using NUnit.Framework;" not in code:
            warnings.append("Brak 'using NUnit.Framework;' w wygenerowanym kodzie")

        # 5.2 Najpierw sprobuj dotnet build
        dotnet_result = self._validate_with_dotnet(code)
        if dotnet_result is not None:
            dotnet_result.warnings = warnings
            return dotnet_result

        # 5.1 Fallback — walidacja strukturalna
        structural_result = self._validate_structural(code)
        structural_result.warnings = warnings
        return structural_result

    # ════════════════════════════════════════════════════════════════
    # Metody prywatne — Task 1: Core generator
    # ════════════════════════════════════════════════════════════════

    # ── 1.4 _build_usings ──

    def _build_usings(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[str]:
        """Buduj liste using statements C# z kontekstu test case'ow."""
        usings: list[str] = list(DEFAULT_NUNIT_USINGS)
        seen: set[str] = set(u for u in usings)

        needs_mock = False

        for tc in test_cases:
            # Sprawdz czy potrzebne importy Moq
            deps = tc.get("dependencies") or tc.get("mocks")
            if deps:
                needs_mock = True

            # Using testowanej klasy — z namespace'u
            source_namespace = tc.get("source_namespace")
            source_class = tc.get("source_class")
            if source_namespace and source_class:
                using_stmt = f"using {source_namespace};"
                if using_stmt not in seen:
                    seen.add(using_stmt)
                    usings.append(using_stmt)
            elif source_class:
                # Sprobuj wywnioskowac namespace ze source_file
                source_file = tc.get("source_file") or tc.get("source_module")
                if source_file:
                    ns = self._file_path_to_namespace(source_file)
                    if ns and ns != "TestProject":
                        using_stmt = f"using {ns};"
                        if using_stmt not in seen:
                            seen.add(using_stmt)
                            usings.append(using_stmt)

            # Explicit usings z test case
            tc_usings = tc.get("usings") or tc.get("imports")
            if isinstance(tc_usings, list):
                for u in tc_usings:
                    if u and u not in seen:
                        seen.add(u)
                        usings.append(u)
            elif isinstance(tc_usings, str) and tc_usings.strip():
                for u in tc_usings.strip().split("\n"):
                    u = u.strip()
                    if u and u not in seen:
                        seen.add(u)
                        usings.append(u)

        # Dodaj importy warunkowe
        if needs_mock:
            for u in MOQ_USINGS:
                if u not in seen:
                    seen.add(u)
                    usings.append(u)

        return usings

    # ── 1.5 _generate_lifecycle_methods ──

    def _build_lifecycle_steps(
        self,
        test_cases: list[dict[str, Any]],
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Buduj kroki setup/teardown z test case'ow.

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

    # ── 1.6 _generate_test_method ──

    def _build_all_test_methods(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje metod testowych z test case'ow."""
        methods: list[dict[str, Any]] = []

        for tc in test_cases:
            method = self._generate_test_method(tc, config)
            if method:
                methods.append(method)

        return methods

    def _generate_test_method(
        self,
        test_case: dict[str, Any],
        config: CodeGenConfig,
    ) -> dict[str, Any]:
        """Generuj specyfikacje pojedynczej metody testowej."""
        # 1.8 Normalizacja nazwy — {Method}_{Scenario}_{Result} (PascalCase)
        scenario = test_case.get("scenario_name") or test_case.get("title") or "Unnamed"
        source_function = test_case.get("source_function") or "Method"
        method_name = self._normalize_method_name(source_function, scenario)

        # Opis
        description = test_case.get("description") or test_case.get("scenario_description") or scenario

        # Parametryzacja (Task 2)
        parameterized = False
        test_case_attrs: list[str] | None = None
        test_case_source: str | None = None
        test_case_source_data: list[dict[str, Any]] | None = None
        parameters: list[dict[str, str]] = []

        if config.include_parametrize:
            param_result = self._generate_parameterized_test(test_case)
            if param_result:
                parameterized = True
                test_case_attrs = param_result.get("test_case_attrs")
                test_case_source = param_result.get("test_case_source")
                test_case_source_data = param_result.get("test_case_source_data")
                parameters = param_result.get("parameters", [])

        # Kroki
        steps = self._build_steps(test_case)

        # Asercje
        assertions = self._build_assertions(test_case)

        # Mock stubbing
        mock_stubbing = self._build_mock_stubbing(test_case)

        return {
            "name": method_name,
            "description": description,
            "parameterized": parameterized,
            "test_case_attrs": test_case_attrs,
            "test_case_source": test_case_source,
            "test_case_source_data": test_case_source_data,
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
        message: str | None = None,
    ) -> str:
        """Mapuj comparison_type na asercje NUnit 3."""
        template = ASSERTION_MAP.get(comparison_type)
        msg_part = f', "{message}"' if message else ""

        if template:
            result = template.format(
                expected=expected,
                actual=actual,
                message=msg_part,
            )
        else:
            result = f"Assert.AreEqual({expected}, {actual}); // nieznany comparison_type: {comparison_type}"

        return result

    # ── 1.8 _normalize_method_name ──

    @staticmethod
    def _normalize_method_name(source_function: str, scenario: str) -> str:
        """Konwersja nazwy scenariusza na PascalCase: {Method}_{Scenario}_{Result}.

        Zamiana spacji na _, usuwanie special chars, konwencja PascalCase.
        """
        if not scenario and not source_function:
            return "TestMethod_WhenCalled_ReturnsExpected"

        # Buduj czesci nazwy
        parts: list[str] = []

        # czlon 1: nazwa metody (PascalCase)
        func_part = re.sub(r"[^a-zA-Z0-9]", "", source_function)
        if func_part:
            parts.append(func_part)

        # czlon 2+: scenariusz → PascalCase
        if scenario:
            # Zamien separatory na spacje
            clean = re.sub(r"[_\-]+", " ", scenario)
            # Split na slowa i PascalCase
            words = clean.split()
            scenario_part = "".join(w.capitalize() for w in words if w)
            if scenario_part:
                parts.append(scenario_part)

        result = "_".join(parts)

        # Usun special chars (zostaw alfanumeryki i _)
        result = re.sub(r"[^a-zA-Z0-9_]", "", result)

        if not result:
            return "TestMethod_WhenCalled_ReturnsExpected"

        # Ogranicz dlugosc
        if len(result) > 80:
            result = result[:80]

        return result

    # ── 1.9 _build_namespace ──

    def _build_namespace(
        self,
        test_case: dict[str, Any],
        config: CodeGenConfig,
    ) -> str:
        """Generuj namespace C# z kontekstu projektu."""
        # Najpierw sprobuj z project_context
        if config.project_context:
            ns = config.project_context.get("csharp_namespace")
            if ns:
                return ns

        # Z source_namespace
        source_ns = test_case.get("source_namespace")
        if source_ns:
            return source_ns

        # Z source_file
        source_file = test_case.get("source_file") or test_case.get("source_module")
        if source_file:
            return self._file_path_to_namespace(source_file)

        return "TestProject.Tests"

    @staticmethod
    def _file_path_to_namespace(file_path: str) -> str:
        """Konwertuj sciezke pliku na namespace C#."""
        if not file_path:
            return "TestProject.Tests"

        path = Path(file_path)
        # Szukaj wzorca projektowego w sciezce
        parts = path.parts
        for i, part in enumerate(parts):
            if part in ("src", "Source") and i + 1 < len(parts):
                # Namespace to wszystko po src/ (bez nazwy pliku)
                ns_parts = parts[i + 1 : -1]
                if ns_parts:
                    return ".".join(ns_parts)

        # Fallback — uzyj katalogu nadrzednego
        if path.parent and path.parent.name:
            ns = str(path.parent).replace("/", ".").replace("\\", ".")
            ns = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
            ns = ns.strip(".")
            if ns and ns not in ("src", "Source", "test", "tests"):
                return ns

        return "TestProject.Tests"

    @staticmethod
    def _build_file_path(namespace: str, test_class_name: str) -> str:
        """Generuj sciezke pliku testowego C#.

        Format: Tests/{namespace_path}/{TestedClass}Tests.cs
        """
        ns_path = namespace.replace(".", "/")
        return f"Tests/{ns_path}/{test_class_name}.cs"

    @staticmethod
    def _extract_tested_class(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe testowanej klasy z test case."""
        source_class = test_case.get("source_class")
        if source_class:
            return re.sub(r"\.\w+$", "", source_class)

        source_file = test_case.get("source_file") or test_case.get("source_module")
        if source_file:
            return Path(source_file).stem

        return "Unknown"

    @staticmethod
    def _to_camel_case(class_name: str) -> str:
        """Zamien nazwe klasy na camelCase (pierwsza litera mala)."""
        if not class_name:
            return "instance"
        return class_name[0].lower() + class_name[1:]

    # ════════════════════════════════════════════════════════════════
    # Task 2: Parametryzacja
    # ════════════════════════════════════════════════════════════════

    def _generate_parameterized_test(
        self,
        test_case: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generuj specyfikacje [TestCase] / [TestCaseSource].

        Zwraca None jesli tylko 1 zestaw danych (zwykla metoda testowa).
        """
        test_data = test_case.get("test_data")
        if not test_data:
            return None

        data_sets = self._normalize_test_data(test_data)
        if len(data_sets) <= 1:
            return None  # 2.4 — zwykla metoda bez parametryzacji

        # Sprawdz typy danych
        first_set = data_sets[0]
        is_complex = self._is_complex_data(first_set)

        if is_complex:
            # 2.5 [TestCaseSource] dla zlozonych typow
            return self._build_test_case_source_spec(data_sets, test_case)
        else:
            # [TestCase(params)] dla prostych typow
            return self._build_test_case_attrs_spec(data_sets)

    def _build_test_case_attrs_spec(
        self,
        data_sets: list[Any],
    ) -> dict[str, Any]:
        """Buduj specyfikacje [TestCase(arg1, arg2, ...)] z danych testowych."""
        attrs: list[str] = []

        for ds in data_sets:
            if isinstance(ds, dict):
                values = [self._csharp_value_literal(v) for v in ds.values()]
                attrs.append(", ".join(values))
            elif isinstance(ds, list | tuple):
                values = [self._csharp_value_literal(v) for v in ds]
                attrs.append(", ".join(values))
            else:
                attrs.append(self._csharp_value_literal(ds))

        # Parametry metody
        parameters = []
        if data_sets and isinstance(data_sets[0], dict):
            for key in data_sets[0]:
                cs_type = self._infer_csharp_type(data_sets, key)
                parameters.append({"name": self._to_camel_case(key), "type": cs_type})
        else:
            parameters.append({"name": "input", "type": "string"})
            parameters.append({"name": "expected", "type": "string"})

        return {
            "test_case_attrs": attrs,
            "parameters": parameters,
        }

    def _build_test_case_source_spec(
        self,
        data_sets: list[Any],
        test_case: dict[str, Any],
    ) -> dict[str, Any]:
        """Buduj specyfikacje [TestCaseSource(nameof(Data))] dla zlozonych typow."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        source_name = self._normalize_method_name("Data", scenario) + "Source"

        data_items: list[dict[str, Any]] = []
        for ds in data_sets:
            if isinstance(ds, dict):
                item = {k: self._csharp_value_literal(v) for k, v in ds.items()}
                data_items.append(item)
            else:
                data_items.append({"value": self._csharp_value_literal(ds)})

        # Parametry metody
        parameters = []
        if data_sets and isinstance(data_sets[0], dict):
            for key in data_sets[0]:
                cs_type = self._infer_csharp_type(data_sets, key)
                parameters.append({"name": self._to_camel_case(key), "type": cs_type})
        else:
            parameters.append({"name": "input", "type": "object"})

        return {
            "test_case_source": source_name,
            "test_case_source_data": data_items,
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
    def _is_complex_data(data_set: Any) -> bool:
        """Sprawdz czy zestaw danych zawiera zlozone typy (obiekty, kolekcje)."""
        if isinstance(data_set, dict):
            for v in data_set.values():
                if isinstance(v, list | dict):
                    return True
                if isinstance(v, str) and v.startswith(("new ", "List<", "Dictionary<", "new[]")):
                    return True
        return False

    @staticmethod
    def _csharp_value_literal(value: Any) -> str:
        """Konwertuj wartosc Python na literal C#."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return f"{value}f"
        if isinstance(value, str):
            # Escapuj cudzyslowy
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, list):
            items = ", ".join(NUnitCodeGenerator._csharp_value_literal(v) for v in value)
            return f"new[] {{ {items} }}"
        if isinstance(value, dict):
            entries = ", ".join(
                f"{{ {NUnitCodeGenerator._csharp_value_literal(k)}, {NUnitCodeGenerator._csharp_value_literal(v)} }}"
                for k, v in value.items()
            )
            return f"new Dictionary<string, object> {{ {entries} }}"
        return str(value)

    @staticmethod
    def _infer_csharp_type(data_sets: list[Any], key: str) -> str:
        """Wnioskuj typ C# na podstawie danych testowych."""
        for ds in data_sets:
            if isinstance(ds, dict) and key in ds:
                val = ds[key]
                if val is None:
                    return "object"
                if isinstance(val, bool):
                    return "bool"
                if isinstance(val, int):
                    return "int"
                if isinstance(val, float):
                    return "double"
                if isinstance(val, str):
                    return "string"
                if isinstance(val, list):
                    return "List<object>"
                return "object"
        return "string"

    # ════════════════════════════════════════════════════════════════
    # Task 3: Mockowanie Moq
    # ════════════════════════════════════════════════════════════════

    def _build_all_mocks(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje mockow Moq z test case'ow."""
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
                mock = self._generate_mock(dep)
                if mock and mock["name"] not in seen:
                    seen.add(mock["name"])
                    mocks.append(mock)

        return mocks

    def _generate_mock(self, dependency: dict[str, Any]) -> dict[str, Any] | None:
        """Generuj specyfikacje pojedynczego mocka Moq."""
        target = dependency.get("target") or dependency.get("type") or dependency.get("module")
        if not target:
            return None

        # Nazwa mocka — ostatni czlon interfejsu/klasy, camelCase
        interface_name = target.split(".")[-1] if "." in target else target
        # Usun prefix I z interfejsu dla nazwy pola (IRepository -> repository)
        name = self._to_camel_case(interface_name)

        return {
            "name": name,
            "type": target,
            "return_value": dependency.get("return_value"),
            "side_effect": dependency.get("side_effect"),
            "verify_method": dependency.get("verify_method"),
        }

    def _build_mock_stubbing(
        self,
        test_case: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Buduj kod stubbingu Moq (Setup/Returns) dla test case."""
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

            interface_name = target.split(".")[-1] if "." in target else target
            name = self._to_camel_case(interface_name)
            method = dep.get("method") or dep.get("method_name", "SomeMethod")

            return_value = dep.get("return_value")
            side_effect = dep.get("side_effect")

            if side_effect:
                stubs.append(
                    {
                        "code": f"_{name}.Setup(x => x.{method}()).Throws(new {side_effect}());",
                    }
                )
            elif return_value is not None:
                cs_val = self._csharp_value_literal(return_value)
                stubs.append(
                    {
                        "code": f"_{name}.Setup(x => x.{method}()).Returns({cs_val});",
                    }
                )

            # 3.4 Verify() calls
            verify = dep.get("verify")
            if verify:
                verify_method = verify if isinstance(verify, str) else method
                stubs.append(
                    {
                        "code": f"_{name}.Verify(x => x.{verify_method}(), Times.Once);",
                    }
                )

        return stubs

    def _enrich_mock_stubbing(
        self,
        test_methods: list[dict[str, Any]],
        mocks: list[dict[str, Any]],
    ) -> None:
        """Enrich test methods z mock stubbingiem z mockow klasowych."""
        if not mocks:
            return

        for method in test_methods:
            if not method.get("mock_stubbing"):
                method["mock_stubbing"] = []

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
            }
            for m in mocks
        ]

    # ════════════════════════════════════════════════════════════════
    # Task 4: Szablony — TestCaseSource helpers
    # ════════════════════════════════════════════════════════════════

    def _build_test_case_sources(
        self,
        test_methods: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje TestCaseSource helper methods."""
        sources: list[dict[str, Any]] = []

        for tm in test_methods:
            if tm.get("test_case_source") and tm.get("test_case_source_data"):
                sources.append(
                    {
                        "name": tm["test_case_source"],
                        "data": tm["test_case_source_data"],
                    }
                )

        return sources

    # ════════════════════════════════════════════════════════════════
    # Task 5: Walidacja kompilacji
    # ════════════════════════════════════════════════════════════════

    def _validate_with_dotnet(self, code: str) -> CompilationResult | None:
        """Sprobuj zwalidowac kod C# przez dotnet build (opcjonalnie).

        Returns:
            CompilationResult lub None jesli dotnet niedostepny.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".cs", delete=False, mode="w", encoding="utf-8") as f:
                tmp_path = f.name
                f.write(code)

            # Prosta walidacja skladniowa przez dotnet — wymaga projektu
            # Uzyj bardziej agresywnego timeoutu (C# kompilator moze byc wolny)
            result = subprocess.run(
                ["dotnet", "build", tmp_path],
                capture_output=True,
                text=True,
                timeout=15,
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
                # Sprawdz czy blad to brak SDK (dotnet istnieje ale nie ma SDK)
                if "No .NET SDKs were found" in error_msg or "does not exist" in error_msg:
                    logger.debug("dotnet bez SDK — fallback do walidacji strukturalnej")
                    return None
                line, col = self._parse_dotnet_error(error_msg)
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
            # dotnet niedostepny
            logger.debug("dotnet niedostepny — fallback do walidacji strukturalnej")
            return None
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                code=code,
                error_message="Timeout kompilacji dotnet build (>15s)",
                framework=self.FRAMEWORK,
            )
        except Exception as exc:
            logger.warning("Blad walidacji dotnet: %s", exc)
            return None
        finally:
            if tmp_path:
                from contextlib import suppress

                with suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)

    def _validate_structural(self, code: str) -> CompilationResult:
        """Walidacja strukturalna kodu C# (bez dotnet build).

        Sprawdza: nawiasy klamrowe, sredniki, poprawnosc deklaracji klas, atrybuty.
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

        # Sprawdz obecnosc deklaracji klasy
        if not re.search(r"(?:public\s+)?class\s+\w+", code):
            errors.append("Brak deklaracji klasy w kodzie C#")

        # Sprawdz obecnosc namespace
        if not re.search(r"namespace\s+[\w.]+", code):
            errors.append("Brak deklaracji namespace")

        # Sprawdz poprawnosc atrybutow NUnit: [Test], [TestFixture]
        # Nawiasy kwadratowe musza byc zbalansowane
        open_brackets = code.count("[")
        close_brackets = code.count("]")
        if open_brackets != close_brackets:
            errors.append(f"Niezbalansowane nawiasy kwadratowe: [ = {open_brackets}, ] = {close_brackets}")

        # Sprawdz sredniki na koncu statements (prosta heurystyka)
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Pomin puste linie, komentarze, bloki, using, namespace
            if not stripped or stripped.startswith(("//", "/*", "*", "*/", "[", "using ", "namespace ")):
                continue
            if stripped.endswith(("{", "}", ")", ",")):
                continue
            # Deklaracje pol prywatnych wymagaja srednika
            if re.match(r"(?:private|public|protected|internal)\s+\w+\s+_\w+", stripped) and not stripped.endswith(";"):
                errors.append(f"Linia {i}: brak srednika: {stripped}")

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
    def _parse_dotnet_error(error_msg: str) -> tuple[int | None, int | None]:
        """Parsuj linie i kolumne z komunikatu bledu dotnet build."""
        # Format: 'TestClass.cs(10,5): error CS...: ...'
        match = re.search(r"\((\d+),(\d+)\)", error_msg)
        if match:
            return int(match.group(1)), int(match.group(2))
        # Format bez kolumny
        line_match = re.search(r"\((\d+)\)", error_msg)
        if line_match:
            return int(line_match.group(1)), None
        return None, None

    # ════════════════════════════════════════════════════════════════
    # Metody pomocnicze
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

    def _build_assertions(self, test_case: dict[str, Any]) -> list[dict[str, Any]]:
        """Buduj asercje z test case."""
        assertions: list[dict[str, Any]] = []

        expected = test_case.get("expected_result")
        comparison_type = test_case.get("comparison_type", "equals")

        if expected:
            assertions.append(
                {
                    "comparison_type": comparison_type,
                    "expected": str(expected),
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
                            "expected": str(a.get("expected", "")),
                            "actual": str(a.get("actual", "result")),
                            "message": a.get("message"),
                        }
                    )

        return assertions

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy C#."""
        return TestCodeFile(
            content="// Brak test case'ow do wygenerowania\n",
            file_path="Tests/EmptyTests.cs",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any]) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        lines = [
            f"namespace {context.get('namespace', 'TestProject.Tests')};",
            "",
            "using NUnit.Framework;",
            "",
            "/// <summary>Wygenerowano automatycznie przez TestGEN.</summary>",
            "[TestFixture]",
            f"public class {context.get('test_class_name', 'UnknownTests')}",
            "{",
            "    [Test]",
            "    public void TestMethod_WhenCalled_ReturnsExpected()",
            "    {",
            "        // TODO: szablon niedostepny — reczne generowanie",
            "    }",
            "}",
        ]
        return "\n".join(lines) + "\n"
