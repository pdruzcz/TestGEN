# ADR-002: Multi-tenancy z Row-Level Security (RLS)

## Status

Accepted

## Kontekst

Platforma obsługuje wielu tenantów (organizacji) potencjalnie z wrażliwym kodem
źródłowym i dokumentacją. Wymagana jest silna izolacja danych między tenantami
na poziomie bazy danych — poleganie wyłącznie na filtrowaniu w warstwie
aplikacji (klauzula `WHERE tenant_id = ...` w każdym zapytaniu) jest podatne na
błąd: jedno pominięcie filtru ujawnia dane sąsiada.

## Decyzja

Wielodostępność oparta na **shared database + Row-Level Security (RLS)
PostgreSQL**. Każda tabela dziedziczy `tenant_id` (mixinx `TenantMixin`). Przed
wykonaniem zapytania sesja ustawia zmienną transakcji
`app.current_tenant = <uuid>`, a polityki RLS wymuszają, że wiersz jest widoczny
tylko gdy `tenant_id` odpowiada bieżącej sesji. Migracje definiują polityki RLS
per tabela.

## Konsekwencje

**Pozytywne:**

- Izolacja wymuszana przez bazę — nawet pominięcie filtru w ORM nie ujawni
  danych innego tenanta.
- Oszczędność zasobów: jedna baza, jeden schemat, wspólne indeksy.
- Spójny model dla wszystkich modułów analizy (kod, dokumentacja, UML/GUI).

**Negatywne:**

- Wymaga dyscypliny: każda nowa tabela musi mieć `tenant_id` + politykę RLS.
- Większe indeksy (z uwzględnieniem `tenant_id`).
- Utrudnione współdzielenie danych między tenantami (z założenia rzadkie).
- Złożoność testowania: testy muszą ustawiać kontekst sesji RLS.

## Powiązane

- [ADR-010](./ADR-010-audit-logging.md) — logowanie audytowe obejmuje kontekst
  tenanta.
- [architecture.md](../system.md) — warstwa trwała.
