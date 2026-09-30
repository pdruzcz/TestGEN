"""Base infrastructure for test code generators — Story 1.35 + 1.36.

Dostarcza:
- BaseTestCodeGenerator: ABC dla framework-specific generatorow
- CodeGenRegistry: rejestr generatorow (singleton, jak ASTParserRegistry)
- TestCodeFile: wynik generowania (dataclass)
- CodeGenConfig: konfiguracja generowania (dataclass)
- CompilationResult: wynik walidacji kompilacji (dataclass)
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeGenFramework(StrEnum):
    """Obslugiwane frameworki generowania kodu testowego.

    Story 1.56: wartosci enumu sa 1:1 z kluczami ``CodeGenRegistry``
    (patrz tests/.../test_registry_alignment.py) — historicznie enum mial
    7 nazw przy 12 zarejestrowanych generatorach.
    """

    PYTEST = "pytest"
    JUNIT = "junit"
    NUNIT = "nunit"
    MOCHA_JEST = "mocha_jest"
    CYPRESS = "cypress"
    SIKULIX = "sikulix"
    DATABASE = "database"
    PHPUNIT = "phpunit"
    PEST = "pest"
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"
    APPIUM = "appium"
    UNITTEST = "unittest"  # Story 1.57 — natywne frameworki jednostkowe
    TESTNG = "testng"  # Story 1.57
    MSTEST = "mstest"  # Story 1.57


@dataclass
class CompilationResult:
    """Wynik walidacji kompilacji wygenerowanego kodu."""

    success: bool
    code: str
    file_path: str | None = None
    error_message: str | None = None
    error_line: int | None = None
    error_column: int | None = None
    framework: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class TestCodeFile:
    """Wygenerowany plik kodu testowego."""

    __test__ = False
    """Wygenerowany plik kodu testowego."""
    content: str
    file_path: str
    framework: str
    language: str
    module_name: str
    fixtures: list[dict[str, Any]] = field(default_factory=list)
    test_functions: list[dict[str, Any]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    compilation_result: CompilationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "file_path": self.file_path,
            "framework": self.framework,
            "language": self.language,
            "module_name": self.module_name,
            "num_fixtures": len(self.fixtures),
            "num_test_functions": len(self.test_functions),
            "compilation_success": (self.compilation_result.success if self.compilation_result else None),
        }


@dataclass
class CodeGenConfig:
    """Konfiguracja generowania kodu testowego."""

    framework: str = "pytest"
    language: str = "python"
    file_extension: str = ".py"
    templates_dir: Path | None = None
    validate_compilation: bool = True
    include_mocks: bool = True
    include_parametrize: bool = True
    max_function_name_length: int = 60
    project_context: dict[str, Any] | None = None


class BaseTestCodeGenerator(ABC):
    """Bazowa klasa dla generatorow kodu testowego.

    Kazdy framework-specific generator dziedziczy po tej klasie
    i implementuje wymagane metody abstrakcyjne.
    """

    FRAMEWORK: str = ""
    LANGUAGE: str = ""
    FILE_EXTENSION: str = ""

    def __init__(self, config: CodeGenConfig | None = None):
        self.config = config or CodeGenConfig()

    @abstractmethod
    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        """Generuj plik testowy z listy test case'ow."""
        ...

    @abstractmethod
    def generate_setup(
        self,
        project_context: dict[str, Any] | None = None,
    ) -> str:
        """Generuj plik setup (np. conftest.py)."""
        ...

    @abstractmethod
    def generate_assertion(
        self,
        expected: str,
        actual: str,
        comparison_type: str,
        message: str | None = None,
    ) -> str:
        """Generuj pojedyncza asercje."""
        ...

    @abstractmethod
    def validate_syntax(self, code: str) -> CompilationResult:
        """Zwaliduj skladnie wygenerowanego kodu."""
        ...


class CodeGenRegistry:
    """Rejestr generatorow kodu testowego (singleton).

    Wzorowany na ASTParserRegistry — thread-safe singleton
    z metodami register/get/is_supported.
    """

    _instance: "CodeGenRegistry | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._generators: dict[str, type[BaseTestCodeGenerator]] = {}

    @classmethod
    def get_instance(cls) -> "CodeGenRegistry":
        """Pobierz singleton instancje rejestru."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, framework: str, generator_class: type[BaseTestCodeGenerator]) -> None:
        """Zarejestruj generator dla danego frameworka."""
        self._generators[framework] = generator_class
        logger.info("Zarejestrowano generator kodu: %s -> %s", framework, generator_class.__name__)

    def get_generator(self, framework: str, config: CodeGenConfig | None = None) -> BaseTestCodeGenerator:
        """Pobierz instancje generatora dla frameworka."""
        if framework not in self._generators:
            raise KeyError(
                f"Brak generatora kodu dla frameworka '{framework}'. Dostepne: {list(self._generators.keys())}"
            )
        return self._generators[framework](config=config)

    def is_supported(self, framework: str) -> bool:
        """Sprawdz czy framework jest obslugiwany."""
        return framework in self._generators

    def supported_frameworks(self) -> list[str]:
        """Lista obslugiwanych frameworkow."""
        return list(self._generators.keys())


def register_generator(framework: str):
    """Dekorator rejestrujacy generator w CodeGenRegistry.

    Uzycie:
        @register_generator("pytest")
        class PytestCodeGenerator(BaseTestCodeGenerator):
            ...
    """

    def decorator(cls: type[BaseTestCodeGenerator]) -> type[BaseTestCodeGenerator]:
        CodeGenRegistry.get_instance().register(framework, cls)
        return cls

    return decorator
