# ADR-010: Logowanie audytowe operacji

## Status

Accepted

## Kontekst

Platforma przetwarza zastrzeżony kod i dokumentację, a wygenerowane testy mogą
zawierać informacje poufne. Wymagana jest rozliczalność wszystkich działań
wrażliwych: operacji zapisu, zdarzeń uwierzytelniania, dostępu do danych oraz
decyzji w workflow przeglądu (akceptacja/odrzucenie/edycja).

## Decyzja

Kompleksowe **logowanie audytowe** dla operacji zapisu, zdarzeń auth (logowanie,
MFA, refresh, blokady po nieudanych próbach) oraz dostępu do danych. Logi
zawierają kontekst tenanta i użytkownika (RLS — ADR-002). Endpointy audytowe
dostępne dla ról z uprawnieniami (`/admin/audit-logs`).

## Konsekwencje

**Pozytywne:**

- Spełnienie wymogów zgodności i możliwość badania incydentów.
- Analityka aktywności użytkowników; diagnozowanie problemów produkcyjnych.
- Ślad decyzji w workflow (ADR-009) powiązany z wykonawcą.

**Negatywne:**

- Dodatkowe wymagania pojemnościowe (polityka retencji logów).
- Może nieznacznie wpłynąć na wydajność zapisu.
- Kwestie prywatności danych w logach (sanityzacja pól wrażliwych).

## Powiązane

- [ADR-002](./ADR-002-multi-tenancy-rls.md) — kontekst tenanta w logach.
- [ADR-009](./ADR-009-code-review-workflow.md) — decyzje przeglądu logowane.
- [api/examples/audit_examples.md](../api/examples/audit_examples.md) —
  endpointy audytowe.
