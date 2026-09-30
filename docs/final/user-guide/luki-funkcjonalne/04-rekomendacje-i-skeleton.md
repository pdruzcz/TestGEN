# Rekomendacje i skeleton generator

> Przewodnik P2 — praca z rekomendacjami i generowanie skeleton kodu.

## Widok Rekomendacji

Dostęp: Project Detail → **"Rekomendacje"** (route: `/projects/:id/recommendations`).

### Struktura tabeli

| Kolumna | Opis |
|---|---|
| Priority badge | P1 (czerwony), P2 (pomarańczowy), P3 (żółty), P4 (niebieski) |
| Gap | ID luky powiązanej + typ (chip) |
| Sugerowana akcja | Tekst rekomendacji |
| Confidence | 0–100% + ostrzeżenie jeśli < 50% |
| Effort | S / M / L |
| Source | pochodzenie rekomendacji (badge) |
| Status | open / accepted / applied / dismissed |

### Generowanie rekomendacji

Jeśli lista jest pusta lub chcesz odświeżyć:

1. Kliknij **"Generuj rekomendacje"** w prawym górnym rogu.
2. Potwierdź — backend uruchamia `RecommendationEngine` i persystuje wyniki.
3. Tabela odświeża się automatycznie.

### Akcje na rekomendacji

Kliknij wiersz → panel boczny pokazuje szczegóły + akcje:

- **"Oznacz jako zaakceptowana"** — zmienia status na `accepted` (zespół zatwierdził)
- **"Oznacz jako zastosowana"** — zmienia na `applied` (implementacja ukończona)
- **"Odrzuć"** — status `dismissed` + pole `reason` (wymagane)
- **"Generuj skeleton"** — tworzy plik skeleton (jeśli finding type=missing)
- **"Sync do Jira/ADO"** — tworzy issue w zewnętrznym trackerze

## Skeleton generator

### Kiedy dostępny

Skeleton jest dostępny **tylko** dla findings typu `missing` (gdy wymagane jest
stworzenie nowej funkcji/klasy).

### Generowanie

1. W tabeli findings lub w panelu rekomendacji kliknij **"Generuj skeleton"**.
2. Modal pokazuje:
   - Język (auto-detected z codebase'u projektu)
   - Nazwę funkcji (auto-pochodząca z nazwy wymagania)
   - Podgląd kodu z syntax highlighting
3. Akcje:
   - **"Kopiuj do schowka"** — skopiuj kod
   - **"Pobierz plik"** — pobierz `.py` / `.ts` / `.java` / `.cs`
   - **"Otwórz w edytorze"** — wskaż miejsce docelowe

### Przykład

Dla wymagania `REQ-ANL-004: "System must export an analytics report to PDF"`:

```python
"""TODO: System must export an analytics report to PDF

Requirement ID: REQ-ANL-004
Priority: low
Generated from gap analysis — do not edit this header.
"""


def export_pdf_report(data):
    """System must export an analytics report to PDF."""
    raise NotImplementedError(
        "Skeleton for REQ-ANL-004 — implement per spec."
    )
```

### Walidacja

Skeleton jest walidowany przez tree-sitter przed zwróceniem. Gdyby szablon
wygenerował niepoprawną składnię, backend zwróci HTTP 422 z informacją.

## Tryby pracy z rekomendacjami

### Workflow 1: Developer samodzielnie

1. Uruchom analizę po implementacji feature'a.
2. Przejrzyj P1 / P2 rekomendacje.
3. Zaakceptuj / zastosuj / odrzuć.
4. Generuj skeleton dla brakujących funkcji.
5. Commit + powtórz.

### Workflow 2: Zespół z PO

1. Po każdym sprincie uruchom analizę luk.
2. Wyeksportuj rekomendacje do CSV.
3. Na planningu omów P1 — wymagają decyzji biznesowej.
4. Zaplanuj P2 / P3 do sprintu.
5. Oznacz w UI statusy.

### Workflow 3: Automatyzacja z Jira

1. Skonfiguruj integrację Jira (patrz [05 — Integracje](05-integracje-trackery.md)).
2. Po analizie kliknij **"Sync do Jira"** — wszystkie P1 tworzą issues.
3. Zespół pracuje w Jira — zmiany statusów w TestGEN po ponownym sync.

## Konfidencja rekomendacji

- **≥ 0.8** — wysoka ufność (czerwony/zielony check)
- **0.5–0.8** — średnia (żółty)
- **< 0.5** — niska, ostrzeżenie (czerwony alert)

Rekomendacje z niską ufnością wymagają weryfikacji człowieka przed
wprowadzeniem zmian.

## Następne kroki

- [05 — Integracje z trackerami](05-integracje-trackery.md)
- [03 — Compliance](03-compliance-i-priorytetyzacja.md)
