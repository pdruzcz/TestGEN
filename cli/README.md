# TestGEN CLI

Klient wiersza poleceń platformy TestGEN — analiza kodu, generowanie testów,
skany bezpieczeństwa i raporty bez otwierania przeglądarki (Story 8.10).

## Instalacja

```bash
pip install testgen-cli
```

Z repozytorium (tryb deweloperski):

```bash
cd cli
pip install -e ".[dev]"
```

Wymagany Python 3.11 lub nowszy.

## Logowanie

```bash
testgen login --api-key tgn_...     # zalecane; klucz wygenerujesz w Ustawienia → Klucze API
testgen login --email dev@firma.pl  # hasło pobierane interaktywnie
testgen whoami
testgen logout
```

Poświadczenia trafiają do `~/.testgen/auth` z prawami `600`.

W CI/CD **nie loguj się** — podaj klucz zmienną środowiskową:

```bash
export TESTGEN_API_KEY=tgn_...
export TESTGEN_PROJECT_ID=...
```

Token z logowania e-mailem to token sesji i wygasa po kilkudziesięciu minutach —
do automatyzacji nadaje się wyłącznie klucz API. Konta z MFA logują się tylko
kluczem.

## Konfiguracja — `.testgen.yaml`

Plik szukany jest w bieżącym katalogu i wyżej, aż do korzenia (tak jak `.git`).

```yaml
api_key: tgn_...              # opcjonalnie — lepiej trzymać w zmiennej środowiskowej
project_id: 11111111-1111-1111-1111-111111111111
engine_mode: native           # native | llm | hybrid
default_framework: pytest
severity_threshold: critical  # critical | high | medium — próg kodu wyjścia 1
api_url: https://api.testgen.io
exclude:                      # dodatkowe wzorce pomijane przy wysyłce kodu
  - "dane_testowe/*"
```

Pierwszeństwo źródeł, od najsilniejszego:

1. argumenty wiersza poleceń (`--project-id`, `--api-url`, …),
2. zmienne środowiskowe `TESTGEN_API_KEY`, `TESTGEN_API_URL`, `TESTGEN_PROJECT_ID`,
3. `.testgen.yaml` w katalogu projektu,
4. `~/.testgen/config.yaml`.

## Komendy

```bash
testgen analyze [KATALOG] --wait            # wysyła kod i uruchamia analizę
testgen generate --framework pytest -o tests
testgen export --format pdf -o raport.pdf
testgen scan --type sast --severity-threshold high
testgen status <task_id> --watch
testgen projects
```

`analyze` pakuje katalog do archiwum, pomijając `.git`, `node_modules`,
`venv`, katalogi budowania i pliki binarne. Z `--wait` czeka na zakończenie
analizy i sprawdza próg znalezisk.

`generate` zapisuje kod testów wytworzonych przez ostatnią analizę. Przypadki
opisowe (bez kodu) są pomijane, a ich liczba raportowana.

## Formaty wyjścia

| Opcja     | Zastosowanie                                      |
|-----------|---------------------------------------------------|
| domyślnie | tabele i kolory dla człowieka                     |
| `--json`  | wynik na stdout jako JSON — gotowy pod `jq`        |
| `--yaml`  | wynik na stdout jako YAML                         |
| `--quiet` | bez wyjścia; liczy się tylko kod zakończenia      |

Komunikaty postępu idą na **stderr**, więc `testgen analyze --json | jq` działa
bez dodatkowych sztuczek. Kolory włączają się tylko dla terminala.

## Kody wyjścia

| Kod | Znaczenie                                                        |
|-----|------------------------------------------------------------------|
| 0   | sukces; brak znalezisk powyżej progu                             |
| 1   | znaleziska powyżej progu — build ma się zatrzymać                |
| 2   | błąd narzędzia: brak sieci, złe poświadczenia, zły argument      |

Rozróżnienie 1 i 2 jest celowe: „znaleźliśmy podatność" wymaga innej reakcji
zespołu niż „zepsuł się klucz API".

## Przykład: bramka w CI

```yaml
- name: Analiza TestGEN
  env:
    TESTGEN_API_KEY: ${{ secrets.TESTGEN_API_KEY }}
    TESTGEN_PROJECT_ID: ${{ vars.TESTGEN_PROJECT_ID }}
  run: |
    pip install testgen-cli
    testgen analyze . --wait --json > wynik.json
```

Krok kończy się niepowodzeniem, gdy analiza znajdzie problemy powyżej progu —
werdykt liczy serwer, więc bramka w CI i status check na pull requeście zawsze
mówią to samo.

## Brak połączenia

Przy nieosiągalnym API komenda wypisuje „Brak połączenia z serwerem TestGEN"
wraz z użytym adresem i kończy się kodem 2. Limit czasu ustawia `--timeout`
(domyślnie 30 s).

## Testy

```bash
cd cli
pytest
ruff check testgen tests
```
