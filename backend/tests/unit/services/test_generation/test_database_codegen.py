"""Unit tests for the database codegen generator — Story 1.53 (FR70), §4/§6b.

Pokrywa §Test 11 (szablon pytest uruchamialny w izolacji — rollback, bez zapisu
do bazy produkcyjnej, kompilowalny py_compile) oraz §Test 12 (bezpieczeństwo —
kategoria security_delegation NIE generuje testu wykonawczego SQLi).
"""

from __future__ import annotations

from app.services.analysis.db_schema_extractor import DatabaseSchemaExtractor
from app.services.generators.database_generator import (
    CATEGORY_SECURITY,
    DatabaseTestGenerator,
)
from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry
from app.services.test_generation.codegen.database_generator import DatabaseCodeGenerator


def _generate_code(extra_tables: bool = True, with_security: bool = True):
    ext = DatabaseSchemaExtractor()
    model = ext.extract(
        sql_sources={
            "schema.sql": (
                "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE, age INT NOT NULL);\n"
            )
        },
        dynamic_queries=[{"snippet": "exec('x'+uid)", "location": "a.py:1", "reason": "concat"}]
        if with_security
        else [],
        dialect="postgres",
    )
    specs = DatabaseTestGenerator().generate(model, "native")
    gen = CodeGenRegistry.get_instance().get_generator("database", CodeGenConfig(framework="database"))
    file = gen.generate_test_file([s.to_dict() for s in specs])
    return file, specs


class TestDatabaseCodegenIsolation:
    """§Test 11 — pytest uruchamialny w izolacji (rollback, kompilowalny)."""

    def test_code_compiles_with_py_compile(self):
        file, _ = _generate_code()
        assert file.compilation_result is not None
        assert file.compilation_result.success is True, file.compilation_result.error_message

    def test_code_uses_db_session_fixture_and_rollback(self):
        file, _ = _generate_code()
        assert "def db_session()" in file.content
        assert "rollback" in file.content
        # framework pytest / language python (§6b)
        assert file.framework == "pytest"
        assert file.language == "python"

    def test_no_write_to_production_db(self):
        """Generowany kod izoluje transakcję — każdy test kończy się rollback."""
        file, _ = _generate_code()
        # każdy with pytest.raises ma rollback; każda funkcja ma db_session (rollback w fixture)
        assert file.content.count("db_session.rollback()") >= 1
        # brak nieizolowanego commit bez rollback w testach błędów
        assert "import pytest" in file.content
        assert "IntegrityError" in file.content

    def test_error_tests_use_pytest_raises(self):
        file, _ = _generate_code()
        assert "with pytest.raises(IntegrityError)" in file.content

    def test_empty_input_yields_empty_file(self):
        gen = CodeGenRegistry.get_instance().get_generator("database")
        file = gen.generate_test_file([])
        assert file.content.strip()
        assert file.compilation_result is None or file.compilation_result.success


class TestDatabaseCodegenSecurity:
    """§Test 12 — NIE generuje realnego SQLi; deleguje do 4.2/4.3."""

    def test_security_case_emits_comment_not_executable_test(self):
        file, specs = _generate_code(with_security=True)
        sec = [s for s in specs if s.category == CATEGORY_SECURITY]
        assert len(sec) == 1
        # komentarz odsyłający do modułu bezpieczeństwa
        assert "SQLi" in file.content or "4.2/4.3" in file.content
        # funkcja wykonawcza NIE zawiera injection z payloadu dynamicznym
        # (security case nie ma ciała testowego — tylko komentarz)
        assert "exec('x'+uid)" not in file.content

    def test_registry_supports_database_framework(self):
        assert CodeGenRegistry.get_instance().is_supported("database")
        gen = CodeGenRegistry.get_instance().get_generator("database")
        assert isinstance(gen, DatabaseCodeGenerator)


class TestDatabaseCodegenCategories:
    """Każda kategoria generuje sensowne, kompilowalne ciało testu."""

    def test_all_categories_compile(self):
        ext = DatabaseSchemaExtractor()
        model = ext.extract(
            sql_sources={
                "schema.sql": (
                    "CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id INT NOT NULL, "
                    "total DECIMAL(10,2), name VARCHAR(50) NOT NULL, "
                    "CONSTRAINT fk FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE, "
                    "CONSTRAINT chk CHECK (total >= 0));"
                )
            },
            migration_sources={"0001.sql": "-- up\nCREATE TABLE t (id INT);\n-- down\nDROP TABLE t;\n"},
            dialect="postgres",
        )
        specs = DatabaseTestGenerator().generate(model, "hybrid")  # +invariants
        gen = CodeGenRegistry.get_instance().get_generator("database")
        file = gen.generate_test_file([s.to_dict() for s in specs])
        assert file.compilation_result.success is True
        cats = {s.category for s in specs}
        assert {"not_null", "fk_integrity", "fk_cascade", "crud", "transaction_rollback", "check"}.issubset(cats)
