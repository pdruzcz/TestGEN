"""Unit tests for the database schema extractor — Story 1.53 (FR70).

Pokrywa AC/§Testy 1-3: ekstrakcja z DDL (.sql), ORM SQLAlchemy (Python),
ORM Eloquent (PHP/Laravel) + Doctrine (PHP/Symfony), migracje up/down,
auto-detekcję warstwy danych oraz delegację zapytań dynamicznych do modułu
bezpieczeństwa (AC12).
"""

from __future__ import annotations

from app.services.analysis.db_schema_extractor import (
    DatabaseModel,
    DatabaseSchemaExtractor,
    DynamicQuery,
)


class TestDdlExtraction:
    """§Test 1 — DDL (CREATE TABLE z FK/CHECK/UNIQUE)."""

    def test_create_table_with_pk_notnull_unique_check(self):
        sql = """
        CREATE TABLE users (
            id BIGSERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            age INT NOT NULL,
            balance DECIMAL(10,2) DEFAULT 0,
            CONSTRAINT chk_age CHECK (age >= 18)
        );
        """
        tables = DatabaseSchemaExtractor().parse_ddl(sql, dialect="postgres")
        assert len(tables) == 1
        t = tables[0]
        assert t.name == "users"
        cols = {c.name: c for c in t.columns}
        assert cols["id"].primary_key is True
        assert cols["email"].nullable is False
        assert cols["email"].unique is True
        assert cols["age"].nullable is False
        assert cols["balance"].default is not None
        assert "age >= 18" in t.checks

    def test_foreign_key_with_on_delete_cascade(self):
        sql = """
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
        tables = DatabaseSchemaExtractor().parse_ddl(sql, dialect="postgres")
        t = tables[0]
        assert len(t.foreign_keys) == 1
        fk = t.foreign_keys[0]
        assert fk.columns == ["user_id"]
        assert fk.ref_table == "users"
        assert fk.ref_columns == ["id"]
        assert fk.on_delete == "CASCADE"

    def test_composite_unique_and_pk(self):
        sql = """
        CREATE TABLE memberships (
            org_id INT NOT NULL,
            user_id INT NOT NULL,
            role VARCHAR(50),
            CONSTRAINT pk_mem PRIMARY KEY (org_id, user_id),
            CONSTRAINT uq_pair UNIQUE (org_id, user_id)
        );
        """
        tables = DatabaseSchemaExtractor().parse_ddl(sql, dialect="postgres")
        t = tables[0]
        assert set(t.primary_key) == {"org_id", "user_id"}
        assert any(set(u) == {"org_id", "user_id"} for u in t.uniques)

    def test_multiple_tables_and_empty_input(self):
        sql = """
        CREATE TABLE a (id INT PRIMARY KEY);
        CREATE TABLE b (id INT PRIMARY KEY);
        """
        tables = DatabaseSchemaExtractor().parse_ddl(sql)
        assert {t.name for t in tables} == {"a", "b"}
        assert DatabaseSchemaExtractor().parse_ddl("") == []
        assert DatabaseSchemaExtractor().parse_ddl("   ") == []

    def test_regex_fallback_when_sqlglot_unavailable(self, monkeypatch):
        """Gdy sqlglot rzuci błędem, fallback regexowy wciąż parsuje DDL."""
        ext = DatabaseSchemaExtractor()

        def _boom(sql, dialect=None):
            raise RuntimeError("forced sqlglot failure")

        monkeypatch.setattr(ext, "_parse_ddl_sqlglot", _boom)
        # wymuśmy ścieżkę sqlglot (SQLGLOT_AVAILABLE == True) → fallback
        tables = ext.parse_ddl("CREATE TABLE z (id INT PRIMARY KEY, name VARCHAR(50) NOT NULL);")
        assert len(tables) == 1
        assert tables[0].name == "z"
        cols = {c.name: c for c in tables[0].columns}
        assert cols["id"].primary_key is True
        assert cols["name"].nullable is False


class TestSqlAlchemyOrmExtraction:
    """§Test 2 — ORM SQLAlchemy (declarative)."""

    def test_declarative_class_maps_to_table(self):
        source = """
        from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()

        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True)
            email = Column(String(255), nullable=False, unique=True)
            active = Column(Boolean, nullable=False)
            org_id = Column(Integer, ForeignKey("organizations.id"))
        """
        tables = DatabaseSchemaExtractor().parse_sqlalchemy_models(source)
        assert len(tables) == 1
        t = tables[0]
        assert t.name == "users"
        cols = {c.name: c for c in t.columns}
        assert cols["id"].primary_key is True
        assert cols["email"].unique is True
        assert cols["email"].nullable is False
        assert cols["active"].nullable is False
        assert any("FK organizations.id" in rc for rc in cols["org_id"].raw_constraints)
        assert "id" in t.primary_key


class TestEloquentDoctrineOrmExtraction:
    """§Test 3 — ORM Eloquent (Laravel) + Doctrine (Symfony): model → schema."""

    def test_eloquent_model_fillable(self):
        source = """
        <?php
        namespace App\\Models;
        use Illuminate\\Database\\Eloquent\\Model;
        class Product extends Model {
            protected $table = 'products';
            protected $fillable = ['name', 'price', 'sku'];
        }
        """
        tables = DatabaseSchemaExtractor().parse_eloquent_models(source)
        assert len(tables) == 1
        t = tables[0]
        assert t.name == "products"
        assert {c.name for c in t.columns} == {"name", "price", "sku"}

    def test_eloquent_schema_create_migration(self):
        source = """
        Schema::create('carts', function (Blueprint $table) {
            $table->id();
            $table->integer('user_id');
            $table->string('status');
        });
        """
        tables = DatabaseSchemaExtractor().parse_eloquent_models(source)
        assert len(tables) == 1
        assert tables[0].name == "carts"
        assert {c.name for c in tables[0].columns} >= {"user_id", "status"}

    def test_doctrine_entity_attributes(self):
        source = """
        <?php
        namespace App\\Entity;
        use Doctrine\\ORM\\Mapping as ORM;

        #[ORM\\Entity]
        #[ORM\\Table(name: 'invoices')]
        class Invoice {
            #[ORM\\Column(type: 'integer')]
            public int $id;

            #[ORM\\Column(type: 'string', length: 180, unique: true)]
            public string $number;

            #[ORM\\Column(type: 'integer', nullable: true)]
            public ?int $note;
        }
        """
        tables = DatabaseSchemaExtractor().parse_doctrine_models(source)
        assert len(tables) == 1
        t = tables[0]
        assert t.name == "invoices"
        cols = {c.name: c for c in t.columns}
        assert cols["number"].unique is True
        # Doctrine: brak nullable:True => domyślnie NOT NULL
        assert cols["id"].nullable is False
        assert cols["note"].nullable is True


class TestMigrationsAndComposition:
    """§Test 8 — migracje up/down + extract() composition."""

    def test_migration_up_down_split(self):
        content = """
        -- up
        CREATE TABLE accounts (id INT PRIMARY KEY);
        -- down
        DROP TABLE accounts;
        """
        mig = DatabaseSchemaExtractor().parse_migration_file("2024_01_01_000001_create_accounts.sql", content)
        assert mig is not None
        assert mig.version == "20240101000001"
        assert "CREATE TABLE accounts" in mig.up_sql
        assert "DROP TABLE accounts" in mig.down_sql

    def test_extract_composes_sources_and_resolves_orm(self):
        ext = DatabaseSchemaExtractor()
        model = ext.extract(
            sql_sources={
                "schema.sql": "CREATE TABLE organizations (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL);",
            },
            orm_sources={
                "models.py": ("class User:\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n")
            },
            migration_sources={"0001_init.sql": "-- up\nCREATE TABLE x (id INT);\n-- down\nDROP TABLE x;\n"},
        )
        assert isinstance(model, DatabaseModel)
        assert {t.name for t in model.tables} == {"organizations", "users"}
        assert len(model.migrations) == 1
        assert model.orm == "sqlalchemy"
        assert model.has_data_layer is True

    def test_extract_dynamic_queries_delegated(self):
        ext = DatabaseSchemaExtractor()
        model = ext.extract(
            sql_sources={"schema.sql": "CREATE TABLE t (id INT PRIMARY KEY);"},
            dynamic_queries=[
                {
                    "snippet": 'cursor.execute("SELECT * FROM t WHERE id=" + uid)',
                    "location": "app.py:query",
                    "reason": "string concat",
                },
                DynamicQuery(snippet="db.raw(...)", location="repo.go:42"),
            ],
        )
        assert len(model.dynamic_queries) == 2
        assert all(isinstance(q, DynamicQuery) for q in model.dynamic_queries)
        assert model.dynamic_queries[0].location == "app.py:query"

    def test_has_data_layer_autodetect(self):
        ext = DatabaseSchemaExtractor()
        assert ext.has_data_layer({"schema.sql": "CREATE TABLE t (id INT);"}) is True
        assert ext.has_data_layer({"models.py": "class User:\n    __tablename__ = 'users'\n"}) is True
        assert ext.has_data_layer({"eloquent.php": "class P extends Model { protected $table = 'p'; }"}) is True
        assert ext.has_data_layer({"readme.md": "# Hello world\nJust docs."}) is False
