# ADR-009: Przepływ przeglądu wygenerowanych elementów

## Status

Accepted

## Kontekst

Wygenerowane przypadki testowe (oraz wyekstrahowane wymagania, glosariusz,
niespójności) mogą nie idealnie odpowiadać standardom projektu. Ręczny przegląd
i edycja są niezbędne przed użyciem wyników. Bez jawnych statusów i śledzenia
decyzji trudno o kontrolę jakości i audyt.

## Decyzja

Jawny **workflow statusów** dla wygenerowanych/ekstrahowanych elementów, z
edycją inline oraz operacjami masowymi:

- **Przypadki testowe (kod):** `draft` → `ready` (po akceptacji) → `passed`/
  `failed` (po uruchomieniu).
- **Wymagania (dokumentacja):** `extracted` → `accepted` / `rejected` / `edited`.
- **Niespójności:** `open` → `accepted` / `false_positive` / `fixed`.
- **Glosariusz:** `is_verified` + `confirmed_mapping_ids` (potwierdzenie
  mapowań na kod).

Mutacje statusów utrwalane w `AnalysisResult.result_data` (JSONB); operacje
masowe (bulk-approve/reject) dla efektywności. Edycja tekstu oznacza
odpowiedni status (`edited`).

## Konsekwencje

**Pozytywne:**

- Kontrola jakości wygenerowanych elementów przed użyciem.
- Pełny ślad decyzji (kto zaakceptował/odrzucił/edytował i dlaczego).
- Operacje masowe zwiększają przepustowość przeglądu.

**Negatywne:**

- Dodatkowy krok w pipeline (przegląd przed gotowością).
- Wymaga zaangażowania recenzentów.
- Może spowolnić pierwsze wdrożenie wyników.

## Powiązane

- [ADR-010](./ADR-010-audit-logging.md) — decyzje przeglądu są logowane audytowo.
- [api/examples/test_cases_examples.md](../api/examples/test_cases_examples.md)
  — endpointy akceptacji/odrzucania.
