# Przewodnik — nawigacja i ekrany główne

> Dokumentacja P2, Epic 6. Frontend TestGEN (przeglądarka lub aplikacja
> mobilna — ten sam interfejs).

## 1. Logowanie i start

1. `/login` — email + hasło; przy włączonym MFA podajesz kod
   jednorazowy (`/mfa-verify`).
2. Należysz do więcej niż jednej firmy? Wybierz tenant na
   `/select-tenant`.
3. Lądujesz na **dashboardzie** (`/dashboard`): lista projektów,
   statystyki aktywności, skróty do ostatnich analiz.

Pierwsze kroki w nowej firmie: zaproś współpracowników
(`/users/invite`), utwórz projekt i wgraj pliki
([02 — Projekty i upload](02-projekty-i-upload.md)).

## 2. Górny pasek (navbar)

- **Menu główne** — projekty, wyniki, raporty, rozliczenia (zależnie od
  roli),
- **dzwonek powiadomień** — powiadomienia o progach limitów (80/90/100%),
  licznik nieprzeczytanych, „oznacz wszystkie" (szczegóły:
  `docs/final/user-guide/billing/`),
- **pasek dostępności** — przełączniki wysokiego kontrastu i wyłączenia
  animacji ([05 — Dostępność](05-dostepnosc.md)),
- **profil** — dane konta, MFA, wylogowanie.

## 3. Ekrany i ich adresy

| Ekran | Adres | Kto widzi |
|---|---|---|
| Dashboard | `/dashboard` | wszyscy |
| Projekty | `/projects` | wszyscy w tenancie |
| Szczegóły projektu | `/projects/{id}` + zakładki (pliki, analiza, wyniki, testy, raporty) | wszyscy w tenancie |
| Test case'y | `/projects/{id}/test-cases` | wszyscy |
| Raporty | `/projects/{id}/reports` | wszyscy |
| Rozliczenia | `/billing/…` (plany, subskrypcja, faktury, zużycie) | plany/faktury — wszyscy; zakupy — Owner |
| Ustawienia | `/settings/profile`, `/settings/mfa`, `/settings/users` | profil/MFA — ja; użytkownicy — Owner |
| Panel administratora | `/admin` | Admin platformy |

Niektóre zakładki modułów analiz mogą być **zablokowane planem**
(kłódka) — opis w `docs/final/user-guide/billing/`.

## 4. Błędy i stany brakowe

- `/403` — brak uprawnień do ekranu (np. panel admina bez roli Admin),
- 404 — nieistniejący adres,
- bannery limitów — wyczerpany limit operacji (co robić:
  [05 — Zużycie](05-dostepnosc.md) i dokumentacja billingowa).

## 5. Aplikacja mobilna/desktopowa

Ta sama aplikacja działa w natywnej powłoce (Android, iOS, Windows;
Linux otwiera przeglądarkę). Linki `testgen://…` z maili i powiadomień
otwierają właściwy ekran aplikacji. Bez sieci powłoka pokazuje
komunikat offline i wraca po odzyskaniu połączenia.
