"""Unit tests for the database-layer test generator — Story 1.53 (FR70).

Pokrywa §Testy 4-10 (native constraints / FK / CRUD / transaction / migration,
klasyfikacja + db_object) oraz §Test 12 (bezpieczeństwo — brak realnego SQLi,
delegacja do 4.2/4.3). Ścieżka LLM (§Test 9) testowana z heurystyką + mock LLM.
"""

from __future__ import annotations

from app.services.analysis.db_schema_extractor import (
    DatabaseModel,
    DatabaseSchemaExtractor,
    DynamicQuery,
    Table,
)
from app.services.generators.database_generator import (
    CATEGORY_CRUD,
    CATEGORY_FK_CASCADE,
    CATEGORY_FK_INTEGRITY,
    CATEGORY_MIGRATION,
    CATEGORY_NOT_NULL,
    CATEGORY_SECURITY,
    CATEGORY_TRANSACTION,
    CATEGORY_UNIQUE,
    DatabaseTestGenerator,
)


def _sample_model() -> DatabaseModel:
    """Model z FK/CHECK/UNIQUE/NOT NULL + migracja + zapytanie dynamiczne."""
    ext = DatabaseSchemaExtractor()
    return ext.extract(
        sql_sources={
            "schema.sql": (
                "CREATE TABLE organizations (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL);\n"
                "CREATE TABLE users ("
                "id BIGSERIAL PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL UNIQUE, "
                "age INT NOT NULL, "
                "balance DECIMAL(10,2) DEFAULT 0, "
                "org_id INT, "
                "CONSTRAINT chk_age CHECK (age >= 18), "
                "CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
                ");\n"
            )
        },
        migration_sources={"0001_init.sql": "-- up\nCREATE TABLE x (id INT);\n-- down\nDROP TABLE x;\n"},
        dynamic_queries=[
            {
                "snippet": 'execute("SELECT * FROM u WHERE id=" + uid)',
                "location": "app.py:42",
                "reason": "string concat",
            },
        ],
        dialect="postgres",
    )


