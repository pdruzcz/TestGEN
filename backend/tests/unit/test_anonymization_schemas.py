"""Tests for anonymization schemas — Story 1.54."""

from app.schemas.anonymization import AnonymizationStats


class TestAnonymizationStats:
    def test_defaults(self):
        stats = AnonymizationStats(anonymized=True)
        assert stats.token_count == 0
        assert stats.secret_count == 0
        assert stats.analysis_id is None

    def test_counts_only_no_value_fields(self):
        stats = AnonymizationStats(anonymized=True, token_count=12, secret_count=3, analysis_id="abc")
        dumped = stats.model_dump()
        # Statystyki zawierają WYŁĄCZNIE liczby/flagi — brak pól na wartości
        assert set(dumped) == {"anonymized", "token_count", "secret_count", "analysis_id"}

    def test_extra_ignored(self):
        stats = AnonymizationStats.model_validate({"anonymized": True, "token_count": 1, "secret_key_value": "leak"})
        assert not hasattr(stats, "secret_key_value")
