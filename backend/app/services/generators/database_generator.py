"""Database-layer test case generator — Story 1.53 (FR70), dual-path (1.11).

Generuje specyfikacje przypadków testowych warstwy danych (``test_type =
database``) z :class:`DatabaseModel` (patrz ``db_schema_extractor.py``):

- **NATIVE** (deterministyczne): ograniczenia schematu (NOT NULL / UNIQUE /
  CHECK), spójność referencyjna (FK integrity / cascade), cykl CRUD,
  transakcje (rollback / commit / savepoint), migracje (up/down idempotentność).
- **LLM** (semantyczne): reguły biznesowe / invariants wywnioskowane z modelu
  (np. ``saldo >= 0``, format e-mail, status jako enum).

Specyfikacje (``DBTestSpec`` → ``dict``) są kompatybilne z wejściem codegen'a
(:class:`DatabaseCodeGenerator`) oraz z modelem ``TestCase`` (``type=database``,
metadane ``db_object``).

**Bezpieczeństwo (AC12)**: zapytania dynamiczne z ``data_flow`` (Story 1.23)
NIE są wykonywane jako testy — generator tworzy jedynie dokumentacyjny
przypadek ``security_delegation`` odsyłający do modułu SQLi (Stories 4.2/4.3).
Nigdy nie generujemy realnego SQL injection.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from app.models.test_case import TestType

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.services.analysis.db_schema_extractor import (
        Column,
        DatabaseModel,
        Migration,
        Table,
    )

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════
# Kategorie testów warstwy danych
# ════════════════════════════════════════════════════════════════════════

CATEGORY_NOT_NULL = "not_null"
CATEGORY_UNIQUE = "unique"
CATEGORY_CHECK = "check"
CATEGORY_FK_INTEGRITY = "fk_integrity"
CATEGORY_FK_CASCADE = "fk_cascade"
CATEGORY_CRUD = "crud"
CATEGORY_TRANSACTION = "transaction_rollback"
CATEGORY_MIGRATION = "migration_up_down"
CATEGORY_INVARIANT = "invariant"
CATEGORY_SECURITY = "security_delegation"

#: Kategoria → czy test oczekuje błędu integralności (IntegrityError)
ERROR_CATEGORIES = {
    CATEGORY_NOT_NULL,
    CATEGORY_UNIQUE,
    CATEGORY_CHECK,
    CATEGORY_FK_INTEGRITY,
}


class LLMClient(Protocol):
    """Minimalny kontrakt klienta LLM (callable) dla ścieżki semantycznej."""

    def __call__(self, prompt: str) -> str: ...


# ════════════════════════════════════════════════════════════════════════
# Specyfikacja testu warstwy danych
# ════════════════════════════════════════════════════════════════════════


@dataclass
class DBTestSpec:
    """Specyfikacja pojedynczego przypadku testowego warstwy danych.

    ``to_dict()`` produkuje kształt kompatybilny z wejściem
    :class:`~app.services.test_generation.codegen.database_generator.DatabaseCodeGenerator`
    oraz serializowalny do ``TestCase`` (``type=database``).
    """

    title: str
    description: str
    category: str
    db_object: str  # np. "users.email", "orders.fk_user", "migration:0001"
    table: str | None = None
    expected_result: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    test_data: dict[str, Any] | None = None
    engine: str = "native"  # native | llm
    expects_error: bool = False
    error_type: str | None = None  # np. "IntegrityError"
    invalid_payload: dict[str, Any] | None = None
    valid_payload: dict[str, Any] | None = None
    sql_hint: str | None = None
    invariant: str | None = None  # dla kategorii invariant (reguła biznesowa)
    security_ref: str | None = None  # dla security_delegation (link do 4.2/4.3)

    @property
    def test_type(self) -> str:
        return TestType.DATABASE.value

    def to_dict(self) -> dict[str, Any]:
        d = {
            "title": self.title,
            "name": _snake(self.title),
            "description": self.description,
            "type": self.test_type,
            "test_type": self.test_type,
            "category": self.category,
            "db_object": self.db_object,
            "table": self.table,
            "model_class": _pascal(self.table) if self.table else None,
            "expected_result": self.expected_result,
            "steps": self.steps,
            "test_data": self.test_data,
            "engine": self.engine,
            "generation_engine": self.engine,
            "expects_error": self.expects_error,
            "error_type": self.error_type,
            "invalid_payload": self.invalid_payload,
            "valid_payload": self.valid_payload,
            "sql_hint": self.sql_hint,
            "invariant": self.invariant,
            "security_ref": self.security_ref,
            # metadane dla TestCase.meta / UI badge
            "metadata": {
                "db_object": self.db_object,
                "category": self.category,
                "engine": self.engine,
                "table": self.table,
            },
            "tags": ["database", self.category],
        }
        return d


# ════════════════════════════════════════════════════════════════════════
# Generator (dual-path)
# ════════════════════════════════════════════════════════════════════════


class DatabaseTestGenerator:
    """Generuje przypadki testowe warstwy danych (FR70). Dual-path (1.11).

    Args:
        llm_client: opcjonalny klient LLM (callable) dla kategorii
            semantycznych (invariants). Gdy brak, invariants są wnioskowane
            heurystycznie z modelu (deterministycznie, testowalnie).
    """

    def __init__(self, llm_client: Callable[[str], str] | None = None):
        self.llm_client = llm_client

    # ── Główny entry point ──

    def generate(self, db_model: DatabaseModel, engine_mode: str = "native") -> list[DBTestSpec]:
        """Wygeneruj wszystkie przypadki testowe DB dla danego modelu.

        Args:
            db_model: model warstwy danych (z ``DatabaseSchemaExtractor``).
            engine_mode: ``native`` | ``llm`` | ``hybrid`` (zgodnie z 1.11).
        """
        cases: list[DBTestSpec] = []

        for table in db_model.tables:
            cases.extend(self._native_not_null(table))
            cases.extend(self._native_unique(table))
            cases.extend(self._native_check(table))
            cases.extend(self._native_fk_integrity(table, db_model))
            cases.extend(self._native_crud(table))
            cases.extend(self._native_transaction(table))

        for mig in db_model.migrations:
            cases.extend(self._native_migration(mig))

        # Bezpieczeństwo (AC12): zapytania dynamiczne → delegacja, NIE test wykonawczy
        for q in db_model.dynamic_queries:
            cases.append(self._security_delegation(q.snippet, q.location, q.reason))

        if engine_mode in ("llm", "hybrid"):
            cases.extend(self._llm_invariants(db_model))

        return cases

    # ════════════════════════════════════════════════════════════════════════
    # NATIVE — ograniczenia schematu
    # ════════════════════════════════════════════════════════════════════════

    def _native_not_null(self, table: Table) -> list[DBTestSpec]:
        out: list[DBTestSpec] = []
        for col in table.columns:
            if not col.nullable and not col.primary_key:
                invalid = _payload_for(table, overrides={col.name: None})
                out.append(
                    DBTestSpec(
                        title=f"{table.name}.{col.name} odrzuca NULL (NOT NULL)",
                        description=(
                            f"Wstawienie wiersza z NULL w kolumnie NOT NULL "
                            f"„{table.name}.{col.name}” musi zostać odrzucone."
                        ),
                        category=CATEGORY_NOT_NULL,
                        db_object=f"{table.name}.{col.name}",
                        table=table.name,
                        expected_result="Wstawienie kończy się IntegrityError (NOT NULL).",
                        expects_error=True,
                        error_type="IntegrityError",
                        invalid_payload=invalid,
                        valid_payload=_payload_for(table),
                        sql_hint=f"INSERT INTO {table.name} ({col.name}) VALUES (NULL);  -- oczekiwany błąd",
                        steps=[
                            {"action": "insert", "code": f"db_session.add(model(**{invalid}))"},
                            {"action": "flush", "code": "db_session.flush()"},
                            {"action": "assert_error", "code": "# oczekiwany IntegrityError"},
                        ],
                    )
                )
        return out

    def _native_unique(self, table: Table) -> list[DBTestSpec]:
        out: list[DBTestSpec] = []
        seen_unique: set[str] = set()
        for col in table.columns:
            if col.unique and col.name not in seen_unique:
                seen_unique.add(col.name)
                base = _payload_for(table, overrides={col.name: '"dup-value"'})
                out.append(
                    DBTestSpec(
                        title=f"{table.name}.{col.name} odrzuca duplikat (UNIQUE)",
                        description=(
                            f"Wstawienie dwóch wierszy z tą samą wartością w kolumnie "
                            f"UNIQUE „{table.name}.{col.name}” musi zostać odrzucone."
                        ),
                        category=CATEGORY_UNIQUE,
                        db_object=f"{table.name}.{col.name}",
                        table=table.name,
                        expected_result="Drugie wstawienie kończy się IntegrityError (UNIQUE).",
                        expects_error=True,
                        error_type="IntegrityError",
                        invalid_payload=base,
                        valid_payload=_payload_for(table),
                        sql_hint=f"INSERT INTO {table.name} ({col.name}) VALUES ('dup');  -- x2 → błąd",
                        steps=[
                            {"action": "insert_first", "code": f"db_session.add(model(**{base}))"},
                            {"action": "insert_dup", "code": f"db_session.add(model(**{base}))  # duplikat"},
                            {"action": "flush", "code": "db_session.flush()"},
                            {"action": "assert_error", "code": "# oczekiwany IntegrityError"},
                        ],
                    )
                )
        # composite UNIQUE
        for group in table.uniques:
            key = ",".join(group)
            if key in seen_unique:
                continue
            seen_unique.add(key)
            out.append(
                DBTestSpec(
                    title=f"{table.name} odrzuca duplikat grupy ({key}) (UNIQUE)",
                    description=f"Naruszenie złożonego ograniczenia UNIQUE ({key}) w „{table.name}”.",
                    category=CATEGORY_UNIQUE,
                    db_object=f"{table.name}.({key})",
                    table=table.name,
                    expected_result="Powtórzone wstawienie grupy kończy się IntegrityError (UNIQUE).",
                    expects_error=True,
                    error_type="IntegrityError",
                    sql_hint=f"UNIQUE ({key}) na {table.name}",
                )
            )
        return out

    def _native_check(self, table: Table) -> list[DBTestSpec]:
        out: list[DBTestSpec] = []
        checks = list(table.checks)
        for col in table.columns:
            checks.extend(col.checks)
        seen: set[str] = set()
        for expr in checks:
            if expr in seen:
                continue
            seen.add(expr)
            out.append(
                DBTestSpec(
                    title=f"{table.name}: naruszenie CHECK ({expr})",
                    description=(
                        f"Wstawienie wiersza naruszającego wyrażenie CHECK "
                        f"„{expr}” w tabeli „{table.name}” musi zostać odrzucone."
                    ),
                    category=CATEGORY_CHECK,
                    db_object=f"{table.name}.check:{_slug(expr)}",
                    table=table.name,
                    expected_result="Wstawienie kończy się IntegrityError (CHECK).",
                    expects_error=True,
                    error_type="IntegrityError",
                    sql_hint=f"-- CHECK ({expr}) na {table.name}",
                )
            )
        return out

    # ════════════════════════════════════════════════════════════════════════
    # NATIVE — spójność referencyjna (FK)
    # ════════════════════════════════════════════════════════════════════════

    def _native_fk_integrity(self, table: Table, model: DatabaseModel) -> list[DBTestSpec]:
        out: list[DBTestSpec] = []
        for fk in table.foreign_keys:
            obj = f"{table.name}.fk:{fk.ref_table}"
            ref_exists = model.table(fk.ref_table) is not None
            invalid = _payload_for(table, overrides={c: 999999 for c in fk.columns})
            # AC: insert dziecka bez rodzica → błąd
            out.append(
                DBTestSpec(
                    title=f"{table.name}: insert dziecka bez rodzica ({fk.label()})",
                    description=(
                        f"Wstawienie wiersza w „{table.name}” ze wskazaniem nieistniejącego "
                        f"rodzica „{fk.ref_table}” musi zostać odrzucone (FK)."
                    ),
                    category=CATEGORY_FK_INTEGRITY,
                    db_object=obj,
                    table=table.name,
                    expected_result="Wstawienie kończy się IntegrityError (FK).",
                    expects_error=True,
                    error_type="IntegrityError",
                    invalid_payload=invalid,
                    valid_payload=_payload_for(table),
                    sql_hint=(
                        f"INSERT INTO {table.name} ({','.join(fk.columns)}) "
                        f"VALUES ({','.join('999999' for _ in fk.columns)});  -- brak rodzica → błąd"
                    ),
                    steps=[
                        {"action": "insert_orphan", "code": f"db_session.add(model(**{invalid}))  # brak rodzica"},
                        {"action": "flush", "code": "db_session.flush()"},
                        {"action": "assert_error", "code": "# oczekiwany IntegrityError"},
                    ],
                )
            )
            # AC: delete rodzica z dependents → cascade/restrict wg definicji
            action = (fk.on_delete or "NO ACTION").upper()
            cascade = action in ("CASCADE", "SET NULL", "SET DEFAULT")
            out.append(
                DBTestSpec(
                    title=f"{table.name}: usunięcie rodzica {fk.ref_table} (ON DELETE {action})",
                    description=(
                        f"Usunięcie rodzica „{fk.ref_table}” posiadającego zależne wiersze w "
                        f"„{table.name}” musi zachować się zgodnie z ON DELETE {action}."
                    ),
                    category=CATEGORY_FK_CASCADE,
                    db_object=obj,
                    table=table.name,
                    expected_result=(
                        f"Zależne wiersze {'kaskadowo usunięte/zaktualizowane' if cascade else 'usunięcie rodzica odrzucone (RESTRICT/NO ACTION)'}."
                    ),
                    expects_error=not cascade,
                    error_type=None if cascade else "IntegrityError",
                    test_data={"on_delete": action, "ref_table": fk.ref_table},
                )
            )
            if not ref_exists:
                logger.debug("FK referencjonuje tabelę spoza modelu: %s", fk.ref_table)
        return out

    # ════════════════════════════════════════════════════════════════════════
    # NATIVE — CRUD
    # ════════════════════════════════════════════════════════════════════════

    def _native_crud(self, table: Table) -> list[DBTestSpec]:
        if not table.pk_columns() and not [c for c in table.columns if c.primary_key]:
            return []
        valid = _payload_for(table)
        pk = table.primary_key or [c.name for c in table.columns if c.primary_key] or ["id"]
        pk_key = pk[0]
        pk_val = valid.get(pk_key, 1)
        select_code = f"assert db_session.query(model).filter_by(**{{{pk_key!r}: {pk_val!r}}}).first() is not None"
        return [
            DBTestSpec(
                title=f"{table.name}: pełny cykl CRUD (insert→select→update→delete)",
                description=(
                    f"Weryfikuje cykl życia rekordu w „{table.name}”: wstawienie, odczyt, "
                    f"aktualizacja, usunięcie — z asercją stanu po każdym kroku."
                ),
                category=CATEGORY_CRUD,
                db_object=f"{table.name}.crud",
                table=table.name,
                expected_result="Rekord poprawnie wstawiony, odczytany, zaktualizowany i usunięty.",
                valid_payload=valid,
                test_data={"pk": pk},
                sql_hint=f"-- INSERT/SELECT/UPDATE/DELETE na {table.name}",
                steps=[
                    {"action": "insert", "code": f"db_session.add(model(**{valid}))"},
                    {"action": "commit", "code": "db_session.commit()"},
                    {"action": "select", "code": select_code},
                    {"action": "update", "code": "obj.field = 'updated'"},
                    {"action": "delete", "code": "db_session.delete(obj)"},
                ],
            )
        ]

    # ════════════════════════════════════════════════════════════════════════
    # NATIVE — transakcje
    # ════════════════════════════════════════════════════════════════════════

    def _native_transaction(self, table: Table) -> list[DBTestSpec]:
        valid = _payload_for(table)
        return [
            DBTestSpec(
                title=f"{table.name}: rollback cofa niezatwierdzone zmiany",
                description=(
                    "Po wstawieniu wiersza i wywołaniu rollback() rekord nie powinien "
                    f"być widoczny w „{table.name}” — izolacja transakcji."
                ),
                category=CATEGORY_TRANSACTION,
                db_object=f"{table.name}.transaction",
                table=table.name,
                expected_result="Po rollback() wstawiony rekord nie istnieje w bazie.",
                valid_payload=valid,
                sql_hint="-- BEGIN; INSERT ...; ROLLBACK; SELECT → 0 wierszy",
                steps=[
                    {"action": "insert", "code": f"db_session.add(model(**{valid}))"},
                    {"action": "rollback", "code": "db_session.rollback()"},
                    {"action": "assert_absent", "code": "# rekord nie powinien istnieć"},
                ],
            ),
            DBTestSpec(
                title=f"{table.name}: commit utrwala zmiany",
                description="Po wstawieniu i commit() rekord jest trwale zapisany.",
                category=CATEGORY_TRANSACTION,
                db_object=f"{table.name}.commit",
                table=table.name,
                expected_result="Po commit() rekord jest widoczny w nowej sesji.",
                valid_payload=valid,
            ),
        ]

    # ════════════════════════════════════════════════════════════════════════
    # NATIVE — migracje (up/down idempotentność)
    # ════════════════════════════════════════════════════════════════════════

    def _native_migration(self, mig: Migration) -> list[DBTestSpec]:
        return [
            DBTestSpec(
                title=f"Migracja {mig.version}: up tworzy, down cofa (idempotentność)",
                description=(
                    f"Migracja „{mig.version}” powinna być odwracalna: wykonanie up następnie down "
                    "przywraca stan wyjściowy, a powtórne up nie powoduje błędu."
                ),
                category=CATEGORY_MIGRATION,
                db_object=f"migration:{mig.version}",
                table=None,
                expected_result="up→down→up kończy się sukcesem (idempotentność).",
                test_data={"version": mig.version, "source_file": mig.source_file},
                sql_hint=(mig.up_sql[:200] + "…") if len(mig.up_sql) > 200 else mig.up_sql,
                steps=[
                    {"action": "up", "code": f"# apply migration {mig.version} (up)"},
                    {"action": "down", "code": f"# revert migration {mig.version} (down)"},
                    {"action": "up_again", "code": "# re-apply (idempotentność)"},
                ],
            )
        ]

    # ════════════════════════════════════════════════════════════════════════
    # Bezpieczeństwo — delegacja dynamicznych zapytań (AC12)
    # ════════════════════════════════════════════════════════════════════════

    def _security_delegation(self, snippet: str, location: str, reason: str) -> DBTestSpec:
        return DBTestSpec(
            title=f"Zapytanie dynamiczne w {location} — delegowane do modułu SQLi (4.2/4.3)",
            description=(
                f"Wykryto dynamiczne zapytanie SQL („{reason}”) w {location}. "
                "To potencjalna podatność SQL injection — NIE generujemy testu wykonawczego. "
                "Zobacz moduł bezpieczeństwa (Stories 4.2/4.3)."
            ),
            category=CATEGORY_SECURITY,
            db_object=location,
            table=None,
            expected_result="Oflagowane dla modułu bezpieczeństwa; brak testu wykonawczego SQLi.",
            security_ref="security_scan/sqli (4.2/4.3)",
            test_data={"snippet": snippet, "reason": reason, "location": location},
        )

    # ════════════════════════════════════════════════════════════════════════
    # LLM — invariants (reguły biznesowe)
    # ════════════════════════════════════════════════════════════════════════

    def _llm_invariants(self, model: DatabaseModel) -> list[DBTestSpec]:
        """Wnioskuj reguły biznesowe (invariants) — heurystycznie + opcjonalnie LLM."""
        out = self._heuristic_invariants(model)
        if self.llm_client is None:
            return out
        try:
            prompt = _invariant_prompt(model)
            raw = self.llm_client(prompt)
        except Exception as exc:  # pragma: no cover — LLM niedostępny
            logger.warning("LLM invariants niedostępny (%s) — heurystyka only", exc)
            return out
        for inv in _parse_invariants(raw):
            out.append(inv)
        return out

    def _heuristic_invariants(self, model: DatabaseModel) -> list[DBTestSpec]:
        out: list[DBTestSpec] = []
        for table in model.tables:
            for col in table.columns:
                rules = _infer_invariants(col)
                for rule in rules:
                    out.append(
                        DBTestSpec(
                            title=f"{table.name}.{col.name}: invariant „{rule}” (LLM)",
                            description=(
                                f"Wnioskowana reguła biznesowa dla „{table.name}.{col.name}”: {rule}. "
                                "Wygenerowane przez LLM — zweryfikuj poprawność w kontekście domeny."
                            ),
                            category=CATEGORY_INVARIANT,
                            db_object=f"{table.name}.{col.name}",
                            table=table.name,
                            engine="llm",
                            invariant=rule,
                            expected_result=f"Wartość „{col.name}” spełnia regułę: {rule}.",
                        )
                    )
        return out


# ════════════════════════════════════════════════════════════════════════
# Funkcje pomocnicze
# ════════════════════════════════════════════════════════════════════════


def _payload_for(table: Table, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Zbuduj przykładowy payload (valid) dla tabeli; nadpisz wybrane kolumny."""
    payload: dict[str, Any] = {}
    for col in table.columns:
        if col.primary_key:
            continue
        payload[col.name] = _sample_value(col)
    if overrides:
        payload.update(overrides)
    return payload


