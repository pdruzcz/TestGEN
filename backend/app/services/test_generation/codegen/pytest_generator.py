"""Pytest code generator — Story 1.36.

Generuje pliki testowe pytest (.py) z test case'ow:
- Funkcje testowe z konwencja test_{scenario_name}()
- @pytest.fixture z setup/teardown
- @pytest.mark.parametrize z wieloma zestawami danych
- Mock fixtures (unittest.mock.patch, pytest-mock)
- Walidacja kompilacji (py_compile)
- Szablony Jinja2 (test_module.py.j2, conftest.py.j2)

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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "pytest"

# ── Mapowanie comparison_type -> asercje pytest ──
ASSERTION_MAP: dict[str, str] = {
    "equals": "assert {actual} == {expected}",
    "not_equals": "assert {actual} != {expected}",
    "contains": "assert {expected} in {actual}",
    "not_contains": "assert {expected} not in {actual}",
    "throws": "pytest.raises({expected})",
    "approx": "assert {actual} == pytest.approx({expected})",
    "is_none": "assert {actual} is None",
    "is_not_none": "assert {actual} is not None",
    "is_instance": "assert isinstance({actual}, {expected})",
    "is_true": "assert {actual} is True",
    "is_false": "assert {actual} is False",
    "greater_than": "assert {actual} > {expected}",
    "less_than": "assert {actual} < {expected}",
    "has_length": "assert len({actual}) == {expected}",
}


@register_generator("pytest")
class PytestCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego pytest (Python).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "pytest".
    """

    FRAMEWORK = "pytest"
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
                logger.warning("Katalog szablonow nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── 1.3 Metoda glowna: generate_test_file ──

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy pytest z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (z modelu TestCase)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        # Pobierz nazwe modulu z pierwszego test case
        first_tc = test_cases[0]
        module_name = self._extract_module_name(first_tc)

        # 1.4 Buduj importy
        imports = self._build_imports(test_cases, cfg)

        # Buduj fixtures
        fixtures = self._build_all_fixtures(test_cases, cfg)

        # Buduj funkcje testowe
        test_functions = self._build_all_test_functions(test_cases, cfg)

        # Renderuj szablon
        context = {
            "module_name": module_name,
            "imports": imports,
            "fixtures": fixtures,
            "test_functions": test_functions,
            "project_context": cfg.project_context,
        }

        try:
            template = self.jinja_env.get_template("test_module.py.j2")
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu pytest: %s", exc)
            content = self._fallback_render(context)

        # Walidacja kompilacji
        file_path = f"tests/test_{module_name}.py"
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=module_name,
            fixtures=fixtures,
            test_functions=test_functions,
            imports=imports,
            compilation_result=compilation_result,
        )

    # ── 1.9 generate_setup — conftest.py ──

    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj conftest.py z wspolnymi fixtures.

        Args:
            project_context: kontekst projektu z informacjami o zaleznosciach

        Returns:
            Zawartosc pliku conftest.py
        """
        shared_fixtures = self._build_shared_fixtures(project_context)
        imports = self._build_conftest_imports(project_context)

        context = {
            "project_name": project_context.get("project_name", "testgen") if project_context else "testgen",
            "shared_fixtures": shared_fixtures,
            "imports": imports,
            "project_context": project_context,
        }

        try:
            template = self.jinja_env.get_template("conftest.py.j2")
            return template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania conftest.py.j2: %s", exc)
            return "# Blad generowania conftest.py\npass\n"

    # ── generate_assertion ──

    def generate_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        message: str | None = None,
    ) -> str:
        """Generuj pojedyncza asercje pytest.

        Args:
            expected: oczekiwana wartosc (kod Python)
            actual: rzeczywista wartosc (kod Python)
            comparison_type: typ porownania (equals, contains, throws, approx, ...)
            message: komunikat przy bledzie (opcjonalny)

        Returns:
            Kod asercji jako string
        """
        # 1.7 Mapowanie comparison_type
        return self._map_assertion(expected, actual, comparison_type, message)

    # ── validate_syntax — py_compile ──

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu Python przez py_compile.

        Args:
            code: kod Python do walidacji

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

        # 5.4 Sprawdz obecnosc import pytest
        warnings: list[str] = []
        if "import pytest" not in code:
            warnings.append("Brak 'import pytest' w wygenerowanym kodzie")

        # Zapisz do pliku tymczasowego i zwaliduj
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
    # Metody prywatne
    # ════════════════════════════════════════════════════════════════

    # ── 1.4 _build_imports ──

    def _build_imports(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[str]:
        """Buduj liste importow z kontekstu test case'ow.

        Automatycznie wykrywa importy z:
        - source_file (testowany modul)
        - source_class, source_function
        - dodatkowe zaleznosci z project_context
        """
        imports: list[str] = []

        # Zbierz unikalne importy z test case'ow
        seen_sources: set[str] = set()

        for tc in test_cases:
            # Import testowanego modulu z source_file
            source_file = tc.get("source_file") or tc.get("source_module")
            if source_file and source_file not in seen_sources:
                seen_sources.add(source_file)
                import_stmt = self._source_file_to_import(source_file)
                if import_stmt:
                    imports.append(import_stmt)

            # Import klasy jesli okreslona
            source_class = tc.get("source_class")
            if source_class and source_class not in seen_sources:
                seen_sources.add(source_class)
                source_mod = tc.get("source_file", "")
                if source_mod:
                    mod_path = self._file_path_to_module(source_mod)
                    imports.append(f"from {mod_path} import {source_class}")

            # Importy z explicit imports field
            tc_imports = tc.get("imports")
            if isinstance(tc_imports, list):
                for imp in tc_imports:
                    if imp and imp not in imports:
                        imports.append(imp)
            elif isinstance(tc_imports, str) and tc_imports.strip():
                for imp in tc_imports.strip().split("\n"):
                    imp = imp.strip()
                    if imp and imp not in imports:
                        imports.append(imp)

        return imports

    # ── 1.5 _generate_fixture / _build_all_fixtures ──

    def _build_all_fixtures(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje fixtures z test case'ow."""
        fixtures: list[dict[str, Any]] = []
        seen_fixture_names: set[str] = set()

        for tc in test_cases:
            fixture = self._generate_fixture(tc, config)
            if fixture and fixture["name"] not in seen_fixture_names:
                seen_fixture_names.add(fixture["name"])
                fixtures.append(fixture)

        return fixtures

    def _generate_fixture(
        self,
        test_case: dict[str, Any],
        config: CodeGenConfig,
    ) -> dict[str, Any] | None:
        """Generuj specyfikacje fixture z test case.

        Fixture powstaje gdy test case ma setup_code lub teardown_code.
        """
        setup_code = test_case.get("setup_code", "")
        teardown_code = test_case.get("teardown_code", "")

        if not setup_code and not teardown_code:
            return None

        # Nazwa fixture z source_class lub source_function
        source_class = test_case.get("source_class")
        source_func = test_case.get("source_function")
        if source_class:
            fixture_name = self._normalize_function_name(source_class)
        elif source_func:
            fixture_name = self._normalize_function_name(source_func)
        else:
            fixture_name = "test_data"

        # Scope z test_type
        test_type = test_case.get("test_type", "unit")
        scope = "module" if test_type in ("integration", "e2e") else "function"

        # Yield value — z setup_code ekstrahuj zmienna
        yield_value = self._extract_yield_value(setup_code) or "None"

        return {
            "name": fixture_name,
            "scope": scope,
            "setup_code": setup_code.strip() if setup_code else None,
            "yield_value": yield_value,
            "teardown_code": teardown_code.strip() if teardown_code else None,
            "params": None,
        }

    # ── 1.6 _generate_test_function / _build_all_test_functions ──

    def _build_all_test_functions(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig,
    ) -> list[dict[str, Any]]:
        """Buduj specyfikacje funkcji testowych z test case'ow."""
        functions: list[dict[str, Any]] = []

        for tc in test_cases:
            func = self._generate_test_function(tc, config)
            if func:
                functions.append(func)

        return functions

    def _generate_test_function(
        self,
        test_case: dict[str, Any],
        config: CodeGenConfig,
    ) -> dict[str, Any]:
        """Generuj specyfikacje pojedynczej funkcji testowej."""
        # 1.8 Normalizacja nazwy
        scenario = test_case.get("scenario_name") or test_case.get("title") or "unnamed"
        func_name = self._normalize_function_name(scenario)
        if not func_name.startswith("test_"):
            func_name = f"test_{func_name}"

        # Opis
        description = test_case.get("description") or test_case.get("scenario_description") or scenario

        # Parametry
        parameters = self._build_function_parameters(test_case)

        # Parametryzacja (Task 2)
        parametrize = None
        if config.include_parametrize:
            parametrize = self._generate_parametrize(test_case)

        # Mocki (Task 3)
        mocks = None
        if config.include_mocks:
            mocks = self._generate_mocks_for_test(test_case)

        # Kroki
        steps = self._build_steps(test_case)

        # Asercje
        assertions = self._build_assertions(test_case)

        # Markery
        markers = self._build_markers(test_case)

        return {
            "name": func_name,
            "description": description,
            "parameters": parameters,
            "parametrize": parametrize,
            "mocks": mocks,
            "steps": steps,
            "assertions": assertions,
            "markers": markers,
        }

    # ── 1.7 _map_assertion ──

    def _map_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        message: str | None = None,
    ) -> str:
        """Mapuj comparison_type na asercje pytest.

        Obsluguje: equals, not_equals, contains, not_contains, throws, approx,
        is_none, is_not_none, is_instance, is_true, is_false,
        greater_than, less_than, has_length.
        """
        template = ASSERTION_MAP.get(comparison_type)
        if template:
            result = template.format(expected=expected, actual=actual)
        else:
            # Fallback — zwykly assert equals
            result = f"assert {actual} == {expected}  # nieznany comparison_type: {comparison_type}"

        if message and comparison_type != "throws":
            result += f', "{message}"'

        return result

    # ── 1.8 _normalize_function_name ──

    @staticmethod
    def _normalize_function_name(name: str) -> str:
        """Konwertuj nazwe scenariusza na snake_case.

        Zamienia spacje na '_', usuwa special chars, lowercase.
        Ogranicza dlugosc do max_function_name_length.
        """
        if not name:
            return "unnamed"

        # Zamien na lowercase
        result = name.lower()

        # Zamien spacje i mysliniki na podkreslenia
        result = re.sub(r"[\s\-]+", "_", result)

        # Usun znaki specjalne (zostaw alfanumeryki i _)
        result = re.sub(r"[^a-z0-9_]", "", result)

        # Usun wielokrotne podkreslenia
        result = re.sub(r"_+", "_", result)

        # Usun podkreslenia z poczatku i konca
        result = result.strip("_")

        # Ogranicz dlugosc
        if len(result) > 60:
            result = result[:60].rstrip("_")

        return result or "unnamed"

    # ════════════════════════════════════════════════════════════════
    # Task 2: Parametryzacja
    # ════════════════════════════════════════════════════════════════

    def _generate_parametrize(
        self,
        test_case: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generuj specyfikacje @pytest.mark.parametrize.

        Zwraca None jesli tylko 1 zestaw danych (zwykla funkcja testowa).
        """
        test_data = test_case.get("test_data")
        if not test_data:
            return None

        # test_data moze byc lista zestawow lub pojedynczym slownikiem
        data_sets = self._normalize_test_data(test_data)
        if len(data_sets) <= 1:
            return None  # 2.4 — zwykla funkcja bez parametrize

        # Ekstrahuj nazwy parametrow z pierwszego zestawu
        if isinstance(data_sets[0], dict):
            args = ",".join(data_sets[0].keys())
            values = [list(ds.values()) for ds in data_sets]
        else:
            args = "input_value,expected"
            values = [[ds, ds] for ds in data_sets]

        return {
            "args": args,
            "values": values,
        }

    @staticmethod
    def _normalize_test_data(test_data: Any) -> list[Any]:
        """Normalizuj test_data do listy zestawow danych."""
        if isinstance(test_data, list):
            return test_data
        if isinstance(test_data, dict):
            # Moze byc {"sets": [...]} lub pojedynczy zestaw
            if "sets" in test_data and isinstance(test_data["sets"], list):
                return test_data["sets"]
            return [test_data]
        return []

    # ════════════════════════════════════════════════════════════════
    # Task 3: Mockowanie
    # ════════════════════════════════════════════════════════════════

    def _generate_mocks_for_test(
        self,
        test_case: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        """Generuj specyfikacje mockow dla test case."""
        dependencies = test_case.get("dependencies") or test_case.get("mocks")
        if not dependencies:
            return None

        mocks: list[dict[str, Any]] = []

        if isinstance(dependencies, list):
            for dep in dependencies:
                mock = self._generate_mock_fixture(dep)
                if mock:
                    mocks.append(mock)
        elif isinstance(dependencies, dict):
            mock = self._generate_mock_fixture(dependencies)
            if mock:
                mocks.append(mock)

        return mocks or None

    def _generate_mock_fixture(self, dependency: dict[str, Any]) -> dict[str, Any] | None:
        """Generuj specyfikacje pojedynczego mocka.

        Obsluguje typy: db, api, http, file, service.
        """
        target = dependency.get("target") or dependency.get("module")
        if not target:
            return None

        name = dependency.get("name", self._normalize_function_name(target.split(".")[-1]))
        return_value = dependency.get("return_value")
        side_effect = dependency.get("side_effect")

        return {
            "target": target,
            "name": f"mock_{name}",
            "return_value": str(return_value) if return_value is not None else None,
            "side_effect": str(side_effect) if side_effect is not None else None,
        }

    # ════════════════════════════════════════════════════════════════
    # Metody pomocnicze
    # ════════════════════════════════════════════════════════════════

    def _build_function_parameters(self, test_case: dict[str, Any]) -> list[str]:
        """Buduj parametry funkcji testowej."""
        params: list[str] = []

        # Fixture parameter
        source_class = test_case.get("source_class")
        source_func = test_case.get("source_function")
        if source_class:
            params.append(self._normalize_function_name(source_class))
        elif source_func:
            params.append(self._normalize_function_name(source_func))

        # Parametry z parametrize
        test_data = test_case.get("test_data")
        data_sets = self._normalize_test_data(test_data)
        if len(data_sets) > 1 and isinstance(data_sets[0], dict):
            for key in data_sets[0]:
                if key not in params:
                    params.append(key)

        # Parametry z mockow
        mocks = test_case.get("dependencies") or test_case.get("mocks")
        if isinstance(mocks, list):
            for mock_dep in mocks:
                target = mock_dep.get("target", "") if isinstance(mock_dep, dict) else str(mock_dep)
                mock_name = f"mock_{self._normalize_function_name(target.split('.')[-1])}"
                if mock_name not in params:
                    params.append(mock_name)
        elif isinstance(mocks, dict):
            target = mocks.get("target", "")
            mock_name = f"mock_{self._normalize_function_name(target.split('.')[-1])}"
            if mock_name not in params:
                params.append(mock_name)

        return params

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
            # steps moze byc {"step_1": "kod", "step_2": "kod"}
            for _key, val in steps_raw.items():
                if isinstance(val, str) and val.strip():
                    steps.append({"code": val.strip()})

        return steps

    def _build_assertions(self, test_case: dict[str, Any]) -> list[dict[str, Any]]:
        """Buduj asercje z test case."""
        assertions: list[dict[str, Any]] = []

        # Asercje z expected_result
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

        # Asercje z explicit assertions list
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

    def _build_markers(self, test_case: dict[str, Any]) -> list[str] | None:
        """Buduj markery pytest z test case."""
        markers: list[str] = []

        test_type = test_case.get("test_type", "")
        if test_type == "integration":
            markers.append("@pytest.mark.integration")
        elif test_type == "e2e":
            markers.append("@pytest.mark.e2e")
        elif test_type == "slow":
            markers.append("@pytest.mark.slow")

        # Markery z tags
        tags = test_case.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag not in ("unit", "positive"):
                    markers.append(f"@pytest.mark.{tag}")

        return markers or None

    def _build_shared_fixtures(
        self,
        project_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Buduj wspolne fixtures dla conftest.py."""
        if not project_context:
            return []

        fixtures: list[dict[str, Any]] = []

        # DB fixture jesli projekt wymaga DB
        deps = project_context.get("dependencies", [])
        if "database" in deps or "postgresql" in deps:
            fixtures.append(
                {
                    "name": "db_session",
                    "scope": "session",
                    "description": "Wspolna sesja bazy danych testowej.",
                    "setup_code": "# TODO: configure test database connection",
                    "yield_value": "session",
                    "teardown_code": "session.close()",
                    "is_mock": False,
                    "mock_target": None,
                }
            )

        # API mock fixture
        if "api" in deps or "http" in deps:
            fixtures.append(
                {
                    "name": "mock_api_client",
                    "scope": "function",
                    "description": "Mock klienta API.",
                    "setup_code": "mock_obj.return_value = {}",
                    "yield_value": "mock_obj",
                    "teardown_code": None,
                    "is_mock": True,
                    "mock_target": "httpx.AsyncClient",
                }
            )

        return fixtures

    def _build_conftest_imports(
        self,
        project_context: dict[str, Any] | None,
    ) -> list[str]:
        """Buduj importy dla conftest.py."""
        if not project_context:
            return []

        imports: list[str] = []
        deps = project_context.get("dependencies", [])

        if "database" in deps or "postgresql" in deps:
            imports.append("from sqlalchemy import create_engine")
            imports.append("from sqlalchemy.orm import sessionmaker")

        if "http" in deps or "api" in deps:
            imports.append("import httpx")

        return imports

    # ── Metody util ──

    @staticmethod
    def _extract_module_name(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe modulu z test case."""
        source = test_case.get("source_file") or test_case.get("source_module") or "unknown"
        path = Path(source)
        return path.stem if path.stem else "unknown"

    @staticmethod
    def _source_file_to_import(source_file: str) -> str | None:
        """Konwertuj sciezke pliku na statement importu."""
        if not source_file:
            return None
        path = Path(source_file)
        module = str(path.with_suffix("")).replace("/", ".").replace("\\", ".")
        # Usun leading dots
        module = module.lstrip(".")
        # Sanitizuj niedozwolone znaki w nazwach modulow Python (np. myślniki)
        module = re.sub(r"[^a-zA-Z0-9_.]", "_", module)
        if not module or module == "_":
            return None
        return f"import {module}"

    @staticmethod
    def _file_path_to_module(file_path: str) -> str:
        """Konwertuj sciezke pliku na nazwe modulu Python."""
        path = Path(file_path)
        module = str(path.with_suffix("")).replace("/", ".").replace("\\", ".")
        return module.lstrip(".") or "module"

    @staticmethod
    def _extract_yield_value(setup_code: str) -> str | None:
        """Ekstrahuj zmienna yield z kodu setup."""
        if not setup_code:
            return None
        # Szukaj przypisania np. "calc = Calculator()"
        match = re.match(r"(\w+)\s*=\s*", setup_code.strip())
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _parse_compile_error(error_msg: str) -> tuple[int | None, int | None]:
        """Parsuj linie i kolumne z komunikatu bledu py_compile."""
        # Format: 'File "...", line N'
        line_match = re.search(r"line\s+(\d+)", error_msg)
        col_match = re.search(r"column\s+(\d+)", error_msg)
        line = int(line_match.group(1)) if line_match else None
        col = int(col_match.group(1)) if col_match else None
        return line, col

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy."""
        return TestCodeFile(
            content="# Brak test case'ow do wygenerowania\n",
            file_path="tests/test_empty.py",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any]) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        lines = [
            "# -*- coding: utf-8 -*-",
            '"""Wygenerowano automatycznie przez TestGEN."""',
            "",
            "import pytest",
        ]
        imports = context.get("imports", [])
        if imports:
            lines.extend(imports)
        lines.append("")
        lines.append("# TODO: reczne generowanie — szablon niedostepny")
        lines.append("pass")
        return "\n".join(lines) + "\n"
