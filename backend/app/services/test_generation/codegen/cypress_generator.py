"""Cypress code generator — Epic 3, Story 3.12.

Generuje pliki testowe Cypress (.cy.ts) z test case'ow GUI/e2e:
- Struktura describe() / beforeEach() / it()
- Komendy cy.visit/get/contains/click/type/select + asercje should()
- Mockowanie API przez cy.intercept() + cy.wait()
- Visual testing przez cy.matchImageSnapshot() (plugin cypress-image-snapshot)
- Priorytetyzacja selektorow: data-cy > data-testid > [role] > cy.contains('tekst')
- Szablon Jinja2 (cypress_spec.jinja2)

AC: 1-6
"""

import logging
import re
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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "cypress"

# ── Mapowanie comparison_type -> asercje Cypress should() ──
ASSERTION_MAP: dict[str, str] = {
    "equals": "should('have.text', {expected})",
    "contains": "should('contain', {expected})",
    "is_visible": "should('be.visible')",
    "exists": "should('exist')",
    "not_exists": "should('not.exist')",
    "is_checked": "should('be.checked')",
    "has_value": "should('have.value', {expected})",
}

# Domyslna konfiguracja snapshota wizualnego (AC3)
DEFAULT_SNAPSHOT_THRESHOLD = 0.05
DEFAULT_DIFF_THRESHOLD = 0.1


