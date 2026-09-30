"""Unit tests for LLM requirement extraction — Story 2.5 closure.

Covers ``extract_llm`` with a mocked gateway and its non-fatal native fallback
(AC1), the ``extract_async`` routing by ``engine_mode`` (AC2), ``source``
tagging, and the ``HallucinationValidator`` language/grounding checks (AC3).
No API keys and no network — the LLM gateway is patched at the module level.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.document.hallucination_validator import HallucinationValidator
from app.services.analysis.document.requirement_extractor import (
    ExtractedRequirement,
    LLMRequirementExtractor,
    extract_requirements_async,
)

EXTRACTOR_PATH = "app.services.analysis.document.requirement_extractor"


def _section(title: str, content: str, sid: str = "s1", level: int = 1) -> SectionStructure:
    return SectionStructure(section_id=sid, title=title, level=level, content=content)


def _doc(*sections: SectionStructure) -> DocumentStructure:
    return DocumentStructure(sections=list(sections))


def _req_doc() -> DocumentStructure:
    """A doc whose native extraction yields >= 1 requirement (for fallback/routing)."""
    return _doc(
        _section(
            "2. Wymagania funkcjonalne",
            "System musi weryfikować poprawność danych logowania użytkownika.",
            sid="s1",
        )
    )


def _mock_gateway(content: str) -> MagicMock:
    gateway = MagicMock()
    gateway.complete = AsyncMock(
        return_value=SimpleNamespace(
            content=content,
            model="claude-test",
            tokens_input=10,
            tokens_output=5,
            total_tokens=15,
        )
    )
    return gateway


@contextmanager
def _patches(gateway):
    """Patch the gateway + provider for a deterministic LLM call."""
    with (
        patch(f"{EXTRACTOR_PATH}.get_llm_gateway", return_value=gateway),
        patch.object(LLMRequirementExtractor, "_select_llm_provider", return_value="anthropic"),
    ):
        yield


# ── AC1: extract_llm with mocked gateway + non-fatal fallback ────────────────


class TestExtractLlm:
    async def test_extract_llm_success_tags_llm_and_reasoning(self):
        """Mocked gateway returns JSON → extraction_method/source=llm, reasoning kept."""
        extractor = LLMRequirementExtractor()
        gateway = _mock_gateway(
            '{"requirements":['
            '{"text":"System musi weryfikować poprawność danych logowania.",'
            '"type":"functional","priority":"high","reasoning":"Bezpieczeństwo logowania"}'
            "]}"
        )
        with _patches(gateway):
            reqs = await extractor.extract_llm(_req_doc())

        assert len(reqs) == 1
        req = reqs[0]
        assert req.extraction_method == "llm"
        assert req.source == "llm"
        assert req.reasoning == "Bezpieczeństwo logowania"
        assert req.req_id.startswith("FR-LLM-")
        assert req.source_section_id == "doc-root"

        kwargs = gateway.complete.call_args.kwargs
        assert kwargs["module"] == "requirements"
        assert kwargs["task_type"] == "requirement_extraction"
        assert kwargs["temperature"] == 0.1
        assert kwargs["model"] is None

    async def test_extract_llm_handles_fenced_json(self):
        """LLM may wrap the JSON in ```json fences — parsing still succeeds."""
        extractor = LLMRequirementExtractor()
        gateway = _mock_gateway(
            '```json\n{"requirements":['
            '{"text":"System musi weryfikować poprawność danych logowania.","type":"functional"}'
            "]}\n```"
        )
        with _patches(gateway):
            reqs = await extractor.extract_llm(_req_doc())

        assert len(reqs) == 1
        assert reqs[0].source == "llm"

    async def test_extract_llm_bad_json_falls_back_to_native(self):
        """Unparseable LLM output → non-fatal native fallback, tagged native."""
        extractor = LLMRequirementExtractor()
        gateway = _mock_gateway("this is not json at all")
        with _patches(gateway):
            reqs = await extractor.extract_llm(_req_doc())

        assert reqs  # native fallback is non-empty
        assert all(r.source == "native" for r in reqs)
        assert all(r.extraction_method == "native" for r in reqs)

    async def test_extract_llm_gateway_exception_falls_back_to_native(self):
        """Gateway raises → fallback to native, tagged native."""
        extractor = LLMRequirementExtractor()
        gateway = MagicMock()
        gateway.complete = AsyncMock(side_effect=RuntimeError("network down"))
        with _patches(gateway):
            reqs = await extractor.extract_llm(_req_doc())

        assert reqs
        assert all(r.source == "native" for r in reqs)

    async def test_extract_llm_no_provider_falls_back_to_native(self):
        """No API key configured → LLMError → native fallback."""
        extractor = LLMRequirementExtractor()
        with patch.object(
            LLMRequirementExtractor,
            "_select_llm_provider",
            side_effect=Exception("no provider"),
        ):
            reqs = await extractor.extract_llm(_req_doc())

        assert reqs
        assert all(r.source == "native" for r in reqs)

    async def test_extract_llm_drops_hallucinated_requirement(self):
        """A requirement that fails validation (foreign language) is dropped, not persisted."""
        extractor = LLMRequirementExtractor()
        gateway = _mock_gateway(
            '{"requirements":['
            '{"text":"The system must be able to process the data efficiently.",'
            '"type":"functional","reasoning":"x"}'
            "]}"
        )
        with _patches(gateway):
            reqs = await extractor.extract_llm(_req_doc())

        assert reqs == []  # rejected by validator — not a native fallback


# ── AC2: routing (native / llm / hybrid) ─────────────────────────────────────


class TestRouting:
    async def test_routing_native_tags_native(self):
        reqs = await extract_requirements_async(_req_doc(), "native")

        assert reqs
        assert all(r.source == "native" for r in reqs)

    async def test_routing_llm_tags_llm(self):
        gateway = _mock_gateway(
            '{"requirements":[{"text":"System musi weryfikować poprawność danych logowania.","type":"functional"}]}'
        )
        with _patches(gateway):
            reqs = await extract_requirements_async(_req_doc(), "llm")

        assert reqs
        assert all(r.source == "llm" for r in reqs)

    async def test_routing_hybrid_falls_back_to_native(self):
        """AC2: hybrid is not implemented in v1 → warning + native, tagged native."""
        reqs = await extract_requirements_async(_req_doc(), "hybrid")

        assert reqs
        assert all(r.source == "native" for r in reqs)

    async def test_routing_unknown_mode_defaults_to_native(self):
        reqs = await extract_requirements_async(_req_doc(), "totally-unknown")

        assert reqs
        assert all(r.source == "native" for r in reqs)


# ── AC3: HallucinationValidator ──────────────────────────────────────────────


def _requirement(text: str) -> ExtractedRequirement:
    return ExtractedRequirement(
        req_id="X",
        text=text,
        type="functional",
        priority=None,
        source_section_id="doc-root",
        source_section_title="Dokument",
        confidence=75.0,
        extraction_method="llm",
        source="llm",
    )


class TestHallucinationValidator:
    def test_polish_text_grounded_in_source_is_valid(self):
        validator = HallucinationValidator()
        source = "System musi weryfikować poprawność danych logowania użytkownika."
        req = _requirement("System musi weryfikować poprawność danych logowania.")

        result = validator.validate(req, source_text=source, document_language="pl")

        assert result.is_valid
        assert result.reasons == []

    def test_foreign_text_is_invalid_language(self):
        validator = HallucinationValidator()
        req = _requirement("The system must be able to process the data and return the results.")

        result = validator.validate(req, source_text="whatever", document_language="pl")

        assert not result.is_valid
        assert "language_mismatch" in result.reasons

    def test_ungrounded_text_is_invalid_grounding(self):
        """Polish-looking text whose keywords do not appear in the source."""
        validator = HallucinationValidator()
        source = "Logowanie użytkownika za pomocą hasła."
        req = _requirement("Aplikacja generuje raporty finansowe kwartalnie.")

        result = validator.validate(req, source_text=source, document_language="pl")

        assert not result.is_valid
        assert "content_not_grounded" in result.reasons

    def test_non_polish_document_language_skips_language_check(self):
        validator = HallucinationValidator()
        req = _requirement("The system must be able to process the data.")

        result = validator.validate(
            req, source_text="the system must be able to process the data", document_language="en"
        )

        assert result.is_valid
