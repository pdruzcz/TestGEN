"""Database-layer pytest code generator — Story 1.53 (FR70), §6b/§4.

Generuje samodzielny, kompilowalny (``py_compile``) kod testowy pytest z
przypadków testowych warstwy danych (``test_type = database``). Zarejestrowany
w ``CodeGenRegistry`` pod kluczem ``"database"`` (mirror generatora Cypress).

Ciała testów oparte na surowym SQL (``sqlalchemy.text``) — niezależne od
konkretnej klasy modelu ORM, więc są uruchamialne w izolacji (testowa baza +
``rollback`` po każdym teście). Izolacja: transakcja rollback — **bez zapisu
do bazy produkcyjnej** (AC §Test 11).

Bezpieczeństwo (AC12): kategoria ``security_delegation`` NIE generuje testu
wykonawczego — jedynie komentarz odsyłający do modułu SQLi (4.2/4.3).
"""

from __future__ import annotations

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

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "generators" / "templates" / "database"

#: Kategorie, które oczekują IntegrityError (generują with pytest.raises).
ERROR_CATEGORIES = {"not_null", "unique", "check", "fk_integrity"}
#: Kategorie niewykonawcze (komentarz / delegacja, bez ciała testu SQL).
NON_EXECUTABLE_CATEGORIES = {"security_delegation"}


