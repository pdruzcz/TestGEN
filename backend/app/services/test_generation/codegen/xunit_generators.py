"""unittest / TestNG / MSTest code generators — Story 1.57.

Generatory natywnych frameworków jednostkowych wykrywanych przez
``FrameworkDetector`` (unittest/nose2, testng, mstest):

- unittest: klasa ``unittest.TestCase`` + ``self.assertEqual…`` +
  ``if __name__ == "__main__": unittest.main()`` (``python -m unittest``);
- TestNG: adnotacje ``@Test``/``@BeforeMethod``/``@AfterMethod``
  (``org.testng.annotations``), ``Assert.assertEquals`` — Java 11+ (``var``);
- MSTest: atrybuty ``[TestClass]``/``[TestMethod]``/``[TestInitialize]``,
  ``Assert.AreEqual`` — .NET 8 (file-scoped namespace).

Wspólna infrastruktura (Jinja2, walidacja, nazewnictwo, literały) w
``_BaseXUnitGenerator`` — wzorzec ``_BasePhpGenerator`` z Story 1.55.
Mapowania asercji trzymane w Pythonie (jedna tabela per framework), nie
w szablonie (Dev Notes story 1.57).
"""

from __future__ import annotations

import logging
import py_compile
import re
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.test_generation.codegen.base import (
    BaseTestCodeGenerator,
    CodeGenConfig,
    CompilationResult,
    TestCodeFile,
    register_generator,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates"

#: Mapowanie comparison_type → asercja unittest ({expected}/{actual}).
UNITTEST_ASSERTIONS: dict[str, str] = {
    "equals": "self.assertEqual({actual}, {expected})",
    "not_equals": "self.assertNotEqual({actual}, {expected})",
    "contains": "self.assertIn({expected}, {actual})",
    "not_contains": "self.assertNotIn({expected}, {actual})",
    "approx": "self.assertAlmostEqual({actual}, {expected})",
    "is_none": "self.assertIsNone({actual})",
    "is_not_none": "self.assertIsNotNone({actual})",
    "is_instance": "self.assertIsInstance({actual}, {expected})",
    "is_true": "self.assertTrue({actual})",
    "is_false": "self.assertFalse({actual})",
    "greater_than": "self.assertGreater({actual}, {expected})",
    "less_than": "self.assertLess({actual}, {expected})",
    "has_length": "self.assertEqual(len({actual}), {expected})",
}

#: Mapowanie comparison_type → asercja TestNG (actual first — konwencja TestNG).
TESTNG_ASSERTIONS: dict[str, str] = {
    "equals": "Assert.assertEquals({actual}, {expected});",
    "not_equals": "Assert.assertNotEquals({actual}, {expected});",
    "contains": "Assert.assertTrue({actual}.contains({expected}));",
    "not_contains": "Assert.assertFalse({actual}.contains({expected}));",
    "approx": "Assert.assertEquals({actual}, {expected}, 0.0001);",
    "is_none": "Assert.assertNull({actual});",
    "is_not_none": "Assert.assertNotNull({actual});",
    "is_instance": "Assert.assertTrue({actual} instanceof {expected});",
    "is_true": "Assert.assertTrue({actual});",
    "is_false": "Assert.assertFalse({actual});",
    "greater_than": "Assert.assertTrue({actual} > {expected});",
    "less_than": "Assert.assertTrue({actual} < {expected});",
    "has_length": "Assert.assertEquals({expected}, {actual}.length());",
}

#: Mapowanie comparison_type → asercja MSTest (expected first — konwencja MSTest).
MSTEST_ASSERTIONS: dict[str, str] = {
    "equals": "Assert.AreEqual({expected}, {actual});",
    "not_equals": "Assert.AreNotEqual({expected}, {actual});",
    "contains": "Assert.IsTrue({actual}.Contains({expected}));",
    "not_contains": "Assert.IsFalse({actual}.Contains({expected}));",
    "approx": "Assert.AreEqual({expected}, {actual}, 0.0001);",
    "is_none": "Assert.IsNull({actual});",
    "is_not_none": "Assert.IsNotNull({actual});",
    "is_instance": "Assert.IsInstanceOfType({actual}, typeof({expected}));",
    "is_true": "Assert.IsTrue({actual});",
    "is_false": "Assert.IsFalse({actual});",
    "greater_than": "Assert.IsTrue({actual} > {expected});",
    "less_than": "Assert.IsTrue({actual} < {expected});",
    "has_length": "Assert.AreEqual({expected}, {actual}.Length);",
}

DEFAULT_TESTNG_PACKAGE = "com.example"
DEFAULT_MSTEST_NAMESPACE = "Tests"


class _BaseXUnitGenerator(BaseTestCodeGenerator):
    """Wspólna infrastruktura unittest/TestNG/MSTest (Jinja2, walidacja, nazwy)."""

    FRAMEWORK = ""
    LANGUAGE = ""
    FILE_EXTENSION = ""
    ASSERTIONS: ClassVar[dict[str, str]] = {}
    TEMPLATES_SUBDIR = ""
    #: Markery wymagane w wygenerowanym kodzie (walidacja strukturalna).
    REQUIRED_MARKERS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, config: CodeGenConfig | None = None):
        super().__init__(config)
        self._jinja_env: Environment | None = None

    # ── Jinja2 (lazy) ──

    @property
    def jinja_env(self) -> Environment:
        if self._jinja_env is None:
            templates_dir = self.config.templates_dir or (TEMPLATES_DIR / self.TEMPLATES_SUBDIR)
            if not templates_dir.exists():
                logger.warning("Katalog szablonów %s nie istnieje: %s", self.FRAMEWORK, templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── Walidacja strukturalna (javac/dotnet niedostępne w kontenerze) ──

    def validate_syntax(self, code: str) -> CompilationResult:
        if not code.strip():
            return CompilationResult(success=False, code=code, error_message="Pusty kod", framework=self.FRAMEWORK)

        warnings: list[str] = ["javac/dotnet niedostępne — walidacja strukturalna"]
        stripped = code.strip()
        for marker in self.REQUIRED_MARKERS:
            if marker not in code:
                warnings.append(f"Brak wymaganego markera: {marker}")

        pairs = {"{": "}", "(": ")", "[": "]"}
        stack: list[str] = []
        in_string: str | None = None
        for char in stripped:
            if in_string:
                if char == in_string:
                    in_string = None
                continue
            if char in ("'", '"'):
                in_string = char
            elif char in pairs:
                stack.append(char)
            elif char in pairs.values():
                if not stack or pairs[stack[-1]] != char:
                    return CompilationResult(
                        success=False,
                        code=code,
                        error_message=f"Niezbalansowane nawiasy: nieoczekiwany '{char}'",
                        framework=self.FRAMEWORK,
                        warnings=warnings,
                    )
                stack.pop()
        if stack:
            return CompilationResult(
                success=False,
                code=code,
                error_message=f"Niezbalansowane nawiasy: niedomknięte '{''.join(stack)}'",
                framework=self.FRAMEWORK,
                warnings=warnings,
            )
        return CompilationResult(success=True, code=code, framework=self.FRAMEWORK, warnings=warnings)

    # ── Pomocnicze nazewnictwo / literały ──

    _PL_TO_ASCII = str.maketrans(
        "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
        "acelnoszzACELNOSZZ",
    )

    @classmethod
    def _ascii_name(cls, name: str) -> str:
        """Transliteruj polskie znaki — „dwóch"→„dwoch", nie „dwch"."""
        return (name or "").translate(cls._PL_TO_ASCII)

    @classmethod
    def _pascal(cls, name: str) -> str:
        words = re.split(r"[^a-zA-Z0-9]+", cls._ascii_name(name))
        joined = "".join(w[:1].upper() + w[1:] for w in words if w)
        return joined or "App"

    @classmethod
    def _snake(cls, name: str) -> str:
        result = re.sub(r"[\s\-]+", "_", cls._ascii_name(name).lower())
        result = re.sub(r"[^a-z0-9_]", "", result)
        result = re.sub(r"_+", "_", result).strip("_")
        return result[:60].rstrip("_") or "unnamed"

    @classmethod
    def _camel(cls, name: str) -> str:
        pascal = cls._pascal(name)
        return pascal[:1].lower() + pascal[1:] if pascal else "instance"

    @staticmethod
    def _literal(value: Any, *, true_lit: str, false_lit: str, none_lit: str) -> str:
        if value is None:
            return none_lit
        if isinstance(value, bool):
            return true_lit if value else false_lit
        if isinstance(value, int | float):
            return str(value)
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @classmethod
    def _smart_literal(cls, value: Any, **kw: str) -> str:
        """Literal oczekiwany: string wyglądający na liczbę/bool → bez cudzysłowu."""
        if isinstance(value, str):
            stripped = value.strip()
            if re.fullmatch(r"-?\d+", stripped) or re.fullmatch(r"-?\d+\.\d+", stripped):
                return stripped
            if stripped.lower() == "true":
                return kw.get("true_lit", "True")
            if stripped.lower() == "false":
                return kw.get("false_lit", "False")
        return cls._literal(value, **kw)

    @staticmethod
    def _identifier(value: Any) -> str:
        """Nazwa klasy/identyfikatora (throws) — bez cudzysłowu i escapowania."""
        return str(value).strip() or "Exception"

    @staticmethod
    def _first_data_set(tc: dict[str, Any]) -> dict[str, Any]:
        sets = (tc.get("test_data") or {}).get("sets") or []
        return sets[0] if sets else {}

    def _expected(self, tc: dict[str, Any]) -> Any:
        expected = tc.get("expected_result")
        if expected is None:
            expected = self._first_data_set(tc).get("expected")
        return expected

    def _comparison(self, tc: dict[str, Any]) -> str:
        return (tc.get("comparison_type") or "is_not_none").lower()

    @staticmethod
    def _steps(tc: dict[str, Any]) -> list[str]:
        steps = tc.get("steps") or []
        if isinstance(steps, list):
            return [str(s.get("code") if isinstance(s, dict) else s).strip() for s in steps if s]
        return []

    def _generate_args(self, tc: dict[str, Any], **kw: str) -> str:
        data = self._first_data_set(tc)
        return ", ".join(self._literal(v, **kw) for k, v in data.items() if k != "expected")


@register_generator("unittest")
class UnittestCodeGenerator(_BaseXUnitGenerator):
    """Generator kodu testowego unittest (Python) — Story 1.57 (AC1)."""

    FRAMEWORK = "unittest"
    LANGUAGE = "python"
    FILE_EXTENSION = ".py"
    ASSERTIONS = UNITTEST_ASSERTIONS
    TEMPLATES_SUBDIR = "unittest"

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file()

        class_base = test_cases[0].get("source_class") or test_cases[0].get("scenario_name") or "App"
        class_name = f"{self._pascal(str(class_base))}Test"
        module_name = self._snake(str(class_base))

        setup_body = self._build_setup_body(test_cases)
        methods = [self._build_method(tc) for tc in test_cases]

        context = {
            "imports": ["import unittest"],
            "description": test_cases[0].get("description") or test_cases[0].get("title") or "",
            "class_name": class_name,
            "setup_body": setup_body,
            "teardown_body": self._build_teardown_body(test_cases),
            "methods": methods,
        }
        try:
            content = self.jinja_env.get_template("test_class.py.j2").render(**context)
        except Exception as exc:  # pragma: no cover — Jinja2 niedostępny
            logger.error("Błąd renderowania szablonu unittest: %s", exc)
            content = self._fallback_render(context)

        compilation_result = self._py_compile(content) if cfg.validate_compilation else None

        return TestCodeFile(
            content=content,
            file_path=f"tests/unittest/test_{module_name}.py",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=module_name,
            test_functions=methods,
            imports=list(context["imports"]),
            compilation_result=compilation_result,
        )

    def _build_method(self, tc: dict[str, Any]) -> dict[str, str]:
        title = tc.get("title") or tc.get("scenario_name") or "case"
        name = f"test_{self._snake(title)}"
        comparison = self._comparison(tc)
        expected = self._expected(tc)
        data = self._first_data_set(tc)
        args = ", ".join(
            self._literal(v, true_lit="True", false_lit="False", none_lit="None")
            for k, v in data.items()
            if k != "expected"
        )
        class_name = tc.get("source_class")
        function = tc.get("source_function") or "subject"

        body: list[str] = []
        steps = self._steps(tc)
        if steps:
            body.extend(steps)
        elif comparison == "throws":
            call = self._call_expression(class_name, function, args, assign=False)
            body.append(f"with self.assertRaises({self._identifier(expected)}):")
            body.append(f"    {call}")
        else:
            body.append(self._call_expression(class_name, function, args, assign=True))
            if expected is not None:
                body.append(
                    self.generate_assertion(
                        self._smart_literal(expected, true_lit="True", false_lit="False", none_lit="None"),
                        "result",
                        "equals",
                    )
                )
            else:
                body.append(self.generate_assertion("", "result", comparison))

        return {
            "name": name,
            "doc": f'        """{title}"""',
            "body": "\n".join(f"        {line}" for line in body),
        }

    def _call_expression(self, class_name: str | None, function: str, args: str, *, assign: bool) -> str:
        prefix = "result = " if assign else ""
        if class_name:
            return f"{prefix}self.{self._camel(class_name)}.{function}({args})"
        return f"{prefix}{function}({args})"

    def _build_setup_body(self, test_cases: list[dict[str, Any]]) -> str | None:
        lines: list[str] = []
        seen: set[str] = set()
        for tc in test_cases:
            class_name = tc.get("source_class")
            if class_name and class_name not in seen:
                seen.add(class_name)
                lines.append(f"self.{self._camel(str(class_name))} = {class_name}()")
            for step in (tc.get("setup_code") or "").strip().splitlines():
                if step.strip():
                    lines.append(step.strip())
        return "\n".join(f"        {line}" for line in lines) if lines else None

    def _build_teardown_body(self, test_cases: list[dict[str, Any]]) -> str | None:
        lines: list[str] = []
        for tc in test_cases:
            for step in (tc.get("teardown_code") or "").strip().splitlines():
                if step.strip():
                    lines.append(step.strip())
        return "\n".join(f"        {line}" for line in lines) if lines else None

    def generate_assertion(self, expected: str, actual: str, comparison_type: str, message: str | None = None) -> str:
        template = self.ASSERTIONS.get(comparison_type.lower())
        if template is None:
            return f"self.assertIsNotNone({actual})"
        return template.format(expected=expected, actual=actual)

    def generate_setup(self, project_context: dict[str, Any] | None = None) -> str:
        return (
            "import unittest\n\n\n"
            "class TestGENTestCase(unittest.TestCase):\n"
            "    def setUp(self):\n"
            "        # TODO: wspólne inicjalizacje testów\n"
            "        pass\n"
            "\n"
            "    def tearDown(self):\n"
            "        # TODO: sprzątanie po testach\n"
            "        pass\n"
        )

    def _py_compile(self, content: str) -> CompilationResult:
        """Walidacja przez py_compile (Python dostępny w-house)."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
                tmp_path = f.name
                f.write(content)
            py_compile.compile(tmp_path, doraise=True)
            return CompilationResult(success=True, code=content, framework=self.FRAMEWORK)
        except py_compile.PyCompileError as exc:
            return CompilationResult(success=False, code=content, error_message=str(exc), framework=self.FRAMEWORK)
        finally:
            if tmp_path:
                import contextlib

                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)

    def _empty_test_file(self) -> TestCodeFile:
        return TestCodeFile(
            content="# Brak przypadków testowych.\n",
            file_path="tests/unittest/test_empty.py",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    def _fallback_render(self, context: dict[str, Any]) -> str:
        lines = ["import unittest", "", "class FallbackTest(unittest.TestCase):", "    pass"]
        return "\n".join(lines) + "\n"


@register_generator("testng")
class TestNgCodeGenerator(_BaseXUnitGenerator):
    """Generator kodu testowego TestNG (Java 11+) — Story 1.57 (AC1)."""

    FRAMEWORK = "testng"
    LANGUAGE = "java"
    FILE_EXTENSION = ".java"
    ASSERTIONS = TESTNG_ASSERTIONS
    TEMPLATES_SUBDIR = "testng"
    REQUIRED_MARKERS = ("import org.testng.annotations.Test;", "@Test")

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file()

        class_base = test_cases[0].get("source_class") or test_cases[0].get("scenario_name") or "App"
        class_name = f"{self._pascal(str(class_base))}Test"
        package = (cfg.project_context or {}).get("java_package") or DEFAULT_TESTNG_PACKAGE

        fields: list[str] = []
        setup_lines: list[str] = []
        if test_cases[0].get("source_class"):
            tested = str(test_cases[0]["source_class"])
            fields.append(f"private {tested} {self._camel(tested)};")
            setup_lines.append(f"{self._camel(tested)} = new {tested}();")
        has_setup = bool(setup_lines)
        teardown_lines: list[str] = []
        for tc in test_cases:
            for step in (tc.get("teardown_code") or "").strip().splitlines():
                if step.strip():
                    teardown_lines.append(step.strip())
        has_teardown = bool(teardown_lines)

        # Importy: Assert (kwalifikowane wywołania) + adnotacje warunkowo —
        # @BeforeMethod/@AfterMethod bez importu = błąd kompilacji Javy.
        imports = [
            "import org.testng.Assert;",
            "import org.testng.annotations.Test;",
        ]
        if has_setup:
            imports.append("import org.testng.annotations.BeforeMethod;")
        if has_teardown:
            imports.append("import org.testng.annotations.AfterMethod;")
        imports.sort()
        for tc in test_cases:
            for imp in (tc.get("imports") or []) if isinstance(tc.get("imports"), list) else []:
                if imp and imp not in imports:
                    imports.append(str(imp))
        for tc in test_cases:
            for step in (tc.get("setup_code") or "").strip().splitlines():
                if step.strip():
                    setup_lines.append(step.strip())

        methods = [self._build_method(tc) for tc in test_cases]

        context = {
            "package_name": package,
            "imports": imports,
            "description": test_cases[0].get("description") or test_cases[0].get("title") or "",
            "class_name": class_name,
            "fields": fields,
            "setup_body": "\n".join(f"        {line}" for line in setup_lines) if setup_lines else None,
            "teardown_body": "\n".join(f"        {line}" for line in teardown_lines) if teardown_lines else None,
            "methods": methods,
        }
        try:
            content = self.jinja_env.get_template("TestClass.java.j2").render(**context)
        except Exception as exc:  # pragma: no cover — Jinja2 niedostępny
            logger.error("Błąd renderowania szablonu TestNG: %s", exc)
            content = self._fallback_render(context)

        compilation_result = self.validate_syntax(content) if cfg.validate_compilation else None

        pkg_path = package.replace(".", "/")
        return TestCodeFile(
            content=content,
            file_path=f"src/test/java/{pkg_path}/{class_name}.java",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=class_name.removesuffix("Test"),
            test_functions=methods,
            imports=imports,
            compilation_result=compilation_result,
        )

    def _build_method(self, tc: dict[str, Any]) -> dict[str, str]:
        title = tc.get("title") or tc.get("scenario_name") or "case"
        name = f"test{self._pascal(title)[:58]}"
        comparison = self._comparison(tc)
        expected = self._expected(tc)
        args = self._generate_args(tc, true_lit="true", false_lit="false", none_lit="null")
        class_name = tc.get("source_class")
        function = tc.get("source_function") or "subject"

        if comparison == "throws":
            call = self._call_statement(class_name, function, args)
            body = [f"Assert.assertThrows({self._identifier(expected)}.class, () -> {{ {call} }});"]
        else:
            body = [f"var result = {self._call_statement(class_name, function, args)};"]
            if expected is not None:
                body.append(
                    self.generate_assertion(
                        self._smart_literal(expected, true_lit="true", false_lit="false", none_lit="null"),
                        "result",
                        "equals",
                    )
                )
            else:
                body.append(self.generate_assertion("", "result", comparison))
        steps = self._steps(tc)
        if steps:
            body = steps

        return {"name": name, "body": "\n".join(f"        {line}" for line in body)}

    def _call_statement(self, class_name: str | None, function: str, args: str) -> str:
        if class_name:
            return f"{self._camel(str(class_name))}.{function}({args})"
        return f"{function}({args})"

    def generate_assertion(self, expected: str, actual: str, comparison_type: str, message: str | None = None) -> str:
        template = self.ASSERTIONS.get(comparison_type.lower())
        if template is None:
            return f"Assert.assertNotNull({actual});"
        return template.format(expected=expected, actual=actual)

    def generate_setup(self, project_context: dict[str, Any] | None = None) -> str:
        return (
            "import org.testng.annotations.BeforeMethod;\n"
            "import org.testng.annotations.AfterMethod;\n\n\n"
            "public abstract class TestGENTestCase {\n"
            "    @BeforeMethod\n"
            "    public void setUp() {\n"
            "        // TODO: wspólne inicjalizacje testów\n"
            "    }\n\n"
            "    @AfterMethod\n"
            "    public void tearDown() {\n"
            "        // TODO: sprzątanie po testach\n"
            "    }\n"
            "}\n"
        )

    def _empty_test_file(self) -> TestCodeFile:
        return TestCodeFile(
            content="// Brak przypadków testowych.\n",
            file_path="src/test/java/com/example/EmptyTest.java",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="Empty",
        )

    def _fallback_render(self, context: dict[str, Any]) -> str:
        lines = [
            f"package {context['package_name']};",
            "",
            "import org.testng.annotations.Test;",
            "",
            f"public class {context['class_name']} {{",
            "    @Test",
            "    public void placeholder() {",
            "    }",
            "}",
        ]
        return "\n".join(lines) + "\n"


@register_generator("mstest")
class MsTestCodeGenerator(_BaseXUnitGenerator):
    """Generator kodu testowego MSTest (.NET 8) — Story 1.57 (AC1)."""

    FRAMEWORK = "mstest"
    LANGUAGE = "csharp"
    FILE_EXTENSION = ".cs"
    ASSERTIONS = MSTEST_ASSERTIONS
    TEMPLATES_SUBDIR = "mstest"
    REQUIRED_MARKERS = ("using Microsoft.VisualStudio.TestTools.UnitTesting;", "[TestMethod]")

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file()

        class_base = test_cases[0].get("source_class") or test_cases[0].get("scenario_name") or "App"
        class_name = f"{self._pascal(str(class_base))}Test"
        namespace = (cfg.project_context or {}).get("cs_namespace") or DEFAULT_MSTEST_NAMESPACE

        usings = ["using Microsoft.VisualStudio.TestTools.UnitTesting;"]
        fields: list[str] = []
        setup_lines: list[str] = []
        if test_cases[0].get("source_class"):
            tested = str(test_cases[0]["source_class"])
            fields.append(f"private readonly {tested} _sut;")
            setup_lines.append(f"_sut = new {tested}();")
        for tc in test_cases:
            for step in (tc.get("setup_code") or "").strip().splitlines():
                if step.strip():
                    setup_lines.append(step.strip())

        methods = [self._build_method(tc) for tc in test_cases]

        context = {
            "namespace": namespace,
            "usings": usings,
            "description": test_cases[0].get("description") or test_cases[0].get("title") or "",
            "class_name": class_name,
            "fields": fields,
            "setup_body": "\n".join(f"        {line}" for line in setup_lines) if setup_lines else None,
            "teardown_body": None,
            "methods": methods,
        }
        try:
            content = self.jinja_env.get_template("TestClass.cs.j2").render(**context)
        except Exception as exc:  # pragma: no cover — Jinja2 niedostępny
            logger.error("Błąd renderowania szablonu MSTest: %s", exc)
            content = self._fallback_render(context)

        compilation_result = self.validate_syntax(content) if cfg.validate_compilation else None

        return TestCodeFile(
            content=content,
            file_path=f"tests/{class_name}.cs",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=class_name.removesuffix("Test"),
            test_functions=methods,
            imports=usings,
            compilation_result=compilation_result,
        )

    def _build_method(self, tc: dict[str, Any]) -> dict[str, str]:
        title = tc.get("title") or tc.get("scenario_name") or "case"
        name = f"{self._pascal(title)[:58]}Test"
        comparison = self._comparison(tc)
        expected = self._expected(tc)
        args = self._generate_args(tc, true_lit="true", false_lit="false", none_lit="null")
        class_name = tc.get("source_class")
        function = self._pascal(tc.get("source_function") or "Subject")

        if comparison == "throws":
            call = self._call_statement(class_name, function, args)
            body = [f"Assert.ThrowsException<{self._identifier(expected)}>(() => {{ {call}; }});"]
        else:
            body = [f"var result = {self._call_statement(class_name, function, args)};"]
            if expected is not None:
                body.append(
                    self.generate_assertion(
                        self._smart_literal(expected, true_lit="true", false_lit="false", none_lit="null"),
                        "result",
                        "equals",
                    )
                )
            else:
                body.append(self.generate_assertion("", "result", comparison))
        steps = self._steps(tc)
        if steps:
            body = steps

        return {"name": name, "body": "\n".join(f"        {line}" for line in body)}

    def _call_statement(self, class_name: str | None, function: str, args: str) -> str:
        if class_name:
            return f"_sut.{function}({args})"
        return f"{function}({args})"

    def generate_assertion(self, expected: str, actual: str, comparison_type: str, message: str | None = None) -> str:
        template = self.ASSERTIONS.get(comparison_type.lower())
        if template is None:
            return f"Assert.IsNotNull({actual});"
        return template.format(expected=expected, actual=actual)

    def generate_setup(self, project_context: dict[str, Any] | None = None) -> str:
        return (
            "using Microsoft.VisualStudio.TestTools.UnitTesting;\n\n\n"
            "[TestClass]\n"
            "public abstract class TestGENTestBase\n"
            "{\n"
            "    [TestInitialize]\n"
            "    public void SetUp()\n"
            "    {\n"
            "        // TODO: wspólne inicjalizacje testów\n"
            "    }\n"
            "}\n"
        )

    def _empty_test_file(self) -> TestCodeFile:
        return TestCodeFile(
            content="// Brak przypadków testowych.\n",
            file_path="tests/EmptyTest.cs",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="Empty",
        )

    def _fallback_render(self, context: dict[str, Any]) -> str:
        lines = [
            f"namespace {context['namespace']};",
            "",
            "using Microsoft.VisualStudio.TestTools.UnitTesting;",
            "",
            "[TestClass]",
            f"public class {context['class_name']}",
            "{",
            "    [TestMethod]",
            "    public void Placeholder()",
            "    {",
            "    }",
            "}",
        ]
        return "\n".join(lines) + "\n"
