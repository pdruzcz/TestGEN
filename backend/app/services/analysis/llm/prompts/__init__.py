"""LLM prompts module for Epic 2.

Exports prompt templates for various LLM-powered document analysis tasks.
"""

from app.services.analysis.llm.prompts.classification import (
    build_classification_prompt,
    build_hybrid_prompt,
    CLASSIFICATION_EXAMPLES,
    DOCUMENT_CLASSIFICATION_PROMPT,
    HYBRID_CLASSIFICATION_PROMPT,
)

__all__ = [
    "build_classification_prompt",
    "build_hybrid_prompt",
    "CLASSIFICATION_EXAMPLES",
    "DOCUMENT_CLASSIFICATION_PROMPT",
    "HYBRID_CLASSIFICATION_PROMPT",
]
