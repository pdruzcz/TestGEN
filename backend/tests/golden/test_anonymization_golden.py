"""Golden: anonimizacja próbki z identyfikatorami domenowymi + sekretami — Story 1.54.

Progi ze story: 100% sekretów, ≥95% identyfikatorów domenowych, AST
niezmienione, detokenizacja 100%.
"""

import ast as pyast
import re
from pathlib import Path

import pytest

from app.services.analysis.anonymization import AnonymizationService

FIXTURE = Path(__file__).parents[1] / "fixtures" / "golden" / "anonymization" / "payments_service.py"

# Ground truth (ręcznie zweryfikowane): nazwy zdradzające domenę klienta,
# wykrywalne natywnie (keyword set). Nazwy kontekstowe (tylko-LLM) celowo
# poza zestawem — ścieżka LLM ma własne testy jednostkowe.
GROUND_TRUTH_DOMAIN_IDENTIFIERS = [
    "CustomerSSNValidator",
    "validate_ssn",
    "customer_ssn",
    "NipVerifier",
    "verify_nip",
    "company_nip",
    "CardCVVChecker",
    "check_cvv",
    "cvv_code",
    "fetch_iban_accounts",
    "account_number",
]

GROUND_TRUTH_SECRETS = [
    "AKIAIOSFODNN7EXAMPLE",
    "sk-proj-99aa88bb77cc66dd",
    "sup3rs3cret-p4ssw0rd",
]


@pytest.mark.golden
class TestAnonymizationGolden:
    @pytest.fixture()
    def source(self) -> str:
        return FIXTURE.read_text(encoding="utf-8")

    @pytest.fixture()
    def anonymized(self, source):
        import asyncio

        svc = AnonymizationService()
        return asyncio.run(svc.anonymize(source))

    def test_all_secrets_masked_100pct(self, anonymized):
        anon, _ = anonymized
        for secret in GROUND_TRUTH_SECRETS:
            assert secret not in anon, f"sekret wyciekł: {secret[:6]}…"
        # JWT (prefiks eyJ) również 100%
        assert "eyJhbGciOiJIUzI1NiJ9" not in anon

    def test_domain_identifiers_at_least_95pct(self, anonymized):
        anon, _ = anonymized
        unmasked = [name for name in GROUND_TRUTH_DOMAIN_IDENTIFIERS if re.search(rf"\b{re.escape(name)}\b", anon)]
        masked_ratio = 1 - len(unmasked) / len(GROUND_TRUTH_DOMAIN_IDENTIFIERS)
        assert masked_ratio >= 0.95, f"niezamaskowane identyfikatory domenowe: {unmasked}"

    def test_neutral_identifiers_left_in_place(self, anonymized):
        anon, _ = anonymized
        assert "format_invoice" in anon
        assert "invoice_id" in anon

    def test_ast_structure_preserved(self, source, anonymized):
        anon, _ = anonymized
        original_tree = pyast.parse(source)
        anonymized_tree = pyast.parse(anon)  # placeholdery są identyfikatorami

        shape = lambda tree: [type(n).__name__ for n in pyast.walk(tree)]  # noqa: E731
        assert shape(original_tree) == shape(anonymized_tree)

    def test_deanonymization_100pct(self, source, anonymized):
        import asyncio

        anon, mapping = anonymized
        svc = AnonymizationService()
        restored = asyncio.run(svc.deanonymize(anon, mapping))
        assert restored == source
