"""Tests for AnonymizationService — Story 1.54 (tokenizacja + detokenizacja)."""

import ast as pyast
import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

from app.services.analysis.anonymization import (
    AnonymizationService,
    TokenKind,
)

# --- sample code: domain identifiers + secrets + url/email/ip -----------------

SAMPLE = '''
API_KEY = "sk-proj-4f8a9b2c7d1e"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N65I__7ZLZg"

class CustomerSSNValidator:
    """Walidacja PESEL/SSN klienta."""

    def validate_ssn(self, customer_ssn: str) -> bool:
        endpoint = "https://api.premium-bank.pl/v1/verify"
        contact = "jan.kowalski@premium-bank.pl"
        server_ip = "10.0.3.22"
        iban = "PL61109010140000071219812874"
        return len(customer_ssn) > 0

def calculate_invoice_total():
    return 0
'''


def _make_ast() -> "object":
    from app.services.analysis.ast.ast_tree import ASTTree
    from app.services.analysis.ast.nodes import (
        ClassNode,
        FunctionNode,
        ParameterNode,
        VariableNode,
    )

    param = ParameterNode(name="customer_ssn", type="str")
    method = FunctionNode(
        name="validate_ssn",
        type="function",
        line_start=9,
        line_end=14,
        parameters=[param],
    )
    return ASTTree(
        language="python",
        functions=[FunctionNode(name="calculate_invoice_total", type="function", line_start=16, line_end=17)],
        classes=[
            ClassNode(
                name="CustomerSSNValidator",
                type="class",
                line_start=7,
                line_end=14,
                methods=[method],
            )
        ],
        variables=[VariableNode(name="customer_ssn", type="variable", line_start=1, line_end=1)],
    )


class TestTokenKind:
    def test_values(self):
        assert TokenKind.IDENT.value == "ident"
        assert TokenKind.STR.value == "str"
        assert TokenKind.URL.value == "url"
        assert TokenKind.EMAIL.value == "email"
        assert TokenKind.IP_ACCOUNT.value == "ip_acc"
        assert TokenKind.SECRET.value == "secret"


class TestSecretDetection:
    @pytest.fixture()
    def svc(self):
        return AnonymizationService()

    async def test_all_secrets_detected(self, svc):
        tokens = await svc.detect(SAMPLE)
        secret_values = {t.value for t in tokens if t.kind == TokenKind.SECRET}
        # 100% wykrycia — wszystkie 4 sekrety z próbki (reuse secrets_rules)
        assert "sk-proj-4f8a9b2c7d1e" in secret_values
        assert "AKIAIOSFODNN7EXAMPLE" in secret_values
        assert any(t.value.startswith("eyJ") for t in tokens if t.kind == TokenKind.SECRET)
        assert len(secret_values) >= 3

    async def test_secret_tokens_native_source(self, svc):
        tokens = await svc.detect(SAMPLE)
        assert all(t.source == "native" for t in tokens if t.kind == TokenKind.SECRET)


class TestNativeTokenization:
    @pytest.fixture()
    def svc(self):
        return AnonymizationService()

    async def test_url_email_ip_iban_placeholders(self, svc):
        anon, mapping = await svc.anonymize(SAMPLE)
        assert "https://api.premium-bank.pl/v1/verify" not in anon
        assert "jan.kowalski@premium-bank.pl" not in anon
        assert "10.0.3.22" not in anon
        assert "PL61109010140000071219812874" not in anon
        assert "<URL_001>" in anon
        assert "<EMAIL_001>" in anon
        assert "<ACC_001>" in anon
        # mapping spójny: placeholder → oryginał
        assert mapping["<URL_001>"] == "https://api.premium-bank.pl/v1/verify"

    async def test_domain_identifier_masked_via_ast(self, svc):
        anon, mapping = await svc.anonymize(SAMPLE, ast_tree=_make_ast())
        # nazwy zdradzające domenę (ssn) zanonimizowane
        assert "CustomerSSNValidator" not in anon
        assert "validate_ssn" not in anon
        assert "customer_ssn" not in anon
        assert "IDENT_001" in anon
        assert mapping["IDENT_001"] == "CustomerSSNValidator"

    async def test_same_identifier_consistent_placeholder(self, svc):
        _, mapping = await svc.anonymize(SAMPLE, ast_tree=_make_ast())
        # każda unikalna nazwa → dokładnie jeden placeholder
        assert len(set(mapping.values())) == len(mapping)

    async def test_generic_identifier_not_masked(self, svc):
        source = "def add_numbers(a, b):\n    return a + b\n"
        anon, mapping = await svc.anonymize(source)
        assert "add_numbers" in anon  # nazwa niedomenowa zostaje
        assert not any(k.startswith("IDENT_") for k in mapping)

    async def test_secrets_masked_without_quotes_break(self, svc):
        anon, _ = await svc.anonymize(SAMPLE)
        # literal sekretu: cudzysłowy zostają, wartość w środku zastąpiona
        assert '"<SECRET_' in anon

    async def test_no_false_positive_on_plain_text(self, svc):
        anon, mapping = await svc.anonymize("def hello():\n    print('witaj swiecie')\n")
        assert anon == "def hello():\n    print('witaj swiecie')\n"
        assert mapping == {}


