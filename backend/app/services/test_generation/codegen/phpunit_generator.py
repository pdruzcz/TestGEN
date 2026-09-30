"""PHPUnit/Pest (PHP) test code generator — Story 1.55 (FR24/FR12).

Generuje kod testowy PHP z przypadków testowych:
- PHPUnit: klasa ``final class XTest extends TestCase`` (``assertSame``,
  ``expectException``, ``setUp``/``tearDown``)
- Pest: DSL nad PHPUnit (``it()``, ``expect()->toBe()``, ``toThrow``,
  ``beforeEach``)

Szablony Jinja2: ``templates/php/{phpunit_test,pest_test}.php.j2``.
Walidacja składni: ``php -l`` jeśli PHP CLI dostępne, inaczej walidacja
statyczna (tag ``<?php`` + zbalansowane nawiasy).

Namespace (zależny od aplikacji): Laravel ``Tests\\Feature`` (domyślnie),
Symfony ``App\\Tests``, nadpisywalny przez ``project_context["php_namespace"]``.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "php"

#: Mapowanie comparison_type → asercja PHPUnit ({expected}/{actual}).
PHPUNIT_ASSERTIONS: dict[str, str] = {
    "equals": "$this->assertSame({expected}, {actual});",
    "not_equals": "$this->assertNotSame({expected}, {actual});",
    "contains": "$this->assertStringContainsString({expected}, {actual});",
    "throws": "$this->expectException({expected}::class);",
    "is_none": "$this->assertNull({actual});",
    "is_not_none": "$this->assertNotNull({actual});",
    "is_true": "$this->assertTrue({actual});",
    "is_false": "$this->assertFalse({actual});",
    "greater_than": "$this->assertGreaterThan({expected}, {actual});",
    "less_than": "$this->assertLessThan({expected}, {actual});",
    "has_length": "$this->assertCount({expected}, {actual});",
}

#: Mapowanie comparison_type → asercja Pest (expect API).
PEST_ASSERTIONS: dict[str, str] = {
    "equals": "expect({actual})->toBe({expected});",
    "not_equals": "expect({actual})->not->toBe({expected});",
    "contains": "expect({actual})->toContain({expected});",
    "throws": "->toThrow({expected}::class);",  # doklejane do closure z wywołaniem
    "is_none": "expect({actual})->toBeNull();",
    "is_not_none": "expect({actual})->not->toBeNull();",
    "is_true": "expect({actual})->toBeTrue();",
    "is_false": "expect({actual})->toBeFalse();",
    "greater_than": "expect({actual})->toBeGreaterThan({expected});",
    "less_than": "expect({actual})->toBeLessThan({expected});",
    "has_length": "expect({actual})->toHaveCount({expected});",
}

#: Konwencje namespace wg aplikacji PHP (Story 1.55 §2).
NAMESPACES: dict[str, str] = {
    "laravel": "Tests\\Feature",
    "symfony": "App\\Tests",
}
DEFAULT_NAMESPACE = "Tests\\Feature"


class _BasePhpGenerator(BaseTestCodeGenerator):
    """Wspólna infrastruktura PHPUnit/Pest (Jinja2, walidacja, nazwy)."""

    FRAMEWORK = ""
    LANGUAGE = "php"
    FILE_EXTENSION = ".php"
    ASSERTIONS: ClassVar[dict[str, str]] = {}

    def __init__(self, config: CodeGenConfig | None = None):
        super().__init__(config)
        self._jinja_env: Environment | None = None

    # ── Jinja2 (lazy) ──

    @property
    def jinja_env(self) -> Environment:
        if self._jinja_env is None:
            templates_dir = self.config.templates_dir or TEMPLATES_DIR
            if not templates_dir.exists():
                logger.warning("Katalog szablonów PHP nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ── Walidacja składni: php -l albo statycznie ──

    @property
    def _php_binary(self) -> str | None:
        return shutil.which("php")

    def validate_syntax(self, code: str) -> CompilationResult:
        if not code.strip():
            return CompilationResult(success=False, code=code, error_message="Pusty kod", framework=self.FRAMEWORK)

        php = self._php_binary
        if php is not None:
            return self._lint_with_php(php, code)
        return self._static_validate(code)

    def _lint_with_php(self, php: str, code: str) -> CompilationResult:
        try:
            proc = subprocess.run(  # ścieżka z shutil.which, input kontrolowane
                [php, "-l"],
                input=code,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("php -l niedostępny (%s) — walidacja statyczna", exc)
            return self._static_validate(code)

        if proc.returncode == 0:
            return CompilationResult(success=True, code=code, framework=self.FRAMEWORK)
        error_message = (proc.stderr or proc.stdout or "").strip() or "php -l wykrył błąd składni"
        return CompilationResult(
            success=False,
            code=code,
            error_message=error_message,
            framework=self.FRAMEWORK,
        )

    def _static_validate(self, code: str) -> CompilationResult:
        """Statyczna asercja: tag <?php + zbalansowane nawiasy (php -l niedostępny)."""
        warnings: list[str] = ["php -l niedostępny — walidacja statyczna"]
        stripped = code.strip()
        if not stripped.startswith("<?php"):
            return CompilationResult(
                success=False,
                code=code,
                error_message="Brak otwierającego tagu '<?php'",
                framework=self.FRAMEWORK,
                warnings=warnings,
            )
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

    # ── Pomocnicze nazewnictwo ──

    @staticmethod
    def _pascal(name: str) -> str:
        words = re.split(r"[^a-zA-Z0-9]+", name or "")
        joined = "".join(w[:1].upper() + w[1:] for w in words if w)
        return joined or "App"

    @staticmethod
    def _php_var(class_name: str) -> str:
        return class_name[:1].lower() + class_name[1:] if class_name else "instance"

    @staticmethod
    def _php_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    @classmethod
    def _php_literal(cls, value: Any) -> str:
        """Literal PHP dla wartości z test_data (null/true/false/liczba/string)."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        return f"'{cls._php_escape(str(value))}'"

    @classmethod
    def _php_smart_literal(cls, value: Any) -> str:
        """Literal oczekiwany: string wyglądający na liczbę/bool → bez cudzysłowu."""
        if isinstance(value, str):
            stripped = value.strip()
            if re.fullmatch(r"-?\d+", stripped) or re.fullmatch(r"-?\d+\.\d+", stripped):
                return stripped
            if stripped.lower() == "true":
                return "true"
            if stripped.lower() == "false":
                return "false"
        return cls._php_literal(value)

    def _resolve_namespace(self, config: CodeGenConfig) -> str:
        ctx = config.project_context or {}
        explicit = ctx.get("php_namespace")
        if explicit:
            return str(explicit)
        php_app = str(ctx.get("php_app", "")).lower()
        return NAMESPACES.get(php_app, DEFAULT_NAMESPACE)

    @staticmethod
    def _first_data_set(tc: dict[str, Any]) -> dict[str, Any]:
        sets = (tc.get("test_data") or {}).get("sets") or []
        return sets[0] if sets else {}

    def _call_expression(self, tc: dict[str, Any]) -> tuple[str, str]:
        """Zwraca (setup, wyrażenie wywołania) dla test case'a."""
        class_name = tc.get("source_class")
        function = tc.get("source_function") or "subject"
        data = self._first_data_set(tc)
        args = ", ".join(self._php_literal(v) for k, v in data.items() if k != "expected")
        if class_name:
            var = self._php_var(class_name)
            setup = f"${var} = new {class_name}();"
            call = f"$result = ${var}->{function}({args});"
        else:
            setup = ""
            call = f"$result = {function}({args});"
        return setup, call

    def _empty_test_file(self) -> TestCodeFile:
        return TestCodeFile(
            content="<?php\n\n// Brak przypadków testowych PHP.\n",
            file_path=f"tests/Feature/Empty{self.FRAMEWORK.capitalize()}Test.php",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )


