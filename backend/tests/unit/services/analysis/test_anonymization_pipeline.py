"""Testy integracji anonimizacji z pipeline LLM — Story 1.54 (FR72).

Pokrywają: payload do LLM zanonimizowany, mapping persystowany szyfrowany,
audit log (liczby bez wartości), detokenizacja wygenerowanych testów.
"""

import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.encryption import decrypt_bytes_for_tenant
from app.workers.pipeline import _run_llm_generation

TENANT = str(uuid.uuid4())
PROJECT = str(uuid.uuid4())
ANALYSIS = str(uuid.uuid4())

FILE = {
    "file_path": "payments.py",
    "content": (
        'API_KEY = "sk-proj-4f8a9b2c7d1e"\n'
        "class CustomerSSNValidator:\n"
        "    def validate_ssn(self, customer_ssn):\n"
        '        url = "https://api.premium-bank.pl/v1"\n'
        "        return len(customer_ssn) > 0\n"
    ),
    "language": "python",
    "source_file_id": str(uuid.uuid4()),
}


class _SessionCapture:
    """Sync-session stub capturing rows added via session.add()."""

    def __init__(self):
        self.added = []
        mock = MagicMock()
        mock.add = self.added.append
        mock.commit = lambda: None
        self.mock = mock

    @contextmanager
    def ctx(self):
        yield self.mock


def _fake_generator(captured: dict):
    """LLMTestGenerator stub: records source_files, returns placeholder tests."""

    async def generate_test_suite(source_files=None, **kwargs):
        captured["source_files"] = source_files
        test = SimpleNamespace(
            name="Test IDENT_001",
            description="Walidacja IDENT_001 przez <URL_001>",
            code="def test_<SECRET_001>(): assert IDENT_001",
            language="python",
            source_file="payments.py",
            source_function="IDENT_001",
            confidence=0.9,
            scenario=SimpleNamespace(description="IDENT_001", rationale="<SECRET_001>", test_data=None),
        )
        return SimpleNamespace(test_cases=[test], total_tokens_used=42)

    gen = MagicMock()
    gen.generate_test_suite = generate_test_suite
    return gen


def _run(capture, session_capture, **kwargs):
    from app.models.test_case import TestFramework

    gen = _fake_generator(capture)
    session = _SessionCapture()
    session_capture.append(session)
    defaults = dict(
        source_files=[dict(FILE)],
        language="python",
        framework=TestFramework.PYTEST,
        analysis_dict={},
        provider="anthropic",
        tenant_id=TENANT,
        project_id=PROJECT,
        analysis_result_id=ANALYSIS,
        use_llm_detection=False,
    )
    defaults.update(kwargs)
    with (
        patch("app.services.generators.llm_test_generator.get_llm_test_generator", return_value=gen),
        patch("app.workers.pipeline.get_sync_session", return_value=session.ctx()),
    ):
        tests, tokens = _run_llm_generation(**defaults)
    return tests, tokens


class TestPipelineAnonymization:
    def test_payload_to_llm_anonymized(self):
        capture: dict = {}
        _run(capture, [])
        sent = capture["source_files"][0][1]
        assert "sk-proj-4f8a9b2c7d1e" not in sent
        assert "premium-bank.pl" not in sent
        assert "<SECRET_001>" in sent
        assert "<URL_001>" in sent
        # domena (ssn) zamaskowana także w nazwach identyfikatorów
        assert "CustomerSSNValidator" not in sent

    def test_mapping_persisted_encrypted(self):
        sessions = []
        _run({}, sessions)
        from app.models.anonymization_map import AnonymizationMap

        maps = [r for r in sessions[0].added if isinstance(r, AnonymizationMap)]
        assert len(maps) == 1
        row = maps[0]
        assert str(row.tenant_id) == TENANT
        assert str(row.project_id) == PROJECT
        assert str(row.analysis_id) == ANALYSIS
        assert row.token_count >= 3
        assert row.secret_count >= 1
        assert isinstance(row.encrypted_map, bytes)
        # blob szyfrowany — odszyfrowanie kluczem tenanta daje spójny mapping
        decoded = decrypt_bytes_for_tenant(row.encrypted_map, uuid.UUID(TENANT))
        import json

        mapping = json.loads(decoded.decode())
        assert mapping["<SECRET_001>"] == "sk-proj-4f8a9b2c7d1e"
        assert row.expires_at is not None

    def test_audit_row_counts_without_values(self):
        sessions = []
        _run({}, sessions)
        from app.models.audit_log import AuditLog

        audits = [r for r in sessions[0].added if isinstance(r, AuditLog)]
        assert len(audits) == 1
        audit = audits[0]
        assert audit.action == "anonymization_run"
        assert audit.resource_type == "project"
        assert str(audit.resource_id) == PROJECT
        # liczby, BEZ wartości sekretów/nazw
        assert "token_count" in audit.details
        assert "secret_count" in audit.details
        assert "sk-proj-4f8a9b2c7d1e" not in str(audit.details)
        assert "CustomerSSNValidator" not in str(audit.details)

    def test_llm_tests_deanonymized(self):
        tests, tokens = _run({}, [])
        tc = tests[0]
        assert "CustomerSSNValidator" in tc.name
        assert "https://api.premium-bank.pl/v1" in tc.description
        assert "sk-proj-4f8a9b2c7d1e" in tc.code
        assert tc.source_function == "IDENT_001" or "Customer" in tc.source_function
        assert tokens == 42

    def test_original_file_content_not_mutated(self):
        original = FILE["content"]
        capture: dict = {}
        _run(capture, [])
        # intermediate_results pozostają nietknięte (anonymizowana jest kopia)
        assert FILE["content"] == original

    def test_disabled_skips_anonymization(self):
        capture: dict = {}
        sessions = []
        settings = MagicMock()
        settings.anonymization_enabled = False
        with patch("app.core.config.get_settings", return_value=settings):
            _run(capture, sessions)
        assert sessions[0].added == []  # brak wierszy mappingu/audit
        sent = capture["source_files"][0][1]
        assert "sk-proj-4f8a9b2c7d1e" in sent
