"""JUnit 5 code generator — Story 1.37.

Generuje pliki testowe JUnit 5 (.java) z test case'ow:
- Klasy testowe z konwencja {TestedClass}Test
- Metody testowe should_{expected}_when_{condition}() z @Test
- @BeforeEach / @AfterEach z lifecycle setup/teardown
- @ParameterizedTest z @CsvSource / @MethodSource
- Mockito @Mock, @InjectMocks, when/thenReturn, verify
- Walidacja skladniowa (strukturalna AST lub javac)
- Szablony Jinja2 (TestClass.java.j2)

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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "junit"

# ── Mapowanie comparison_type -> asercje JUnit 5 ──
ASSERTION_MAP: dict[str, str] = {
    "equals": "assertEquals({expected}, {actual}{message})",
    "not_equals": "assertNotEquals({expected}, {actual}{message})",
    "contains": "assertTrue({actual}.contains({expected}){message})",
    "not_contains": "assertFalse({actual}.contains({expected}){message})",
    "throws": "assertThrows({expected}.class, () -> {{ {actual}; }})",
    "approx": "assertEquals({expected}, {actual}, 0.0001{message})",
    "is_none": "assertNull({actual}{message})",
    "is_not_none": "assertNotNull({actual}{message})",
    "is_instance": "assertInstanceOf({expected}.class, {actual}{message})",
    "is_true": "assertTrue({actual}{message})",
    "is_false": "assertFalse({actual}{message})",
    "greater_than": "assertTrue({actual} > {expected}{message})",
    "less_than": "assertTrue({actual} < {expected}{message})",
    "has_length": "assertEquals({expected}, {actual}.length(){message})",
}

# ── Domyślne importy JUnit 5 ──
DEFAULT_JUNIT_IMPORTS = [
    "import org.junit.jupiter.api.Test;",
    "import org.junit.jupiter.api.BeforeEach;",
    "import org.junit.jupiter.api.AfterEach;",
    "import org.junit.jupiter.api.DisplayName;",
    "import static org.junit.jupiter.api.Assertions.*;",
]

PARAMETERIZED_IMPORTS = [
    "import org.junit.jupiter.params.ParameterizedTest;",
    "import org.junit.jupiter.params.provider.CsvSource;",
    "import org.junit.jupiter.params.provider.MethodSource;",
    "import java.util.stream.Stream;",
]

MOCKITO_IMPORTS = [
    "import org.mockito.Mock;",
    "import org.mockito.InjectMocks;",
    "import org.mockito.MockitoAnnotations;",
    "import static org.mockito.Mockito.*;",
]


@register_generator("junit")
class JUnitCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego JUnit 5 (Java).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "junit".
    """

    FRAMEWORK = "junit"
    LANGUAGE = "java"
    FILE_EXTENSION = ".java"

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
                logger.warning("Katalog szablonow JUnit nie istnieje: %s", templates_dir)
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
        """Generuj plik testowy JUnit 5 z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (z modelu TestCase)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem Java
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        first_tc = test_cases[0]

        # Nazwa klasy testowej i pakiet
        tested_class = self._extract_tested_class(first_tc)
        test_class_name = f"{tested_class}Test"
        package_name = self._build_package_name(first_tc, cfg)
        module_name = tested_class

        # 1.4 Buduj importy
        imports = self._build_imports(test_cases, cfg)

        # Mocki
        mocks = self._build_all_mocks(test_cases, cfg)

        # Lifecycle methods
        setup_steps, teardown_steps = self._build_lifecycle_steps(test_cases)
        has_lifecycle = bool(setup_steps or teardown_steps or mocks)

        # Metody testowe
        test_methods = self._build_all_test_methods(test_cases, cfg)

        # MethodSource helpers
        method_sources = self._build_method_sources(test_methods)

        # Mock stubbing per test
        self._enrich_mock_stubbing(test_methods, mocks)

        # Renderuj szablon
        context = {
            "package_name": package_name,
            "test_class_name": test_class_name,
            "tested_class": tested_class,
            "tested_class_instance": self._to_camel_case(tested_class),
            "imports": imports,
            "mocks": mocks,
            "has_lifecycle": has_lifecycle,
            "setup_steps": setup_steps,
            "has_teardown": bool(teardown_steps),
            "teardown_steps": teardown_steps,
            "test_methods": test_methods,
            "method_sources": method_sources,
            "project_context": cfg.project_context,
        }

        try:
            template = self.jinja_env.get_template("TestClass.java.j2")
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu JUnit: %s", exc)
            content = self._fallback_render(context)

        # Walidacja kompilacji (Task 5)
        file_path = self._build_file_path(package_name, test_class_name)
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
        """Generuj setup testowy JUnit (bazowa klasa abstrakcyjna).

        Args:
            project_context: kontekst projektu

        Returns:
            Zawartosc pliku bazowej klasy testowej Java
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
        """Generuj pojedyncza asercje JUnit 5.

        Args:
            expected: oczekiwana wartosc
            actual: rzeczywista wartosc
            comparison_type: typ porownania
            message: komunikat przy bledzie

        Returns:
            Kod asercji Java jako string
        """
        return self._map_assertion(expected, actual, comparison_type, message)

    # ════════════════════════════════════════════════════════════════
    # Task 5: validate_syntax
    # ════════════════════════════════════════════════════════════════

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu Java.

        Najpierw probuje javac (jesli dostepny), potem walidacja strukturalna.

        Args:
            code: kod Java do walidacji

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

        # 5.4 Walidacja specyficzna JUnit: sprawdzenie obecnosci importu
        if "import org.junit.jupiter.api.Test" not in code:
            warnings.append("Brak 'import org.junit.jupiter.api.Test' w wygenerowanym kodzie")

        # 5.1 Najpierw sprobuj javac
        javac_result = self._validate_with_javac(code)
        if javac_result is not None:
            javac_result.warnings = warnings
            return javac_result

        # 5.1 Fallback — walidacja strukturalna
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
    ) -> list[str]:
        """Buduj liste importow Java z kontekstu test case'ow."""
        imports: list[str] = list(DEFAULT_JUNIT_IMPORTS)
        seen: set[str] = set(imp for imp in imports)

        needs_parameterized = False
        needs_mockito = False

        for tc in test_cases:
            # Sprawdz czy potrzebne importy parametryzacji
            test_data = tc.get("test_data")
            data_sets = self._normalize_test_data(test_data)
            if len(data_sets) > 1:
                needs_parameterized = True

            # Sprawdz czy potrzebne importy Mockito
            deps = tc.get("dependencies") or tc.get("mocks")
            if deps:
                needs_mockito = True

            # Import testowanej klasy
            source_class = tc.get("source_class")
            source_file = tc.get("source_file") or tc.get("source_module")
            if source_class and source_class not in seen:
                seen.add(source_class)
                package = self._build_package_name(tc, config)
                if package and package != "com.example":
                    imports.append(f"import {package}.{source_class};")
                elif source_file:
                    pkg = self._file_path_to_package(source_file)
                    if pkg:
                        imports.append(f"import {pkg}.{source_class};")

            # Importy z explicit imports field
            tc_imports = tc.get("imports")
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

        # Dodaj importy warunkowe
        if needs_parameterized:
            for imp in PARAMETERIZED_IMPORTS:
                if imp not in seen:
                    seen.add(imp)
                    imports.append(imp)

        if needs_mockito:
            for imp in MOCKITO_IMPORTS:
                if imp not in seen:
                    seen.add(imp)
                    imports.append(imp)

        return imports

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
        # 1.8 Normalizacja nazwy — should_X_when_Y
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        method_name = self._normalize_method_name(scenario)

        # Opis (do @DisplayName)
        description = test_case.get("description") or test_case.get("scenario_description") or scenario

        # Parametryzacja (Task 2)
        parameterized = False
        csv_source = None
        method_source = None
        parameters: list[dict[str, str]] = []

        if config.include_parametrize:
            param_result = self._generate_parameterized_test(test_case)
            if param_result:
                parameterized = True
                csv_source = param_result.get("csv_source")
                method_source = param_result.get("method_source")
                parameters = param_result.get("parameters", [])

        # Kroki
        steps = self._build_steps(test_case)

        # Asercje
        assertions = self._build_assertions(test_case)

        # Mock stubbing
        mock_stubbing = self._build_mock_stubbing(test_case)

        return {
            "name": method_name,
            "display_name": description,
            "parameterized": parameterized,
            "csv_source": csv_source,
            "method_source": method_source,
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
        """Mapuj comparison_type na asercje JUnit 5."""
        template = ASSERTION_MAP.get(comparison_type)
        msg_part = f', "{message}"' if message else ""

        if template:
            result = template.format(
                expected=expected,
                actual=actual,
                message=msg_part,
            )
        else:
            result = f"assertEquals({expected}, {actual}); // nieznany comparison_type: {comparison_type}"

        return result

    # ── 1.8 _normalize_method_name ──

    @staticmethod
    def _normalize_method_name(name: str) -> str:
        """Konwersja nazwy scenariusza na camelCase: should_X_when_Y.

        Zamiana spacji, usuwanie special chars, konwencja should_X_when_Y.
        """
        if not name:
            return "should_work_whenCalled"

        result = name.strip()

        # Jezeli juz zaczyna sie od "should_" — zostaw
        if result.lower().startswith("should "):
            result = "should_" + result[7:]
        elif not result.lower().startswith("should_"):
            # Sprobuj wyekstrahowac expected behavior z nazwy
            result = f"should_{result}_whenCalled"

        # Zamien spacje na podkreslenia
        result = re.sub(r"\s+", "_", result)

        # Usun special chars (zostaw alfanumeryki i _)
        result = re.sub(r"[^a-zA-Z0-9_]", "", result)

        # Zamien na camelCase: should_some_behavior_when_some_condition
        parts = result.split("_")
        if len(parts) > 0:
            # Pierwszy czlon (should) — lowercase
            method = parts[0].lower()
            # Pozostale czlony — CamelCase
            for part in parts[1:]:
                if part:
                    method += part.capitalize()
            result = method

        # Ogranicz dlugosc
        if len(result) > 80:
            result = result[:80]

        return result or "should_work_whenCalled"

    # ── 1.9 _build_package_path ──

    def _build_package_name(
        self,
        test_case: dict[str, Any],
        config: CodeGenConfig,
    ) -> str:
        """Generuj nazwe pakietu Java z kontekstu projektu."""
        # Najpierw sprobuj z project_context
        if config.project_context:
            pkg = config.project_context.get("java_package")
            if pkg:
                return pkg

        # Z source_file
        source_file = test_case.get("source_file") or test_case.get("source_module")
        if source_file:
            return self._file_path_to_package(source_file)

        return "com.example"

    @staticmethod
    def _file_path_to_package(file_path: str) -> str:
        """Konwertuj sciezke pliku na nazwe pakietu Java."""
        if not file_path:
            return "com.example"

        path = Path(file_path)
        # Szukaj src/main/java lub src/test/java w sciezce
        parts = path.parts
        for i, part in enumerate(parts):
            if part == "java" and i > 0 and parts[i - 1] in ("main", "test"):
                # Pakiet to wszystko po "java/"
                pkg_parts = parts[i + 1 : -1]  # bez nazwy pliku
                if pkg_parts:
                    return ".".join(pkg_parts)

        # Fallback — uzyj katalogu nadrzednego
        if path.parent and path.parent.name:
            # Normalizuj na notacje pakietowa
            pkg = str(path.parent).replace("/", ".").replace("\\", ".")
            pkg = re.sub(r"[^a-zA-Z0-9_.]", "", pkg)
            pkg = pkg.strip(".")
            return pkg if pkg else "com.example"

        return "com.example"

    @staticmethod
    def _build_file_path(package_name: str, test_class_name: str) -> str:
        """Generuj sciezke pliku testowego Java.

        Format: src/test/java/{package_path}/{TestedClass}Test.java
        """
        pkg_path = package_name.replace(".", "/")
        return f"src/test/java/{pkg_path}/{test_class_name}.java"

    @staticmethod
    def _extract_tested_class(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe testowanej klasy z test case."""
        source_class = test_case.get("source_class")
        if source_class:
            # Usun ewentualne rozszerzenia plikow
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
        """Generuj specyfikacje @ParameterizedTest.

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
            # 2.5 @MethodSource dla zlozonych typow
            return self._build_method_source_spec(data_sets, test_case)
        else:
            # @CsvSource dla prostych typow
            return self._build_csv_source_spec(data_sets)

    def _build_csv_source_spec(
        self,
        data_sets: list[Any],
    ) -> dict[str, Any]:
        """Buduj specyfikacje @CsvSource z danych testowych."""
        csv_values: list[str] = []

        for ds in data_sets:
            if isinstance(ds, dict):
                values = []
                for v in ds.values():
                    values.append(self._java_value_literal(v))
                csv_values.append(", ".join(values))
            elif isinstance(ds, list | tuple):
                values = [self._java_value_literal(v) for v in ds]
                csv_values.append(", ".join(values))
            else:
                csv_values.append(self._java_value_literal(ds))

        # Parametry metody
        parameters = []
        if data_sets and isinstance(data_sets[0], dict):
            for key in data_sets[0]:
                java_type = self._infer_java_type(data_sets, key)
                parameters.append({"name": self._to_camel_case(key), "type": java_type})
        else:
            parameters.append({"name": "input", "type": "String"})
            parameters.append({"name": "expected", "type": "String"})

        return {
            "csv_source": csv_values,
            "parameters": parameters,
        }

    def _build_method_source_spec(
        self,
        data_sets: list[Any],
        test_case: dict[str, Any],
    ) -> dict[str, Any]:
        """Buduj specyfikacje @MethodSource dla zlozonych typow."""
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        method_name = self._normalize_method_name(scenario) + "Provider"

        args: list[str] = []
        for ds in data_sets:
            if isinstance(ds, dict):
                args_parts = []
                for v in ds.values():
                    args_parts.append(self._java_value_literal(v))
                args.append(f"Arguments.of({', '.join(args_parts)})")
            else:
                args.append(self._java_value_literal(ds))

        # Parametry metody
        parameters = []
        if data_sets and isinstance(data_sets[0], dict):
            for key in data_sets[0]:
                java_type = self._infer_java_type(data_sets, key)
                parameters.append({"name": self._to_camel_case(key), "type": java_type})
        else:
            parameters.append({"name": "input", "type": "Object"})

        return {
            "method_source": method_name,
            "method_source_args": args,
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
                if isinstance(v, str) and v.startswith(("new ", "List.of", "Map.of", "Arrays")):
                    return True
        return False

    @staticmethod
    def _java_value_literal(value: Any) -> str:
        """Konwertuj wartosc Python na literal Java."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return f"{value}d"
        if isinstance(value, str):
            # Escapuj cudzyslowy
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, list):
            items = ", ".join(JUnitCodeGenerator._java_value_literal(v) for v in value)
            return f"List.of({items})"
        if isinstance(value, dict):
            entries = ", ".join(
                f"{JUnitCodeGenerator._java_value_literal(k)}, {JUnitCodeGenerator._java_value_literal(v)}"
                for k, v in value.items()
            )
            return f"Map.of({entries})"
        return str(value)

    @staticmethod
    def _infer_java_type(data_sets: list[Any], key: str) -> str:
        """Wnioskuj typ Java na podstawie danych testowych."""
        for ds in data_sets:
            if isinstance(ds, dict) and key in ds:
                val = ds[key]
                if val is None:
                    return "Object"
                if isinstance(val, bool):
                    return "boolean"
                if isinstance(val, int):
                    return "int"
                if isinstance(val, float):
                    return "double"
                if isinstance(val, str):
                    return "String"
                if isinstance(val, list):
                    return "List"
                return "Object"
        return "String"

    # ════════════════════════════════════════════════════════════════
    # Task 3: Mockowanie Mockito
    # ════════════════════════════════════════════════════════════════

    def _build_all_mocks(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje mockow Mockito z test case'ow."""
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
        """Generuj specyfikacje pojedynczego mocka Mockito."""
        target = dependency.get("target") or dependency.get("type") or dependency.get("module")
        if not target:
            return None

        # Nazwa mocka — ostatni czlon klasy, camelCase
        class_name = target.split(".")[-1] if "." in target else target
        name = self._to_camel_case(class_name)

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
        """Buduj kod stubbingu Mockito (when/thenReturn) dla test case."""
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

            name = self._to_camel_case(target.split(".")[-1])
            method = dep.get("method") or dep.get("method_name", "someMethod")

            return_value = dep.get("return_value")
            side_effect = dep.get("side_effect")

            if side_effect:
                stubs.append(
                    {
                        "code": f"when({name}.{method}()).thenThrow(new {side_effect}());",
                    }
                )
            elif return_value is not None:
                java_val = self._java_value_literal(return_value)
                stubs.append(
                    {
                        "code": f"when({name}.{method}()).thenReturn({java_val});",
                    }
                )

            # 3.4 verify() calls
            verify = dep.get("verify")
            if verify:
                verify_method = verify if isinstance(verify, str) else method
                stubs.append(
                    {
                        "code": f"verify({name}).{verify_method}();",
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
    # Task 4: Szablony — method sources helper
    # ════════════════════════════════════════════════════════════════

    def _build_method_sources(
        self,
        test_methods: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje method source helper methods."""
        sources: list[dict[str, Any]] = []

        for tm in test_methods:
            if tm.get("method_source") and tm.get("method_source_args"):
                sources.append(
                    {
                        "name": tm["method_source"],
                        "return_type": "Stream<Arguments>",
                        "args": tm["method_source_args"],
                    }
                )

        return sources

    # ════════════════════════════════════════════════════════════════
    # Task 5: Walidacja kompilacji
    # ════════════════════════════════════════════════════════════════

    def _validate_with_javac(self, code: str) -> CompilationResult | None:
        """Sprobuj zwalidowac kod Java przez javac (opcjonalnie).

        Returns:
            CompilationResult lub None jesli javac niedostepny.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".java", delete=False, mode="w", encoding="utf-8") as f:
                tmp_path = f.name
                f.write(code)

            result = subprocess.run(
                ["javac", "-Xlint:none", tmp_path],
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
                error_msg = result.stderr.strip()
                line, col = self._parse_javac_error(error_msg)
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
            # javac niedostepny
            logger.debug("javac niedostepny — fallback do walidacji strukturalnej")
            return None
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                code=code,
                error_message="Timeout kompilacji javac (>10s)",
                framework=self.FRAMEWORK,
            )
        except Exception as exc:
            logger.warning("Blad walidacji javac: %s", exc)
            return None
        finally:
            if tmp_path:
                from contextlib import suppress

                with suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)
                    # Usun tez .class jesli powstal
                    class_path = Path(tmp_path).with_suffix(".class")
                    class_path.unlink(missing_ok=True)

    def _validate_structural(self, code: str) -> CompilationResult:
        """Walidacja strukturalna kodu Java (bez javac).

        Sprawdza: nawiasy, sredniki, poprawnosc deklaracji klas.
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
            errors.append("Brak deklaracji klasy w kodzie Java")

        # Sprawdz obecnosc package
        if not re.search(r"^package\s+[\w.]+;", code, re.MULTILINE):
            errors.append("Brak deklaracji package")

        # Sprawdz sredniki na koncu statements (prosta heurystyka)
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Pomin puste linie, komentarze, bloki, importy juz sprawdzone
            if not stripped or stripped.startswith(("//", "/*", "*", "*/", "@", "package", "import")):
                continue
            if stripped.endswith(("{", "}", ")", ",")):
                continue
            # Deklaracje pol wymagaja srednika
            if re.match(r"(?:private|public|protected)\s+\w+\s+\w+\s*(?:=.*)?$", stripped) and not stripped.endswith(
                ";"
            ):
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
    def _parse_javac_error(error_msg: str) -> tuple[int | None, int | None]:
        """Parsuj linie i kolumne z komunikatu bledu javac."""
        # Format: 'TestClass.java:10: error: ...'
        line_match = re.search(r":(\d+):", error_msg)
        line = int(line_match.group(1)) if line_match else None
        return line, None

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
        """Zwroc pusty plik testowy Java."""
        return TestCodeFile(
            content="// Brak test case'ow do wygenerowania\n",
            file_path="src/test/java/EmptyTest.java",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any]) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        lines = [
            f"package {context.get('package_name', 'com.example')};",
            "",
            "import org.junit.jupiter.api.Test;",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            "/** Wygenerowano automatycznie przez TestGEN. */",
            f"public class {context.get('test_class_name', 'UnknownTest')} {{",
            "",
            "    @Test",
            "    void should_work() {",
            "        // TODO: szablon niedostepny — reczne generowanie",
            "    }",
            "}",
        ]
        return "\n".join(lines) + "\n"
