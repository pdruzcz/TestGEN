# TestGEN — dokumentacja końcowa

> Jednolity zbiór dokumentacji platformy TestGEN po konsolidacji faz
> P1–P2 (Epic 1–7). Utworzony w Story 9.1; uzupełniany przez Story
> 9.2–9.12 (podręcznik użytkownika, wdrożeniowa, administratora, C4,
> moduły AI, troubleshooting, release notes).
>
> Zasady zbioru: język polski (terminy techniczne angielskie), opis
> wyłącznie deterministycznych silników, ceny/limity z dokumentacji
> billingowej.

## Struktura katalogów

| Katalog | Zawartość | Kto czyta |
|---|---|---|
| [user-guide/](user-guide/README.md) | Podręczniki per moduł: interfejs webowy, billing, bezpieczeństwo, luki funkcjonalne | użytkownicy platformy |
| [deployment-guide/](deployment-guide/README.md) | Środowisko: pierwsze uruchomienie (dev), konfiguracja produkcyjna | devops / backend |
| [admin-guide/](admin-guide/README.md) | Panel administratora platformy | administratorzy (rola Admin) |
| [architecture/](architecture/README.md) | Architektura systemu, konwencje, przepływy, ADR, API, architektura UI i billingu | zespół rozwojowy |
| [ai-modules/](ai-modules/README.md) | Moduły analiz: kod, dokumentacja, UML/GUI, bezpieczeństwo, luki funkcjonalne | zespół rozwojowy |
| [troubleshooting/](troubleshooting/README.md) | Runbooki i przewodnik rozwiązywania problemów | wszyscy |
| [release-notes/](release-notes/README.md) | Informacje o wydaniach (Story 9.12) | wszyscy |

Pliki pomocnicze w korzeniu:

- [glosariusz.md](glosariusz.md) — wspólny słownik pojęć (PL/EN, 100+ terminów)
- [consolidation-report.md](consolidation-report.md) — raport konsolidacji
  (mapa źródło → cel, statystyki, de-dualizacja)
- [inwentaryzacja-dokumentacji.md](inwentaryzacja-dokumentacji.md) — arkusz
  inwentaryzacji źródeł (stan wyjściowy)
- [VALIDATION-REPORT.md](VALIDATION-REPORT.md) — raport walidacji kompletności
  i spójności dokumentacji (Story 9.13)
- [REVIEW-LOG.md](REVIEW-LOG.md) — log uwag z review interesariuszy (Story 9.14)
- [SIGN-OFF.md](SIGN-OFF.md) — formalny sign-off dokumentacji v3.0 (Story 9.14)

## Jak nawigować

- **Szukasz „jak coś zrobić w aplikacji"?** → [user-guide/](user-guide/README.md),
  wybierz moduł (np. [billing — zakup planu](user-guide/billing/01-plany-i-zakup.md)).
- **Wdrażasz/utrzymujesz środowisko?** → [deployment-guide/](deployment-guide/README.md).
- **Administrujesz platformą?** → [admin-guide/](admin-guide/README.md).
- **Chcesz zrozumieć, jak to działa w środku?** →
  [architecture/](architecture/README.md) (przegląd: [system](architecture/system.md))
  i szczegóły modułów w [ai-modules/](ai-modules/README.md).
- **Coś nie działa?** → [troubleshooting/](troubleshooting/README.md).
- **Termin nieznany?** → [glosariusz.md](glosariusz.md).

## Historia i pochodzenie

Dokumentacja powstała w fazach P1–P2 w katalogach fazowych (Epic 1–3,
model „1.50"; Epic 4–7: moduły bezpieczeństwa, luk funkcjonalnych,
interfejs webowy, billing) i została skonsolidowana do
tej struktury (pełne mapowanie: [consolidation-report.md](consolidation-report.md)).
Historię zmian poszczególnych plików śledzi `git log --follow <ścieżka>`.
Oryginalna specyfikacja produktu pozostaje w `docs/TestGEN/` (punkt
odniesienia, poza konsolidacją).

## Status i plan

- **Gotowe**: 9.1 (struktura, konsolidacja, glosariusz), 9.2 (API/OpenAPI),
  9.3 (moduły AI), 9.6–9.7 (wdrożeniowa), 9.8 (administratora),
  9.9 (architektura C4 + 21 diagramów), 9.10 (moduły AI — szczegółowa),
  9.11 (troubleshooting), 9.12 (release notes + changelog),
  9.13 (walidacja — [VALIDATION-REPORT.md](VALIDATION-REPORT.md)),
  9.14 (review i sign-off — [SIGN-OFF.md](SIGN-OFF.md)).
- **Zatwierdzona jako v3.0** (faza P3) — patrz [SIGN-OFF.md](SIGN-OFF.md).
- **W przygotowaniu**: podręcznik użytkownika — część 3 (9.4, wycofana)
  i część 4 (9.5, w realizacji).
