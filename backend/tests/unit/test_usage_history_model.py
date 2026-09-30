"""Testy modelu UsageHistory — Story 7.9, Task 1 (AC3).

Daily snapshoty zużycia per tenant per counter_type per dzień — jedno
źródło danych wykresu historii (AC3) i prognozy (AC4).
"""

from datetime import date

from app.models import get_all_models
from app.models.usage import CounterType
from app.models.usage_history import UsageHistory


class TestUsageHistoryModel:
    def test_tabela_i_kolumny(self):
        assert UsageHistory.__tablename__ == "usage_history"
        columns = UsageHistory.__table__.columns
        assert set(columns.keys()) == {
            "id",
            "tenant_id",
            "counter_type",
            "value",
            "snapshot_date",
            "period_start",
            "period_end",
            "created_at",
            "updated_at",
        }
        assert columns["value"].type.python_type is int
        assert columns["snapshot_date"].type.python_type is date
        assert columns["period_start"].type.python_type is date
        assert columns["period_end"].type.python_type is date

    def test_counter_type_reuzywa_enum_usage_counter_type(self):
        """Ten sam enum PG co UsageCounter (analyses|test_cases|storage_bytes|files_per_analysis)."""
        enum = UsageHistory.__table__.columns["counter_type"].type
        assert enum.name == "usage_counter_type"
        assert {m.value for m in enum.enum_class} == {
            "analyses",
            "test_cases",
            "storage_bytes",
            "files_per_analysis",
        }

    def test_unique_constraint_tenant_type_date(self):
        """(tenant_id, counter_type, snapshot_date) — jeden snapshot per dzień (Task 1.2)."""
        constraints = {
            c.name: tuple(col.name for col in c.columns)
            for c in UsageHistory.__table__.constraints
            if c.__class__.__name__ == "UniqueConstraint"
        }
        assert constraints.get("uq_usage_history_tenant_type_date") == (
            "tenant_id",
            "counter_type",
            "snapshot_date",
        )

    def test_fk_cascade_do_tenants(self):
        fk = next(iter(UsageHistory.__table__.foreign_keys))
        assert fk.target_fullname == "tenants.id"
        assert fk.ondelete == "CASCADE"

    def test_w_get_all_models_dla_alembic(self):
        assert UsageHistory in get_all_models()

    def test_counter_type_przyjmuje_wartosci_enumu(self):
        """Konstrukcja wiersza z każdym typem licznika (bez users — CR#2)."""
        for counter_type in CounterType:
            row = UsageHistory(
                tenant_id=None,
                counter_type=counter_type,
                value=1,
                snapshot_date=date(2026, 9, 10),
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
            )
            assert row.counter_type is counter_type