@register_generator("phpunit")
class PhpUnitCodeGenerator(_BasePhpGenerator):
    """Generator kodu testowego PHPUnit (klasa + TestCase) — Story 1.55."""

    FRAMEWORK = "phpunit"
    ASSERTIONS = PHPUNIT_ASSERTIONS

    TEMPLATE_NAME = "phpunit_test.php.j2"
    TEST_DIR = "tests/Unit"

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
        namespace = self._resolve_namespace(cfg)

        methods: list[dict[str, str]] = []
        for tc in test_cases:
            methods.append(self._build_method(tc))

        context = {
            "namespace": namespace,
            "class_name": class_name,
            "description": (test_cases[0].get("description") or test_cases[0].get("title") or ""),
            "methods": methods,
        }
        try:
            template = self.jinja_env.get_template(self.TEMPLATE_NAME)
            content = template.render(**context)
        except Exception as exc:  # pragma: no cover — Jinja2 niedostępny
            logger.error("Błąd renderowania szablonu PHPUnit: %s", exc)
            content = self._fallback_render(context)

        compilation_result = self.validate_syntax(content) if cfg.validate_compilation else None

        return TestCodeFile(
            content=content,
            file_path=f"{self.TEST_DIR}/{class_name}.php",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=class_name.removesuffix("Test").lower(),
            test_functions=methods,
            imports=["use PHPUnit\\Framework\\TestCase;"],
            compilation_result=compilation_result,
        )

    def _build_method(self, tc: dict[str, Any]) -> dict[str, str]:
        title = tc.get("title") or tc.get("scenario_name") or "case"
        method = f"test{self._pascal(_slugify(title))[:60]}"
        setup, call = self._call_expression(tc)
        comparison = (tc.get("comparison_type") or "is_not_none").lower()
        expected = tc.get("expected_result")
        data = self._first_data_set(tc)
        if expected is None and "expected" in data:
            expected = data["expected"]

        body_lines: list[str] = [f"// {title}"]
        if setup:
            body_lines.append(setup)
        if comparison == "throws":
            body_lines.append(self.generate_assertion(str(expected), "", "throws"))
            body_lines.append(call.replace("$result = ", "", 1) if call.startswith("$result") else call)
            body_lines.append("$this->fail('Oczekiwany wyjątek nie został rzucony.');")
        else:
            body_lines.append(call)
            if comparison == "equals" and expected is not None:
                body_lines.append(self.generate_assertion(self._php_smart_literal(expected), "$result", "equals"))
            else:
                body_lines.append(self.generate_assertion("", "$result", comparison))
        return {"name": method, "title": title, "body": "\n        ".join(body_lines)}

    def generate_setup(self, project_context: dict[str, Any] | None = None) -> str:
        return (
            "<?php\n\n"
            "use PHPUnit\\Framework\\TestCase;\n\n"
            "abstract class TestGENTestCase extends TestCase\n"
            "{\n"
            "    protected function setUp(): void\n"
            "    {\n"
            "        parent::setUp();\n"
            "        // TODO: wspólne inicjalizacje testów\n"
            "    }\n\n"
            "    protected function tearDown(): void\n"
            "    {\n"
            "        // TODO: sprzątanie po testach\n"
            "        parent::tearDown();\n"
            "    }\n"
            "}\n"
        )

    def generate_assertion(self, expected: str, actual: str, comparison_type: str, message: str | None = None) -> str:
        template = self.ASSERTIONS.get(comparison_type.lower(), PHPUNIT_ASSERTIONS["is_not_none"])
        return template.format(expected=expected, actual=actual)

    def _fallback_render(self, context: dict[str, Any]) -> str:
        lines = [
            "<?php",
            f"namespace {context['namespace']};",
            "",
            "use PHPUnit\\Framework\\TestCase;",
            "",
            f"final class {context['class_name']} extends TestCase",
            "{",
        ]
        for method in context["methods"]:
            lines.append(f"    public function {method['name']}(): void")
            lines.append("    {")
            for line in method["body"].split("\n"):
                lines.append(f"        {line}")
            lines.append("    }")
            lines.append("")
        lines.append("}")
        return "\n".join(lines) + "\n"


