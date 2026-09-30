"""SikuliX (image-based) code generator — Epic 3, Story 3.13.

Generuje skrypty SikuliX (Jython/.py) do testowania GUI w oparciu
o rozpoznawanie obrazow (Pattern matching), a nie selektory DOM:
- Struktura: importy ``from sikuli import *`` -> klasa -> metoda testFlow()
- Operacje: self.s.click/type/wait + asercje exists()/waitVanish()
- Patterny: Pattern("nazwa.png").similar(0.8) wycinane z bbox screenshotow
- Konfiguracja similarity zalezna od typu komponentu (0.7-0.9)
- Szablon Jinja2 (sikulix_test.jinja2)

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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "sikulix"

# Domyslny timeout operacji oczekiwania (AC4)
DEFAULT_TIMEOUT = 10


@register_generator("sikulix")
class SikuliXCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego SikuliX (Jython).

    Dziedziczy po BaseTestCodeGenerator, zarejestrowany
    w CodeGenRegistry pod kluczem "sikulix" (AC6 — CodeGeneratorFactory).
    """

    FRAMEWORK = "sikulix"
    LANGUAGE = "python"
    FILE_EXTENSION = ".py"

    # Mapa typ komponentu -> bazowy threshold similarity (AC3).
    # Wyzsza unikalnosc elementu -> wyzszy threshold (mniej falszywych trafien).
    SIMILARITY_MAP: ClassVar[dict[str, float]] = {
        "button": 0.7,
        "link": 0.7,
        "input": 0.75,
        "textfield": 0.75,
        "dropdown": 0.8,
        "select": 0.8,
        "checkbox": 0.85,
        "radio": 0.85,
        "modal": 0.9,
        "dialog": 0.9,
        "icon": 0.85,
    }
    DEFAULT_SIMILARITY = 0.8
    MIN_SIMILARITY = 0.7
    MAX_SIMILARITY = 0.9

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
                logger.warning("Katalog szablonow SikuliX nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ════════════════════════════════════════════════════════════════
    # Metoda glowna: generate_test_file (AC1, AC4, AC5)
    # ════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj skrypt SikuliX z listy test case'ow.

        Args:
            test_cases: lista slownikow z danymi test case (z modelu TestCase)
            config: opcjonalna konfiguracja nadpisujaca domyslna

        Returns:
            TestCodeFile z wygenerowanym kodem Jython oraz lista patternow.
        """
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        first_tc = test_cases[0]
        feature_name = self._extract_feature_name(first_tc)
        class_name = self._class_name(feature_name)
        class_doc = first_tc.get("title") or feature_name

        operations: list[str] = []
        patterns: list[dict[str, Any]] = []
        for tc in test_cases:
            steps = self._normalize_steps(tc.get("steps"))
            for idx, step in enumerate(steps, start=1):
                operations.append(f"# Krok {idx}: {(step.get('action') or 'brak').strip()}")
                op, pattern = self._map_step_to_operation(step)
                operations.append(op)
                if pattern is not None:
                    patterns.append(pattern)

        context = {
            "class_name": class_name,
            "class_doc": class_doc,
            "operations": operations,
        }

        try:
            template = self.jinja_env.get_template("sikulix_test.jinja2")
            content = template.render(**context)
        except Exception as exc:
            logger.error("Blad renderowania szablonu SikuliX: %s", exc)
            content = self._fallback_render(context)

        name = self._snake_case(feature_name)
        file_path = f"tests/sikuli/{name}/{name}.py"
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=name,
            fixtures=self._dedupe_patterns(patterns),
            test_functions=[{"name": "testFlow", "operations": operations}],
            imports=["from sikuli import *"],
            compilation_result=compilation_result,
        )

    # ── generate_setup — runner pomocniczy ──

    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj skrypt uruchamiajacy SikuliX (Region/Screen setup)."""
        return (
            "from sikuli import *\n\n"
            "# Globalna konfiguracja SikuliX\n"
            f"Settings.MinSimilarity = {self.MIN_SIMILARITY}\n"
            f"Settings.AutoWaitTimeout = {DEFAULT_TIMEOUT}\n"
        )

    # ── generate_assertion ──

    def generate_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        message: str | None = None,
    ) -> str:
        """Generuj pojedyncza asercje SikuliX.

        Args:
            expected: nazwa pliku patternu (np. "success.png")
            actual: ignorowany (SikuliX operuje na obrazie ekranu)
            comparison_type: "exists" (domyslnie) lub "vanish"
            message: opcjonalny komunikat bledu

        Returns:
            Kod asercji jako string.
        """
        pattern = self._pattern_statement(expected, self.DEFAULT_SIMILARITY)
        if comparison_type == "vanish":
            return f"self.s.waitVanish({pattern})"
        msg = self._escape(message) if message else f"Brak elementu {expected}"
        return f'assert exists({pattern}) is not None, "{msg}"'

    # ── validate_syntax — walidacja strukturalna ──

    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie skryptu SikuliX (walidacja strukturalna).

        Jython nie jest kompilowany w tym srodowisku — sprawdzamy
        import sikuli, obecnosc klasy oraz metody testFlow.
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

        if "from sikuli import" not in code:
            errors.append("Brak importu 'from sikuli import *'")
        if not re.search(r"\bclass\s+\w+", code):
            errors.append("Brak definicji klasy testowej")
        if not re.search(r"def\s+testFlow\s*\(", code):
            warnings.append("Brak metody testFlow() — skrypt nie zawiera krokow")
        if code.count("(") != code.count(")"):
            errors.append("Niezbalansowane nawiasy okragle")

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
    # AC3: Konfiguracja similarity
    # ════════════════════════════════════════════════════════════════

    def _calculate_similarity(self, component: dict[str, Any] | None) -> float:
        """Oblicz threshold similarity dla komponentu (zakres 0.7-0.9, AC3)."""
        if not component:
            return self.DEFAULT_SIMILARITY
        ctype = (component.get("component_type") or component.get("type") or "").strip().lower()
        similarity = self.SIMILARITY_MAP.get(ctype, self.DEFAULT_SIMILARITY)

        # Niska pewnosc OCR -> podnosimy prog dopasowania (mniej falszywych trafien).
        confidence = component.get("confidence")
        if isinstance(confidence, int | float) and confidence < 0.5:
            similarity += 0.05

        return round(max(self.MIN_SIMILARITY, min(self.MAX_SIMILARITY, similarity)), 2)

    def _pattern_statement(self, image_name: str, similarity: float) -> str:
        """Zbuduj wyrazenie Pattern("img.png").similar(sim) (AC3)."""
        return f'Pattern("images/{image_name}").similar({similarity})'

    # ════════════════════════════════════════════════════════════════
    # AC1, AC4: Mapowanie krokow na operacje SikuliX
    # ════════════════════════════════════════════════════════════════

    def _map_step_to_operation(self, step: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        """Mapuj pojedynczy krok testowy na operacje SikuliX.

        Zwraca krotke (linia_kodu, metadane_patternu | None).
        """
        action = (step.get("action") or "").strip().lower()
        value = step.get("value") or step.get("input_data") or step.get("data") or ""
        component = step.get("component") or {}
        image_name = self._pattern_image_name(component, step)
        similarity = self._calculate_similarity(component)
        pattern_meta: dict[str, Any] | None = {
            "name": image_name,
            "component_type": (component.get("component_type") or component.get("type") or "element"),
            "similarity": similarity,
        }
        pattern = self._pattern_statement(image_name, similarity)

        if action == "click":
            return f"self.s.click({pattern})", pattern_meta
        if action in ("type", "input"):
            return f"self.s.type({pattern}, \"{self._escape(value)}\")", pattern_meta
        if action == "wait":
            timeout = step.get("timeout") or DEFAULT_TIMEOUT
            return f"self.s.wait({pattern}, {timeout})", pattern_meta
        if action in ("assert_exists", "assert_visible"):
            return f"assert exists({pattern}) is not None", pattern_meta
        if action in ("assert_vanish", "vanish"):
            return f"self.s.waitVanish({pattern})", pattern_meta

        # Nieznana akcja — bezpieczny komentarz, bez patternu
        return f"# nieobslugiwana akcja: {action or 'brak'}", None

    # ════════════════════════════════════════════════════════════════
    # AC2: Nazewnictwo patternow (wycinanie bbox realizuje PatternCropper)
    # ════════════════════════════════════════════════════════════════

    def _pattern_image_name(self, component: dict[str, Any], step: dict[str, Any]) -> str:
        """Zbuduj nazwe pliku patternu: {component_type}_{label_sanitized}.png (AC2)."""
        explicit = component.get("pattern_image") or step.get("pattern_image")
        if explicit:
            return str(explicit)
        ctype = (component.get("component_type") or component.get("type") or "element")
        label = (
            component.get("label")
            or component.get("text")
            or step.get("target")
            or step.get("action")
            or "element"
        )
        return f"{self._sanitize(ctype)}_{self._sanitize(label)}.png"

    # ════════════════════════════════════════════════════════════════
    # Metody pomocnicze
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _dedupe_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Usun duplikaty patternow po nazwie pliku."""
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for p in patterns:
            name = p.get("name", "")
            if name and name not in seen:
                seen.add(name)
                result.append(p)
        return result

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
    def _class_name(name: str) -> str:
        """Konwertuj nazwe na PascalCase nazwy klasy Jython."""
        if not name:
            return "TestFlow"
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", name).strip()
        parts = [p.capitalize() for p in cleaned.split()]
        result = "".join(parts) or "TestFlow"
        if result[0].isdigit():
            result = f"Test{result}"
        return result

    @staticmethod
    def _snake_case(name: str) -> str:
        """Konwertuj nazwe na snake_case (struktura katalogow AC5)."""
        if not name:
            return "test_flow"
        result = name.lower()
        result = re.sub(r"[\s-]+", "_", result)
        result = re.sub(r"[^a-z0-9_]", "", result)
        result = re.sub(r"_+", "_", result).strip("_")
        return result or "test_flow"

    @staticmethod
    def _sanitize(value: Any) -> str:
        """Sanityzuj fragment nazwy pliku patternu."""
        text = str(value).lower()
        text = re.sub(r"[\s-]+", "_", text)
        text = re.sub(r"[^a-z0-9_]", "", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "element"

    @staticmethod
    def _escape(value: Any) -> str:
        """Escapuj cudzyslowy do literalu Jython w podwojnych cudzyslowach."""
        return str(value).replace("\\", "\\\\").replace('"', '\\"')

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        """Zwroc pusty skrypt SikuliX."""
        return TestCodeFile(
            content="from sikuli import *\n\n# Brak test case'ow do wygenerowania\n",
            file_path="tests/sikuli/empty/empty.py",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any]) -> str:
        """Fallback renderowanie gdy Jinja2 niedostepny."""
        class_name = context.get("class_name", "TestFlow")
        lines = [
            "from sikuli import *",
            "",
            f"class {class_name}:",
            "    def __init__(self):",
            "        self.s = Screen()",
            "",
            "    def testFlow(self):",
        ]
        operations = context.get("operations") or ["pass"]
        lines.extend(f"        {op}" for op in operations)
        return "\n".join(lines) + "\n"
