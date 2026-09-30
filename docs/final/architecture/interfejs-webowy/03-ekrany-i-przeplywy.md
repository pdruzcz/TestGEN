# Mapa ekranów i przepływów

> Dokumentacja P2, Epic 6 — Stories 6-1…6-8.
> Implementacja: `frontend/src/app/features/`.

## 1. Dashboard (Story 6-1)

`/dashboard` (`features/dashboard/`): lista projektów z filtrowaniem,
statystyki aktywności tenanta, skróty do ostatnich analiz. Dane z
`dashboard.service.ts` (backend `/dashboard`).

## 2. Upload (Story 6-2)

Wspólny komponent `shared/components/file-upload.component.ts` używany
przez upload kodu i dokumentacji (`features/projects/document-upload/`):

- **drag & drop** lub wybór plików; wielu plików naraz,
- walidacja po stronie klienta (`file-validation.service`): rozszerzenia
  (`DEFAULT_DOCUMENT_EXTENSIONS`), rozmiar (`DEFAULT_MAX_FILE_SIZE_BYTES`),
- upload równoległy z **progresem per plik** — statusy
  `pending → uploading → success | failed | cancelled`,
- podsumowanie po zakończeniu (powodzenia / porażki / pominięte) i
  komunikaty błędów po polsku.

## 3. Konfiguracja i uruchamianie analiz (Story 6-3)

Widoki projektu: wybór źródeł (kod/dokumentacja/UML/GUI), konfiguracja
analizy i uruchomienie (`features/projects/analysis/`), raport
preprocessingu (`preprocessing-report/`) przed startem, śledzenie postępu
zadania. Wynik analizy ląduje w przeglądarce wyników.

## 4. Przeglądarka wyników (Story 6-4)

`features/results/` + `features/projects/*/view`:

| Komponent | Rola |
|---|---|
| `filter-panel` | filtry wyników (typ, waga, status, moduł) |
| `result-detail` | szczegóły znaleziska z kontekstem |
| `code-highlighter` | podświetlanie składni fragmentów kodu |
| `diff-viewer` | widok różnic (diff) — np. kod ↔ dokumentacja |

Ta sama przeglądarka obsługuje wyniki wszystkich modułów (E2–E5) —
wspólne komponenty w `features/results/components/`.

## 5. Zarządzanie test case'ami (Story 6-5)

`features/test-cases/`:

| Element | Rola |
|---|---|
| `test-cases-management` | kompletny widok zarządzania (tabela TC projektu) |
| `test-cases-list` / `test-case-detail` | lista i szczegóły TC |
| `test-case-editor` | edycja kroków/oczekiwanych rezultatów |
| `filter-group-panel` | grupowe filtry |
| `bulk-actions-bar` | operacje masowe (status, eksport, usunięcie) |
| `history-dialog` | historia zmian TC |
| `locator-badge` | informacja o lokatorze (testy UI) |
| `field-mapping` | mapowanie pól przy imporcie/eksportcie |
| `tms-export-dialog` | eksport do TMS (CSV/XML) — FR46 |

## 6. Raporty (Stories 6-6, 6-7 — FR43/FR44/FR45)

`features/reports/`:

| Element | Rola |
|---|---|
| `executive-summary` | raport poziomu zarządczego (podsumowanie, metryki) |
| `technical-details` | raport techniczny (szczegóły znalezisk) |
| `report-preview` | podgląd raportu przed eksportem |
| `export-buttons` + `export-progress-dialog` | eksport **PDF, HTML, CSV, Excel, JSON, YAML** (FR45) z progresem |
| `report.service` / `export.service` / `chart-rendering.service` | dane raportów, eksporty, wykresy |

Raporty dwupoziomowe (FR44): executive summary dla zarządu +
szczegóły techniczne dla zespołów QA — ten sam źródłowy zbiór wyników.

## 7. Ekran błędów i statusów

`features/errors/` — `/403` (brak uprawnień) i 404 (wildcard). Blokady
modułów planem (FR71) nie są błędem — to komponenty
`locked-module`/`locked-feature-tab` z CTA do planów (E7).

## 8. Typowy przepływ użytkownika

```
login → select-tenant → dashboard
  → projects → nowy projekt → upload plików (drag & drop)
  → preprocessing-report → konfiguracja analizy → uruchomienie
  → results (filtry, diff, podświetlanie)
  → test-cases (edycja, operacje masowe, eksport TMS)
  → reports (executive/techniczny → eksport PDF/HTML/…)
```

Każdy krok dostępny z klawiatury i czytnika ekranu (sekcja dostępności),
a operacje objęte limitami planu sygnalizowane bannerami (quota/402).