@register_generator("pest")
class PestCodeGenerator(_BasePhpGenerator):
    """Generator kodu testowego Pest (DSL: it() + expect()) — Story 1.55."""

    FRAMEWORK = "pest"
    ASSERTIONS = PEST_ASSERTIONS

    TEMPLATE_NAME = "pest_test.php.j2"
    TEST_DIR = "tests/Feature"

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
        namespace = self._resolve_namespace(cfg)

        tests: list[dict[str, str]] = []
        for tc in test_cases:
            tests.append(self._build_test(tc))

        context = {
            "namespace": namespace,
            "class_name": class_name,
            "tests": tests,
        }
        try:
            template = self.jinja_env.get_template(self.TEMPLATE_NAME)
            content = template.render(**context)
        except Exception as exc:  # pragma: no cover — Jinja2 niedostępny
            logger.error("Błąd renderowania szablonu Pest: %s", exc)
            content = self._fallback_render(context)

        compilation_result = self.validate_syntax(content) if cfg.validate_compilation else None

        return TestCodeFile(
            content=content,
            file_path=f"{self.TEST_DIR}/{class_name}.php",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=class_name.removesuffix("Test").lower(),
            test_functions=tests,
            imports=[],
            compilation_result=compilation_result,
        )

    def _build_test(self, tc: dict[str, Any]) -> dict[str, str]:
        title = tc.get("title") or tc.get("scenario_name") or "case"
        setup, call = self._call_expression(tc)
        comparison = (tc.get("comparison_type") or "is_not_none").lower()
        expected = tc.get("expected_result")
        data = self._first_data_set(tc)
        if expected is None and "expected" in data:
            expected = data["expected"]

        body_lines: list[str] = []
        if setup:
            body_lines.append(setup)
        if comparison == "throws":
            closure = call.replace("$result = ", "", 1) if call.startswith("$result") else call
            body_lines.append(f"expect(fn () => {closure}){self.generate_assertion(str(expected), '', 'throws')}")
        else:
            body_lines.append(call)
            if comparison == "equals" and expected is not None:
                body_lines.append(self.generate_assertion(self._php_smart_literal(expected), "$result", "equals"))
            else:
                body_lines.append(self.generate_assertion("", "$result", comparison))
        return {"title": self._php_escape(title), "body": "\n    ".join(body_lines)}

    def generate_setup(self, project_context: dict[str, Any] | None = None) -> str:
        return (
            "<?php\n\n"
            "beforeEach(function () {\n"
            "    // TODO: wspólne inicjalizacje testów\n"
            "});\n\n"
            "afterEach(function () {\n"
            "    // TODO: sprzątanie po testach\n"
            "});\n"
        )

    def generate_assertion(self, expected: str, actual: str, comparison_type: str, message: str | None = None) -> str:
        template = self.ASSERTIONS.get(comparison_type.lower(), PEST_ASSERTIONS["is_not_none"])
        return template.format(expected=expected, actual=actual)

    def _fallback_render(self, context: dict[str, Any]) -> str:
        lines = ["<?php"]
        for test in context["tests"]:
            lines.append(f"it('{test['title']}', function () {{")
            for line in test["body"].split("\n"):
                lines.append(f"    {line}")
            lines.append("});")
            lines.append("")
        return "\n".join(lines) + "\n"


def _slugify(name: str) -> str:
    """ASCII slug dla nazw metod (znaki nienależące do [A-Za-z0-9] → '_')."""
    slug = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")
    # Metody PHP nie mogą zaczynać się od cyfry
    if slug[:1].isdigit():
        slug = f"case_{slug}"
    return slug or "case"