@register_generator("cypress")
class CypressCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego Cypress (TypeScript).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "cypress" (AC6 — CodeGeneratorFactory).
    """

    FRAMEWORK = "cypress"
    LANGUAGE = "typescript"
    FILE_EXTENSION = ".cy.ts"

    # Typy test case'ow traktowane jako regresja wizualna (AC3)
    VISUAL_TYPES: ClassVar[set[str]] = {"visual", "visual_regression", "regression", "visual-regression"}

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
                logger.warning("Katalog szablonow Cypress nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ════════════════════════════════════════════════════════════════
    # Metoda glowna: generate_test_file (AC1, AC4)
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy Cypress z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (z modelu TestCase)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem TypeScript
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        first_tc = test_cases[0]
        feature_name = self._extract_feature_name(first_tc)
        describe_title = first_tc.get("title") or feature_name
        base_url = self._resolve_base_url(test_cases, cfg)

        before_each = self._build_before_each(first_tc, base_url)

        tests: list[dict[str, Any]] = []
        needs_image_snapshot = False
        for tc in test_cases:
            commands = self._build_commands(tc, base_url)
            if self._is_visual(tc):
                commands.append(self._add_visual_testing_step(tc))
                needs_image_snapshot = True
            tests.append({"name": tc.get("title") or "scenariusz", "commands": commands})

        context = {
            "describe_title": describe_title,
            "before_each": before_each,
            "tests": tests,
            "needs_image_snapshot": needs_image_snapshot,
        }

        try:
            template = self.jinja_env.get_template("cypress_spec.jinja2")
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu Cypress: %s", exc)
            content = self._fallback_render(context)

        file_path = f"cypress/e2e/{self._kebab_case(feature_name)}.cy.ts"
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=self._kebab_case(feature_name),
            fixtures=[],
            test_functions=tests,
            imports=['/// <reference types="cypress" />'],
            compilation_result=compilation_result,
        )

    # ── generate_setup — cypress/support/e2e.ts ──

    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj plik wsparcia Cypress (rejestracja pluginu snapshot)."""
        return (
            "/// <reference types=\"cypress\" />\n"
            "import 'cypress-image-snapshot/command';\n"
        )

    # ── generate_assertion ──

    def generate_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        message: str | None = None,
    ) -> str:
        """Generuj pojedyncza asercje Cypress should().

        Args:
            expected: oczekiwana wartosc (literal TS, np. "'Zaloguj'")
            actual: selektor lub lancuch cy.get(...) do ktorego dopinana jest asercja
            comparison_type: typ porownania (equals, contains, is_visible, exists, ...)
            message: ignorowany (Cypress nie wspiera komunikatu w should)

        Returns:
            Kod asercji jako string
        """
        should = ASSERTION_MAP.get(comparison_type, "should('exist')")
        should = should.format(expected=expected)
        return f"{actual}.{should};"

    # ── validate_syntax — walidacja strukturalna ──

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie kodu Cypress (walidacja strukturalna).

        TypeScript nie jest kompilowany w tym srodowisku — sprawdzamy
        balans nawiasow oraz obecnosc bloku describe().
        """
        if not code.strip():
            return CompilationResult(
                success=False,
                code=code,
                error_message="Pusty kod",
                framework=self.FRAMEWORK,
            )

        errors: list[str] = []
        warnings: list[str] = []

        if code.count("{") != code.count("}"):
            errors.append("Niezbalansowane nawiasy klamrowe")
        if code.count("(") != code.count(")"):
            errors.append("Niezbalansowane nawiasy okragle")
        if not re.search(r"describe\s*\(", code):
            errors.append("Brak bloku describe()")
        if not re.search(r"\bit\s*\(", code):
            warnings.append("Brak bloku it() — plik nie zawiera testow")

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
    # AC2: Priorytetyzacja selektorow
    # ════════════════════════════════════════════════════════════════

    def _resolve_selector(self, component: dict[str, Any] | None) -> str | None:
        """Dobierz selektor cy.get() wg priorytetu: data-cy > data-testid > [role].

        Zwraca None gdy element nie ma atrybutow testowych — wowczas
        wywolujacy uzyje cy.contains('tekst') (AC2 — nigdy klasy/tagi CSS).
        """
        if not component:
            return None
        attrs = component.get("attributes") or {}
        for attr in ("data-cy", "data-testid"):
            val = attrs.get(attr)
            if val:
                return f'[{attr}="{val}"]'
        role = attrs.get("role")
        if role:
            return f'[role="{role}"]'
        return None

    def _cy_target(self, step: dict[str, Any]) -> str:
        """Zbuduj poczatek lancucha komendy: cy.get(...) lub cy.contains(...)."""
        explicit = step.get("selector")
        if explicit:
            return f"cy.get('{explicit}')"

        component = step.get("component") or {}
        resolved = self._resolve_selector(component)
        if resolved:
            return f"cy.get('{resolved}')"

        text = (
            component.get("label")
            or component.get("text")
            or step.get("text")
            or step.get("target")
            or ""
        )
        return f"cy.contains('{self._escape(text)}')"

    # ════════════════════════════════════════════════════════════════
    # AC1: Mapowanie krokow na komendy Cypress
    # ════════════════════════════════════════════════════════════════

    def _map_step_to_command(self, step: dict[str, Any]) -> list[str]:
        """Mapuj pojedynczy krok testowy na liste komend Cypress.

        Zwraca liste (zwykle 1 linia; wait_api zwraca 2 linie:
        cy.intercept(...).as(alias) + cy.wait('@alias')).
        """
        action = (step.get("action") or "").strip().lower()
        value = step.get("value") or step.get("input_data") or step.get("data") or ""

        if action == "navigate":
            url = step.get("url") or value or "/"
            return [f"cy.visit('{self._escape(url)}');"]

        if action == "wait_api":
            method = (step.get("method") or "GET").upper()
            url = step.get("url") or "**"
            alias = step.get("alias") or "apiCall"
            return [
                f"cy.intercept('{method}', '{self._escape(url)}').as('{alias}');",
                f"cy.wait('@{alias}');",
            ]

        target = self._cy_target(step)

        if action == "click":
            return [f"{target}.click();"]
        if action == "type":
            return [f"{target}.type('{self._escape(value)}');"]
        if action == "select":
            return [f"{target}.select('{self._escape(value)}');"]
        if action == "assert_visible":
            return [f"{target}.should('be.visible');"]
        if action == "assert_text":
            return [f"{target}.should('have.text', '{self._escape(value)}');"]
        if action == "assert_exists":
            return [f"{target}.should('exist');"]

        # Nieznana akcja — bezpieczny komentarz, nie psujemy struktury
        return [f"// nieobslugiwana akcja: {action or 'brak'}"]

    def _build_commands(self, test_case: dict[str, Any], base_url: str | None) -> list[str]:
        """Zbuduj liste komend Cypress dla pojedynczego test case (bloku it)."""
        commands: list[str] = []
        steps = self._normalize_steps(test_case.get("steps"))
        for step in steps:
            commands.extend(self._map_step_to_command(step))
        return commands

    # ════════════════════════════════════════════════════════════════
    # AC3: Visual testing
    # ════════════════════════════════════════════════════════════════

    def _add_visual_testing_step(self, test_case: dict[str, Any]) -> str:
        """Generuj komende cy.matchImageSnapshot() z konfiguracja threshold."""
        name = self._kebab_case(test_case.get("title") or "snapshot")
        return (
            f"cy.matchImageSnapshot('{name}', "
            f"{{ failureThreshold: {DEFAULT_SNAPSHOT_THRESHOLD}, "
            f"failureThresholdType: 'percent', "
            f"customDiffConfig: {{ threshold: {DEFAULT_DIFF_THRESHOLD} }} }});"
        )

    # ════════════════════════════════════════════════════════════════
    # Metody pomocnicze
    # ════════════════════════════════════════════════════════════════

    def _build_before_each(self, test_case: dict[str, Any], base_url: str | None) -> list[str]:
        """Zbuduj komendy beforeEach() z preconditions i base_url."""
        commands: list[str] = []
        if base_url:
            commands.append(f"cy.visit('{self._escape(base_url)}');")

        preconditions = test_case.get("preconditions")
        if isinstance(preconditions, dict):
            steps = preconditions.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        commands.extend(self._map_step_to_command(step))
                    elif isinstance(step, str) and step.strip():
                        commands.append(f"// {step.strip()}")
        elif isinstance(preconditions, list):
            for step in preconditions:
                if isinstance(step, dict):
                    commands.extend(self._map_step_to_command(step))
                elif isinstance(step, str) and step.strip():
                    commands.append(f"// {step.strip()}")

        return commands

    def _is_visual(self, test_case: dict[str, Any]) -> bool:
        """Czy test case dotyczy regresji wizualnej (AC3)."""
        if test_case.get("visual") is True:
            return True
        tc_type = (test_case.get("type") or "").strip().lower()
        return tc_type in self.VISUAL_TYPES

    def _resolve_base_url(self, test_cases: list[dict[str, Any]], config: CodeGenConfig) -> str | None:
        """Ustal base_url z konfiguracji lub preconditions."""
        if config.project_context:
            url = config.project_context.get("base_url")
            if url:
                return url
        for tc in test_cases:
            preconditions = tc.get("preconditions")
            if isinstance(preconditions, dict) and preconditions.get("base_url"):
                return preconditions["base_url"]
        return None

    @staticmethod
    def _normalize_steps(steps_raw: Any) -> list[dict[str, Any]]:
        """Normalizuj pole steps test case do listy slownikow krokow."""
        if not steps_raw:
            return []
        if isinstance(steps_raw, list):
            return [s for s in steps_raw if isinstance(s, dict)]
        if isinstance(steps_raw, dict):
            inner = steps_raw.get("steps")
            if isinstance(inner, list):
                return [s for s in inner if isinstance(s, dict)]
            return [v for v in steps_raw.values() if isinstance(v, dict)]
        return []

    @staticmethod
    def _extract_feature_name(test_case: dict[str, Any]) -> str:
        """Ekstrahuj nazwe feature z test case."""
        return (
            test_case.get("feature_name")
            or test_case.get("title")
            or test_case.get("source_function")
            or "feature"
        )

    @staticmethod
    def _kebab_case(name: str) -> str:
        """Konwertuj nazwe na kebab-case (AC4)."""
        if not name:
            return "feature"
        result = name.lower()
        result = re.sub(r"[\s_]+", "-", result)
        result = re.sub(r"[^a-z0-9-]", "", result)
        result = re.sub(r"-+", "-", result).strip("-")
        return result or "feature"

    @staticmethod
    def _escape(value: Any) -> str:
        """Escapuj apostrofy do literalu TypeScript w pojedynczych cudzyslowach."""
        return str(value).replace("\\", "\\\\").replace("'", "\\'")

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty plik testowy Cypress."""
        return TestCodeFile(
            content="// Brak test case'ow do wygenerowania\n",
            file_path="cypress/e2e/empty.cy.ts",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any]) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        lines = [
            '/// <reference types="cypress" />',
            "",
            f"describe('{context.get('describe_title', 'Test')}', () => {{",
            "  it('scenariusz', () => {",
            "    // TODO: szablon niedostepny — reczne generowanie",
            "  });",
            "});",
        ]
        return "\n".join(lines) + "\n"
