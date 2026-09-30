# Import wymagań z Jiry

Historyjki, epiki, błędy i podzadania z Jiry trafiają do TestGEN jako
wymagania, a ich załączniki — jako pliki projektu. Dzięki temu analiza luk
(Epic 5) porównuje kod z tym, co zespół faktycznie uzgodnił w Jirze, zamiast
z ręcznie wgranym dokumentem sprzed trzech sprintów.

## Warunek wstępny

Projekt TestGEN musi mieć skonfigurowaną integrację z Jirą (`provider: jira`,
ta sama, której używa wysyłka znalezisk ze Story 5.8). Import korzysta z jej
adresu i poświadczeń, więc widzi dokładnie te projekty Jiry, do których ma
dostęp wskazane w niej konto.

```bash
curl "$TESTGEN_API_URL/api/v1/projects/$PROJECT_ID/import/jira/projects" \
  -H "Authorization: Bearer $TESTGEN_API_KEY"
```

## Uruchomienie importu

```bash
curl -X POST "$TESTGEN_API_URL/api/v1/projects/$PROJECT_ID/import/jira" \
  -H "Authorization: Bearer $TESTGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "jira_project_key": "QA",
        "issue_types": ["Story", "Epic", "Bug"],
        "full_reimport": false
      }'
```

Odpowiedź niesie `task_id`; postęp śledzi się przez `/api/v1/tasks/{task_id}`.
Import idzie w tle, bo składa się z zapytania JQL ze stronicowaniem i jednego
pobrania na każdy załącznik — przy kilkudziesięciu historyjkach z diagramami
to minuty pracy.

| Pole | Domyślnie | Znaczenie |
| --- | --- | --- |
| `jira_project_key` | — | klucz projektu Jiry, np. `QA` |
| `issue_types` | wszystkie obsługiwane | `Story`, `Epic`, `Bug`, `Sub-task` |
| `updated_after` | brak | pobiera zgłoszenia zmienione po tej dacie |
| `full_reimport` | `false` | ignoruje znacznik ostatniego importu |

Inne typy zgłoszeń są odrzucane kodem `422`: zadanie techniczne ani zgłoszenie
serwisowe nie opisuje zachowania systemu, więc nie da się z niego zrobić
wymagania.

## Co powstaje po stronie TestGEN

| Jira | TestGEN |
| --- | --- |
| `summary` | treść wymagania |
| `description` (znaczniki wiki) | opis wymagania, przetłumaczony na Markdown |
| sekcja „Acceptance Criteria" | lista kryteriów |
| `priority` | priorytet wymagania |
| `labels` | etykiety |
| epik | moduł, do którego należy wymaganie |
| klucz zgłoszenia | `jira_key` wymagania |
| załączniki | pliki źródłowe projektu |

**Typ wymagania zależy od typu zgłoszenia.** Historyjka, epik i podzadanie
dają wymaganie funkcjonalne; błąd — **negatywne**, bo opisuje zachowanie,
którego system wykazywać nie powinien.

**Epik jest własnym modułem.** Inaczej epik i należące do niego historyjki
wylądowałyby w dwóch różnych grupach.

Zaimportowane wymagania wiszą przy syntetycznym dokumencie
`jira-<KLUCZ>.md`. Wymagania w TestGEN należą do pliku źródłowego, a Jira
pliku nie ma — dokument daje im miejsce i zarazem pozwala zobaczyć, co
właściwie zostało zaimportowane. Ekrany wymagań, analiza luk i macierz
śledzenia czytają go tak samo jak każdy inny dokument.

## Kryteria akceptacji

Parser szuka nagłówka `h2. Acceptance Criteria` (albo `h3. Kryteria
akceptacji`) i zbiera punkty listy aż do następnego nagłówka:

```
h2. Acceptance Criteria
* System przyjmuje adres e-mail
* System odrzuca puste hasło

h2. Uwagi
* To już nie jest kryterium
```

Akapit bez punktora kończy sekcję — w praktyce jest to komentarz, nie
kryterium.

## Import przyrostowy

Kolejny import pyta Jirę wyłącznie o zgłoszenia zmienione po ostatnim
**udanym** przebiegu (`updated >= …`) i aktualizuje istniejące wymagania,
dopasowując je po `jira_key`. Przerwany import nie przesuwa znacznika, więc
zgłoszenia, których nie zdążył pobrać, wrócą przy następnym.

Decyzja z przeglądu wymagań (zaakceptowane/odrzucone) przeżywa import —
ponowne pobranie nie cofa akceptacji, którą ktoś świadomie podjął.

Załączniki nie dublują się: ten sam diagram dołączony do trzech historyjek
zapisuje się raz, bo pliki są porównywane po sumie SHA-256.

## Ograniczenia

| Ograniczenie | Wartość | Dlaczego |
| --- | --- | --- |
| Załączników na przebieg | 200 | import ma wnieść dokumentację, nie zrobić kopii cudzego systemu |
| Rozmiar załącznika | 25 MB | nagranie ekranu ani zrzut bazy nie są dokumentacją |
| Zgłoszeń na przebieg | 5000 | 50 stron po 100 — tyle odda Jira w rozsądnym czasie |

Niedostępny załącznik albo zgłoszenie z uszkodzonym opisem nie przerywa
importu — trafia do licznika pominiętych wraz z powodem.

## Stan importu

```bash
curl "$TESTGEN_API_URL/api/v1/projects/$PROJECT_ID/import/jira/status" \
  -H "Authorization: Bearer $TESTGEN_API_KEY"
```

Jeden wpis na projekt Jiry: data ostatniego udanego importu, liczba wymagań
i załączników, liczba zgłoszeń pominiętych oraz ostatni błąd.

Po udanym imporcie uruchamiana jest analiza luk na zaimportowanych
wymaganiach — jeśli w projekcie jest już kod, wynik czeka bez dodatkowej
akcji.

## Rozwiązywanie problemów

| Objaw | Przyczyna | Co zrobić |
| --- | --- | --- |
| `404` przy liście projektów | brak integracji z Jirą dla projektu | skonfiguruj ją w ustawieniach integracji projektu |
| „Jira odrzuciła poświadczenia" | wygasły token API | wygeneruj nowy token w Atlassian i zapisz w integracji |
| „Konto nie ma uprawnień do tego projektu" | konto nie widzi projektu Jiry | nadaj mu dostęp albo wskaż inny projekt |
| Import pobiera zero zgłoszeń | wszystko już zaimportowane | to poprawne zachowanie importu przyrostowego; użyj `full_reimport` |
| Brak kryteriów akceptacji | opis nie ma sekcji z nagłówkiem | dodaj `h2. Acceptance Criteria` w Jirze albo uzupełnij kryteria w TestGEN |
| Część zgłoszeń pominięta | uszkodzony opis albo brak klucza | powód jest w `last_error` w stanie importu |

## Zobacz też

- [Endpointy: integracje](endpoints/integrations.md)
- [Integracja z TMS](tms-integration.md)
- [Uwierzytelnianie](authentication.md)

[↩ Powrót do spisu treści](index.md)
