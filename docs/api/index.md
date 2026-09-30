# API TestGEN — dokumentacja

TestGEN wystawia REST‑owe API nad JSON‑em. Wszystko, co da się zrobić
w interfejsie webowym, da się też zrobić programowo: wysłać kod, uruchomić
analizę, pobrać wyniki, wyeksportować przypadki testowe do systemu zarządzania
testami.

Bazowy adres API zależy od instalacji — w tej dokumentacji używamy
`https://api.testgen.io`. Wszystkie ścieżki zaczynają się od `/api/v1/`.

## Od czego zacząć

1. **[Uwierzytelnianie](authentication.md)** — utwórz klucz API i zrozum
   różnicę między zakresem tylko do odczytu a pełnym dostępem.
2. **[Przykłady i szybki start](sdk-examples.md)** — pełny przepływ analizy
   w curl, Pythonie i JavaScripcie, gotowy do wklejenia.
3. **[Integracja CI/CD](cicd-integration.md)** albo
   **[Integracja z TMS](tms-integration.md)** — zależnie od tego, co chcesz
   osiągnąć.

## Podstawy

| Strona | O czym |
| --- | --- |
| [Uwierzytelnianie](authentication.md) | klucze API, tokeny JWT, MFA, zakresy, kontekst firmy |
| [Błędy](errors.md) | format RFC 7807, kody odpowiedzi, błędy walidacji |
| [Limity żądań](rate-limiting.md) | progi per plan, nagłówki `X-RateLimit-*`, obsługa `429` |

## Przewodniki

| Strona | Dla kogo |
| --- | --- |
| [Przykłady i szybki start](sdk-examples.md) | każdy, kto pierwszy raz woła API |
| [Webhooki](webhooks.md) | integratorzy reagujący na zdarzenia w czasie rzeczywistym |
| [Integracja CI/CD](cicd-integration.md) | deweloperzy wpinający analizę w pipeline |
| [Integracja z TMS](tms-integration.md) | analitycy QA eksportujący i synchronizujący testy z TestRailem, Xrayem lub Zephyrem |
| [Import z Jiry](jira-import.md) | analitycy QA przenoszący wymagania i załączniki z Jiry do TestGEN |

## Referencja endpointów

Poniższe strony są **generowane ze schemy OpenAPI**, więc odpowiadają temu, co
API faktycznie robi. Każda operacja ma opis, parametry, kody odpowiedzi
i gotowe przykłady w trzech językach.

| Grupa | Endpointów | Zakres |
| --- | ---: | --- |
| [Uwierzytelnianie i użytkownicy](endpoints/auth.md) | 27 | logowanie, MFA, konta, firmy, klucze API |
| [Projekty i pliki](endpoints/projects.md) | 18 | CRUD projektów, upload kodu, repozytoria Git |
| [Analiza](endpoints/analysis.md) | 42 | uruchamianie analiz, zadania, dokumentacja, UML, GUI |
| [Przypadki testowe](endpoints/test-cases.md) | 31 | CRUD, generowanie kodu, Gherkin, self‑healing |
| [Raporty i eksport](endpoints/reports.md) | 3 | generowanie i pobieranie raportów |
| [Bezpieczeństwo](endpoints/security-scan.md) | 20 | skany, znaleziska, rekomendacje, baza CVE |
| [Luki funkcjonalne](endpoints/gap-analysis.md) | 24 | porównanie kodu z dokumentacją, macierz śledzenia |
| [Integracje](endpoints/integrations.md) | 45 | GitHub, GitLab, Jira, TestRail, synchronizacja TMS, import z Jiry, generator CI/CD |
| [Webhooki](endpoints/webhooks.md) | 8 | konfiguracja, testy, historia dostaw |
| [Subskrypcje i limity](endpoints/billing.md) | 36 | plany, faktury, liczniki, powiadomienia |

Razem **254 operacje**.

## Interaktywna dokumentacja

W środowiskach deweloperskim i testowym działają `/docs` (Swagger UI) oraz
`/redoc`. Przycisk *Authorize* przyjmuje zarówno klucz API, jak i token JWT,
a wpisane poświadczenie przeżywa odświeżenie strony. W produkcji interaktywna
dokumentacja jest wyłączona, żeby nie ujawniać całej powierzchni API.

Surową specyfikację pobierzesz spod `/openapi.json`.

## Konwencje

**Język.** Opisy i komunikaty są po polsku; terminy techniczne (endpoint,
webhook, API key, token) zostają w angielskim, bo w tej formie występują
w kodzie i w nagłówkach.

**Format danych.** Żądania i odpowiedzi są w JSON‑ie, pola w `snake_case`.
Znaczniki czasu są w ISO 8601 ze strefą UTC. Identyfikatory zasobów to UUID.

**Izolacja firm.** Każdy zasób należy do firmy. Próba sięgnięcia po zasób innej
firmy kończy się `404`, a nie `403` — inaczej odpowiedź potwierdzałaby, że
zasób o takim identyfikatorze istnieje.

**Operacje długotrwałe.** Analiza i eksport do TMS działają w tle: endpoint
zwraca `202` z `task_id` i adresem do śledzenia postępu. Zamiast odpytywania
możesz użyć [webhooków](webhooks.md).

## Jak utrzymywana jest ta dokumentacja

Strony w `endpoints/` powstają z żywej schemy OpenAPI:

```bash
cd backend
python -m scripts.generate_api_docs
```

Uruchom to polecenie po każdej zmianie kontraktu API. Pozostałe strony są
pisane ręcznie i generator ich nie dotyka.

## Zobacz też

- [Dokumentacja platformy](../final/README.md) — podręcznik użytkownika,
  architektura, wdrożenie i administracja
