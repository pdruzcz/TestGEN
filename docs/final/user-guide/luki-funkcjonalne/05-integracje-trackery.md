# Integracje z trackerami (Jira, Azure DevOps)

> Przewodnik P2 — konfiguracja i sync znalezisk do zewnętrznych trackerów.

## Dostęp

Ustawienia → **Integracje** (route: `/projects/:id/integrations`).

## Konfiguracja Jira

### Wymagania

- Konto Jira Cloud z uprawnieniami "Create Issues"
- API token wygenerowany na https://id.atlassian.com/manage-profile/security/api-tokens
- Email używany do logowania do Jira
- Project Key docelowy (np. ENG, DEV, PROJ)

### Kroki konfiguracji

1. Otwórz **Integrations** → zakładka **Jira**.
2. Wypełnij formularz:
   - **Base URL**: np. `https://twoja-org.atlassian.net`
   - **Email**: twój email do Jira
   - **API Token**: wklej token
   - **Project Key**: np. `ENG`
   - **Issue Type**: `Task` (domyślnie), `Story`, `Bug`
3. Kliknij **Test connection** — backend wywoła `/rest/api/3/serverinfo`.
4. Po sukcesie kliknij **Zapisz konfigurację**.

### Walidacja

Backend sprawdza:
- URL jest HTTPS
- API token nie jest pusty
- Poświadczenia szyfrowane Fernet (at-rest)
- Test połączenia zwraca 200 z Jira

## Konfiguracja Azure DevOps

### Wymagania

- Organizacja Azure DevOps z projekt
- PAT (Personal Access Token) z scope `Work Items: Read & Write`
- Nazwa organizacji i projektu

### Kroki konfiguracji

1. Otwórz **Integrations** → zakładka **Azure DevOps**.
2. Wypełnij formularz:
   - **Organization URL**: `https://dev.azure.com/twoja-org`
   - **Project Name**: np. `MyProject`
   - **PAT**: wklej Personal Access Token
   - **Work Item Type**: `Task` (domyślnie), `User Story`, `Bug`
3. Kliknij **Test connection** — backend wywoła `/_apis/projects/{project}`.
4. Po sukcesie kliknij **Zapisz konfigurację**.

## Sync znalezisk

### Pojedyncze finding

1. W tabeli gap-findings kliknij finding.
2. W panelu bocznym kliknij **"Sync do {provider}"**.
3. Backend tworzy issue / work item i zapisuje `external_id`.

### Bulk sync

1. Zaznacz wiele findings w tabeli (checkbox).
2. Kliknij **"Sync zaznaczonych"** w toolbarze.
3. Wybierz providera (Jira / ADO).
4. Backend uruchamia asynchroniczny task sync.
5. Progress widoczny w toolbarze.

### Sync wszystkie P1

1. W tabeli recommendations kliknij **"Sync P1 do Jira"**.
2. Wszystkie rekomendacje o priority P1 zostaną zgrane.
3. Warto domyślnie filtrować po critical, aby uniknąć spamu w trackerze.

## Mapowanie pól

### Jira

| Pole TestGEN | Pole Jira |
|---|---|
| Severity: critical | Priority: Highest |
| Severity: warning | Priority: High |
| Severity: info | Priority: Medium |
| Gap type | Labels: testgen, gap-analysis, {gap_type} |
| Requirement ID | Description (formatted text) |
| Code reference | Description (formatted text) |
| Match score | Custom field (jeśli skonfigurowane) |

### Azure DevOps

| Pole TestGEN | Pole ADO |
|---|---|
| Severity: critical | Priority: 1 |
| Severity: warning | Priority: 2 |
| Severity: info | Priority: 3 |
| Gap type | Tags: testgen; gap-analysis; {gap_type} |
| Requirement ID | Description (HTML) |
| Code reference | Description (HTML) |

## Status sync

Każdy sync tworzy wpis w `integration_sync_logs`:

| Status | Znaczenie |
|---|---|
| `pending` | W kolejce |
| `running` | W trakcie |
| `success` | Wszystko OK |
| `partial` | Część findingów miała błąd (np. rate limit) |
| `failed` | Cały sync się nie udał (np. poświadczenia wygasły) |

Historia logów dostępna w **Sync Logs** poniżej formularza konfiguracji.

## Deduplikacja

Backend nie tworzy duplikatów issues. Pole `external_ids` w logu sync mapuje
`gap_finding_id → external_issue_key`. Ponowny sync pomija findings, które już
mają external_key, chyba że użytkownik wybierze **"Wymuś ponowne utworzenie"**.

## Bezpieczeństwo

- **Szyfrowanie at-rest**: poświadczenia szyfrowane Fernet. Klucz w zmiennej
  środowiskowej `INTEGRATION_ENCRYPTION_KEY`.
- **RLS**: integracje są widoczne tylko dla członków tenant.
- **Rate limiting**: max 10 syncs / hour / project (zapobieganie pętlom).
- **Audit log**: wszystkie akcje sync są logowane z `user_id`, `timestamp`,
  `provider`, `synced_count`.

## Troubleshooting

### "401 Unauthorized"
- Sprawdź ważność API token / PAT.
- Sprawdź czy email ma uprawnienia w docelowym projekcie.

### "404 Project not found"
- Sprawdź Project Key / Project Name.
- Sprawdź czy organizacja jest poprawna.

### "Rate limit exceeded"
- Poczekaj 5 minut i spróbuj ponownie.
- Zmniejsz liczbę findings na sync (filtruj po P1).

### "Field 'priority' not found"
- Nie każdy projekt Jira ma te same priorytety. Skontaktuj się z adminem Jira
  aby dostosować mapowanie.

## Następne kroki

- [04 — Rekomendacje i skeleton](04-rekomendacje-i-skeleton.md)
- [06 — FAQ](06-faq.md)
