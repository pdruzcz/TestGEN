# Integracja CI/CD

TestGEN potrafi wygenerować gotową konfigurację dla czterech platform CI/CD.
Ekran *Projekt → Konfiguracja CI/CD* (`/projects/{id}/ci-cd`) pozwala ustawić
parametry, zobaczyć podgląd i pobrać plik. Ten przewodnik opisuje, co dzieje
się w wygenerowanym pipelinie i jak go skonfigurować u siebie.

## Co robi wygenerowany pipeline

Każda z czterech konfiguracji przechodzi tę samą ścieżkę:

1. **Pakuje katalog roboczy do archiwum ZIP** (z pominięciem `.git`
   i `node_modules`). Jedno żądanie zamiast setek — TestGEN rozpakuje archiwum
   po swojej stronie.
2. **Wysyła kod** — `POST /api/v1/projects/{id}/upload`.
3. **Uruchamia analizę** — `POST /api/v1/projects/{id}/analyze` z wybranymi
   modułami i trybem silnika; w odpowiedzi dostaje `task_id`.
4. **Odpytuje o status** — `GET /api/v1/tasks/{task_id}` co 10 sekund, aż do
   zakończenia albo do wyczerpania limitu czasu.
5. **Sprawdza próg** — `GET /api/v1/projects/{id}/ci-cd/summary?threshold=…`
   i przerywa build, gdy odpowiedź zawiera `"should_fail": true`.
6. **Zapisuje podsumowanie** jako artefakt builda.

Krok 5 celowo nie liczy progu w skrypcie powłoki. Decyzję podejmuje serwer, więc
werdykt w pipelinie i status check na pull requeście
([Story 8.3](../final/README.md)) zawsze się zgadzają — inaczej te same zmiany
mogłyby dostać dwa różne wyniki i nie dałoby się rozstrzygnąć, który jest prawdziwy.

## Zanim zaczniesz

1. **Utwórz klucz API** w *Ustawienia → Klucze API*, zakres **pełny dostęp**
   (pipeline wysyła kod i uruchamia analizę, więc sam odczyt nie wystarczy).
   Skopiuj klucz od razu — nie da się go odczytać ponownie.
2. **Sprawdź identyfikator projektu** — widać go w adresie strony projektu.
3. **Ustal publiczny adres API** — pipeline musi dosięgnąć TestGEN z sieci,
   w której działają runnery.

## Parametry konfiguracji

| Parametr | Wartości | Znaczenie |
| --- | --- | --- |
| Próg blokowania | `critical`, `high`, `medium` | build przerywa się przy znalezisku co najmniej tak poważnym |
| Moduły analizy | `code_analysis`, `doc_analysis`, `security_scan`, `uml_analysis` | zakres analizy |
| Tryb silnika | `native`, `llm`, `hybrid` | deterministyczny, semantyczny albo mieszany |
| Limit czasu | 1–180 minut | po tym czasie pipeline przerywa oczekiwanie |

Próg jest granicą **dolną**: `high` obejmuje też znaleziska `critical`. Wartości
`low` i `info` nie są dopuszczone — zatrzymywałyby praktycznie każdy build.

Liczba prób odpytywania wynika z limitu czasu (jedna próba co 10 sekund), więc
jeden parametr steruje i limitem platformy, i pętlą w skrypcie.

## GitHub Actions

Plik: `.github/workflows/testgen.yml`

1. Dodaj sekret repozytorium `TESTGEN_API_KEY`
   w *Settings → Secrets and variables → Actions*.
2. Wklej wygenerowany plik i zatwierdź.

Workflow uruchamia się przy `push` i `pull_request`. Podsumowanie analizy trafia
do artefaktu `testgen-summary`, także gdy build się nie powiódł (`if: always()`).

