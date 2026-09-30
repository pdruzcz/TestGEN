# Changelog

Wszystkie istotne zmiany w platformie TestGEN są dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/).
Wersjonowanie zgodne z [Semantic Versioning](https://semver.org/lang/pl/).

## [3.0.0] — 2026-12 (Faza P3)

### Dodane
- Integracja z Jira Cloud — tworzenie zadań, synchronizacja statusów (E7)
- Integracja z Azure DevOps — work items, integracja z pipeline'ami (E7)
- Webhooks GitHub/GitLab — automatyczne analizy przy push/merge (E7)
- Generator konfiguracji CI/CD — Jenkins, GitHub Actions, Azure Pipelines, GitLab CI (E7)
- Eksport do TestRail (CSV) i Jira XRay (XML) (E7)
- Moduł płatności tpay — BLIK, karta, przelew bankowy (E8)
- Plany subskrypcji: Freemium / Basic (30 PLN/mies.) / Premium (50 PLN/mies.) (E8)
- Automatyczne generowanie faktur VAT (PDF → MinIO) (E8)
- Dunning — 7-dniowy grace period dla nieudanych płatności (E8)
- Bramka funkcji — blokowanie modułów niedostępnych w planie (E8)
- Klucze API — tworzenie, rotacja, revoke, rate limiting (E8)
- Gap analysis — porównanie wymagań vs implementacja vs testy (E5)
- Dokumentacja końcowa: podręcznik użytkownika, administratora, wdrożeniowy, architektura C4, moduły AI, troubleshooting (E9)

### Zmienione
- Shell Flutter — wsparcie dla macOS, Windows, Linux (desktop)
- Dashboard Grafana — 10 paneli, ulepszone progi alertów
- Panel admina — sekcja konfiguracji platformy, pipeline CVE, replay webhooków

### Poprawione
- Wyświetlanie dashboardu przy braku danych historycznych
- Sortowanie null-last w tabelach projektów
- Widoczność etykiet w trybie wysokiego kontrastu
- Blokada konta po nieudanym logowaniu z MFA
- Timeout przy generowaniu dużych raportów PDF

### Bezpieczeństwo
- Weryfikacja podpisu JWS dla webhooków tpay
- Anonimizacja danych w wywołaniach LLM (maskowanie sekretów, e-maili, IP)
- Limity kosztów LLM per plan (ochrona przed niekontrolowanymi wydatkami)

## [2.0.0] — 2026-09 (Faza P2)

### Dodane
- Moduł bezpieczeństwa M6 — SAST, taint analysis, dependency scan, config scan (E4)
- Pipeline CVE — automatyczna aktualizacja bazy podatności (NVD, GitHub Advisory, OSV) (E4)
- Raport podatności z klasyfikacją CVSS (Critical/High/Medium/Low) (E4)
- SBOM — Software Bill of Materials (CycloneDX / SPDX) (E4)
- Generowanie przypadków testowych — native (Jinja2) + LLM (semantyczne) (E5)
- Generowanie kodu testowego — 12 frameworków: pytest, JUnit 5, NUnit, Playwright, Cypress, Selenium, Appium, SikuliX, Mocha/Jest, PHPUnit, Database (E5)
- Scenariusze Gherkin/BDD z opcjonalnym wzbogaceniem LLM (E5)
- Dashboard — karty statystyk, tabela projektów z sortowaniem i paginacją (E6)
- Eksport raportów — PDF, HTML, Excel (.xlsx), CSV, JSON (E6)
- Asystent AI — chatbot z pomocą kontekstową (E6)
- Tryb silnika LLM i hybrid (`engine_mode`) z konfiguracją per tenant
- LLM Gateway — abstrakcja dostawców (Anthropic/OpenAI), retry, fallback, śledzenie kosztów

### Zmienione
- Dual-path engine — ulepszony ResultMerger (scalenie + deduplikacja + priorytetyzacja)
- Analiza kodu M1 — dodano adaptery: C, C++, PHP (łącznie 8 języków)
- Analiza dokumentacji M2 — ulepszona ekstrakcja wymagań z tabel PDF
- Cross-diagram analyzer M3 — korelacja między diagramami UML
- Visual regression M4 — porównanie wizualne UI (pixelmatch)

### Poprawione
- Parsowanie zagnieżdżonych klas w Javie (tree-sitter)
- Timeout przy plikach > 50 KB w trybie LLM
- Ekstrakcja tabel z wielokolumnowych PDF
- Błąd MFA przy logowaniu z innej strefy czasowej

### Bezpieczeństwo
- LLM SAST — wykrywanie logicznych podatności (TOCTOU, mass assignment, race conditions)
- Dependency scanner — automatyczne sprawdzanie CVE w zależnościach

## [1.0.0] — 2026-06 (Faza P1)

### Dodane
- Monorepo: backend (FastAPI) + frontend (Angular 21) + Flutter (E1)
- Multi-tenancy via PostgreSQL Row-Level Security (RLS) (E1)
- Rejestracja i logowanie — e-mail + hasło (Argon2id) (E1)
- JWT (RS256) — asymetryczne tokeny, HttpOnly cookies, refresh tokens (E1)
- MFA (TOTP) — opcjonalny drugi składnik uwierzytelniania (E1)
- RBAC — role: Owner, User, Admin (E1)
- Zarządzanie projektami — tworzenie, konfiguracja, przesyłanie plików (E1)
- Analiza kodu M1 — parsowanie AST (tree-sitter, 8 języków) (E2)
- Analiza dokumentacji M2 — PDF/DOCX/HTML/MD, ekstrakcja wymagań, glosariusz (E2)
- Analiza UML M3 — XMI/PlantUML/SVG, diagramy klas/sekwencji/use-case (E3)
- Analiza GUI M4 — OCR, detekcja komponentów UI, rekonstrukcja przepływów (E3)
- Macierz śledzenia (traceability) — wymagania ↔ implementacja ↔ testy (E3)
- Celery + RabbitMQ — asynchroniczne przetwarzanie (kolejki: default, analysis, export) (E1)
- MinIO — magazyn plików (S3-compatible) (E1)
- Redis — cache sesji, result backend Celery (E1)
- Prometheus + Grafana + Loki — monitoring i logi (E1)

### Bezpieczeństwo
- Argon2id — haszowanie haseł (najsilniejszy algorytm)
- RS256 JWT — asymetryczne podpisywanie tokenów
- RLS PostgreSQL — izolacja danych firm na poziomie bazy
- Audit logging — rejestrowanie operacji wrażliwych

[3.0.0]: https://bitbucket.org/nexio-workspace/testgen/compare/v2.0.0...v3.0.0
[2.0.0]: https://bitbucket.org/nexio-workspace/testgen/compare/v1.0.0...v2.0.0
[1.0.0]: https://bitbucket.org/nexio-workspace/testgen/commits/tag/v1.0.0
