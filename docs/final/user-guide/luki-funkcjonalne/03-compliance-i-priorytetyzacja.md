# Compliance i priorytetyzacja

> Przewodnik P2 — compliance scoring, snapshoty, porównanie wersji.

## Widok Compliance

Dostęp: Project Detail → **"Compliance"** (route: `/projects/:id/compliance`).

### Struktura

1. **Gauge projektu** — okrągły wskaźnik 0–100 z kolorem:
   - 80–100 zielony (dobry)
   - 60–80 żółty (wymaga uwagi)
   - < 60 czerwony (krytyczny)

2. **Tabela modułów** — `ModuleScores` per `file_path`:
   - Sortowanie: po score rosnąco (najgorsze pierwsze) lub po liczbie findings
   - Każdy wiersz: file_path, score, liczba findings, breakdown per typ
   - Klik → drill-down do funkcji w module

3. **Drill-down funkcji** — `FunctionScores` per `code_entity_id`:
   - Jak wyżej + nazwa funkcji

### Interpretacja score

| Score | Interpretacja | Akcja |
|---|---|---|
| 90–100 | Świetnie — drobne ostrzeżenia | Utrzymać |
| 70–90 | Dobrze, ale są luki | Zaplanować w następnym sprincie |
| 50–70 | Mediokre — znaczące braki | Sprint debt / hardening |
| 30–50 | Krytyczne — dużo luk | Stop-feature, focus na compliance |
| 0–30 | Projects in crisis | Eskalacja, audit |

### Breakdown per typ

Dla każdego poziomu (projekt / moduł / funkcja) pokazany jest breakdown:

```
{missing: 4, different: 2, extra: 1, inconsistent: 0}
```

Skup się najpierw na:
1. `missing` z high priority → największy wpływ na biznes
2. `inconsistent` → ryzyko logiczne
3. `different` → często drobne poprawki
4. `extra` → cleanup, niski priorytet

## Eksport CSV

Przycisk **"Eksportuj CSV"** pobiera raport:
- Wiersz nagłówka projektu (nazwa, score, data)
- Wszystkie ModuleScores
- Wszystkie FunctionScores
- Format kompatybilny z Excel / LibreOffice

## Snapshoty i porównanie wersji

### Kiedy powstają snapshoty

- Ręcznie: kliknij **"Utwórz snapshot"** w widoku Compliance
- Automatycznie: po każdej zakończonej analizie luk (post-hook)

### Porównanie v1 ↔ v2

Dostęp: route `/projects/:id/gap-analysis/compare?v1={snap1}&v2={snap2}`.

Widok diff:
- **Fixed** (zielony) — luki rozwiązane między wersjami
- **New** (czerwony) — luki dodane od v1
- **Unchanged** (szary) — bez zmian
- **Worsened** (pomarańczowy) — score się obniżył

### Trend

Route `/projects/:id/compliance/trend` — wykres liniowy:
- Oś X: data snapshotu
- Oś Y: compliance score 0–100
- Pozwala ocenić długoterminowy trend poprawy/degresji

## Priorytetyzacja napraw

### Heurystyka

1. Posortuj findings po:
   - Severity (critical > warning > info)
   - Priorytet wymagania (high > medium > low)
   - Wpływ na compliance penalty (missing+critical = 15 punktów!)
2. Wybierz top 20% findings (zasadą Pareto) do tego sprintu.
3. Po naprawie uruchom ponownie analizę — sprawdź, czy score rośnie.

### Mapowanie severity → akcja

| Severity | gap_type | Akcja | Kiedy |
|---|---|---|---|
| critical | missing | Implementacja | Ten sprint |
| critical | inconsistent | Sync z PO + rozdzielenie | Ten tydzień |
| critical | different | Rewizja implementacji | Ten sprint |
| warning | missing | Implementacja | Następny sprint |
| warning | different | Poprawki jakościowe | Backlog |
| info | extra | Cleanup | Techniczny dług |

### Przykład planu sprintu

Projekt o compliance 62 (30 findings):
- Sprint 1: 5× missing+critical (P1) → oczekiwany score po naprawie: 62 + 75 = 87
- Sprint 2: 3× inconsistent (P1) → score: 87 + 30 = 100 (teoretycznie)
- Sprint 3: 8× different+warning (P2) → utrzymanie 100
- Sprint 4: 14× extra+info (P4) → cleanup

## Następne kroki

- [04 — Rekomendacje i skeleton](04-rekomendacje-i-skeleton.md)
- [02 — Interpretacja wyników](02-interpretacja-wynikow.md)