class TestNativeConstraintTests:
    """§Test 4 — NOT NULL / UNIQUE / CHECK."""

    def test_generates_not_null_violation_cases(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        nn = [c for c in cases if c.category == CATEGORY_NOT_NULL]
        objects = {c.db_object for c in nn}
        assert "users.email" in objects
        assert "users.age" in objects
        for c in nn:
            assert c.expects_error is True
            assert c.error_type == "IntegrityError"

    def test_generates_unique_violation_cases(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        uniq = [c for c in cases if c.category == CATEGORY_UNIQUE]
        assert any("users.email" in c.db_object for c in uniq)
        assert all(c.expects_error for c in uniq)

    def test_generates_check_violation_cases(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        checks = [c for c in cases if c.category == "check"]
        assert len(checks) >= 1
        assert any("age >= 18" in c.description or "age >= 18" in (c.sql_hint or "") for c in checks)
        assert all(c.expects_error for c in checks)


class TestNativeFkTests:
    """§Test 5 — FK integrity (insert dziecka bez rodzica)."""

    def test_fk_integrity_case_inserts_orphan_and_expects_error(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        fk = [c for c in cases if c.category == CATEGORY_FK_INTEGRITY]
        assert len(fk) == 1
        c = fk[0]
        assert c.table == "users"
        assert c.expects_error is True
        assert c.error_type == "IntegrityError"
        # invalid payload ustawia FK-kolumnę na nieistniejącego rodzica
        assert c.invalid_payload is not None
        assert c.invalid_payload.get("org_id") == 999999

    def test_fk_cascade_case_respects_on_delete(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        cascade = [c for c in cases if c.category == CATEGORY_FK_CASCADE]
        assert len(cascade) == 1
        c = cascade[0]
        # ON DELETE CASCADE → nie oczekujemy błędu (kaskada)
        assert c.expects_error is False
        assert c.test_data["on_delete"] == "CASCADE"


class TestNativeCrudAndTransactions:
    """§Test 6 (CRUD) + §Test 7 (transaction rollback)."""

    def test_crud_lifecycle_per_table(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        crud = [c for c in cases if c.category == CATEGORY_CRUD]
        tables = {c.table for c in crud}
        assert {"users", "organizations"} <= tables

    def test_transaction_rollback_case(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        tx = [c for c in cases if c.category == CATEGORY_TRANSACTION]
        rollback = [c for c in tx if "rollback" in c.title.lower()]
        assert rollback, "oczekiwano przypadku rollback"
        for c in rollback:
            assert c.table is not None
            assert c.valid_payload is not None


class TestNativeMigrations:
    """§Test 8 — migracja up/down (idempotentność)."""

    def test_migration_up_down_idempotent(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        migs = [c for c in cases if c.category == CATEGORY_MIGRATION]
        assert len(migs) == 1
        c = migs[0]
        assert "0001" in c.db_object
        actions = [s["action"] for s in c.steps]
        assert actions == ["up", "down", "up_again"]


class TestClassification:
    """§Test 10 — klasyfikacja test_type=database + db_object."""

    def test_all_cases_classified_as_database_with_db_object(self):
        cases = DatabaseTestGenerator().generate(_sample_model())
        assert len(cases) > 0
        for c in cases:
            d = c.to_dict()
            assert d["test_type"] == "database"
            assert d["metadata"]["db_object"] == c.db_object
            assert "database" in d["tags"]
            assert c.category in d["tags"]

    def test_security_delegation_case_has_no_executable_payload(self):
        """§Test 12 — NIE generuje realnego SQLi; deleguje do 4.2/4.3."""
        cases = DatabaseTestGenerator().generate(_sample_model())
        sec = [c for c in cases if c.category == CATEGORY_SECURITY]
        assert len(sec) == 1
        c = sec[0]
        assert c.expects_error is False  # to nie test wykonawczy
        assert c.security_ref == "security_scan/sqli (4.2/4.3)"
        # brak payloadu wykonującego wstrzyknięcie
        assert c.invalid_payload is None
        assert "SQL injection" in c.description or "SQLi" in c.description


class TestLlmInvariants:
    """§Test 9 — LLM: invariants (reguła biznesowa, np. balance >= 0)."""

    def test_invariants_generated_via_heuristic_fallback(self):
        # engine_mode=llm ale bez klienta → heurystyka deterministyczna
        cases = DatabaseTestGenerator(llm_client=None).generate(_sample_model(), engine_mode="llm")
        inv = [c for c in cases if c.category == "invariant"]
        rules = {c.invariant for c in inv}
        assert any("balance" in r and ">=" in r for r in rules), rules

    def test_invariants_augmented_by_llm_client(self):
        def fake_llm(prompt: str) -> str:
            return "INV: orders.total >= 0\nINV: users.email is unique (logic)\nirrelevant line"

        cases = DatabaseTestGenerator(llm_client=fake_llm).generate(_sample_model(), engine_mode="hybrid")
        inv = [c for c in cases if c.category == "invariant" and c.engine == "llm"]
        llm_rules = {c.invariant for c in inv}
        assert "orders.total >= 0" in llm_rules
        assert "users.email is unique (logic)" in llm_rules

    def test_native_mode_skips_llm_invariants(self):
        cases = DatabaseTestGenerator(llm_client=lambda p: "INV: should_not_appear").generate(
            _sample_model(), engine_mode="native"
        )
        assert not any(c.category == "invariant" for c in cases)


class TestEmptyModel:
    def test_empty_model_yields_no_cases(self):
        cases = DatabaseTestGenerator().generate(DatabaseModel())
        assert cases == []

    def test_security_delegation_from_dynamic_query_object(self):
        model = DatabaseModel(
            tables=[Table(name="t")],
            dynamic_queries=[DynamicQuery(snippet="db.raw('x')", location="svc.go:9", reason="raw execute")],
        )
        cases = DatabaseTestGenerator().generate(model)
        sec = [c for c in cases if c.category == CATEGORY_SECURITY]
        assert len(sec) == 1
        assert sec[0].test_data["location"] == "svc.go:9"
