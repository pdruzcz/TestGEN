# FAQ — moduł luk funkcjonalnych

Najczęstsze pytania i problemy.

## Uruchamianie

### Dlaczego moja analiza zwraca 0 findings?

Sprawdź:
1. Czy projekt ma `AnalysisResult(module="requirements")` (parsowanie SRS).
2. Czy projekt ma `AnalysisResult(module="logic_structures")` (skan kodu).
3. Czy dokument i kod są w tym samym projekcie.
4. Czy istnieje jakikolwiek byt kodu w `code_entities` (analiza nie działa na pustym repo).

### Jak często uruchamiać analizę?

- **Po każdym merge do main** — szybki feedback.
- **Przed release** — pełna analiza.
- **Sprint planning** — analiza stanu + porównanie z poprzednim snapshotem.

### Czy analiza działa offline?

Tak, w pełni — silniki nie zależą od usług zewnętrznych.

## Wyniki

### Dlaczego finding ma niski score, ale wymaganie jest zaimplementowane?

Niski score combined oznacza, że nazwa funkcji / docstring słabo korelują z
tekstem wymagania. Możliwe przyczyny:
- Nazwa funkcji jest zbyt ogólna (`process_data` zamiast `export_pdf_report`)
- Brak docstring lub docstring jest zbyt krótki
- Wymaganie używa innej terminologii niż implementacja

**Rozwiązanie**: popraw docstring (np. dodaj tekst wymagania), rename funkcji, lub
oznacz finding jako `dismissed`.

### Dlaczego "extra" findings pokazują pomocnicze funkcje?

Klasyfikator pomija wzorce `test_*`, `__init__`, `conftest`, `setup`,
`teardown`, `main`, akcesory `get_*`/`set_*`/`is_*`. Pozostałe funkcje pomocnicze
mogą być oflagowane. **Rozwiązanie**:
- Dodaj dekorator `@internal` lub prefix `_` (private)
- Lub dodaj wymaganie w dokumentacji dla tego helpera

### Czy mogę zignorować finding na stałe?

Tak — kliknij finding → **"Oznacz jako dismissed"** + podaj powód. Finding
pozostanie w bazie z statusem `dismissed` i nie będzie liczone w compliance score.

## Compliance

### Dlaczego score spadło po dodaniu nowej funkcjonalności?

Dodanie nowego kodu może spowodować:
- Wykrycie nowych luk `extra` (kod bez wymagań)
- Wykrycie `different` dla częściowo pokrywających się wymagań

**Rozwiązanie**: jeśli kod jest poprawny, dodaj odpowiednie wymagania do
dokumentacji.

### Czy mogę ręcznie ustawić compliance score?

Nie — score jest wyliczany z findings. Aby go poprawić, napraw findings
(zaimplementuj missing, rozwiąż inconsistent, itp.).

## Skeleton

### Czy skeleton jest gotowy do commit?

Nie — skeleton to **stub** z `NotImplementedError`. Musisz zaimplementować ciało
funkcji zgodnie z wymaganiem.

### Dlaczego skeleton ma złą nazwę funkcji?

Skeleton używa `_normalize_identifier()` do konwersji tekstu wymagania na nazwę
funkcji. Jeśli wymaganie jest długie / złożone, nazwa może być nieoptymalna.
**Rozwiązanie**: popraw nazwę w generowanym pliku + dodaj docstring.

## Integracje

### Czy mogę użyć GitLab / GitHub Issues?

Obecnie wspieramy Jira i Azure DevOps. GitLab i GitHub Issues są na roadmapie.

### Czy integracja wymaga admina?

Nie, wymaga tylko uprawnień `write:projects` w TestGEN i uprawnień do tworzenia
issues w trackerze docelowym.

### Czy mogę mieć osobne integracje per projekt?

Tak — każda integracja jest per `project_id`. Możesz mieć projekt A z Jira i
projekt B z Azure DevOps.

## Wydajność

### Analiza jest wolna (> 60 s)

Sprawdź:
1. Rozmiar projektu (> 500 bytów kodu = dłuższa analiza)
2. Obciążenie kolejki zadań (Celery) w logach

### Memory usage wysoki

Comparator ma złożoność O(R×E). Dla 1000 wymagań × 1000 bytów = 1M par. W
takich przypadkach:
- Podziel projekt na moduły
- Lub zwiększ RAM serwera backend

## Bezpieczeństwo

### Gdzie są przechowywane API tokens?

Poświadczenia Jira / ADO są szyfrowane Fernet i persystowane w
`integration_configs.encrypted_credentials`. Klucz szyfrowania w zmiennej
środowiskowej `INTEGRATION_ENCRYPTION_KEY`.

### Kto widzi moje findingi?

Tylko użytkownicy w tym samym tenant (RLS PostgreSQL). Administrator tenant
zarządza członkami.

## Następne kroki

- [Glosariusz](../../glosariusz.md)
- [01 — Architektura — przegląd](../../ai-modules/luki-funkcjonalne/01-architektura/01-overview.md)