class TestAstPreservation:
    async def test_python_ast_structure_preserved(self):
        svc = AnonymizationService()
        source = (
            "class CustomerSSNValidator:\n"
            "    def validate_ssn(self, customer_ssn: str) -> bool:\n"
            "        endpoint = 'https://api.bank.pl/v1'\n"
            "        return len(customer_ssn) > 0\n"
        )
        anon, _ = await svc.anonymize(source)
        tree_a = pyast.parse(source)
        tree_b = pyast.parse(anon)  # nadal parsowalny — placeholdery są identyfikatorami

        def shape(node):
            return [type(n).__name__ for n in pyast.walk(node)]

        assert shape(tree_a) == shape(tree_b)


class TestDeanonymization:
    @pytest.fixture()
    def svc(self):
        return AnonymizationService()

    async def test_roundtrip_full(self, svc):
        anon, mapping = await svc.anonymize(SAMPLE, ast_tree=_make_ast())
        assert "premium-bank" not in anon
        restored = await svc.deanonymize(anon, mapping)
        assert restored == SAMPLE

    async def test_deanonymize_llm_output(self, svc):
        _, mapping = await svc.anonymize(SAMPLE, ast_tree=_make_ast())
        llm_out = "Wygenerowano test dla IDENT_001 z użyciem <URL_001>."
        restored = await svc.deanonymize(llm_out, mapping)
        assert "CustomerSSNValidator" in restored
        assert "https://api.premium-bank.pl/v1/verify" in restored


@dataclass
class _FakeResponse:
    content: str


class _FakeGateway:
    """Gateway stub for the LLM-contextual detection path."""

    def __init__(self, payload: list[dict]):
        self.payload = payload
        self.calls: list[dict] = field(default_factory=list) if False else []
        self.complete = AsyncMock(return_value=_FakeResponse(json.dumps(payload)))


class TestLLMContextualDetection:
    @pytest.fixture()
    def gateway(self):
        return _FakeGateway(
            [
                {"name": "PaymentGatewaySecret", "confidence": 0.95},
                {"name": "calculate_invoice_total", "confidence": 0.3},
            ]
        )

    async def test_domain_name_caught_by_llm(self, gateway):
        svc = AnonymizationService(llm_gateway=gateway, confidence_threshold=0.7)
        source = "def PaymentGatewaySecret():\n    return 1\n"
        anon, mapping = await svc.anonymize(source, use_llm_detection=True)
        assert "PaymentGatewaySecret" not in anon
        assert "IDENT_001" in anon
        assert mapping["IDENT_001"] == "PaymentGatewaySecret"

    async def test_below_threshold_left_in_place(self, gateway):
        svc = AnonymizationService(llm_gateway=gateway, confidence_threshold=0.7)
        source = "def calculate_invoice_total():\n    return 1\n"
        anon, _ = await svc.anonymize(source, use_llm_detection=True)
        # confidence 0.3 < 0.7 → nazwa pozostaje (bez nadmiernej anonimizacji)
        assert "calculate_invoice_total" in anon

    async def test_llm_detection_not_called_by_default(self, gateway):
        svc = AnonymizationService(llm_gateway=gateway)
        await svc.anonymize(SAMPLE)
        gateway.complete.assert_not_called()

    async def test_llm_malformed_response_fails_open(self):
        bad = _FakeGateway([])
        bad.complete = AsyncMock(return_value=_FakeResponse("not-json {{"))
        svc = AnonymizationService(llm_gateway=bad)
        source = "def PaymentGatewaySecret():\n    return 1\n"
        anon, _ = await svc.anonymize(source, use_llm_detection=True)
        # brak detekcji LLM → nazwa zostaje (fail-open, bez crasha)
        assert "PaymentGatewaySecret" in anon


class TestCounts:
    async def test_counts_secret_and_token(self):
        svc = AnonymizationService()
        result = await svc.anonymize_with_stats(SAMPLE, ast_tree=_make_ast())
        assert result.secret_count >= 3
        assert result.token_count >= 8  # 3 sekrety + url + email + ip + iban + identyfikatory
        assert set(result.mapping) >= {"<URL_001>", "<EMAIL_001>"}
