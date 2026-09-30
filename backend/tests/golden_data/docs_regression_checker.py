"""Lekki reporter metryk i detektor regresji — Story 2.11 (AC3).

Zamrożone progi jakości dla natywnej ścieżki analizy dokumentacji. Test
``test_doc_golden_metrics`` agreguje metryki per moduł na wszystkich próbkach
golden i wywołuje ``check_regression`` — pipeline CI fails, gdy jakakolwiek
metryka spadnie poniżej progu.

Celowe minimum (zgodne z istniejącą konwencją golden_data Epic 3/4): brak
pluginu autouse i historii JSONL — agregacja odbywa się w jednym teście
bramkowym, a granularna detekcja regresji w testach parametrycznych per próbka.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

THRESHOLDS_PATH = Path(__file__).parent / "docs_thresholds.json"

# Progi jakości natywnej ścieżki (freeze baseline — dokumenty są czyste i
# projektowane pod wzorce, więc baseline jest wysoki; progi dają margines).
DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "classification": {"accuracy": 0.90},
    "requirement_extraction": {"recall": 0.80, "precision": 0.80},
    "discrepancy_detection": {"recall": 0.80},
    "glossary_extraction": {"recall": 0.80},
}


@dataclass(frozen=True)
class RegressionAlert:
    """Pojedynczy alert regresji: metryka poniżej progu."""

    module: str
    metric: str
    current_value: float
    threshold: float

    @property
    def delta(self) -> float:
        return self.current_value - self.threshold

    def render(self) -> str:
        return (
            f"REGRESJA: {self.module}/{self.metric} = {self.current_value:.2f} "
            f"(próg: {self.threshold:.2f}, delta: {self.delta:+.2f})"
        )


def load_thresholds() -> dict[str, dict[str, float]]:
    """Wczytaj progi z ``docs_thresholds.json`` (fallback na DEFAULT)."""
    if THRESHOLDS_PATH.exists():
        return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    return DEFAULT_THRESHOLDS


def check_regression(
    metrics: dict[str, dict[str, float]],
    thresholds: dict[str, dict[str, float]] | None = None,
) -> list[RegressionAlert]:
    """Porównaj metryki per moduł z progami; zwróć alerty dla spadków."""
    thresholds = thresholds or load_thresholds()
    alerts: list[RegressionAlert] = []
    for module, module_metrics in metrics.items():
        for metric_name, value in module_metrics.items():
            threshold = thresholds.get(module, {}).get(metric_name)
            if threshold is not None and value < threshold:
                alerts.append(
                    RegressionAlert(
                        module=module,
                        metric=metric_name,
                        current_value=value,
                        threshold=threshold,
                    )
                )
    return alerts
