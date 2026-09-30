"""Zgodność enum CodeGenFramework z kluczami rejestru — Story 1.56.

Enum w ``codegen/base.py`` historycznie miał 7 nazw przy 12 zarejestrowanych
kluczach generatorów. Story 1.56 ujednolica enum z rejestrem — ten test
pilnuje, żeby nowy generator zarejestrowany bez wpisu w enum (lub odwrotnie)
zawalił suite z jawnym diffem.
"""

import app.services.test_generation.codegen  # noqa: F401 — import rejestruje generatory
from app.services.test_generation.codegen import CodeGenFramework, CodeGenRegistry


def test_enum_values_match_registered_keys():
    registry = CodeGenRegistry.get_instance()
    enum_values = {member.value for member in CodeGenFramework}
    registered = set(registry.supported_frameworks())

    assert enum_values == registered, (
        f"CodeGenFramework nie pokrywa rejestru: tylko w enumie={sorted(enum_values - registered)}, "
        f"tylko w rejestrze={sorted(registered - enum_values)}"
    )


def test_enum_resolves_every_registered_framework():
    registry = CodeGenRegistry.get_instance()
    for framework in registry.supported_frameworks():
        assert CodeGenFramework(framework) is not None
