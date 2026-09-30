# Dokumentacja modułów AI TestGEN (M1–M6)

> **Wersja:** 1.0 · **Ostatnia aktualizacja:** 2026-09 · **Grupa docelowa:** Deweloperzy platformy, architekci AI

---

## Spis treści

1. [Wprowadzenie](#1-wprowadzenie)
2. [M1 — Analiza kodu źródłowego](#2-m1--analiza-kodu-źródłowego)
3. [M2 — Analiza dokumentacji](#3-m2--analiza-dokumentacji)
4. [M3 — Analiza UML](#4-m3--analiza-uml)
5. [M4 — Analiza GUI](#5-m4--analiza-gui)
6. [M5 — Generowanie testów](#6-m5--generowanie-testów)
7. [M6 — Analiza bezpieczeństwa](#7-m6--analiza-bezpieczeństwa)
8. [Porównanie zbiorcze modułów](#8-porównanie-zbiorcze-modułów)
9. [LLM Gateway — warstwa abstrakcji](#9-llm-gateway--warstwa-abstrakcji)
10. [Optymalizacja i koszty](#10-optymalizacja-i-koszty)

---

## 1. Wprowadzenie

### 1.1. Cel dokumentu

Dokument opisuje sześć modułów AI platformy TestGEN z perspektywy dewelopera:
- Architektura dual-path (native vs LLM vs hybrid)
- Prompty systemowe i użytkownika z parametrami
- Benchmarki jakości (golden test data, metryki)
- Rekomendacje doboru trybu silnika
- Znane ograniczenia i edge case'y

### 1.2. Architektura dual-path

Każdy moduł analityczny implementuje wzorzec **dual-path engine** (patrz [ADR-006](../architecture/adr/ADR-006-jinja2-template-engine.md), [architektura C4 Level 4](../architecture/architecture.md#51-dual-path-engine--wzorzec-strategii)):

```
          ┌─────────────────┐
          │  AnalysisEngine  │
          │ (engine_mode)    │
          └────────┬─────────┘
                   │
      ┌────────────┼────────────┐
      ▼            ▼            ▼
  ┌────────┐  ┌────────┐  ┌──────────┐
  │ Native │  │  LLM   │  │  Hybrid  │
  │Strategy│  │Strategy│  │ Strategy │
  └────────┘  └────────┘  └──────────┘
     AST/NLP    API LLM     Native+LLM
     reguły     semantyka    + Merger
```

| Tryb | Opis | Koszt | Opóźnienie |
|------|------|-------|------------|
| `native` | Deterministyczny — AST, NLP, reguły, szablony | 0 PLN | < 5 s |
| `llm` | Semantyczny — model językowy (Anthropic/OpenAI) | 0,05–0,50 PLN/analiza | 5–30 s |
| `hybrid` | Native + LLM + scalenie wyników (ResultMerger) | Jak LLM | 5–35 s |

### 1.3. LLM Providers

| Dostawca | Model domyślny | Model zapasowy | Koszt (input / output per 1M tokenów) |
|----------|----------------|----------------|---------------------------------------|
| Anthropic | `claude-sonnet-4-20250514` | — | $3,00 / $15,00 |
| OpenAI | `gpt-4o` | `gpt-4o-mini` (fallback na 5xx) | $5,00 / $15,00 |
| OpenAI (mini) | `gpt-4o-mini` | — | $0,15 / $0,60 |

Dostawca konfigurowany zmienną środowiskową `LLM_PROVIDER`. Domyślny: `anthropic`.

### 1.4. Prompt Manager

System zarządzania promptami (`services/analysis/prompt_manager.py`):
- Prompty ładowane z plików YAML (`backend/app/prompts/*.yaml`)
- Renderowanie zmiennych via Jinja2
- Wersjonowanie: `v1` (stable) / `v2` (latest)
- Routing A/B: `sha256(name:tenant_id) % 100 < ab_test_percentage`
- Pozwala na ewolucję promptów bez zmian w kodzie

---

## 2. M1 — Analiza kodu źródłowego

### 2.1. Cel i zakres

Moduł M1 parsuje i analizuje kod źródłowy — ekstrakcja struktury (klasy, funkcje, importy), złożoności cyklomatycznej, zależności modułów, przepływów danych i logiki biznesowej.

**Lokalizacja w kodzie:** `backend/app/services/analysis/`

### 2.2. Obsługiwane języki

| Język | Parser | Adapter | Status |
|-------|--------|---------|--------|
| Python | tree-sitter-python | `ast/python_adapter.py` | Pełne wsparcie |
| Java | tree-sitter-java | `ast/java_adapter.py` | Pełne wsparcie |
| JavaScript | tree-sitter-javascript | `ast/javascript_adapter.py` | Pełne wsparcie |
| TypeScript | tree-sitter-typescript | `ast/typescript_adapter.py` | Pełne wsparcie |
| C# | tree-sitter-c-sharp | `ast/csharp_adapter.py` | Pełne wsparcie |
| C | tree-sitter-c | `ast/c_adapter.py` | Pełne wsparcie |
| C++ | tree-sitter-cpp | `ast/cpp_adapter.py` | Pełne wsparcie |
| PHP | tree-sitter-php | `ast/php_adapter.py` | Pełne wsparcie |

### 2.3. Architektura native (AST)

Ścieżka deterministyczna wykorzystuje tree-sitter do parsowania kodu do drzewa AST:

1. **Parsowanie** — tree-sitter buduje AST w < 50 ms per plik
2. **Ekstrakcja** — adapter językowy wyciąga elementy (klasy, funkcje, importy, dekoratory, docstringi)
3. **Analiza**:
   - Złożoność cyklomatyczna (McCabe)
   - Zależności modułów (import graph)
   - Struktury logiczne (warunki, pętle, zagnieżdżenia)
   - Przepływ danych (zmienne, przypisania, zwracane wartości)
4. **Wynik** — JSON z listą klas/funkcji + metryki

**Zalety:** deterministyczny, powtarzalny, zerowy koszt, szybki  
**Ograniczenia:** nie rozumie semantyki biznesowej, nie wykrywa intencji

### 2.4. Architektura LLM

Ścieżka semantyczna wykorzystuje model językowy do głębszej analizy:

**Orkiestrator:** `LLMAnalysisOrchestrator` (`llm_analysis.py`) — 4 zadania per plik:

| Zadanie | task_type | Opis |
|---------|-----------|------|
| Podsumowanie | `code_summary` | Opis co robi kod, główna logika |
| Intencja | `intent_extraction` | Jaki problem rozwiązuje, dlaczego istnieje |
| Ryzyko | `risk_assessment` | Potencjalne problemy, edge case'y |
| Wgląd | (heurystyczny) | Metryki: rozmiar pliku, głębokość zagnieżdżenia |

### 2.5. Prompty

**Prompt v1** (`prompts/code_analysis_v1.yaml`):

```yaml
name: code_analysis.extract_functions
version: v1
model: claude-sonnet-4-20250514
max_tokens: 4096
temperature: 0.3

system: |
  You are a code analysis assistant.
  Extract function definitions from the source code.
  Return a JSON array of objects.

user: |
  Analyze this {{ language }} file: {{ filename }}

  ```{{ language }}
  {{ content }}
  ```

  Return JSON array: [{name, line_start, line_end,
  parameters, return_type, decorators, docstring, complexity}]
```

**Prompt v2** (A/B test — 10% ruchu):

```yaml
name: code_analysis.extract_functions
version: v2
ab_test_percentage: 10
# Dodatkowe zmienne: framework (opcjonalne)
# Dodatkowe pola wyjściowe: side_effects, calls (graf wywołań)
```

**Parametry domyślne:**
- `temperature: 0.3` — niższa = bardziej deterministyczny wynik
- `max_tokens: 4096`
- Kod obcinany do 2000 znaków per wywołanie (`code[:2000]`)

### 2.6. Golden test data

Dane wzorcowe przechowywane w `backend/tests/golden_data/`.

**Przykład — analiza funkcji Python:**

| Kryterium | Wartość |
|-----------|---------|
| **Wejście** | Klasa `UserService` z metodami `create_user()`, `validate_email()`, `hash_password()` |
| **Native (AST)** | 3 funkcje, parametry, typy, złożoność McCabe: 4, 2, 1 |
| **LLM** | 3 funkcje + opis intencji: „Serwis zarządzania użytkownikami z walidacją i bezpiecznym haszowaniem" |
| **Hybrid** | AST + LLM intencja — pełna ekstrakcja + kontekst semantyczny |

### 2.7. Metryki benchmarkowe

| Metryka | Native (AST) | LLM | Hybrid |
|---------|-------------|-----|--------|
| Ekstrakcja funkcji (accuracy) | 99,5% | 96% | 99,5% |
| Ekstrakcja parametrów (precision) | 99% | 94% | 99% |
| Rozumienie intencji (recall) | 20% | 85% | 87% |
| Średni czas (ms / plik) | 45 | 3500 | 3600 |
| Koszt (PLN / 100 plików) | 0 | ~15 | ~15 |

> **Uwaga:** Analiza AST jest deterministyczna — regresja weryfikowana zamrożonymi wynikami golden data. Metryki LLM mogą się różnić między modelami i wersjami.

### 2.8. Rekomendacje

| Scenariusz | Rekomendowany tryb |
|------------|-------------------|
| Standardowa analiza (CI/CD, duże repo) | `native` |
| Zrozumienie logiki biznesowej, dokumentacja | `llm` |
| Maksymalne pokrycie (krytyczny projekt) | `hybrid` |
| Ograniczony budżet | `native` |

### 2.9. Znane ograniczenia

- **Rozmiar pliku:** > 100 KB obcinane do 2000 znaków (LLM) lub parsowane z ograniczeniem pamięci (AST)
- **Komentarze w kodzie:** AST ignoruje komentarze; LLM je interpretuje
- **Metaprogramowanie:** dekoratory, refleksja, dynamiczne importy — ograniczona dokładność w native
- **Minifikowany kod:** tree-sitter parsuje poprawnie, ale LLM ma trudności z brakiem formatowania

---

## 3. M2 — Analiza dokumentacji

### 3.1. Cel i zakres

Moduł M2 parsuje dokumenty (PDF, DOCX, HTML, MD, TXT), klasyfikuje ich typ, ekstrahuje wymagania (funkcjonalne i niefunkcjonalne), buduje glosariusz i wykrywa niespójności.

**Lokalizacja w kodzie:** `backend/app/services/analysis/document/`

### 3.2. Obsługiwane formaty

| Format | Parser | Uwagi |
|--------|--------|-------|
| PDF | pdfplumber | Tekst, tabele, metadane; OCR dla skanów |
| DOCX | python-docx | Nagłówki, tekst, tabele, style |
| HTML | BeautifulSoup | Struktura DOM, tekst, linki |
| Markdown | markdown-it | Nagłówki, listy, tabele |
| TXT | wbudowany | Czysty tekst |

### 3.3. Architektura native (NLP)

1. **Parsowanie** — parser formatu wyciąga tekst i strukturę
2. **Klasyfikacja** — reguły NLP (wzorce, słowa kluczowe) → typ dokumentu
3. **Ekstrakcja wymagań** — regex + heurystyki: zdania „system powinien/musi/ma"
4. **Glosariusz** — detekcja definicji: „X oznacza Y", tabele definicji
5. **Niespójności** — porównanie wymagań między dokumentami: sprzeczne, zduplikowane

### 3.4. Prompty LLM

**Klasyfikacja dokumentu** (`analysis/llm/prompts/classification.py`):

```python
DOCUMENT_CLASSIFICATION_PROMPT = """
Jesteś ekspertem od analizy dokumentów technicznych.
Przeanalizuj poniższy fragment dokumentu i sklasyfikuj go.

Dostępne typy:
- specyfikacja_wymagań
- podręcznik_użytkownika
- instrukcja_techniczna
- opis_api
- notatki_projektowe
- inny

Odpowiedz WYŁĄCZNIE poprawnym JSON:
{"type": "...", "confidence": 0.0-1.0, "reasoning": "..."}

Dokument (maks. 8000 znaków):
{content}
"""
```

**Ekstrakcja wymagań** (`analysis/llm/prompts/requirement_extraction.py`):

```python
REQUIREMENT_EXTRACTION_PROMPT = """
Jesteś ekspertem od analizy wymagań.
Wyodrębnij wymagania z poniższego tekstu.
Zwróć JSON: {"requirements": [
  {"text": "...", "type": "functional|non_functional",
   "priority": "high|medium|low", "reasoning": "..."}
]}
Maks. 50 wymagań na fragment. Dokument (maks. 8000 znaków):
{content}
"""
```

**Arbitraż hybrid** (klasyfikacja):

```python
HYBRID_CLASSIFICATION_PROMPT = """
Jesteś arbitrem. Dwa systemy sklasyfikowały dokument:
- Native (NLP): typ={native_type}, confidence={native_confidence}
- LLM: typ={llm_type}, confidence={llm_confidence}, reasoning={llm_reasoning}
Rozstrzygnij i podaj ostateczną klasyfikację.
JSON: {"type": "...", "confidence": 0.0-1.0, "reasoning": "..."}
"""
```

**Scalanie wymagań hybrid:**

```python
HYBRID_MERGE_PROMPT = """
Scal dwie listy wymagań (native + LLM).
Reguły: podobieństwo > 80% = duplikat, source: native|llm|both.
"""
```

**Parametry:**
- `temperature: 0.2` (klasyfikacja) / `0.3` (ekstrakcja)
- `max_tokens: 4096`
- Maksymalna długość treści: 8000 znaków (obcinane z adnotacją)

### 3.5. Golden test data

10 dokumentów polskojęzycznych:
- 4× PDF, 3× DOCX, 2× MD, 1× HTML
- 5 dokumentów spójnych + 5 z celowymi niespójnościami

| Plik | Typ | Wymagań | Niespójności |
|------|-----|---------|-------------|
| `spec-01.pdf` | specyfikacja_wymagań | 23 FR, 8 NFR | 0 |
| `spec-02.docx` | specyfikacja_wymagań | 15 FR, 5 NFR | 3 sprzeczne |
| `api-01.md` | opis_api | 8 FR | 0 |
| `user-guide.pdf` | podręcznik_użytkownika | 0 | 0 |
| `notes.html` | notatki_projektowe | 5 FR | 2 brakujące |

### 3.6. Metryki benchmarkowe

| Metryka | Native (NLP) | LLM | Hybrid | Próg |
|---------|-------------|-----|--------|------|
| Klasyfikacja (accuracy) | ≥ 80% | ≥ 90% | ≥ 95% | ≥ 90% |
| Ekstrakcja wymagań (recall) | ≥ 80% | ≥ 85% | ≥ 90% | ≥ 80% |
| Ekstrakcja wymagań (precision) | ≥ 85% | ≥ 80% | ≥ 85% | ≥ 80% |
| Wykrywanie niespójności (recall) | ≥ 70% | ≥ 85% | ≥ 90% | ≥ 80% |
| Glosariusz (recall) | ≥ 80% | ≥ 85% | ≥ 90% | ≥ 80% |
| Średni czas (s / dokument) | < 2 | 5–15 | 6–18 | — |

### 3.7. Rekomendacje

| Scenariusz | Tryb |
|------------|------|
| Dobrze sformatowane dokumenty (nagłówki, tabele) | `native` |
| Dokumenty narracyjne, wieloznaczne | `llm` |
| Audyt wymagań (krytyczny) | `hybrid` |
| Dokumenty wielojęzyczne | `llm` |

### 3.8. Znane ograniczenia

- **OCR:** jakość ekstrakcji z zeskanowanych PDF zależy od rozdzielczości (min. 300 DPI)
- **Tabele w PDF:** pdfplumber radzi sobie z prostymi tabelami; złożone (merge cells) mogą dawać błędy
- **Język:** native NLP zoptymalizowany pod polski; inne języki wymagają trybu LLM
- **Rozmiar:** dokumenty > 100 stron dzielone na chunki (max 8000 znaków per wywołanie LLM)

---

## 4. M3 — Analiza UML

### 4.1. Cel i zakres

Moduł M3 parsuje diagramy UML (klasy, sekwencje, przypadki użycia, maszyny stanów, aktywności) i ekstreahuje elementy modelowe do dalszej analizy i generowania testów.

**Lokalizacja w kodzie:** `backend/app/services/analysis/uml/`

### 4.2. Obsługiwane formaty

| Format | Parser | Typy diagramów |
|--------|--------|----------------|
| XMI | lxml (XML) | Klasy, sekwencje, use-case, stany, aktywności |
| PlantUML | Regex parser | Klasy, sekwencje, use-case, stany |
| SVG | SVG parser + OCR | Wizualne rozpoznawanie elementów |
| PNG/JPG | OCR (Tesseract) + CV | Rozpoznawanie z obrazów rastrowych |

### 4.3. Architektura native

1. **XMI Parser** — ekstrakcja elementów z formatu XMI (eksport z Enterprise Architect, StarUML, etc.)
2. **PlantUML Parser** — parsowanie składni PlantUML za pomocą wyrażeń regularnych
3. **Visual Parser** — OCR + computer vision dla obrazów diagramów
4. **Analizatory per typ:**
   - Class Diagram → relacje, dziedziczenie, kompozycja
   - Sequence Diagram → przepływy, komunikaty, lifeline'y
   - Use-Case → aktorzy, scenariusze, include/extend
   - State Machine → przejścia, warunki, akcje
5. **Cross-Diagram Analyzer** — korelacja między diagramami (spójność nazw, pokrycie)

### 4.4. Prompty LLM

**Rekonstrukcja przepływów:**

```
System: You are a UML analysis expert.
Given the following UML diagram elements, reconstruct the
behavioral flows. Identify: actors, actions, transitions,
conditions, and exception paths.

Parameters: temperature=0.1, max_tokens=4096
```

**Uzupełnienie brakujących elementów (hybrid):**
LLM otrzymuje wyniki native (lista elementów) i uzupełnia: brakujące relacje, niejawne przejścia, edge case'y w maszynach stanów.

### 4.5. Metryki benchmarkowe

| Metryka | Native (parser) | LLM | Hybrid |
|---------|----------------|-----|--------|
| Ekstrakcja elementów z XMI (precision) | 98% | 90% | 98% |
| Ekstrakcja elementów z PlantUML (precision) | 95% | 92% | 96% |
| Rozpoznawanie z obrazów (accuracy) | 60–70% | 80–85% | 82–87% |
| Wykrywanie relacji (recall) | 90% | 85% | 93% |
| Średni czas (s / diagram) | < 1 | 3–10 | 4–12 |

### 4.6. Rekomendacje

| Scenariusz | Tryb |
|------------|------|
| Diagramy w XMI / PlantUML (tekst) | `native` |
| Diagramy jako obrazy (skan, zrzut ekranu) | `llm` lub `hybrid` |
| Cross-diagram analysis (wiele diagramów) | `hybrid` |

### 4.7. Znane ograniczenia

- **Obrazy rastrowe:** rozdzielczość < 150 DPI → znaczący spadek dokładności OCR
- **Ręcznie rysowane diagramy:** OCR nie radzi sobie z odręcznymi szkicami
- **PlantUML:** parser regex nie obsługuje zaawansowanych makr i include'ów
- **Typy diagramów:** component i deployment diagrams — ograniczone wsparcie

---

## 5. M4 — Analiza GUI

### 5.1. Cel i zakres

Moduł M4 analizuje zrzuty ekranu interfejsów graficznych — rozpoznaje elementy UI, rekonstruuje przepływy użytkownika i wykrywa regresje wizualne.

**Lokalizacja w kodzie:** `backend/app/services/analysis/gui/`

### 5.2. Architektura native (CV/OCR)

1. **OCR Engine** (Tesseract) — rozpoznawanie tekstu z elementów GUI
2. **DOM Extractor** (Selenium) — ekstrakcja struktury DOM z live stron webowych
3. **Component Detector** (OpenCV) — identyfikacja elementów: przyciski, formularze, tabele, menu, nawigacja
4. **Flow Reconstructor** — rekonstrukcja przepływów użytkownika z sekwencji ekranów
5. **Visual Regression** (pixelmatch) — porównanie wizualne między wersjami UI

### 5.3. Prompty LLM (vision)

**Identyfikacja elementów GUI:**

```
System: Jesteś ekspertem UX/UI. Przeanalizuj zrzut ekranu
i zidentyfikuj elementy interfejsu.

User: [obraz]
Zidentyfikuj: przyciski (tekst, pozycja), pola formularzy
(etykiety, typy), nawigację, tabele, komunikaty.
Zwróć JSON: [{type, label, position, interactable}]

Parameters: temperature=0.1, max_tokens=4096
```

### 5.4. Metryki benchmarkowe

| Metryka | Native (CV/OCR) | LLM (vision) | Hybrid |
|---------|-----------------|--------------|--------|
| Detekcja przycisków (precision) | 75% | 90% | 92% |
| Detekcja pól formularzy (precision) | 70% | 88% | 90% |
| OCR tekstu (accuracy) | 85% | 95% | 95% |
| Rekonstrukcja przepływu (completeness) | 60% | 80% | 83% |
| Regresja wizualna (sensitivity) | 95% | — | 95% |
| Średni czas (s / ekran) | 2–5 | 5–15 | 7–20 |

### 5.5. Rekomendacje

| Scenariusz | Tryb |
|------------|------|
| Regresja wizualna (porównanie wersji) | `native` (pixelmatch) |
| Rozpoznawanie elementów (nowy ekran) | `hybrid` |
| Ekstrakcja DOM z live strony | `native` (Selenium) |

### 5.6. Znane ograniczenia

- **Rozdzielczość:** obrazy < 720p → spadek dokładności detekcji
- **Nakładające się elementy:** modalne okna, tooltipy, dropdowny — mogą być pominięte
- **Dynamiczne treści:** animacje, lazy loading — wymagają stabilnego zrzutu
- **Ciemne motywy:** OCR ma niższą dokładność na ciemnych tłach (poprawa w toku)

---

## 6. M5 — Generowanie testów

### 6.1. Cel i zakres

Moduł M5 generuje przypadki testowe i kod testowy na podstawie wyników analiz z modułów M1–M4. Obsługuje 12 frameworków testowych.

**Lokalizacja w kodzie:** `backend/app/services/test_generation/` i `backend/app/services/generators/`

### 6.2. Architektura

| Komponent | Ścieżka | Technologia |
|-----------|---------|-------------|
| Test Case Generator | `test_generation/` | Native (reguły) + LLM (semantyczne) |
| Code Generator | `generators/` + `test_generation/codegen/` | **Wyłącznie native** (Jinja2 szablony) |
| Gherkin/BDD | `test_generation/gherkin_generator.py` | Native + opcjonalne LLM enrichment |

> **Ważne:** Generowanie kodu testowego (pytest, JUnit, Playwright, etc.) jest w pełni natywne — nie wymaga API LLM. Jedynie generowanie przypadków testowych (opis, kroki, oczekiwane wyniki) korzysta opcjonalnie z LLM.

### 6.3. Obsługiwane frameworki

| Kategoria | Framework | Język | Generator |
|-----------|-----------|-------|-----------|
| Jednostkowe | pytest | Python | `generators/pytest_generator.py` |
| Jednostkowe | JUnit 5 | Java | `generators/junit_generator.py` |
| Jednostkowe | NUnit | C# | `generators/nunit_generator.py` |
| Jednostkowe | Mocha/Jest | JS/TS | `generators/mocha_generator.py` |
| Jednostkowe | PHPUnit | PHP | `generators/phpunit_generator.py` |
| E2E Web | Playwright | Python/JS/TS | `generators/playwright_generator.py` |
| E2E Web | Cypress | JavaScript | `generators/cypress_generator.py` |
| E2E Web | Selenium | Python/Java/C# | `generators/selenium_generator.py` |
| E2E Mobile | Appium | Python/Java | `generators/appium_generator.py` |
| Desktop GUI | SikuliX | Java (image-based) | `generators/sikulix_generator.py` |
| Baza danych | Database tests | SQL | `generators/database_generator.py` |

### 6.4. Prompty LLM

**Generowanie przypadków testowych:**

```
System: You are a QA expert. Generate test cases from the
analysis results. For each test case provide: title, priority
(critical/high/medium/low), preconditions, steps, expected results.

User: Analysis results for {project_name}:
{analysis_results_json}

Generate comprehensive test cases covering:
- Happy path
- Edge cases
- Error handling
- Boundary values

Parameters: temperature=0.3, max_tokens=8192
```

**Wzbogacanie Gherkin (opcjonalne LLM enrichment):**

```python
# Prompt (polski):
"Jesteś ekspertem QA. Poniżej znajduje się szkic scenariuszy
Gherkin/BDD wygenerowany automatycznie. Wzbogać opisy kroków
i dodaj realistyczne dane testowe, zachowując składnię Gherkin."

# Fallback: jeśli LLM nie zwróci słowa kluczowego "Feature:",
# system wraca do wyników native z ostrzeżeniem.
```

### 6.5. Metryki benchmarkowe

| Metryka | Native (szablony) | LLM | Hybrid |
|---------|------------------|-----|--------|
| Pokrycie scenariuszy (completeness) | 70% | 90% | 93% |
| Poprawność kroków (correctness) | 95% | 85% | 90% |
| Pokrycie edge case'ów | 40% | 80% | 82% |
| Jakość kodu testowego (compiles) | 98% | — | 98% |
| Średni czas (s / analiza) | < 3 | 10–30 | 12–35 |

> **Uwaga:** Kod testowy generowany jest wyłącznie natywnie (Jinja2) — metryka `compiles` dotyczy tylko ścieżki native.

### 6.6. Rekomendacje

| Scenariusz | Tryb |
|------------|------|
| Szybkie generowanie kodu testowego | `native` |
| Kompleksowe przypadki testowe | `hybrid` |
| Edge case'y, scenariusze negatywne | `llm` |
| CI/CD pipeline (automatyzacja) | `native` |

### 6.7. Znane ograniczenia

- **Szablony:** native generuje „szkieletowy" kod — może wymagać ręcznej edycji asercji
- **Kontekst:** LLM widzi max 8192 tokenów — duże analizy dzielone na chunki
- **SikuliX:** wymaga referencyjnych obrazów ekranów (nie generowane automatycznie)
- **Appium:** wymaga konfiguracji capabilities per urządzenie

---

## 7. M6 — Analiza bezpieczeństwa

### 7.1. Cel i zakres

Moduł M6 skanuje kod pod kątem podatności bezpieczeństwa: SAST, taint analysis, skanowanie zależności, analiza konfiguracji. Generuje raporty z klasyfikacją CVSS i SBOM.

**Lokalizacja w kodzie:** `backend/app/services/security_scan/`

**Bramka funkcji:** moduł dostępny wyłącznie w planie **Premium**.

### 7.2. Architektura dual-path

**Orkiestrator:** `SecurityDualPathOrchestrator` (`dual_path_orchestrator.py`)

W trybie `hybrid`:
- Native = baza autorytatywna
- LLM wzbogaca: lepsza rekomendacja (dłuższa), uzupełnia brakujące opisy
- Współdzielone znaleziska: boost confidence +0.1
- Raport porównawczy: diagram Venna (native only / LLM only / both)

### 7.3. Komponenty native

| Komponent | Narzędzie | Cel |
|-----------|-----------|-----|
| SAST Scanner | Reguły Semgrep/Bandit | Statyczna analiza wzorców podatności |
| Taint Analysis | Analiza przepływu danych | SQL injection, XSS, path traversal |
| Dependency Scanner | Baza CVE (NVD/GitHub/OSV) | Znane podatności w zależnościach |
| Config Scanner | Reguły konfiguracji | Sekrety w kodzie, brakujący hardening |

### 7.4. Prompty LLM

**LLM SAST** (`llm_security/llm_sast.py`):

```python
# Provider: anthropic, temperature=0.0, max_tokens=1500
# Kod obcinany do 6000 znaków, max 20 plików

"""
Jesteś ekspertem bezpieczeństwa aplikacji. Przeanalizuj poniższy
kod ({lang}) pod kątem podatności, których NIE wykrywają proste
reguły: błędów logicznych, brakujących kontroli dostępu,
mass assignment, race conditions, TOCTOU.

Zwróć WYŁĄCZNIE JSON:
[{
  "vulnerability_type": "...",
  "severity": "critical|high|medium|low",
  "line_start": N,
  "description": "...",
  "cwe_id": "CWE-XXX",
  "recommendation": "..."
}]
"""
```

**LLM Taint** (`llm_security/llm_taint.py`):

```python
# Provider: anthropic, temperature=0.0, max_tokens=1500
# Max 6000 znaków, max 15 plików

"""
Śledź przepływ danych od źródeł (request, params, body)
do ujść (SQL, exec, eval, system, render) — w tym przepływy
międzyfunkcyjne. Zwróć JSON:
[{vulnerability_type, severity, line_start, description,
  source, sink, cwe_id}]
"""
```

**LLM Config** (`llm_security/llm_config.py`):

```python
# Provider: anthropic, temperature=0.0, max_tokens=1500
# Max 4000 znaków per plik, max 12 plików

"""
Holistyczny przegląd konfiguracji Docker/K8s/Terraform.
Szukaj ryzyk wynikających z KOMBINACJI ustawień.
JSON: [{vulnerability_type, severity, line_start,
  description, recommendation}]
"""
```

**Confidence LLM:** stała wartość 0.6 dla wszystkich znalezisk LLM (niższa niż native ~0.8–0.95).

### 7.5. Golden test data

| Przykład | Język | Podatność | CWE | Oczekiwane |
|----------|-------|-----------|-----|-----------|
| SQL injection (format string) | Python | SQLi | CWE-89 | Native: ✓ (reguła), LLM: ✓ |
| XSS (reflected) | JavaScript | XSS | CWE-79 | Native: ✓, LLM: ✓ |
| Race condition (TOCTOU) | Python | TOCTOU | CWE-367 | Native: ✗, LLM: ✓ |
| Mass assignment (unvalidated) | Python | Mass assign | CWE-915 | Native: ✗, LLM: ✓ |
| Hardcoded secret | Java | Secrets | CWE-798 | Native: ✓, LLM: ✓ |

### 7.6. Metryki benchmarkowe

| Metryka | Native (reguły) | LLM | Hybrid |
|---------|----------------|-----|--------|
| True positives (TP) | 85% | 75% | 92% |
| False positives (FP) | 5% | 15% | 8% |
| False negatives (FN) | 15% | 25% | 8% |
| Precision | 94% | 83% | 92% |
| Recall | 85% | 75% | 92% |
| F1-score | 0,89 | 0,79 | 0,92 |
| Średni czas (s / projekt) | 5–15 | 10–30 | 15–45 |

> **Uwaga:** Native wykrywa znane wzorce z wysoką precyzją; LLM wykrywa logiczne podatności (TOCTOU, mass assignment), ale generuje więcej false positives. Hybrid łączy zalety obu.

### 7.7. Rekomendacje

| Scenariusz | Tryb |
|------------|------|
| Szybkie skanowanie (CI/CD gate) | `native` |
| Pełny audyt bezpieczeństwa | `hybrid` |
| Wykrywanie logicznych podatności | `llm` |
| Compliance (OWASP Top 10) | `hybrid` |

### 7.8. Znane ograniczenia

- **False positives (LLM):** ~15% — wymagają ręcznej weryfikacji
- **Złożone wzorce:** wieloplikowe przepływy danych (> 3 pliki) — ograniczone okno kontekstu LLM
- **Dynamiczne języki:** Python, JavaScript — trudniejsza analiza taint niż języki typowane
- **CVE pipeline:** aktualizacja bazy zależy od zewnętrznych źródeł (NVD może mieć opóźnienia)

---

## 8. Porównanie zbiorcze modułów

### 8.1. Tabela zbiorcza: Native vs LLM vs Hybrid

| Moduł | Native — główna zaleta | LLM — główna zaleta | Hybrid — główna zaleta |
|-------|----------------------|---------------------|----------------------|
| M1 (Kod) | 99,5% accuracy AST | Intencja i semantyka | Pełna ekstrakcja + kontekst |
| M2 (Dokumenty) | Szybkie, deterministyczne | Rozumienie narracji | Arbitraż klasyfikacji |
| M3 (UML) | 98% precision XMI | Obrazy i niekompletne diagramy | Cross-diagram + wzbogacenie |
| M4 (GUI) | Regresja wizualna | Rozpoznawanie z obrazów | Detekcja + kontekst |
| M5 (Testy) | 98% compilable code | Edge case'y, scenariusze | Kompletność + poprawność |
| M6 (Security) | Wysokie precision (94%) | Logiczne podatności | Najwyższy recall (92%) |

### 8.2. Estymacja kosztów API per 100 analiz

| Moduł | Native | LLM (Anthropic) | LLM (OpenAI) | Hybrid |
|-------|--------|------------------|--------------|--------|
| M1 (Kod) | 0 PLN | ~15 PLN | ~25 PLN | ~15 PLN |
| M2 (Dokumenty) | 0 PLN | ~10 PLN | ~17 PLN | ~10 PLN |
| M3 (UML) | 0 PLN | ~8 PLN | ~13 PLN | ~8 PLN |
| M4 (GUI) | 0 PLN | ~20 PLN | ~33 PLN | ~20 PLN |
| M5 (Testy) | 0 PLN | ~25 PLN | ~42 PLN | ~25 PLN |
| M6 (Security) | 0 PLN | ~12 PLN | ~20 PLN | ~12 PLN |
| **Razem** | **0 PLN** | **~90 PLN** | **~150 PLN** | **~90 PLN** |

> Koszty estymowane na podstawie średniego zużycia tokenów per analiza i cennika na 2026-09. Rzeczywiste koszty zależą od rozmiaru kodu, złożoności dokumentów i wybranego modelu.

### 8.3. Rekomendacje engine_mode per scenariusz

| Scenariusz | Rekomendowany tryb | Uzasadnienie |
|------------|-------------------|-------------|
| CI/CD gate (szybkość) | `native` | Zero latencji LLM, zero kosztów |
| Krytyczny projekt (jakość) | `hybrid` | Maksymalne pokrycie i recall |
| Ograniczony budżet | `native` | Darmowe, deterministyczne |
| Nowy projekt (eksploracja) | `llm` | Rozumienie intencji, edge case'y |
| Freemium | `native` (domyślny) | Automatycznie |
| Premium + analiza bezpieczeństwa | `hybrid` | Najlepsza precyzja skanowania |

---

## 9. LLM Gateway — warstwa abstrakcji

### 9.1. Architektura

Wszystkie wywołania LLM przechodzą przez centralny `LLMGateway` (`services/analysis/llm_gateway.py`):

```
Moduł M1/M2/.../M6
       │
       ▼
  ┌─────────────┐
  │ LLM Gateway │ ← retry, fallback, cost tracking, anonymization
  └──────┬──────┘
         │
    ┌────┴────┐
    ▼         ▼
 Anthropic  OpenAI
   API       API
```

### 9.2. Funkcje

| Funkcja | Opis |
|---------|------|
| **Routing** | Wybór dostawcy na podstawie konfiguracji (`LLM_PROVIDER`) |
| **Retry** | 3 próby z inkrementalnym backoff (5s, 15s, 25s) |
| **Fallback** | OpenAI: gpt-4o → gpt-4o-mini na 5xx (próba > 1) |
| **Śledzenie kosztów** | Zapis per wywołanie: moduł, tokeny in/out, koszt USD |
| **Limity kosztów** | Basic: $100/mies., Premium: $1000/mies.; alert na 80% |
| **Anonimizacja** | Maskowanie sekretów, URL-i, e-maili, adresów IP w payloadach |
| **Streaming** | SSE dla Anthropic i OpenAI (odpowiedzi strumieniowe) |
| **Timeout** | Domyślny: 60 s per wywołanie |

### 9.3. Anonimizacja

Domyślnie włączona (`ANONYMIZATION_ENABLED=true`). Przed wysłaniem do LLM:
1. Wykrywanie wzorców: sekrety, tokeny, URL-e, adresy e-mail, adresy IP
2. Zamiana na placeholdery: `[SECRET_1]`, `[URL_1]`, `[EMAIL_1]`
3. Po otrzymaniu odpowiedzi: deanonimizacja (zamiana placeholderów na oryginały)
4. **Fail-open:** błąd anonimizacji logowany, ale wywołanie kontynuowane (bez blokowania)

---

## 10. Optymalizacja i koszty

### 10.1. Strategie optymalizacji

| Strategia | Opis | Wpływ |
|-----------|------|-------|
| **Truncation** | Obcinanie kodu do 2000–6000 znaków per wywołanie | Redukcja tokenów |
| **Chunking** | Dzielenie dużych dokumentów na fragmenty | Utrzymanie kontekstu |
| **Caching** | Redis cache dla powtórzonych analiz tego samego pliku | -30% wywołań |
| **Rate limiting** | Ograniczenie współbieżnych wywołań per tenant | Ochrona budżetu |
| **Model selection** | gpt-4o-mini jako fallback (20× tańszy od gpt-4o) | Redukcja kosztów |
| **Native-first** | Hybrid uruchamia LLM tylko gdy native nie wystarczy | Selektywne koszty |

### 10.2. Monitorowanie kosztów

- Tabela `llm_usage` — zapis per wywołanie: moduł, task_type, provider, model, tokens_in, tokens_out, cost_usd
- Dashboard Grafana: łączny koszt per tenant / per moduł / per dzień
- Alert na 80% limitu kosztów (`llm_alert_threshold=0.8`)
- Blokada wywołań po przekroczeniu limitu — `LLMError` z komunikatem

### 10.3. Limity kosztów per plan

| Plan | Limit miesięczny | Alert (80%) |
|------|-------------------|-------------|
| Basic | $100 USD | $80 USD |
| Premium | $1 000 USD | $800 USD |
| Freemium | $0 (brak LLM) | — |

---

## Powiązane dokumenty

- [Architektura C4](../architecture/architecture.md) — diagramy komponentów M1-M6
- [ADR-005](../architecture/adr/ADR-005-tree-sitter-parser.md) — decyzja: tree-sitter
- [ADR-006](../architecture/adr/ADR-006-jinja2-template-engine.md) — decyzja: Jinja2 szablony
- [analiza-kodu/](analiza-kodu/) — szczegółowa dokumentacja modułu M1
- [analiza-dokumentacji/](analiza-dokumentacji/) — szczegółowa dokumentacja modułu M2
- [analiza-uml-gui/](analiza-uml-gui/) — szczegółowa dokumentacja modułów M3-M4
- [bezpieczenstwo/](bezpieczenstwo/) — szczegółowa dokumentacja modułu M6
- [luki-funkcjonalne/](luki-funkcjonalne/) — dokumentacja gap analysis