@register_generator("database")
class DatabaseCodeGenerator(BaseTestCodeGenerator):
    """Generator kodu testowego warstwy danych (pytest + db_session + rollback)."""

    FRAMEWORK = "pytest"
    LANGUAGE = "python"
    FILE_EXTENSION = ".py"

    def __init__(self, config: CodeGenConfig | None = None):
        super().__init__(config)
        self._jinja_env: Environment | None = None

    @property
    def jinja_env(self) -> Environment:
        if self._jinja_env is None:
            templates_dir = self.config.templates_dir or TEMPLATES_DIR
            if not templates_dir.exists():
                logger.warning("Katalog szablonów DB nie istnieje: %s", templates_dir)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    # ════════════════════════════════════════════════════════════════════════
    # generate_test_file
    # ════════════════════════════════════════════════════════════════════════

    def generate_test_file(
        self,
        test_cases: list[dict[str, Any]],
        config: CodeGenConfig | None = None,
    ) -> TestCodeFile:
        cfg = config or self.config
        if not test_cases:
            return self._empty_test_file(cfg)

        module_name = self._extract_module_name(test_cases[0])
        test_functions: list[dict[str, str]] = []
        security_notes: list[str] = []

        for tc in test_cases:
            category = (tc.get("category") or "").strip()
            if category in NON_EXECUTABLE_CATEGORIES:
                security_notes.append(self._security_note(tc))
                continue
            body = self._build_test_function(tc)
            if body:
                test_functions.append({"name": tc.get("name") or tc.get("title") or "test_db", "body": body})

        context = {
            "module_name": module_name,
            "description": f"Testy warstwy danych — {len(test_functions)} przypadków.",
            "imports": [],
            "needs_db_session": bool(test_functions),
            "test_functions": test_functions,
            "security_notes": security_notes,
        }

        try:
            template = self.jinja_env.get_template("pytest_db.py.j2")
            content = template.render(**context)
        except Exception as exc:  # pragma: no cover — Jinja2 niedostępny
            logger.error("Błąd renderowania szablonu DB: %s", exc)
            content = self._fallback_render(context)

        file_path = f"tests/db/test_{module_name}.py"
        compilation_result = None
        if cfg.validate_compilation:
            compilation_result = self.validate_syntax(content)

        return TestCodeFile(
            content=content,
            file_path=file_path,
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name=module_name,
            test_functions=test_functions,
            imports=["import pytest", "from sqlalchemy import text", "from sqlalchemy.exc import IntegrityError"],
            compilation_result=compilation_result,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Budowa ciał testów (raw SQL — samodzielne, kompilowalne)
    # ════════════════════════════════════════════════════════════════════════

    def _build_test_function(self, tc: dict[str, Any]) -> str | None:
        category = (tc.get("category") or "").strip()
        fn_name = self._normalize_name(tc.get("name") or tc.get("title") or "test_db")
        if not fn_name.startswith("test_"):
            fn_name = f"test_{fn_name}"
        doc = (tc.get("description") or tc.get("title") or "test warstwy danych").replace('"""', "'")
        table = tc.get("table")

        if category in ERROR_CATEGORIES:
            return self._render_error_test(fn_name, doc, table, tc)
        if category == "fk_cascade":
            return self._render_fk_cascade_test(fn_name, doc, table, tc)
        if category == "crud":
            return self._render_crud_test(fn_name, doc, table, tc)
        if category in ("transaction_rollback", "transaction"):
            return self._render_transaction_test(fn_name, doc, table, tc)
        if category == "migration_up_down":
            return self._render_migration_test(fn_name, doc, tc)
        if category == "invariant":
            return self._render_invariant_test(fn_name, doc, table, tc)
        # fallback: dokumentacyjny
        return self._render_doc_test(fn_name, doc, tc)

    def _render_error_test(self, fn_name: str, doc: str, table: str | None, tc: dict[str, Any]) -> str:
        """NOT NULL / UNIQUE / CHECK / FK integrity → oczekiwany IntegrityError."""
        payload = tc.get("invalid_payload") or tc.get("valid_payload") or {}
        sql_hint = tc.get("sql_hint") or ""
        insert = f"# {sql_hint}" if sql_hint else ""
        if table and payload:
            insert = _insert_stmt(table, payload)
        sql_literal = f'    sql = """{insert}"""' if insert else '    sql = ""'
        return (
            f"def {fn_name}(db_session):\n"
            f'    """{doc}"""\n'
            f"{sql_literal}\n"
            f"    with pytest.raises(IntegrityError):\n"
            f"        db_session.execute(text(sql))\n"
            f"        db_session.flush()\n"
            f"    db_session.rollback()\n"
        )

    def _render_fk_cascade_test(self, fn_name: str, doc: str, table: str | None, tc: dict[str, Any]) -> str:
        data = tc.get("test_data") or {}
        action = data.get("on_delete", "NO ACTION")
        ref = data.get("ref_table", "?")
        expects = tc.get("expects_error", False)
        if expects:
            body = (
                "    with pytest.raises(IntegrityError):\n"
                f'        db_session.execute(text("DELETE FROM {ref} WHERE id = 1"))\n'
                "        db_session.flush()\n"
                "    db_session.rollback()\n"
            )
        else:
            body = (
                f'    db_session.execute(text("DELETE FROM {ref} WHERE id = 1"))\n'
                "    db_session.flush()\n"
                f"    # ON DELETE {action} — zależne wiersze w „{table or '?'}” aktualizowane/usunięte\n"
                "    db_session.rollback()\n"
            )
        return f'def {fn_name}(db_session):\n    """{doc}"""\n{body}'

    def _render_crud_test(self, fn_name: str, doc: str, table: str | None, tc: dict[str, Any]) -> str:
        payload = tc.get("valid_payload") or {}
        if not table or not payload:
            return self._render_doc_test(fn_name, doc, tc)
        insert = _insert_stmt(table, payload)
        pk = (tc.get("test_data") or {}).get("pk") or ["id"]
        pk_col = pk[0]
        return (
            f"def {fn_name}(db_session):\n"
            f'    """{doc}"""\n'
            f'    sql = """{insert}"""\n'
            f"    db_session.execute(text(sql))\n"
            f"    db_session.commit()\n"
            f'    row = db_session.execute(text("SELECT * FROM {table} LIMIT 1")).first()\n'
            f"    assert row is not None\n"
            f'    db_session.execute(text("UPDATE {table} SET {pk_col} = {pk_col} WHERE 1=1"))\n'
            f'    db_session.execute(text("DELETE FROM {table}"))\n'
            f"    db_session.commit()\n"
            f'    assert db_session.execute(text("SELECT COUNT(*) FROM {table}")).scalar() == 0\n'
        )

    def _render_transaction_test(self, fn_name: str, doc: str, table: str | None, tc: dict[str, Any]) -> str:
        payload = tc.get("valid_payload") or {}
        is_rollback = "rollback" in (tc.get("title") or "").lower()
        if not table or not payload:
            return self._render_doc_test(fn_name, doc, tc)
        insert = _insert_stmt(table, payload)
        if is_rollback:
            return (
                f"def {fn_name}(db_session):\n"
                f'    """{doc}"""\n'
                f'    sql = """{insert}"""\n'
                f"    db_session.execute(text(sql))\n"
                f"    db_session.rollback()\n"
                f'    assert db_session.execute(text("SELECT COUNT(*) FROM {table}")).scalar() == 0\n'
            )
        return (
            f"def {fn_name}(db_session):\n"
            f'    """{doc}"""\n'
            f'    sql = """{insert}"""\n'
            f"    db_session.execute(text(sql))\n"
            f"    db_session.commit()\n"
            f'    assert db_session.execute(text("SELECT COUNT(*) FROM {table}")).scalar() >= 1\n'
        )

    def _render_migration_test(self, fn_name: str, doc: str, tc: dict[str, Any]) -> str:
        data = tc.get("test_data") or {}
        version = data.get("version", "?")
        src = (tc.get("sql_hint") or "").replace('"""', "'''")
        return (
            f"def {fn_name}(db_session):\n"
            f'    """{doc}"""\n'
            f"    # Migracja {version} — up→down→up (idempotentność).\n"
            f'    up_sql = """{src}"""\n'
            f"    db_session.execute(text(up_sql))\n"
            f"    db_session.rollback()\n"
            f"    # TODO: zweryfikuj down_sql + ponowne up bez błędu\n"
        )

    def _render_invariant_test(self, fn_name: str, doc: str, table: str | None, tc: dict[str, Any]) -> str:
        rule = (tc.get("invariant") or "").replace('"""', "'")
        return (
            f"def {fn_name}(db_session):\n"
            f'    """{doc}"""\n'
            f"    # Invariant (reguła biznesowa, LLM): {rule}\n"
            f"    # TODO: dodaj asercję sprawdzającą regułę na danych testowych\n"
            f"    assert True  # placeholder — zweryfikuj regułę: {rule}\n"
        )

    def _render_doc_test(self, fn_name: str, doc: str, tc: dict[str, Any]) -> str:
        hint = (tc.get("sql_hint") or "").replace('"""', "'")
        return (
            f"def {fn_name}(db_session):\n"
            f'    """{doc}"""\n'
            f"    # {hint}\n"
            f"    # TODO: zaimplementuj asercję warstwy danych\n"
            f"    assert True  # dokumentacyjny\n"
        )

    def _security_note(self, tc: dict[str, Any]) -> str:
        ref = tc.get("security_ref") or "security_scan/sqli (4.2/4.3)"
        loc = tc.get("db_object") or ""
        return f"Zapytanie dynamiczne w {loc} → potencjalne SQLi; zobacz moduł {ref}."

    # ════════════════════════════════════════════════════════════════════════
    # BaseTestCodeGenerator — pozostałe metody abstrakcyjne
    # ════════════════════════════════════════════════════════════════════════

    def generate_setup(self, project_context: dict[str, Any] | None = None) -> str:
        """conftest.py z fixture db_session (rollback)."""
        return (
            "# conftest.py — fixture sesji testowej (izolacja rollback).\n"
            "import pytest\n"
            "from sqlalchemy import create_engine\n"
            "from sqlalchemy.orm import sessionmaker\n\n\n"
            "@pytest.fixture\n"
            "def db_session():\n"
            "    engine = create_engine('sqlite:///:memory:')  # TODO: testowa baza projektu\n"
            "    Session = sessionmaker(bind=engine)\n"
            "    session = Session()\n"
            "    try:\n"
            "        yield session\n"
            "    finally:\n"
            "        session.rollback()\n"
            "        session.close()\n"
        )

    def generate_assertion(self, expected: str, actual: str, comparison_type: str, message: str | None = None) -> str:
        return f"assert {actual} == {expected}  # {comparison_type}"

    def validate_syntax(self, code: str) -> CompilationResult:
        if not code.strip():
            return CompilationResult(success=False, code=code, error_message="Pusty kod", framework=self.FRAMEWORK)
        warnings: list[str] = []
        if "import pytest" not in code:
            warnings.append("Brak 'import pytest'")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
                tmp_path = f.name
                f.write(code)
            py_compile.compile(tmp_path, doraise=True)
            return CompilationResult(
                success=True, code=code, file_path=tmp_path, framework=self.FRAMEWORK, warnings=warnings
            )
        except py_compile.PyCompileError as exc:
            return CompilationResult(
                success=False,
                code=code,
                file_path=tmp_path,
                error_message=str(exc),
                framework=self.FRAMEWORK,
                warnings=warnings,
            )
        finally:
            if tmp_path:
                import contextlib

                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)

    # ════════════════════════════════════════════════════════════════════════
    # Pomocnicze
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_module_name(test_case: dict[str, Any]) -> str:
        table = test_case.get("table")
        if table:
            return _snake(table)
        return "database"

    @staticmethod
    def _normalize_name(name: str) -> str:
        result = re.sub(r"[\s\-]+", "_", name or "")
        result = re.sub(r"[^a-zA-Z0-9_]", "", result).lower()
        result = re.sub(r"_+", "_", result).strip("_")
        return result[:60] or "test_db"

    def _empty_test_file(self, config: CodeGenConfig) -> TestCodeFile:
        return TestCodeFile(
            content="# Brak przypadków testowych warstwy danych.\n",
            file_path="tests/db/test_empty.py",
            framework=self.FRAMEWORK,
            language=self.LANGUAGE,
            module_name="empty",
        )

    @staticmethod
    def _fallback_render(context: dict[str, Any]) -> str:
        lines = [
            "# -*- coding: utf-8 -*-",
            '"""Wygenerowano przez TestGEN — generator DB."""',
            "",
            "import pytest",
            "from sqlalchemy import text",
            "from sqlalchemy.exc import IntegrityError",
            "",
            "# TODO: szablon niedostępny — reczne generowanie",
        ]
        for fn in context.get("test_functions", []):
            lines.append(fn.get("body", ""))
        return "\n".join(lines) + "\n"


# ════════════════════════════════════════════════════════════════════════
# Pomocnicze modułowe
# ════════════════════════════════════════════════════════════════════════


def _snake(name: str) -> str:
    s = re.sub(r"[\s\-]+", "_", name or "")
    s = re.sub(r"[^a-zA-Z0-9_]", "", s).lower()
    return re.sub(r"_+", "_", s).strip("_") or "database"


def _sql_literal(value: Any) -> str:
    """Literal SQL dla wartości payloadu (NULL / liczba / string)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    safe = str(value).replace("'", "''")
    return f"'{safe}'"


def _insert_stmt(table: str, payload: dict[str, Any]) -> str:
    """Zbuduj INSERT INTO table (cols) VALUES (literals) z payloadu."""
    cols = ", ".join(payload.keys())
    vals = ", ".join(_sql_literal(v) for v in payload.values())
    return f"INSERT INTO {table} ({cols}) VALUES ({vals});"
