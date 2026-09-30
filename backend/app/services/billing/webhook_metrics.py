"""Metryki webhooków płatności — Story 7.3 (AC6, Task 4.1).

Prometheus (scrapowane z ``/metrics``):
- ``webhook_processed_total{provider, type, status}`` — licznik notyfikacji,
- ``webhook_processing_seconds`` — histogram czasu przetwarzania.

Dodatkowo snapshot in-process (endpoint health ``/billing/webhooks/health``
i panel admina): liczniki przetworzonych/odrzuconych/pominiętych, wiek
ostatniego sukcesu oraz seria kolejnych porażek — podstawa alertu
„>3 kolejne nieudane przetworzenia w ciągu 5 minut" (AC6; pełna reguła
Prometheus w README modułu billing — konfiguracja alertmanagera żyje
w infrastrukturze serwera, nie w repo).
"""

import threading
from datetime import UTC, datetime

from prometheus_client import Counter, Histogram

WEBHOOK_PROCESSED_TOTAL = Counter(
    "webhook_processed_total",
    "Webhook notyfikacji tpay przetworzone per typ i status",
    ["provider", "type", "status"],
)
WEBHOOK_PROCESSING_SECONDS = Histogram(
    "webhook_processing_seconds",
    "Czas przetwarzania notyfikacji webhook (sekundy)",
)

# Rodziny statusów do liczników health (AC6): przetworzone / odrzucone / pominięte.
_PROCESSED_STATUSES = {"processed"}
_REJECTED_STATUSES = {"rejected_signature", "rejected_md5", "rejected_payload"}
_SKIPPED_STATUSES = {"skipped", "duplicate", "no_match"}

# AC6: alert przy >3 kolejnych nieudanych przetworzeniach w ciągu 5 minut —
# seria in-process resetowana każdym sukcesem; okno czasowe w regule Prometheusa.
ALERT_CONSECUTIVE_FAILURES = 3

_lock = threading.Lock()
_counters: dict[str, int] = {"processed": 0, "rejected": 0, "skipped": 0, "failed": 0}
_last_success_at: datetime | None = None
_consecutive_failures = 0


def observe(provider: str, notification_type: str, status: str, duration: float) -> None:
    """Zapis pojedynczego przetworzenia: metryki Prometheus + snapshot health."""
    global _last_success_at, _consecutive_failures

    WEBHOOK_PROCESSED_TOTAL.labels(provider=provider, type=notification_type, status=status).inc()
    WEBHOOK_PROCESSING_SECONDS.observe(duration)

    with _lock:
        if status in _PROCESSED_STATUSES:
            _counters["processed"] += 1
            _last_success_at = datetime.now(UTC)
            _consecutive_failures = 0
        elif status in _REJECTED_STATUSES:
            _counters["rejected"] += 1
            # Odrzucenie walidacji to nie awaria pipeline'u — nie podnosi serii.
        elif status in _SKIPPED_STATUSES:
            _counters["skipped"] += 1
        else:  # error — nieudane przetworzenie (tpay ponowi)
            _counters["failed"] += 1
            _consecutive_failures += 1


def snapshot() -> dict:
    """Stan dla endpointu health (AC6): liczniki + wiek ostatniego sukcesu."""
    with _lock:
        last_success = _last_success_at
        consecutive = _consecutive_failures
        counters = dict(_counters)
    return {
        **counters,
        "last_success_age_seconds": ((datetime.now(UTC) - last_success).total_seconds() if last_success else None),
        "consecutive_failures": consecutive,
        # AC6: >3 kolejne nieudane przetworzenia — flaga dla panelu/alerta.
        "alert": consecutive > ALERT_CONSECUTIVE_FAILURES,
    }


def reset() -> None:
    """Czyszczenie snapshotu (testy)."""
    global _last_success_at, _consecutive_failures
    with _lock:
        for key in _counters:
            _counters[key] = 0
        _last_success_at = None
        _consecutive_failures = 0