def _sample_value(col: Column) -> Any:
    t = (col.type or "").upper()
    if col.name.lower() == "email" or "EMAIL" in t:
        return "user@example.com"
    if "BOOL" in t or t == "BOOLEAN":
        return True
    if any(k in t for k in ("INT", "SERIAL", "BIGINT", "NUM", "DEC", "FLOAT", "DOUBLE")):
        if "PRICE" in col.name.upper() or "BALANCE" in col.name.upper() or "AMOUNT" in col.name.upper():
            return 100.00
        return 1
    if "DATE" in t or "TIME" in t:
        return "2026-01-01"
    if "UUID" in t:
        return "550e8400-e29b-41d4-a716-446655440000"
    return "sample"


def _infer_invariants(col: Column) -> list[str]:
    """Heurystycznie wnioskuj reguły biznesowe z nazwy/typu kolumny."""
    rules: list[str] = []
    name = col.name.lower()
    if any(k in name for k in ("balance", "amount", "price", "salary", "total")):
        rules.append(f"{col.name} >= 0")
    if name == "email":
        rules.append(f"{col.name} pasuje do wzorca e-mail")
    if name in ("quantity", "stock", "count"):
        rules.append(f"{col.name} >= 0")
    if name in ("status", "state"):
        rules.append(f"{col.name} należy do dozwolonego zbioru wartości")
    if "percent" in name or name == "discount":
        rules.append(f"0 <= {col.name} <= 100")
    return rules


