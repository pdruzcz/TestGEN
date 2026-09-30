# Przewodnik użytkownika — priorytetyzacja napraw

## 1. Jak liczony jest priorytet

Risk engine sortuje znaleziska po kluczu:

```
(-severity, -confidence, effort, -cvss_score)
```

i przypisuje `priority` (1 = najwyższy). Oznacza to: najpierw najpoważniejsze,
najpewniejsze i najtańsze w naprawie podatności.

## 2. Szacowanie wysiłku (effort)

Mapowanie CWE → effort (`_EFFORT_BY_CWE`):

| Effort | Przykładowe CWE | Charakter naprawy |
|---|---|---|
| low | 89, 79, 352, 22, 798, 1104, 611 | sanityzacja / aktualizacja |
| medium | 78, 94, 502, 668, 918, 200 | refaktoryzacja |
| high | 639, 862 | przeprojektowanie autoryzacji |

## 3. Eskalacja severity

Risk engine podbija severity o 1 poziom, gdy:
- znalezisko ma źródła SAST **i** DAST (potwierdzenie dynamiczne) →
  „Potwierdzona dynamicznie”,
- zależność (DEPENDENCY) ma CVSS ≥ 9.0 → „Zależność z publicznym exploitem”.

Powód eskalacji zapisany jest w `escalation_reason`.

## 4. Sekwencja napraw (dashboard)

```
GET /projects/{project_id}/security-dashboard
```

`repair_sequence` to uporządkowana lista kroków naprawczych — realizuj od
priorytetu 1. Strategia: najpierw critical/high z niskim effort („szybkie
zwycięstwa”), potem kosztowne przeprojektowania.

## 5. Praca z patchami zbiorczymi

Przy naprawie wielu znalezisk w jednym pliku sprawdź konflikty:

```
GET /projects/{project_id}/security-patches/conflicts
POST /projects/{project_id}/security-patches/batch
```

Konflikty oznaczane są jako `critical` (te same linie) lub `warning`
(sąsiadujące) — patrz [rekomendacje i patche](04-rekomendacje-i-patche.md).

## 6. Triage statusu

```
PATCH /projects/{project_id}/security-findings/{finding_id}/status
```

Ustaw `ACKNOWLEDGED`, `FIXED` lub `FALSE_POSITIVE`, aby utrzymać czysty backlog.
