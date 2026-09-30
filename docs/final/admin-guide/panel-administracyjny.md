# Panel administracyjny

> Panel administratora platformy TestGEN (Epic 6, Story 6-15) — scalone:
> architektura panelu + przewodnik użytkownika.
> Implementacja: `frontend/src/app/features/admin/` (+ backend
> `backend/app/api/routes/admin.py`, `admin_cve.py`).

## 1. Dostęp i architektura

Trasa `/admin` — lazy loading, ochrona `role.guard` rolą **Admin**
(platformowy; poza hierarchią tenanta). Użytkownicy bez roli trafiają
na `/403`. Panel obsługuje całą platformę, nie pojedynczy tenant.

Sekcje (komponenty `features/admin/`):

| Komponent | Zakres |
|---|---|
| `user-management` (+ `user-dialog`) | użytkownicy platformy: lista, wyszukiwanie, blokada/odblokowanie, zmiana roli, reset MFA |
| `tenant-management` | tenanci: lista, stan subskrypcji (plan), blokada tenanta |
| `audit-log` | dziennik operacji wrażliwych (audyt backendowy) z filtrami: kto, co, kiedy, tenant |
| `platform-config` | ustawienia platformy (parametry globalne) |
| `cve-pipeline` (`/admin/cve-pipeline`) | pipeline CVE modułu bezpieczeństwa (E4): status aktualizacji bazy CVE, historia uruchomień, wymuszenie rescanu |

## 2. Użytkownicy

Sekcja **Użytkownicy**: lista wszystkich kont platformy z wyszukiwaniem.

- **Blokada/odblokowanie konta** — zablokowany użytkownik nie loguje się,
- **zmiana roli** — User/Owner/Admin (dialog z potwierdzeniem),
- **reset MFA** — zdjęcie wymogu drugiego składnika (np. utrata
  telefonu); użytkownik konfiguruje MFA ponownie przy logowaniu,
- każda operacja zapisuje się w audycie.

## 3. Firmy (tenanci)

Sekcja **Firmy**: lista tenantów z planem subskrypcji i stanem.
Blokada tenanta odcina jego użytkowników od platformy (dane pozostają).
Tu widać też plan i status subskrypcji (aktywna/grace) — szczegóły
modelu planów: [../architecture/billing/](../architecture/billing/).

## 4. Dziennik audytu

Sekcja **Audyt**: operacje wrażliwe z całej platformy — kto, co, kiedy,
w którym tenancie. Filtry po użytkowniku, typie operacji i zakresie
dat. Audyt obejmuje także działania administratorów (własne operacje
widać na liście) oraz przetwarzanie webhooków płatności.

## 5. Konfiguracja platformy

Sekcja **Konfiguracja**: parametry globalne platformy. Zmiany działają
natychmiast i są audytowane; ustawienia wrażliwe (np. sekrety providerów)
nie są edytowalne z panelu — wyłącznie przez env/infrastrukturę.

## 6. Pipeline CVE

Sekcja **CVE** (`/admin/cve-pipeline`, moduł bezpieczeństwa): stan bazy
CVE, harmonogram i historia aktualizacji, wymuszenie ponownego skanu
po odświeżeniu reguł. Szczegóły działania pipeline'u:
[../ai-modules/bezpieczenstwo/04-pipeline-cve/01-zrodla-danych.md](../ai-modules/bezpieczenstwo/04-pipeline-cve/01-zrodla-danych.md).

## 7. Zdrowie webhooków płatności

Operacje bilingowe admina (health webhooków tpay, replay notyfikacji)
opisane w [../architecture/billing/04-webhooki.md](../architecture/billing/04-webhooki.md).

## 8. Zasady i dostępność

- Każda operacja administracyjna ląduje w audycie ([sekcja 4](#4-dziennik-audytu)),
- zmiany ról/blokad działają natychmiast; blokada tenanta = odcięcie
  jego użytkowników od API (RLS + guards),
- panel podlega tym samym wymogom WCAG 2.1 AA co cała aplikacja —
  potwierdzone dedykowanym specem `admin.a11y.spec.ts` (struktura
  nagłówków, etykiety tabel, komunikaty operacji w live region).
