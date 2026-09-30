"""Schemas for anonymization statistics — Story 1.54 (FR72).

Liczby bez wartości: statystyki operacji anonimizacji (audit log / response
metadata). Nigdy nie zawierają oryginalnych wartości sekretów ani nazw.
"""

from pydantic import BaseModel, ConfigDict, Field


class AnonymizationStats(BaseModel):
    """Counts-only summary of one anonymization run."""

    model_config = ConfigDict(extra="ignore")

    anonymized: bool = Field(description="Czy anonimizacja była aktywna")
    token_count: int = Field(default=0, ge=0, description="Liczba zamaskowanych tokenów")
    secret_count: int = Field(default=0, ge=0, description="Liczba wykrytych sekretów")
    analysis_id: str | None = Field(default=None, description="Powiązana analiza")
