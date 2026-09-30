from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.analysis.ast.base_parser import BaseASTParser

logger = logging.getLogger(__name__)

_decorated_parsers: list[tuple[str, type]] = []


class UnsupportedLanguageError(Exception):
    def __init__(self, language: str, supported: list[str] | None = None):
        self.language = language
        self.supported = supported or []
        supported_list = ", ".join(self.supported) if self.supported else "none"
        super().__init__(f"No AST parser registered for language '{language}'. Supported languages: {supported_list}")


class ASTParserRegistry:
    _instance: ASTParserRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._parsers: dict[str, type[BaseASTParser]] = {}

    @classmethod
    def get_instance(cls) -> ASTParserRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    for lang, parser_cls in _decorated_parsers:
                        cls._instance.register(lang, parser_cls)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def register(self, language: str, parser_class: type[BaseASTParser]) -> None:
        language_key = language.lower().strip()
        self._parsers[language_key] = parser_class
        logger.info(f"Registered AST parser for language: {language_key}")

    def get_parser(self, language: str) -> BaseASTParser:
        language_key = language.lower().strip()
        parser_class = self._parsers.get(language_key)
        if parser_class is None:
            raise UnsupportedLanguageError(
                language=language_key,
                supported=list(self._parsers.keys()),
            )
        return parser_class()

    def is_supported(self, language: str) -> bool:
        return language.lower().strip() in self._parsers

    def supported_languages(self) -> list[str]:
        return sorted(self._parsers.keys())


def register_parser(language: str):
    def decorator(cls: type[BaseASTParser]) -> type[BaseASTParser]:
        _decorated_parsers.append((language, cls))
        ASTParserRegistry.get_instance().register(language, cls)
        return cls

    return decorator
