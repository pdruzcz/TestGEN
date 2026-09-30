"""
LLM analysis service — deprecated, use LLMGateway instead.

This module is kept for backward compatibility (DEMO-001).
New code should use app.services.analysis.llm_gateway directly.
"""

import logging

from app.services.analysis.llm_gateway import LLMGateway, LLMMessage, LLMProvider, get_llm_gateway

logger = logging.getLogger(__name__)

# Legacy system prompt for demo compatibility
ANALYSIS_SYSTEM_PROMPT = (
    "Jesteś ekspertem analizy kodu źródłowego. Przeanalizuj podany kod i zwróć wynik "
    "w formacie JSON z sekcjami:\n"
    '- "structures": lista struktur (klasy, interfejsy, moduły) z opisami\n'
    '- "functions": lista funkcji/metod z opisami i parametrami\n'
    '- "patterns": wykryte wzorce projektowe\n'
    '- "test_suggestions": sugestie scenariuszy testowych (pozytywne, negatywne, brzegowe)\n'
    '- "summary": krótkie podsumowanie pliku\n'
    "Odpowiadaj WYŁĄCZNIE w języku polskim. Formatuj jako czysty JSON."
)


async def analyze_file_content(
    filename: str,
    content: str,
    tenant_id: int | None = None,
) -> dict:
    """
    Analyze file content using LLM (legacy function for backward compatibility).

    Args:
        filename: Name of the file being analyzed
        content: Source code content
        tenant_id: Tenant ID for cost tracking

    Returns:
        Dict with analysis results
    """
    gateway = get_llm_gateway()

    try:
        # Try Anthropic first (for demo-001 compatibility)
        response = await gateway.complete(
            provider=LLMProvider.ANTHROPIC,
            messages=[
                LLMMessage(role="user", content=f"Plik: {filename}\n\n```\n{content}\n```")
            ],
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            tenant_id=tenant_id,
            module="code_analysis",
            task_type="demo_001_analysis",
        )

        return {
            "raw_response": response.content,
            "model": response.model,
            "usage": {
                "input_tokens": response.tokens_input,
                "output_tokens": response.tokens_output,
                "total_tokens": response.total_tokens,
            },
            "cost_usd": float(response.cost_usd),
            "latency_ms": response.latency_ms,
        }

    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        raise
