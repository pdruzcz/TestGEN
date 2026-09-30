import logging

logger = logging.getLogger(__name__)

# Each adapter self-registers via @register_parser when imported.
# Graceful import so missing tree-sitter grammar doesn't crash the app.
_ADAPTERS = [
    ("python_parser", "PythonAdapter"),
    ("java_parser", "JavaAdapter"),
    ("javascript_parser", "JavaScriptAdapter"),
    ("typescript_parser", "TypeScriptAdapter"),
    ("csharp_parser", "CSharpAdapter"),
    ("c_parser", "CAdapter"),
    ("cpp_parser", "CppAdapter"),
    ("php_parser", "PhpAdapter"),  # Story 1.52 (FR12)
]

_LOADED: list[str] = []

for _module_name, _class_name in _ADAPTERS:
    try:
        __import__(f"app.services.analysis.ast.adapters.{_module_name}")
        _LOADED.append(_module_name)
    except ImportError:
        logger.warning("Skipping AST adapter %s: missing tree-sitter grammar", _module_name)

__all__ = ["LOADED_ADAPTERS"]
LOADED_ADAPTERS = _LOADED
