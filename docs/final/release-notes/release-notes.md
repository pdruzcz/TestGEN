# Release notes — TestGEN

> **Format:** per wersja · **Język:** polski · **Odbiorcy:** użytkownicy, administratorzy, DevOps

---

## Spis treści

- [v3.0 — Faza P3 (Q4 2026)](#v30--faza-p3-q4-2026)
- [v2.0 — Faza P2 (Q3 2026)](#v20--faza-p2-q3-2026)
- [v1.0 — Faza P1 (Q2 2026)](#v10--faza-p1-q2-2026)
- [Szablon release notes](#szablon-release-notes)

---

## v3.0 — Faza P3 (Q4 2026)

**Data wydania:** grudzień 2026 · **Faza:** P3 — Integracje, płatności i dokumentacja

### Podsumowanie

Wersja 3.0 zamyka rozwój funkcjonalny platformy TestGEN. Dodaje integracje z zewnętrznymi systemami (Jira, Azure DevOps, GitHub/GitLab, CI/CD), kompletny moduł płatności z bramką tpay (BLIK, karta, przelew) oraz pełną dokumentację końcową obejmującą podręczniki użytkownika, administratora, wdrożeniowy, architekturę C4 i przewodniki rozwiązywania problemów.

### Nowe funkcje

| Funkcja | Epik | Opis |
|---------|------|------|
| **Integracja z Jira** | E7 | Tworzenie zadań, synchronizacja statusów, eksport wyników analiz |
| **Integracja z Azure DevOps** | E7 | Tworzenie work items, integracja z pipeline'ami |
| **Webhooks GitHub/GitLab** | E7 | Automatyczne wyzwalanie analiz przy push/merge |
| **Generator konfiguracji CI/CD** | E7 | Szablony: Jenkins, GitHub Actions, Azure Pipelines, GitLab CI |
| **Eksport do TestRail** | E7 | Eksport przypadków testowych w formacie CSV/XML |
| **Eksport do Jira XRay** | E7 | Eksport testów w formacie XRay |
| **Moduł płatności tpay** | E8 | Checkout, BLIK, karta, przelew bankowy |
| **Plany subskrypcji** | E8 | Freemium (0 PLN) / Basic (30 PLN/mies.) / Premium (50 PLN/mies.) |
| **Faktury VAT** | E8 | Automatyczne generowanie faktur PDF po płatności |
| **Dunning** | E8 | Obsługa nieudanych płatności: 7-dniowy grace period |
| **Bramka funkcji** | E8 | Blokowanie modułów niedostępnych w danym planie (ikona kłódki) |
| **Klucze API** | E8 | Tworzenie, rotacja, revoke, rate limiting per plan |
| **Dokumentacja końcowa** | E9 | Podręczniki: użytkownika, administratora, wdrożeniowy, architektura C4, moduły AI, troubleshooting |

### Ulepszenia

- **Gap Analysis** — analiza luk funkcjonalnych: porównanie wymagań vs implementacja vs testy z rekomendacjami
- **API Keys** — programistyczny dostęp z rate limiting i scope'em uprawnień
- **Shell Flutter** — aplikacja mobilna/desktopowa (WebView) opakowująca SPA
- **Monitoring** — ulepszone dashboardy Grafana (10 paneli), alerty Prometheus, integracja Loki
- **Panel admina** — nowe sekcje: konfiguracja platformy, pipeline CVE, replay webhooków

### Poprawki błędów

- Naprawiono wyświetlanie dashboardu przy braku danych historycznych
- Naprawiono sortowanie null-last w tabelach projektów
- Naprawiono problem z widocznością etykiet w trybie wysokiego kontrastu
- Naprawiono blokadę konta po nieudanym logowaniu z MFA
- Naprawiono timeout przy generowaniu dużych raportów PDF

### Znane problemy

| Problem | Obejście |
|---------|----------|
| Eksport PDF > 200 stron może trwać > 60 s | Podziel raport na mniejsze sekcje |
| Integracja z Jira Server (on-premise) nie testowana | Używaj Jira Cloud |
| Flutter shell na Linuxie — okazjonalne mruganie WebView | Zaktualizuj flutter do najnowszej wersji |

### Breaking changes

- **Nowe zmienne środowiskowe wymagane:**
  - `TPAY_CLIENT_ID`, `TPAY_CLIENT_SECRET`, `TPAY_NOTIFICATION_URL` — integracja płatności
  - `BILLING_BASIC_MONTHLY_PRICE`, `BILLING_PREMIUM_MONTHLY_PRICE` — ceny planów
- **Nowe serwisy Docker Compose:** brak nowych (tpay to zewnętrzna usługa)

### Wymagania migracji

1. Zaktualizuj zmienne środowiskowe (`.env`) o klucze tpay i konfigurację planów
2. Uruchom migracje bazy danych:
   ```bash
   docker compose exec backend alembic upgrade head
   ```
3. Skonfiguruj webhook URL w panelu tpay: `https://<domena>/api/v1/billing/webhooks/tpay`
4. Zweryfikuj nowe tabele: `subscriptions`, `subscription_plans`, `invoices`, `payments`, `payment_tokens`, `webhook_events`
5. Zaktualizuj Helm values (K8s) o sekcję `billing`

---

## v2.0 — Faza P2 (Q3 2026)

**Data wydania:** wrzesień 2026 · **Faza:** P2 — Bezpieczeństwo, testy i raporty

### Podsumowanie

Wersja 2.0 dodaje zaawansowane moduły analityczne: skanowanie bezpieczeństwa (SAST, taint analysis, dependency scan), generowanie przypadków testowych i kodu testowego (12 frameworków), dashboard z widgetami, kompletny system eksportu raportów oraz asystenta AI (chatbot).

### Nowe funkcje

| Funkcja | Epik | Opis |
|---------|------|------|
| **Moduł bezpieczeństwa (M6)** | E4 | SAST, taint analysis, dependency scan, config scan |
| **Pipeline CVE** | E4 | Automatyczna aktualizacja bazy podatności (NVD, GitHub Advisory, OSV) |
| **Raport podatności** | E4 | Klasyfikacja: Critical/High/Medium/Low, wynik CVSS |
| **SBOM** | E4 | Software Bill of Materials (CycloneDX / SPDX) |
| **Generowanie przypadków testowych** | E5 | Native (szablony) + LLM (semantyczne), priorytetyzacja |
| **Generowanie kodu testowego** | E5 | 12 frameworków: pytest, JUnit, NUnit, Playwright, Cypress, Selenium, Appium, SikuliX, Mocha/Jest, PHPUnit, Database |
| **Scenariusze Gherkin/BDD** | E5 | Given-When-Then z opcjonalnym wzbogaceniem LLM |
| **Dashboard** | E6 | Karty statystyk, tabela projektów z sortowaniem i paginacją, szybkie akcje |
| **Eksport raportów** | E6 | PDF (WeasyPrint), HTML, Excel (.xlsx), CSV, JSON |
| **Asystent AI** | E6 | Chatbot — pomoc kontekstowa w panelu |

### Ulepszenia

- **Dual-path engine** — ulepszony tryb `hybrid` z ResultMerger (scalenie + deduplikacja + priorytetyzacja)
- **Analiza kodu (M1)** — dodano adaptery: C, C++, PHP (łącznie 8 języków)
- **Analiza dokumentacji (M2)** — ulepszona ekstrakcja wymagań z tabel PDF
- **Cross-diagram analyzer (M3)** — korelacja między diagramami UML
- **Visual regression (M4)** — porównanie wizualne UI (pixelmatch)

### Poprawki błędów

- Naprawiono parsowanie zagnieżdżonych klas w Javie (tree-sitter)
- Naprawiono timeout przy plikach > 50 KB w trybie LLM
- Naprawiono ekstrakcję tabel z wielokolumnowych PDF
- Naprawiono błąd MFA przy logowaniu z innej strefy czasowej

### Znane problemy

| Problem | Obejście |
|---------|----------|
| SikuliX wymaga ręcznych referencyjnych obrazów | Przygotuj zrzuty ekranu przed generowaniem |
| OCR na ciemnym motywie UI — niższa dokładność | Używaj jasnego motywu do zrzutów GUI |
| Dependency scan może nie wykryć podatności < 24 h | Uruchom ręczną aktualizację CVE pipeline |

### Breaking changes

- **Nowe kolejki Celery:** `security` (skanowanie bezpieczeństwa) — dodaj do konfiguracji workera
- **Nowe zmienne środowiskowe:**
  - `ENGINE_MODE` — domyślny tryb silnika (`native`/`llm`/`hybrid`)
  - `LLM_PROVIDER`, `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — konfiguracja dostawcy LLM
  - `LLM_COST_LIMIT_BASIC`, `LLM_COST_LIMIT_PROFESSIONAL` — limity kosztów

### Wymagania migracji

1. Zaktualizuj zmienne środowiskowe o konfigurację LLM i trybu silnika
2. Uruchom migracje bazy danych:
   ```bash
   docker compose exec backend alembic upgrade head
   ```
3. Dodaj kolejkę `security` do konfiguracji Celery workera
4. Zweryfikuj nowe tabele: `test_cases`, `test_code`, `security_findings`, `gap_findings`, `gherkin_features`
5. Zaimportuj dashboard Grafana: `grafana-dashboard.json`

---

## v1.0 — Faza P1 (Q2 2026)

**Data wydania:** czerwiec 2026 · **Faza:** P1 — Infrastruktura i podstawowe analizy

### Podsumowanie

Pierwsze wydanie platformy TestGEN. Obejmuje infrastrukturę (monorepo, Docker Compose, PostgreSQL z RLS, multi-tenancy), uwierzytelnianie (Argon2id + RS256 JWT + MFA TOTP), zarządzanie projektami oraz trzy moduły analityczne: analiza kodu (M1), analiza dokumentacji (M2), analiza UML (M3) i analiza GUI (M4).

### Nowe funkcje

| Funkcja | Epik | Opis |
|---------|------|------|
| **Monorepo** | E1 | Backend (FastAPI) + Frontend (Angular) + Flutter w jednym repozytorium |
| **Multi-tenancy (RLS)** | E1 | Izolacja danych firm za pomocą Row-Level Security PostgreSQL |
| **Rejestracja i logowanie** | E1 | E-mail + hasło (Argon2id), weryfikacja e-mail |
| **JWT (RS256)** | E1 | Asymetryczne tokeny, HttpOnly cookies, refresh tokens |
| **MFA (TOTP)** | E1 | Opcjonalny drugi składnik uwierzytelniania |
| **RBAC** | E1 | Role: Owner (firma), User (firma), Admin (platforma) |
| **Zarządzanie projektami** | E1 | Tworzenie, konfiguracja, przesyłanie plików |
| **Analiza kodu (M1)** | E2 | Parsowanie AST (tree-sitter, 8 języków), ekstrakcja struktury |
| **Analiza dokumentacji (M2)** | E2 | Parsowanie PDF/DOCX/HTML/MD, ekstrakcja wymagań, glosariusz |
| **Analiza UML (M3)** | E3 | Parsowanie XMI/PlantUML/SVG, diagramy klas/sekwencji/use-case |
| **Analiza GUI (M4)** | E3 | OCR, detekcja komponentów UI, rekonstrukcja przepływów |
| **Macierz śledzenia** | E3 | Traceability: wymagania ↔ implementacja ↔ testy |
| **Celery + RabbitMQ** | E1 | Asynchroniczne przetwarzanie analiz (4 kolejki) |
| **MinIO** | E1 | Magazyn plików użytkowników (S3-compatible) |

### Ulepszenia

Pierwsze wydanie — brak ulepszeń.

### Poprawki błędów

Pierwsze wydanie — brak poprawek.

### Znane problemy

| Problem | Obejście |
|---------|----------|
| Brak trybu LLM (engine_mode=native only) | Planowane w v2.0 |
| Brak eksportu raportów | Planowane w v2.0 |
| Brak integracji z systemami zewnętrznymi | Planowane w v3.0 |

### Breaking changes

Nie dotyczy (pierwsze wydanie).

### Wymagania migracji

Nie dotyczy (pierwsze wydanie). Instalacja od zera — patrz [Dokumentacja wdrożeniowa](../deployment-guide/01-instalacja.md).

---

## Szablon release notes

Szablon nowego wydania wraz z zasadami wypełniania: [_template.md](_template.md).

---

## Powiązane dokumenty

- [CHANGELOG.md](CHANGELOG.md) — szczegółowy changelog w formacie Keep a Changelog
- [Dokumentacja wdrożeniowa](../deployment-guide/) — instrukcje instalacji i aktualizacji
- [Podręcznik administratora](../admin-guide/admin-guide.md) — procedura aktualizacji z perspektywy admina
