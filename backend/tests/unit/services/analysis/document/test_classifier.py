"""Unit tests for DocumentClassifier — Story 2.3 closure.

Covers native rules per type (AC2), the LLM path with a mocked gateway and its
non-fatal native fallback (AC3), the AC6 low-confidence override, and the
``classify_document_async`` routing (native/llm/hybrid). No API keys and no
network — the LLM gateway is patched at the module level.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.document import (
    ClassificationResult,
    ClassificationSource,
    DocumentStructure,
    DocumentType,
    SectionStructure,
)
from app.services.analysis.document.classifier import (
    DocumentClassifier,
    classify_document_async,
)

CLASSIFIER_PATH = "app.services.analysis.document.classifier"


def _section(title: str, content: str, sid: str = "s1", level: int = 1) -> SectionStructure:
    return SectionStructure(section_id=sid, title=title, level=level, content=content)


def _doc(*sections: SectionStructure) -> DocumentStructure:
    return DocumentStructure(sections=list(sections))


# ── AC2: native rules per type ──────────────────────────────────────────────


class TestNativeClassification:
    async def test_native_classifies_requirements_spec(self):
        """Title + section + keywords → SPECYFIKACJA_WYMAGAN, confidence ≥ 50."""
        doc = _doc(
            _section(
                "Specyfikacja wymagań",
                "2. Wymagania funkcjonalne. Każde wymaganie ma kryterium akceptacji.",
                sid="s1",
            ),
        )
        result = await classify_document_async(doc, "native")

        assert result.doc_type == DocumentType.SPECIFIKACJA_WYMAGAN
        assert result.confidence >= 50
        assert result.source == ClassificationSource.NATIVE

    async def test_native_classifies_api_docs(self):
        """API keywords/structure → OPIS_API."""
        doc = _doc(
            _section(
                "API Documentation",
                "POST /api/v1/users — request body JSON, response 201. "
                "Endpoint requires authentication. curl http://example.com",
                sid="s1",
            ),
        )
        result = await classify_document_async(doc, "native")

        assert result.doc_type == DocumentType.OPIS_API
        assert result.confidence >= 50

    async def test_native_generic_doc_falls_back_to_inny_with_ac6_note(self):
        """Empty/generic doc → INNY; AC6 appends the low-confidence note."""
        doc = _doc(_section("Lorem ipsum", "Dolor sit amet consectetur.", sid="s1"))
        result = await classify_document_async(doc, "native")

        assert result.doc_type == DocumentType.INNY
        assert "Niska pewność klasyfikacji" in (result.reasoning or "")

    def test_sync_classify_preserved(self):
        """The sync ``classify`` entry point is unchanged (delegates native)."""
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie funkcjonalne", sid="s1"))
        result = DocumentClassifier().classify(doc)

        assert result.doc_type == DocumentType.SPECIFIKACJA_WYMAGAN
        assert result.source == ClassificationSource.NATIVE


# ── AC3: LLM path with mocked gateway + non-fatal fallback ─────────────────


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


class TestLLMClassification:
    async def test_classify_llm_success(self):
        """Mocked gateway returns JSON → source LLM, type mapped (accent-tolerant)."""
        classifier = DocumentClassifier()
        doc = _doc(_section("API", "POST /api/v1/users JSON endpoint", sid="s1"))
        gateway = _mock_gateway('{"type": "opis_api", "confidence": 92, "reasoning": "Endpointy REST"}')

        with (
            patch(f"{CLASSIFIER_PATH}.get_llm_gateway", return_value=gateway),
            patch.object(DocumentClassifier, "_select_llm_provider", return_value="anthropic"),
        ):
            result = await classifier._classify_llm(doc)

        assert result.doc_type == DocumentType.OPIS_API
        assert result.source == ClassificationSource.LLM
        assert result.confidence == 92.0
        assert result.llm_confidence == 92.0
        assert result.native_confidence is not None  # populated from native run
        # gateway called with deterministic classification params
        kwargs = gateway.complete.call_args.kwargs
        assert kwargs["module"] == "classification"
        assert kwargs["task_type"] == "document_classification"
        assert kwargs["temperature"] == 0.0
        assert kwargs["model"] is None

    async def test_classify_llm_handles_fenced_json(self):
        """LLM may wrap the JSON in ```json fences — parsing still succeeds."""
        classifier = DocumentClassifier()
        doc = _doc(_section("API", "endpoint", sid="s1"))
        gateway = _mock_gateway('```json\n{"type": "opis_api", "confidence": 80, "reasoning": "x"}\n```')

        with (
            patch(f"{CLASSIFIER_PATH}.get_llm_gateway", return_value=gateway),
            patch.object(DocumentClassifier, "_select_llm_provider", return_value="anthropic"),
        ):
            result = await classifier._classify_llm(doc)

        assert result.source == ClassificationSource.LLM
        assert result.doc_type == DocumentType.OPIS_API
        assert result.confidence == 80.0

    async def test_classify_llm_bad_json_falls_back_to_native(self):
        """Unparseable LLM output → non-fatal native fallback."""
        classifier = DocumentClassifier()
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie", sid="s1"))
        gateway = _mock_gateway("this is not json at all")

        with (
            patch(f"{CLASSIFIER_PATH}.get_llm_gateway", return_value=gateway),
            patch.object(DocumentClassifier, "_select_llm_provider", return_value="anthropic"),
        ):
            result = await classifier._classify_llm(doc)

        assert result.source == ClassificationSource.NATIVE

    async def test_classify_llm_unknown_type_falls_back_to_native(self):
        """Unknown type string → fallback to native (AC3 fallback)."""
        classifier = DocumentClassifier()
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie", sid="s1"))
        gateway = _mock_gateway('{"type": "nieistniejacy_typ", "confidence": 90, "reasoning": "x"}')

        with (
            patch(f"{CLASSIFIER_PATH}.get_llm_gateway", return_value=gateway),
            patch.object(DocumentClassifier, "_select_llm_provider", return_value="anthropic"),
        ):
            result = await classifier._classify_llm(doc)

        assert result.source == ClassificationSource.NATIVE

    async def test_classify_llm_gateway_exception_falls_back_to_native(self):
        """Gateway raises → fallback to native (AC3 fallback)."""
        classifier = DocumentClassifier()
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie", sid="s1"))
        gateway = MagicMock()
        gateway.complete = AsyncMock(side_effect=RuntimeError("network down"))

        with (
            patch(f"{CLASSIFIER_PATH}.get_llm_gateway", return_value=gateway),
            patch.object(DocumentClassifier, "_select_llm_provider", return_value="anthropic"),
        ):
            result = await classifier._classify_llm(doc)

        assert result.source == ClassificationSource.NATIVE

    async def test_classify_llm_no_provider_falls_back_to_native(self):
        """No API key configured → LLMError → native fallback."""
        classifier = DocumentClassifier()
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie", sid="s1"))

        with patch.object(
            DocumentClassifier,
            "_select_llm_provider",
            side_effect=Exception("no provider"),
        ):
            result = await classifier._classify_llm(doc)

        assert result.source == ClassificationSource.NATIVE


# ── AC6: low-confidence override ────────────────────────────────────────────


class TestMinConfidenceEnforcement:
    def test_low_confidence_forces_inny(self):
        classifier = DocumentClassifier()
        result = ClassificationResult(
            doc_type=DocumentType.OPIS_API,
            confidence=30.0,
            source=ClassificationSource.NATIVE,
            reasoning="x",
        )

        enforced = classifier._enforce_min_confidence(result)

        assert enforced.doc_type == DocumentType.INNY
        assert "Niska pewność klasyfikacji" in enforced.reasoning

    def test_high_confidence_unchanged(self):
        classifier = DocumentClassifier()
        result = ClassificationResult(
            doc_type=DocumentType.OPIS_API,
            confidence=90.0,
            source=ClassificationSource.NATIVE,
            reasoning="x",
        )

        enforced = classifier._enforce_min_confidence(result)

        assert enforced.doc_type == DocumentType.OPIS_API
        assert "Niska pewność" not in (enforced.reasoning or "")


# ── Routing: classify_document_async (native / llm / hybrid) ────────────────


class TestRouting:
    async def test_routing_native(self):
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie funkcjonalne", sid="s1"))
        result = await classify_document_async(doc, "native")

        assert result.source == ClassificationSource.NATIVE
        assert result.doc_type == DocumentType.SPECIFIKACJA_WYMAGAN

    async def test_routing_llm(self):
        doc = _doc(_section("API", "POST endpoint JSON", sid="s1"))
        gateway = _mock_gateway('{"type": "opis_api", "confidence": 88, "reasoning": "REST"}')

        with (
            patch(f"{CLASSIFIER_PATH}.get_llm_gateway", return_value=gateway),
            patch.object(DocumentClassifier, "_select_llm_provider", return_value="openai"),
        ):
            result = await classify_document_async(doc, "llm")

        assert result.source == ClassificationSource.LLM
        assert result.doc_type == DocumentType.OPIS_API

    async def test_routing_hybrid_uses_native_with_note(self):
        """AC4: hybrid runs native today + appends the 'not implemented' note."""
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie funkcjonalne", sid="s1"))
        result = await classify_document_async(doc, "hybrid")

        assert result.source == ClassificationSource.NATIVE
        assert "hybrydowy" in (result.reasoning or "")

    async def test_routing_unknown_mode_defaults_to_native(self):
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie funkcjonalne", sid="s1"))
        result = await classify_document_async(doc, "totally-unknown")

        assert result.source == ClassificationSource.NATIVE


# ── all_scores helper (no schema field — returned as dict) ──────────────────


class TestNativeScores:
    def test_native_scores_returns_per_type_dict(self):
        classifier = DocumentClassifier()
        doc = _doc(_section("Specyfikacja wymagań", "wymaganie", sid="s1"))

        scores = classifier._native_scores(doc)

        assert isinstance(scores, dict)
        assert set(scores.keys()) == {t.value for t in DocumentType}
        # the matched type scores highest
        assert scores[DocumentType.SPECIFIKACJA_WYMAGAN.value] == max(scores.values())