Jeśli chcesz, aby wynik blokował scalenie, dodaj wymagany status check
`TestGEN / Code Analysis` w *Settings → Branches → Branch protection rules*.
Ta nazwa jest stała — patrz [Integracja z GitHub](#status-checki-na-pull-requestach).

## GitLab CI

Plik: `.gitlab-ci.yml`

1. Dodaj zmienną `TESTGEN_API_KEY` w *Settings → CI/CD → Variables*,
   zaznaczając **Mask variable** (bez maskowania klucz trafi do logów joba).
2. Wklej wygenerowany plik.

Zadanie działa na obrazie `alpine:3.20` i instaluje `curl`, `jq` oraz `zip`.
Jeśli używasz własnego obrazu, upewnij się, że te narzędzia są dostępne, albo
podmień `image:` i `before_script:`.

Podsumowanie trafia do artefaktu `testgen-summary.json` z tygodniowym okresem
przechowywania.

## Jenkins

Plik: `Jenkinsfile`

1. Dodaj poświadczenie typu **Secret text** o identyfikatorze
   `testgen_api_key` (*Manage Jenkins → Credentials*).
2. Upewnij się, że agent ma `curl`, `jq` i `zip`.
3. Wklej wygenerowany plik do repozytorium.

Jenkins maskuje wartość poświadczenia w logach, więc klucz nie wycieknie przez
`sh` z `set -x`. Podsumowanie jest archiwizowane w bloku `post { always { … } }`.

## Azure DevOps

Plik: `azure-pipelines.yml`

1. Dodaj zmienną sekretną `TESTGEN_API_KEY`
   w *Pipelines → Library → Variable groups* albo bezpośrednio w ustawieniach
   pipeline'u.
2. Wklej wygenerowany plik.

Pipeline wyzwala się na gałęziach `main` i `master` oraz przy pull requestach.
Podsumowanie publikowane jest jako artefakt `testgen-summary`.

## Dobre praktyki

### Zarządzanie sekretami

Klucz API trzymaj wyłącznie w magazynie sekretów platformy. Nie wklejaj go do
pliku konfiguracyjnego — trafiłby do historii repozytorium, skąd usuwa się go
dużo trudniej, niż się go tam wstawia.

Załóż **osobny klucz dla każdego pipeline'u**. Gdy jeden wycieknie albo
przestanie być potrzebny, odwołasz go bez wpływu na pozostałe integracje,
a kolumna *Ostatnie użycie* podpowie, który klucz jest jeszcze żywy.

### Przyspieszanie

Wyklucz z archiwum wszystko, czego analiza nie potrzebuje — katalogi zależności,
artefakty builda, dane testowe. Mniejsze archiwum to krótszy upload
i krótsza analiza.

Zawęź moduły do tych, które faktycznie chcesz na tym pipelinie. Pełny zestaw na
każdym commicie rzadko ma sens; typowy podział to `code_analysis` na każdym
pushu i pełny zestaw nocą.

### Limity żądań

Odpytywanie co 10 sekund jest już dobrane pod limity; nie skracaj go.
Przy równoległych pipeline'ach pamiętaj, że limit jest wspólny dla całej firmy —
patrz [Limity żądań](rate-limiting.md).

Przy dużej liczbie buildów rozważ [webhooki](webhooks.md): zdarzenie
`analysis.completed` przychodzi samo i nie kosztuje ani jednego żądania.

### Obsługa niepowodzeń

Rozróżniaj dwie sytuacje. Kod wyjścia z kroku sprawdzania progu oznacza
**znalezione problemy** — to poprawne działanie pipeline'u. Błąd wcześniejszego
kroku oznacza **awarię integracji** (zły klucz, brak łączności, przekroczony
czas) i wymaga innej reakcji niż przejrzenie znalezisk.

Jeśli zależy Ci na widoczności bez blokowania, ustaw w konfiguracji status
checka *„nie blokuj merge'a"* — liczby będą widoczne, a build pozostanie zielony.

## Status checki na pull requestach

Jeśli podłączysz repozytorium przez *Ustawienia → Integracja GitHub* albo
*GitLab*, analiza uruchomi się automatycznie przy każdym pull requeście —
bez żadnego pliku CI. Wynik trafia na zmianę jako status check o nazwie
**`TestGEN / Code Analysis`**, a przy pull requeście pojawia się komentarz
z podsumowaniem i trzema najpoważniejszymi znaleziskami.

Obie ścieżki można łączyć: automatyczna analiza z webhooka daje status check
i komentarz, a pipeline CI/CD dodatkowo zatrzymuje build.

## Rozwiązywanie problemów

| Objaw | Przyczyna | Co zrobić |
| --- | --- | --- |
| `401` na pierwszym kroku | brak, zły albo odwołany klucz | sprawdź nazwę sekretu i czy klucz nadal jest aktywny |
| `403` przy uruchamianiu analizy | klucz ma zakres tylko do odczytu | utwórz klucz z pełnym dostępem |
| `404` przy uploadzie | zły identyfikator projektu albo projekt innej firmy | sprawdź identyfikator w adresie strony projektu |
| `429` w trakcie odpytywania | wspólny limit firmy wyczerpany przez równoległe buildy | zmniejsz równoległość albo przejdź na webhooki |
| Analiza nie kończy się w limicie czasu | duże repozytorium albo tryb `llm` | zwiększ limit czasu, zawęź moduły, wyklucz katalogi z archiwum |
| `jq: command not found` | obraz runnera bez `jq` | dodaj instalację narzędzi albo użyj obrazu, który je ma |
| Build zielony mimo znalezisk | wyłączone blokowanie progu | włącz *„blokuj merge po przekroczeniu progu"* w ustawieniach status checka |

## Zobacz też

- [Endpointy: integracje](endpoints/integrations.md)
- [Uwierzytelnianie](authentication.md) — klucze API i ich zakresy
- [Limity żądań](rate-limiting.md)
- [Webhooki](webhooks.md)

[↩ Powrót do spisu treści](index.md)
