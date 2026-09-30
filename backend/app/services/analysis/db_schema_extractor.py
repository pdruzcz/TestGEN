"""Database schema extractor — Story 1.53 (FR70).

Identyfikuje warstwę danych projektu i buduje :class:`DatabaseModel` z trzech
źródeł:

1. **Pliki SQL / DDL** (schema, migracje) — parsowane przez ``sqlglot``.
   Rozpoznaje ``CREATE TABLE`` z kolumnami, typami, ograniczeniami kolumnowymi
   (NOT NULL / UNIQUE / PRIMARY KEY / DEFAULT / CHECK) oraz tabelowymi
   (FOREIGN KEY, composite UNIQUE / PRIMARY KEY, CHECK).
2. **Modele ORM** — SQLAlchemy (Python, declarative), Eloquent (PHP/Laravel),
   Doctrine (PHP/Symfony, atrybuty ``#[Column]`` / ``#[ManyToOne]``).
3. **Zapytania dynamiczne** — przekazywane z ``data_flow.py`` (Story 1.23) jako
   dane wejściowe; ekstraktor **nie importuje** data_flow (storybook: „reużywamy
   detekcji, nie modyfikujemy"). Zapytania dynamiczne są oflagowywane dla
   modułu bezpieczeństwa (4.2/4.3) — **NIE** wykonywane jako testy (AC12).

Public API czysto funkcyjne (``parse_ddl`` / ``parse_*_models`` / ``extract``)
— w pełni testowalne bez bazy danych. Asynchroniczny wrapper czytający pliki
projektu ze storage'a jest cienką warstwą wyżej (analogicznie do innych
ekstraktorów w repo, testowanych na poziomie czystych metod).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.models.test_case import TestType  # noqa: F401  (re-export for convenience)

logger = logging.getLogger(__name__)

# ── sqlglot: opcjonalna zależność (deklarowana w pyproject). Defensive import —
#    brak sqlglot nie wywala całego modułu, fallback do regexowego parsera DDL.
try:
    import sqlglot
    from sqlglot import exp as sqlglot_exp

    SQLGLOT_AVAILABLE = True
except ImportError:  # pragma: no cover — zależność deklarowana, ale defensywnie
    sqlglot = None  # type: ignore[assignment]
    sqlglot_exp = None  # type: ignore[assignment]
    SQLGLOT_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════════
# Modele danych (database schema model)
# ════════════════════════════════════════════════════════════════════════


@dataclass
class ForeignKey:
    """Klucz obcy — referencja do innej tabeli."""

    columns: list[str]
    ref_table: str
    ref_columns: list[str]
    on_delete: str | None = None  # CASCADE | RESTRICT | SET NULL | NO ACTION | SET DEFAULT
    on_update: str | None = None
    name: str | None = None

    def label(self) -> str:
        cols = ", ".join(self.columns)
        ref_cols = ", ".join(self.ref_columns) or "?"
        return f"{cols} → {self.ref_table}({ref_cols})"


@dataclass
class Index:
    """Indeks tabeli."""

    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class Column:
    """Kolumna tabeli z ograniczeniami."""

    name: str
    type: str
    nullable: bool = True
    default: str | None = None
    primary_key: bool = False
    unique: bool = False
    checks: list[str] = field(default_factory=list)  # wyrażenia CHECK (column-level)
    raw_constraints: list[str] = field(default_factory=list)  # oryginalne teksty ograniczeń

    @property
    def constraints(self) -> list[str]:
        """Czytelna lista ograniczeń kolumny (dla opisu testu)."""
        result: list[str] = []
        if not self.nullable:
            result.append("NOT NULL")
        if self.primary_key:
            result.append("PRIMARY KEY")
        if self.unique:
            result.append("UNIQUE")
        if self.default is not None:
            result.append(f"DEFAULT {self.default}")
        for chk in self.checks:
            result.append(f"CHECK ({chk})")
        return result


@dataclass
class Table:
    """Tabela bazy danych."""

    name: str
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    uniques: list[list[str]] = field(default_factory=list)  # composite UNIQUE groups
    checks: list[str] = field(default_factory=list)  # table-level CHECK expressions
    schema: str | None = None
    source: str = "sql"  # sql | sqlalchemy | eloquent | doctrine

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)

    def pk_columns(self) -> list[Column]:
        return [c for c in self.columns if c.primary_key or c.name in self.primary_key]


@dataclass
class Migration:
    """Migracja bazy (up/down SQL)."""

    version: str
    up_sql: str
    down_sql: str = ""
    source_file: str = ""


@dataclass
class DynamicQuery:
    """Dynamiczne/złożone zapytanie SQL wykryte w kodzie — delegowane do 4.2/4.3.

    Nie wykonywane jako test — potencjalne SQLi (AC12).
    """

    snippet: str
    location: str  # plik:funkcja
    reason: str = "dynamic SQL"  # string-concat / raw execute / ORM raw


@dataclass
class DatabaseModel:
    """Pełny model warstwy danych projektu."""

    tables: list[Table] = field(default_factory=list)
    migrations: list[Migration] = field(default_factory=list)
    seed_files: list[str] = field(default_factory=list)
    dynamic_queries: list[DynamicQuery] = field(default_factory=list)
    orm: str = "unknown"  # sqlalchemy | eloquent | doctrine | sql | mixed | unknown

    @property
    def has_data_layer(self) -> bool:
        return bool(self.tables or self.migrations or self.dynamic_queries)

    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name == name), None)

    def referenced_tables(self) -> set[str]:
        """Zbiór tabel referencjonowanych przez FK (czyli bezpiecznych rodziców)."""
        return {fk.ref_table for t in self.tables for fk in t.foreign_keys}


# ════════════════════════════════════════════════════════════════════════
# Ekstraktor
# ════════════════════════════════════════════════════════════════════════

# Regexy pomocnicze dla table-level constraints (działają na .sql() fragmentach)
_RE_FK = re.compile(
    r"FOREIGN\s+KEY\s*\((?P<cols>[^)]+)\)\s+REFERENCES\s+(?P<ref>[A-Za-z_][\w.]*)"
    r"\s*\((?P<refcols>[^)]*)\)"
    r"(?:.*?ON\s+DELETE\s+(?P<ondel>[A-Z\s]+?))?"
    r"(?:.*?ON\s+UPDATE\s+(?P<onupd>[A-Z\s]+?))?"
    r"(?:\s|,|$|\))",
    re.IGNORECASE,
)
_RE_UNIQUE_COLS = re.compile(r"UNIQUE\s*\((?P<cols>[^)]+)\)", re.IGNORECASE)
_RE_CHECK = re.compile(r"CHECK\s*\((?P<expr>.+?)\)\s*(?:,|$)", re.IGNORECASE | re.DOTALL)
_RE_PK_COLS = re.compile(r"PRIMARY\s+KEY\s*\((?P<cols>[^)]+)\)", re.IGNORECASE)


class DatabaseSchemaExtractor:
    """Identyfikuje i modeluje warstwę danych ze źródeł projektu (FR70)."""

    # ── Auto-detekcja warstwy danych (dla UI — opcja „Testy warstwy danych") ──
    SQLALCHEMY_MARKERS = ("__tablename__", "Column(", "ForeignKey(", "mapped_column", "declarative_base")
    ELOQUENT_MARKERS = ("extends Model", "$table", "$fillable", "Schema::create", "$timestamps")
    DOCTRINE_MARKERS = (
        "#[Entity]",
        "#[ORM\\Entity]",
        "#[Column]",
        "#[ORM\\Column]",
        "#[ManyToOne]",
        "#[ORM\\ManyToOne]",
        "#[ORM\\Table]",
        "@ORM\\Column",
    )

    def has_data_layer(self, sources: dict[str, str]) -> bool:
        """Czy którekolwiek źródło sugeruje warstwę danych (auto-detekcja UI)."""
        for path, content in sources.items():
            low = content if isinstance(content, str) else ""
            if path.lower().endswith(".sql") and re.search(r"CREATE\s+TABLE", low, re.IGNORECASE):
                return True
            if any(m in low for m in self.SQLALCHEMY_MARKERS):
                return True
            if any(m in low for m in self.ELOQUENT_MARKERS):
                return True
            if any(m in low for m in self.DOCTRINE_MARKERS):
                return True
            if "migrations" in path.lower() and path.lower().endswith((".sql", ".php", ".py")):
                return True
        return False

    # ════════════════════════════════════════════════════════════════════════
    # 1. Parsowanie DDL (.sql) — sqlglot (z fallbackiem regexowym)
    # ════════════════════════════════════════════════════════════════════════

    def parse_ddl(self, sql: str, dialect: str | None = None) -> list[Table]:
        """Sparsuj tekst DDL na listę tabel.

        Używa sqlglot gdy dostępny (deklarowana zależność); w przeciwn razie
        regexowy parser DDL (pokrywa wspólny podzbiór CREATE TABLE).
        """
        if not sql or not sql.strip():
            return []
        if SQLGLOT_AVAILABLE:
            try:
                return self._parse_ddl_sqlglot(sql, dialect)
            except Exception as exc:  # pragma: no cover — sqlglot wewnętrzny błąd
                logger.warning("sqlglot nie sparsował DDL (%s) — fallback regex: %s", dialect, exc)
        return self._parse_ddl_regex(sql)

    def _parse_ddl_sqlglot(self, sql: str, dialect: str | None) -> list[Table]:
        tables: list[Table] = []
        statements = sqlglot.parse(sql, read=dialect)  # type: ignore[union-attr]
        for stmt in statements:
            if stmt is None:
                continue
            if isinstance(stmt, sqlglot_exp.Create) and str(stmt.args.get("kind", "")).upper() == "TABLE":  # type: ignore[union-attr]
                table = self._table_from_create(stmt)
                if table is not None:
                    tables.append(table)
        # drugi przebieg: rozwiązanie nazw tabel referencyjnych już po zebraniu wszystkich
        return tables

    def _table_from_create(self, stmt: Any) -> Table | None:
        schema = stmt.this  # exp.Schema
        if schema is None:
            return None
        table_name = self._schema_name(schema)
        if not table_name:
            return None

        table = Table(name=table_name, source="sql")
        raw_body = stmt.sql()

        for node in schema.expressions or []:
            cls_name = type(node).__name__
            if cls_name == "ColumnDef":
                col = self._column_from_columndef(node)
                if col is not None:
                    table.columns.append(col)
            elif cls_name == "Constraint":
                self._apply_table_constraint(table, node)

        # Bezpieczna siatka: table-level ograniczenia też przez regex na całym ciele
        self._extract_table_constraints_regex(table, raw_body)

        # konsolidacja PK
        pk_from_cols = [c.name for c in table.columns if c.primary_key]
        if pk_from_cols and not table.primary_key:
            table.primary_key = pk_from_cols
        return table

    @staticmethod
    def _schema_name(schema: Any) -> str:
        token = schema.this
        # Table/Identifier — .name działa dla obu
        name = getattr(token, "name", None) or getattr(token, "this", None)
        return str(name) if name else ""

    def _column_from_columndef(self, col: Any) -> Column | None:
        name = getattr(col, "name", None) or getattr(getattr(col, "this", None), "name", None)
        if not name:
            return None
        dtype_node = col.args.get("kind") if hasattr(col, "args") else None
        dtype = dtype_node.sql() if dtype_node is not None and hasattr(dtype_node, "sql") else ""
        column = Column(name=str(name), type=str(dtype) or "UNKNOWN")

        constraints = col.args.get("constraints") if hasattr(col, "args") else []
        for cc in constraints or []:
            kind = cc.args.get("kind") if hasattr(cc, "args") else None
            kind_cls = type(kind).__name__ if kind is not None else ""
            kind_sql = kind.sql() if kind is not None and hasattr(kind, "sql") else ""
            if kind_cls == "PrimaryKeyColumnConstraint":
                column.primary_key = True
                column.nullable = False
                column.raw_constraints.append("PRIMARY KEY")
            elif kind_cls == "NotNullColumnConstraint":
                column.nullable = False
                column.raw_constraints.append("NOT NULL")
            elif kind_cls == "UniqueColumnConstraint":
                column.unique = True
                column.raw_constraints.append("UNIQUE")
            elif kind_cls == "DefaultColumnConstraint":
                # wartość domyślna — tekst wyrażenia po DEFAULT
                m = re.search(r"DEFAULT\s+(.+?)(?:\s|$)", kind_sql)
                column.default = m.group(1).strip() if m else kind_sql.strip() or None
                column.raw_constraints.append(kind_sql)
            elif kind_cls == "CheckColumnConstraint":
                m = re.search(r"CHECK\s*\((.+)\)", kind_sql, re.IGNORECASE)
                expr = m.group(1).strip() if m else kind_sql
                column.checks.append(expr)
                column.raw_constraints.append(kind_sql)
            elif kind_sql:
                column.raw_constraints.append(kind_sql)
        return column

    def _apply_table_constraint(self, table: Table, node: Any) -> None:
        """Zastosuj table-level Constraint (sqlglot) — jeśli regex tego nie złapie."""
        inner = node.args.get("expressions") if hasattr(node, "args") else []
        name = getattr(getattr(node, "this", None), "name", None)
        for x in inner or []:
            xcls = type(x).__name__
            xsql = x.sql() if hasattr(x, "sql") else str(x)
            if xcls == "ForeignKey":
                self._add_fk_from_sql(table, xsql, name)
            elif xcls in ("UniqueColumnConstraint", "Unique"):
                m = _RE_UNIQUE_COLS.search(xsql)
                if m:
                    cols = [c.strip() for c in m.group("cols").split(",") if c.strip()]
                    if len(cols) == 1:
                        c = table.column(cols[0])
                        if c:
                            c.unique = True
                    else:
                        table.uniques.append(cols)
            elif xcls in ("CheckColumnConstraint", "Check"):
                m = _RE_CHECK.search(xsql)
                if m and m.group("expr").strip() not in table.checks:
                    table.checks.append(m.group("expr").strip())
            elif xcls in ("PrimaryKeyColumnConstraint", "PrimaryKey"):
                m = _RE_PK_COLS.search(xsql)
                if m:
                    table.primary_key = [c.strip() for c in m.group("cols").split(",") if c.strip()]

    def _extract_table_constraints_regex(self, table: Table, body: str) -> None:
        """Bezpieczna siatka regex — łapie FK/composite-UNIQUE/PK/CHECK tabelowe."""
        for m in _RE_FK.finditer(body):
            self._add_fk_from_match(table, m)
        for m in _RE_UNIQUE_COLS.finditer(body):
            cols = [c.strip() for c in m.group("cols").split(",") if c.strip()]
            if len(cols) == 1:
                c = table.column(cols[0])
                if c:
                    c.unique = True
            elif cols not in table.uniques:
                table.uniques.append(cols)
        for m in _RE_PK_COLS.finditer(body):
            cols = [c.strip() for c in m.group("cols").split(",") if c.strip()]
            if cols and not table.primary_key:
                table.primary_key = cols
        for m in _RE_CHECK.finditer(body):
            expr = m.group("expr").strip()
            if expr and expr not in table.checks:
                table.checks.append(expr)

    def _add_fk_from_sql(self, table: Table, sql_fragment: str, name: str | None) -> None:
        m = _RE_FK.search(sql_fragment)
        if m:
            self._add_fk_from_match(table, m, name)

    def _add_fk_from_match(self, table: Table, m: re.Match, name: str | None = None) -> None:
        cols = [c.strip() for c in m.group("cols").split(",") if c.strip()]
        ref = m.group("ref").split(".")[-1].strip()
        refcols = [c.strip() for c in (m.group("refcols") or "").split(",") if c.strip()]
        ondel = (m.group("ondel") or "").strip().upper() or None
        onupd = (m.group("onupd") or "").strip().upper() or None
        fk = ForeignKey(
            columns=cols,
            ref_table=ref,
            ref_columns=refcols,
            on_delete=ondel,
            on_update=onupd,
            name=name,
        )
        if not any(fk.columns == e.columns and fk.ref_table == e.ref_table for e in table.foreign_keys):
            table.foreign_keys.append(fk)

    def _parse_ddl_regex(self, sql: str) -> list[Table]:
        """Fallback regex (gdy sqlglot niedostępny) — wspólny podzbiór DDL."""
        tables: list[Table] = []
        for m in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\((?P<body>.*?)\)\s*(?:;|$)",
            sql,
            re.IGNORECASE | re.DOTALL,
        ):
            name = m.group(1)
            body = m.group("body")
            table = Table(name=name, source="sql")
            # podziel na elementy najwyższego poziomu (uwaga na zagnieżdżone nawiasy)
            for raw in _split_top_level(body):
                item = raw.strip()
                if not item or item.upper().startswith(
                    ("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "KEY", "INDEX")
                ):
                    if item:
                        self._extract_table_constraints_regex(table, item)
                    continue
                col = self._parse_column_line(item)
                if col is not None:
                    table.columns.append(col)
            self._extract_table_constraints_regex(table, body)
            pk = [c.name for c in table.columns if c.primary_key]
            if pk and not table.primary_key:
                table.primary_key = pk
            tables.append(table)
        return tables

    @staticmethod
    def _parse_column_line(line: str) -> Column | None:
        parts = line.split()
        if len(parts) < 2:
            return None
        name = parts[0].strip('`"[]')
        # typ = pierwszy token po nazwie (+ opcjonalnie (n))
        rest = line[len(parts[0]) :].strip()
        tm = re.match(r"([\w]+(?:\s*\([^)]*\))?)", rest)
        dtype = tm.group(1).strip() if tm else "UNKNOWN"
        col = Column(name=name, type=dtype)
        upper = line.upper()
        if "NOT NULL" in upper:
            col.nullable = False
        if "PRIMARY KEY" in upper:
            col.primary_key = True
            col.nullable = False
        if "UNIQUE" in upper:
            col.unique = True
        dm = re.search(r"DEFAULT\s+([^,\s]+)", upper)
        if dm:
            col.default = dm.group(1)
        cm = re.search(r"CHECK\s*\((.+?)\)", line, re.IGNORECASE)
        if cm:
            col.checks.append(cm.group(1).strip())
        return col

    # ════════════════════════════════════════════════════════════════════════
    # 2. Modele ORM
    # ════════════════════════════════════════════════════════════════════════

    def parse_sqlalchemy_models(self, source: str) -> list[Table]:
        """Sparsuj klasy declarative SQLAlchemy → tabele.

        Rozpoznaje ``__tablename__`` oraz definicje ``Column(...)``
        / ``mapped_column(...)`` z typami i ForeignKey.
        """
        tables: list[Table] = []
        # Klasa SQLAlchemy: `class User(Base):` lub `class User:` (bez klasy bazowej).
        # Body = wcięte linie do następnego `class` / EOF.
        for cls in re.finditer(
            r"class\s+(?P<name>\w+)(?:\s*\([^)]*\))?\s*:.*?\n(?P<body>(?:[ \t]+.*\n?)+)",
            source,
            re.DOTALL,
        ):
            body = cls.group("body")
            tnm = re.search(r"__tablename__\s*=\s*[\"']([\w]+)[\"']", body)
            if not tnm:
                continue
            table = Table(name=tnm.group(1), source="sqlalchemy")
            # Column / mapped_column — `.*` działa w obrębie linii (nie przekracza \n),
            # więc poprawnie łapie zagniężdżone nawiasy typu String(255).
            for cm in re.finditer(r"(?P<name>\w+)\s*=\s*(?:mapped_)?Column\s*\((?P<args>.*)\)", body):
                col = self._sqlalchemy_column(cm.group("name"), cm.group("args"))
                if col:
                    table.columns.append(col)
            if table.columns:
                pk = [c.name for c in table.columns if c.primary_key]
                if pk:
                    table.primary_key = pk
                tables.append(table)
        return tables

    def _sqlalchemy_column(self, name: str, args: str) -> Column | None:
        args = args.strip()
        if not args:
            return None
        # pierwszy token = typ (Integer, String(255), ...)
        tm = re.match(r"\s*(?P<type>[\w.]+(?:\s*\([^)]*\))?)", args)
        dtype = tm.group("type").split(".")[-1] if tm else "UNKNOWN"
        col = Column(name=name, type=dtype)
        if re.search(r"primary_key\s*=\s*True", args, re.IGNORECASE):
            col.primary_key = True
            col.nullable = False
        if re.search(r"nullable\s*=\s*False", args, re.IGNORECASE):
            col.nullable = False
        if re.search(r"unique\s*=\s*True", args, re.IGNORECASE):
            col.unique = True
        # ForeignKey("tbl.col") → referencja
        fm = re.search(r"ForeignKey\s*\(\s*[\"']([\w]+)\.([\w]+)[\"']", args)
        if fm:
            col.raw_constraints.append(f"FK {fm.group(1)}.{fm.group(2)}")
        return col

    def parse_eloquent_models(self, source: str) -> list[Table]:
        """Sparsuj modele Eloquent (PHP/Laravel) → tabele.

        Rozpoznaje ``protected $table`` / ``$fillable`` / ``$guarded``.
        Detale kolumn zwykle w migracjach (Schema::create) — tu model+fillable.
        """
        tables: list[Table] = []
        for cm in re.finditer(
            r"class\s+(\w+)\s+extends\s+Model\b[^{]*\{(?P<body>.*?)\s*\}",
            source,
            re.IGNORECASE | re.DOTALL,
        ):
            body = cm.group("body")
            tnm = re.search(r"\$table\s*=\s*[\"']([\w]+)[\"']", body)
            name = tnm.group(1) if tnm else _snake(cm.group(1))
            table = Table(name=name, source="eloquent")
            fm = re.search(r"\$fillable\s*=\s*\[(?P<v>[^\]]*)\]", body)
            if fm:
                for f in re.findall(r"[\"']([\w]+)[\"']", fm.group("v")):
                    table.columns.append(Column(name=f, type="fillable", nullable=False))
            gm = re.search(r"\$guarded\s*=\s*\[(?P<v>[^\]]*)\]", body)
            if gm and gm.group("v").strip() not in ("", "['*']", '["*"]'):
                for f in re.findall(r"[\"']([\w]+)[\"']", gm.group("v")):
                    if not table.column(f):
                        table.columns.append(Column(name=f, type="guarded"))
            if table.columns:
                tables.append(table)
        # migracje Laravel: Schema::create('tbl', function ... { $table->... })
        for sm in re.finditer(
            r"Schema::create\s*\(\s*[\"']([\w]+)[\"']\s*,\s*(?P<body>function.*?)\}\s*\)\s*;", source, re.DOTALL
        ):
            name = sm.group(1)
            body = sm.group("body")
            table = next((t for t in tables if t.name == name), Table(name=name, source="eloquent"))
            for lm in re.finditer(r"\$table->(\w+)\s*\(\s*[\"']([\w]+)[\"']", body):
                method, colname = lm.group(1), lm.group(2)
                dtype = method
                col = table.column(colname) or Column(name=colname, type=dtype)
                if not table.column(colname):
                    table.columns.append(col)
            if table not in tables:
                tables.append(table)
        return tables

    def parse_doctrine_models(self, source: str) -> list[Table]:
        """Sparsuj modele Doctrine (PHP/Symfony, atrybuty) → tabele.

        Rozpoznaje ``#[Entity]``, ``#[Table(name:)]``, ``#[Column]``,
        ``#[ManyToOne, JoinColumn]``.
        """
        tables: list[Table] = []
        # Podział na bloki encji: od `#[ORM\Entity]` do następnego `#[...Entity]` / EOF.
        for block_match in re.finditer(
            r"#\[(?:ORM\\)?Entity[^\]]*\](?P<body>.*?)(?=#\[(?:ORM\\)?Entity|\Z)",
            source,
            re.IGNORECASE | re.DOTALL,
        ):
            body = block_match.group("body")
            cls_match = re.search(r"class\s+(\w+)", body)
            if not cls_match:
                continue
            cls_name = cls_match.group(1)
            tnm = re.search(r"#\[(?:ORM\\)?Table\s*\([^)]*name\s*:\s*[\"']([\w]+)[\"']", body, re.IGNORECASE)
            name = tnm.group(1) if tnm else _snake(cls_name)
            table = Table(name=name, source="doctrine")
            # #[Column(...)] z opcjonalnym type / nullable — atrybut nad właściwością
            for am in re.finditer(
                r"#\[(?:ORM\\)?Column\s*\((?P<a>[^)]*)\)\]\s*(?:public|protected|private)?\s*(?:\??[\w\\]+)?\s*\$(?P<name>\w+)",
                body,
            ):
                a = am.group("a")
                cname = am.group("name")
                tm = re.search(r"type\s*:\s*[\"']?([\w\\]+)[\"']?", a)
                dtype = tm.group(1).split("\\")[-1] if tm else "UNKNOWN"
                col = Column(name=cname, type=dtype)
                if re.search(r"nullable\s*:\s*True", a, re.IGNORECASE):
                    col.nullable = True
                else:
                    col.nullable = False  # Doctrine domyślnie NOT NULL
                if re.search(r"unique\s*:\s*True", a, re.IGNORECASE):
                    col.unique = True
                table.columns.append(col)
            # #[ManyToOne / OneToOne ...] #[JoinColumn(name:)]  → FK
            for jm in re.finditer(
                r"#\[(?:ORM\\)?(?P<rel>ManyToOne|OneToOne)\s*\((?P<rela>[^)]*)\)\][^\n]*\n\s*"
                r"#\[(?:ORM\\)?JoinColumn\s*\((?P<a>[^)]*)\)\]",
                body,
            ):
                a = jm.group("a")
                rela = jm.group("rela")
                tmn = re.search(r"name\s*:\s*[\"']([\w]+)[\"']", a)
                rtm = re.search(r"referencedColumnName\s*:\s*[\"']([\w]+)[\"']", a)
                tgt = re.search(r"targetEntity\s*:\s*([\w\\]+)::class", rela)
                ref_table = _snake(tgt.group(1).split("\\")[-1]) if tgt else "unknown"
                if tmn:
                    table.foreign_keys.append(
                        ForeignKey(
                            columns=[tmn.group(1)],
                            ref_table=ref_table,
                            ref_columns=[rtm.group(1)] if rtm else ["id"],
                            name="doctrine_join",
                        )
                    )
            if table.columns:
                tables.append(table)
        return tables

    # ════════════════════════════════════════════════════════════════════════
    # 3. Migracje
    # ════════════════════════════════════════════════════════════════════════

    def parse_migration_file(self, name: str, content: str) -> Migration | None:
        """Sparsuj plik migracji na :class:`Migration` (up/down).

        Obsługuje: pliki .sql z markerami ``-- up`` / ``-- down`` (lub
        ``UP:``/``DOWN:``), oraz wspólny schemat wersjonowania (nazwa pliku).
        """
        if not content or not content.strip():
            return None
        version = _derive_version(name)
        up_sql, down_sql = _split_up_down(content)
        if not up_sql.strip():
            up_sql = content.strip()
        return Migration(version=version, up_sql=up_sql.strip(), down_sql=down_sql.strip(), source_file=name)

    # ════════════════════════════════════════════════════════════════════════
    # Główny entry point — złożenie modelu ze wszystkich źródeł
    # ════════════════════════════════════════════════════════════════════════

    def extract(
        self,
        *,
        sql_sources: dict[str, str] | None = None,
        orm_sources: dict[str, str] | None = None,
        migration_sources: dict[str, str] | None = None,
        dynamic_queries: list[dict[str, Any]] | list[DynamicQuery] | None = None,
        dialect: str | None = None,
    ) -> DatabaseModel:
        """Zbuduj :class:`DatabaseModel` ze źródeł projektu.

        Args:
            sql_sources: ścieżka → treść pliku .sql (DDL / schema).
            orm_sources: ścieżka → treść pliku modelu ORM (auto-detekcja dialektu).
            migration_sources: ścieżka → treść pliku migracji.
            dynamic_queries: zapytania dynamiczne z ``data_flow.py`` (delegowane do 4.2/4.3).
            dialect: dialekt SQL dla sqlglot (np. ``"postgres"``).
        """
        sql_sources = sql_sources or {}
        orm_sources = orm_sources or {}
        migration_sources = migration_sources or {}

        tables: list[Table] = []
        orm_kinds: set[str] = set()

        for _path, content in sql_sources.items():
            for t in self.parse_ddl(content, dialect=dialect):
                tables.append(t)

        for _path, content in orm_sources.items():
            low = content
            if any(m in low for m in self.SQLALCHEMY_MARKERS):
                tables.extend(self.parse_sqlalchemy_models(content))
                orm_kinds.add("sqlalchemy")
            if any(m in low for m in self.ELOQUENT_MARKERS):
                tables.extend(self.parse_eloquent_models(content))
                orm_kinds.add("eloquent")
            if any(m in low for m in self.DOCTRINE_MARKERS):
                tables.extend(self.parse_doctrine_models(content))
                orm_kinds.add("doctrine")

        # dedup tabel po nazwie (sql + orm mogą się pokrywać → zachowaj bogatszy)
        tables = _merge_tables(tables)

        migrations = [
            m for m in (self.parse_migration_file(n, c) for n, c in migration_sources.items()) if m is not None
        ]

        dyn: list[DynamicQuery] = []
        for q in dynamic_queries or []:
            if isinstance(q, DynamicQuery):
                dyn.append(q)
            elif isinstance(q, dict):
                dyn.append(
                    DynamicQuery(
                        snippet=str(q.get("snippet") or q.get("sql") or ""),
                        location=str(q.get("location") or q.get("file") or "unknown"),
                        reason=str(q.get("reason") or "dynamic SQL"),
                    )
                )

        orm = _resolve_orm(orm_kinds, sql_sources, tables)
        return DatabaseModel(
            tables=tables,
            migrations=migrations,
            seed_files=[p for p in (*sql_sources,) if "seed" in p.lower()],
            dynamic_queries=dyn,
            orm=orm,
        )


# ════════════════════════════════════════════════════════════════════════
# Funkcje pomocnicze modułowe
# ════════════════════════════════════════════════════════════════════════


def _split_top_level(body: str) -> list[str]:
    """Podziel treść CREATE TABLE na elementy szanując zagnieżdżone nawiasy."""
    items: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf))
    return items


def _split_up_down(content: str) -> tuple[str, str]:
    """Podziel plik migracji na sekcje up/down po markerach."""
    low = content.lower()
    up_idx = re.search(r"(--|#|/\*)\s*up\s*[:\n]", low)
    down_idx = re.search(r"(--|#|/\*)\s*down\s*[:\n]", low)
    if up_idx and down_idx and up_idx.start() < down_idx.start():
        up_start = up_idx.end()
        return content[up_start : down_idx.start()], content[down_idx.end() :]
    if up_idx:
        return content[up_idx.end() :], ""
    return content, ""


def _derive_version(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    # Laravel / Alembic: wiodący ciąg cyfr z podkreślnikami → usuń '_' (np. 2024_01_01_000001)
    m = re.match(r"((?:\d+_)*\d+)", base)
    if m:
        return m.group(1).replace("_", "")
    m = re.search(r"(\d{4,})", base)
    return m.group(1) if m else base


def _snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()
    return s


def _merge_tables(tables: list[Table]) -> list[Table]:
    """Dedup po nazwie — przy kolizji zachowaj tabelę z większą liczbą kolumn."""
    by_name: dict[str, Table] = {}
    for t in tables:
        existing = by_name.get(t.name)
        if existing is None or len(t.columns) > len(existing.columns):
            # scal ograniczenia jeśli dwie wersje
            if existing is not None:
                t.foreign_keys = list(
                    {
                        (fk.name, tuple(fk.columns), fk.ref_table): fk
                        for fk in [*existing.foreign_keys, *t.foreign_keys]
                    }.values()
                )
                t.checks = list({*existing.checks, *t.checks})
            by_name[t.name] = t
    return list(by_name.values())


def _resolve_orm(orm_kinds: set[str], sql_sources: dict[str, str], tables: list[Table]) -> str:
    if len(orm_kinds) > 1:
        return "mixed"
    if orm_kinds:
        return next(iter(orm_kinds))
    if tables and any(t.source == "sql" for t in tables):
        return "sql"
    if sql_sources:
        return "sql"
    return "unknown"


def get_db_schema_extractor() -> DatabaseSchemaExtractor:
    """Factory — singletonowy ekstraktor (wzorzec z repo)."""
    return DatabaseSchemaExtractor()