def _invariant_prompt(model: DatabaseModel) -> str:
    table_desc = "; ".join(
        f"{t.name}({', '.join(f'{c.name}:{c.type}' for c in t.columns[:8])})" for t in model.tables[:10]
    )
    return (
        "Zidentifikuj reguły biznesowe (invariants) warstwy danych, które powinny być "
        "testowane (np. saldo >= 0, status w enumie, unikalność logiczna). "
        "Zwróć po jednej regule w linii, prefiks 'INV: '. Baza: " + table_desc
    )


def _parse_invariants(raw: str) -> list[DBTestSpec]:
    """Sparsuj odpowiedź LLM na listę specyfikacji invariant."""
    out: list[DBTestSpec] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("INV:"):
            continue
        rule = line[4:].strip()
        if rule:
            out.append(
                DBTestSpec(
                    title=f"Invariant (LLM): {rule}",
                    description=f"Reguła biznesowa wnioskowana przez LLM: {rule}.",
                    category=CATEGORY_INVARIANT,
                    db_object="llm_invariant",
                    engine="llm",
                    invariant=rule,
                    expected_result=f"Warunek spełniony: {rule}.",
                )
            )
    return out


def _snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name or "")
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return s.strip("_") or "test"


def _pascal(name: str | None) -> str:
    if not name:
        return "Model"
    parts = re.split(r"[_\s]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Model"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "expr"


def get_database_test_generator(llm_client: Callable[[str], str] | None = None) -> DatabaseTestGenerator:
    """Factory — singletonowy generator DB (wzorzec z repo)."""
    return DatabaseTestGenerator(llm_client=llm_client)
