# Interpretacja wyników analizy luk

> Przewodnik P2 — jak czytać tabela findings i podejmować decyzje.

## Widok tabeli findings

Po uruchomieniu analizy w `projects/:id/gap-analysis` pojawi się tabela:

| Kolumna | Opis |
|---|---|
| Typ luki | Chip koloru: czerwony (missing), pomarańczowy (different), żółty (extra), fioletowy (inconsistent) |
| Wymaganie | ID wymagań (np. REQ-ANL-004) |
| Treść wymagania | Skrócony tekst wymagania |
| Byt kodu | Nazwa funkcji / metody / klasy |
| Lokalizacja | `file_path:line` |
| Score | 0–100% (jak silne dopasowanie) |
| Metoda | lev, jw, sem, combined |
| Severity | info / warning / critical |

## Filtry

Górny panel filtrów:

- **Typ luki** (MultiSelect) — zawęź do wybranych typów
- **Severity** (MultiSelect) — critical / warning / info
- **Min score** (Slider 0–100) — ukryj findingi poniżej progu
- **Metoda** (Select) — combined / lev / jw / sem

## Klasyfikacje luk — kiedy się pojawiają

### `missing` (czerwony)
**Co znaczy**: wymaganie istnieje, ale kod nie zawiera odpowiadającego bytu.

**Decyzja**:
- Priorytet high/critical → zaplanuj sprint implementation
- Priorytet medium → dodaj do backlog
- Priorytet low → discuss z PO (może nieaktualne wymaganie)

**Akcja**: Kliknij finding → "Generuj skeleton" (jeśli dostępny) → skopiuj kod
do repo → implementuj według spec.

### `different` (pomarańczowy)
**Co znaczy**: kod częściowo spełnia wymaganie (score 30–70).

**Decyzja**:
- Przeczytaj `context` aby zobaczyć, czego dokładnie brakuje
- Jeśli kod jest niekompletny → zaplanuj rozszerzenie
- Jeśli kod jest poprawny, ale nazwa myląca → rename lub popraw docstring

**Akcja**: Kliknij finding → rozwiń panel "Context" → przejrzyj excerpt.

### `extra` (żółty)
**Co znaczy**: byt kodu nie ma odpowiadającego wymagania.

**Decyzja**:
- Kod pomocniczy (utils, helpers) → dodaj tag `@internal` lub pomiń
- Kod z feature creep → discuss z PO: dodać wymaganie czy usunąć?
- Dead code → rozważ usunięcie

**Akcja**: Kliknij finding → "Oznacz jako @internal" (pomija w przyszłych
analizach) lub "Dodaj wymaganie" (tworzy draft wymagania).

### `inconsistent` (fioletowy)
**Co znaczy**: ten sam byt kodu jest mapowany do sprzecznych wymagań.

**Decyzja**:
- **Zawsze critical** — wymaga koordynacji z PO i zespołem
- Przeczytaj oba wymagania — które jest autorytatywne?
- Rozdziel implementację na osobne funkcje, lub ujednolić wymagania

**Akcja**: Kliknij finding → "Zobacz sprzeczne wymagania" → wybierz
dominujące lub utwórz zadanie sync z PO.

## Sortowanie i priorytetyzacja

Domyślnie tabela sortuje po:
1. Severity descending (critical → warning → info)
2. Score ascending (najgorsze dopasowanie pierwsze)
3. Requirement ID

Możesz kliknąć nagłówek kolumny aby zmienić sortowanie. Typowe podejście:

1. **Critical + inconsistent** — natychmiast (P1)
2. **Critical + missing** — ten sprint (P1)
3. **Warning + different** — następny sprint (P2)
4. **Info + extra** — techniczny dług (P4)

## Eksport

Przycisk **"Eksportuj CSV"** w prawym górnym rogu pobiera wszystkie findings
(widoczne po filtrach) jako CSV z kolumnami: `req_id`, `gap_type`, `severity`,
`description`, `file_path`, `line_number`, `score`, `match_method`.

## Panel podsumowania

Górny panel pokazuje:
- **Liczba findings per typ** (4 chipy z licznikami)
- **Średni score** — ogólna jakość dopasowania
- **Coverage %** — procent wymagań z dobrym dopasowaniem
- **Liczba wymagań** — total / zaimplementowanych / brakujących

## Następne kroki

- [03 — Compliance i priorytetyzacja](03-compliance-i-priorytetyzacja.md)
- [04 — Rekomendacje i skeleton](04-rekomendacje-i-skeleton.md)
