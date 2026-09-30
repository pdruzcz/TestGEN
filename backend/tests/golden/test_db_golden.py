"""Golden + end-to-end tests for the database-layer generator — Story 1.53 (FR70).

§Test 13 (golden): golden schema (FK / CHECK / UNIQUE / NOT NULL + migracja) →
generowane przypadki pokrywają ≥90% ograniczeń i relacji.

§Weryfikacja E2E: ekstrakcja → generacja (native+hybrid) → codegen (pytest,
izolacja rollback, py_compile) → obecność testu FK (insert dziecka bez rodzica)
→ migracja up/down → dynamiczne zapytanie delegowane do bezpieczeństwa (4.2/4.3),
NIE wykonane jako test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.analysis.db_schema_extractor import DatabaseSchemaExtractor
from app.services.generators.database_generator import DatabaseTestGenerator
from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden" / "db"


def _read(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8")


def _golden_model():
    ext = DatabaseSchemaExtractor()
    return ext.extract(
        sql_sources={"schema.sql": _read("schema.sql")},
        orm_sources={"models_sqlalchemy.py": _read("models_sqlalchemy.py")},
        migration_sources={"migration_0001.sql": _read("migration_0001.sql")},
        dynamic_queries=[
            {
                "snippet": 'cursor.execute("SELECT * FROM users WHERE id=" + uid)',
                "location": "app/repo.py:get_user",
                "reason": "string concat",
            },
        ],
        dialect="postgres",
    )


@pytest.mark.golden
class TestDbGoldenCoverage:
    """§Test 13 — pokrycie ograniczeń i relacji ≥ 90%."""

    def test_constraint_coverage_at_least_90_percent(self):
        model = _golden_model()
        cases = DatabaseTestGenerator().generate(model, engine_mode="native")

        # Zbierz wszystkie ograniczenia oczekujące dedykowanego testu.
        expected: set[str] = set()
        for t in model.tables:
            for col in t.columns:
                if not col.nullable and not col.primary_key:
                    expected.add(f"not_null:{t.name}.{col.name}")
                if col.unique:
                    expected.add(f"unique:{t.name}.{col.name}")
            for chk in t.checks:
                expected.add(f"check:{t.name}:{chk}")
            for fk in t.foreign_keys:
                expected.add(f"fk:{t.name}:{fk.ref_table}")

        # Ograniczenia pokryte przez wygenerowane przypadki.
        covered: set[str] = set()
        for c in cases:
            tbl = c.table or ""
            if c.category == "not_null" and c.table:
                covered.add(f"not_null:{c.db_object}")
            elif c.category == "unique" and "." in (c.db_object or ""):
                covered.add(f"unique:{c.db_object}")
            elif c.category == "check":
                covered.add(f"check:{tbl}:{c.invariant or c.sql_hint or c.db_object}")
            elif c.category in ("fk_integrity", "fk_cascade"):
                covered.add(f"fk:{c.table}:{(c.test_data or {}).get('ref_table', '')}")

        # CHECK pokrycie: złagodzone dopasowanie (wyrażenia)
        check_exprs = {(t.name, chk) for t in model.tables for chk in t.checks}
        check_cases = [c for c in cases if c.category == "check"]
        checks_covered = sum(
            1
            for (tn, expr) in check_exprs
            if any(expr in (c.sql_hint or "") or expr in c.description for c in check_cases)
        )

        not_null_total = sum(1 for e in expected if e.startswith("not_null:"))
        unique_total = sum(1 for e in expected if e.startswith("unique:"))
        fk_total = sum(1 for e in expected if e.startswith("fk:"))
        not_null_cov = sum(1 for e in covered if e.startswith("not_null:"))
        unique_cov = sum(1 for e in covered if e.startswith("unique:"))
        fk_cov = sum(1 for e in covered if e.startswith("fk:"))

        total = not_null_total + unique_total + len(check_exprs) + fk_total
        cov = not_null_cov + unique_cov + checks_covered + fk_cov
        ratio = cov / total if total else 1.0
        assert ratio >= 0.9, f"pokrycie ograniczeń {ratio:.0%} < 90% (cov={cov}/{total})"

    def test_all_tables_have_crud_and_transaction_tests(self):
        model = _golden_model()
        cases = DatabaseTestGenerator().generate(model, engine_mode="native")
        tables = {t.name for t in model.tables}
        crud_tables = {c.table for c in cases if c.category == "crud"}
        tx_tables = {c.table for c in cases if c.category == "transaction_rollback"}
        assert tables <= crud_tables, f"brak CRUD dla: {tables - crud_tables}"
        assert tables <= tx_tables, f"brak transakcji dla: {tables - tx_tables}"


@pytest.mark.golden
class TestDbEndToEnd:
    """§Weryfikacja end-to-end (1-7)."""

    def test_extract_generates_compileable_pytest_with_fk_and_migrations(self):
        model = _golden_model()
        assert model.has_data_layer
        assert {t.name for t in model.tables} >= {"organizations", "users", "orders"}

        specs = DatabaseTestGenerator().generate(model, engine_mode="hybrid")
        gen = CodeGenRegistry.get_instance().get_generator("database", CodeGenConfig(framework="database"))
        file = gen.generate_test_file([s.to_dict() for s in specs])

        # E2E 3: wygenerowany kod uruchamia się w izolacji (py_compile green)
        assert file.compilation_result.success is True
        assert "db_session" in file.content and "rollback" in file.content

        # E2E 4: test FK (insert dziecka bez rodzica → IntegrityError)
        fk_integrity = [c for c in specs if c.category == "fk_integrity"]
        assert len(fk_integrity) >= 2  # orders→users, users→organizations
        assert all(c.expects_error for c in fk_integrity)

        # E2E 5: migracja up/down obecna
        migs = [c for c in specs if c.category == "migration_up_down"]
        assert len(migs) == 1 and "audit_log" in (migs[0].sql_hint or "")

        # E2E 6: pokrycie ≥90% (deleguje do TestDbGoldenCoverage)
        # E2E 7: dynamiczne zapytanie SQL → delegowane, nie wykonane jako test
        sec = [c for c in specs if c.category == "security_delegation"]
        assert len(sec) == 1
        assert sec[0].invalid_payload is None
        assert "4.2/4.3" in (sec[0].security_ref or "")
        # kod NIE zawiera realnego SQLi z payloadu
        assert "SELECT * FROM users WHERE id=" not in file.content

    def test_sqlalchemy_orm_extraction_matches_schema(self):
        """§Test 2/13 — model SQLAlchemy ekstrahowany poprawnie."""
        model = _golden_model()
        orgs = model.table("organizations")
        users = model.table("users")
        assert orgs is not None and users is not None
        assert {c.name for c in orgs.columns} >= {"id", "name", "code"}
        # users z ORM (nullable/unique z deklaracji)
        email = next((c for c in users.columns if c.name == "email"), None)
        assert email is not None and email.unique is True

    def test_has_data_layer_autodetect_on_golden(self):
        ext = DatabaseSchemaExtractor()
        assert ext.has_data_layer({"schema.sql": _read("schema.sql")}) is True
        assert ext.has_data_layer({"models_sqlalchemy.py": _read("models_sqlalchemy.py")}) is True
