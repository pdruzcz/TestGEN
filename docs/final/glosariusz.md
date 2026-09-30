# Glosariusz TestGEN

> Wspólny słownik pojęć dokumentacji końcowej — scalony z glosariuszy
> modułowych (bezpieczeństwo, luki funkcjonalne, interfejs webowy, billing)
> i uzupełniony o terminy architektury. Terminy techniczne pozostają
> w angielskim oryginale, definicje po polsku.

## A — analiza, integracje

| Termin | Definicja |
|---|---|
| **Active scan** | Faza ZAP wstrzykująca payloady ataków do odkrytych punktów wejścia. |
| **ADR** | Architecture Decision Record — zapis decyzji architektonicznej z kontekstem i konsekwencjami (`architecture/adr/`). |
| **ADO (Azure DevOps)** | Platforma Microsoft do zarządzania cyklem życia oprogramowania; moduł integracji synchronizuje znaleziska jako Work Items. |
| **AOT** | Ahead-of-Time compilation — produkcyjna kompilacja szablonów Angulara; łapie błędy typów niewidoczne w testach. |
| **Alembic** | Narzędzie migracji schematu bazy danych dla SQLAlchemy (`backend/alembic/versions/`). |
| **Analiza regresji** | Porównanie wyników analizy między uruchomieniami — wykrywa, co się zmieniło w kodzie/dokumentacji. |
| **Angular** | Framework frontendowy (v21, komponenty standalone, Material, signals) — warstwa UI platformy. |
| **AnalysisResult** | Rekord wyniku uruchomienia modułu analizy (`analysis_results`); np. `module="requirements"`, `module="logic_structures"`. |
| **ARIA** | Atrybuty dostępności (role, etykiety, stany) dla technologii wspomagających. |
| **Argon2id** | Algorytm haszowania haseł (wybór ADR-003). |
| **Audit log** | Dziennik operacji wrażliwych (kto, co, kiedy, tenant) — retencja 1 rok. |
| **axe-core** | Silnik automatycznego audytu dostępności; w CI próg: 0 naruszeń critical/serious (WCAG 2.1 A/AA). |
| **Azure DevOps** | patrz ADO. |

## B — billing

| Termin | Definicja |
|---|---|
| **Beat (Celery beat)** | Harmonogram zadań okresowych (odnowienia 03:30, snapshoty 00:00, progi co godzinę). |
| **BLIK** | Metoda płatności mobilnej w Polsce; w TestGEN z Płatnościami Powtarzalnymi (alias). |
| **Checkout** | Przepływ zakupu: utworzenie transakcji u tpay i przekierowanie na Panel Transakcyjny. |
| **CodeEntity** | Ustrukturyzowana reprezentacja bytu kodu (funkcja/klasa): `entity_id`, `name`, `type`, `file_path`, `language`, `docstring`. |
| **Compliance score** | Ocena 0–100, jak dobrze kod spełnia dokumentację; wyliczana przez `ComplianceEngine` z `gap_findings`. |
| **Compliance snapshot** | Punkt w czasie z compliance score — podstawa porównań wersji. |
| **Confidence** | Zaufanie do znaleziska/rekomendacji (0.0–1.0); zależy od narzędzia i potwierdzeń; < 0.5 = weryfikacja człowieka. |
| **Context (luki)** | Fragment wymagania + kodu dołączany do znaleziska — pomaga zrozumieć źródło luki. |
| **CSRF** | Cross-Site Request Forgery — wymuszenie niezamierzonej operacji (CWE-352). |
| **CVE** | Common Vulnerabilities and Exposures — publiczny identyfikator znanej podatności. |
| **CVSS** | Common Vulnerability Scoring System — ocena powagi 0.0–10.0 (wersja 3.1). |
| **CVE pipeline** | Miesięczna aktualizacja bazy CVE z NVD/OSV/GitHub Advisory + auto-reguły SAST. |
| **CWE** | Common Weakness Enumeration — klasyfikacja typów słabości (np. CWE-89 = SQLi). |

## D—F

| Termin | Definicja |
|---|---|
| **DAST** | Dynamic Application Security Testing — analiza uruchomionej aplikacji (OWASP ZAP). |
| **Deep link** | Link `testgen://ścieżka` otwierający konkretny ekran w aplikacji natywnej. |
| **Diff viewer** | Widok porównania dwóch wersji obok siebie (kod↔dokumentacja, porównania analiz). |
| **Dunning** | Procedura ponowień po nieudanym obciążeniu odnowieniowym; kończy się downgrade do Freemium. |
| **Drag & drop** | Przeciąganie plików na obszar uploadu (wspólny `file-upload.component`). |
| **Effort** | Szacowany koszt naprawy: S/M/L (luki) lub low/medium/high (bezpieczeństwo). |
| **Event_uid** | Deterministyczny identyfikator notyfikacji tpay — podstawa idempotencji webhooków. |
| **Extra** | Typ luki: kod nie ma odpowiadającego wymagania w dokumentacji; severity info. |
| **False positive (FP)** | Fałszywy alarm — znalezisko, które nie jest realną podatnością. |
| **FastAPI** | Framework backendowy (Python) — REST API `/api/v1` z automatycznym OpenAPI. |
| **Feature gating (402)** | Blokada modułu analizy poza planem — widoczna-zablokowana w UI, HTTP 402 w API (FR71). |
| **Finding** | Pojedynczy rekord luki w `gap_findings` (lub zagrożenia w `security_findings`). |
| **Faktura VAT** | Automatyczna faktura po płatności: numer `FV/rok/miesiąc/seq`, VAT 23%, snapshoty stron, PDF w MinIO + email. |
| **Fernet** | Szyfrowanie poświadczeń integracji (Jira/ADO) w `integration_configs`. |
| **FindingStatus** | Status znaleziska: OPEN / ACKNOWLEDGED / FIXED / FALSE_POSITIVE. |
| **Flutter** | Framework aplikacji natywnych — powłoka WebView (mobile/desktop) dla frontendu webowego. |
| **FR38–FR42** | Wymagania funkcjonalne Epic 5: dopasowanie wymagań, 4 typy luk, compliance, detekcja błędów, rekomendacje. |

## G—I

| Termin | Definicja |
|---|---|
| **GapClassifier** | Serwis klasyfikujący wynik `ComparatorService` w 4 typy luk + severity. |
| **Golden data** | Korpus referencyjny (wejście + oczekiwany wynik) do testów dokładności analiz (ADR-008). |
| **Grace (7 dni)** | Okres łaski po dunningu — limit płatnego planu jeszcze obowiązuje. |
| **Guard** | Ochrona tras Angulara: `auth.guard` (zalogowanie), `role.guard` (rola). |
| **Hardcoded secret** | Sekret zakodowany na stałe w kodzie (CWE-798). |
| **HttpOnly cookie** | Ciasteczko sesyjne niedostępne dla JavaScript — nośnik uwierzytelnienia. |
| **IDOR** | Insecure Direct Object Reference — dostęp do obiektu po ID bez kontroli właściciela (CWE-639). |
| **Idempotencja** | Gwarancja, że powtórzona operacja nie wywoła podwójnych skutków (webhooki, faktury, seed). |
| **Inconsistent** | Typ luki: byt kodu mapowany do sprzecznych wymagań; severity critical. |
| **Interceptor** | Przetwarzanie żądań HTTP w Angularze: auth (token, 401), snake-case (konwersja pól JSON). |
| **IntegrationProvider** | Enum dostawcy integracji: `jira` \| `azure_devops`. |
| **IntegrationSyncLog** | Wpis historii synchronizacji z zewnętrznym trackerem. |

## J—M

| Termin | Definicja |
|---|---|
| **Jaro-Winkler** | Algorytm podobieństwa napisów (favoruje wspólny prefiks) — jeden z 3 algorytmów dopasowania luk. |
| **Jinja2** | Silnik szablonów (ADR-006): generowanie kodu testów, skeletonów, raportów, PDF faktur. |
| **Jira** | Tracker Atlassian; integracja synchronizuje luki jako issues (skeleton w załączniku). |
| **JWS** | JSON Web Signature — podpis notyfikacji tpay w nagłówku `X-JWS-Signature` (detached payload). |
| **JWT RS256** | Tokeny uwierzytelniające podpisywane asymetrycznie (klucz prywatny/ publiczny RSA; ADR-003). |
| **Kolejki Celery** | `default`, `analysis`, `export`, `security` — routing zadań per moduł. |
| **Lazy loading** | Ładowanie kodu ekranu dopiero przy wejściu na trasę (`loadComponent`/`loadChildren`). |
| **Levenshtein** | Odległość edycyjna napisów — algorytm dopasowania wymagań do bytów kodu. |
| **Liczniki zużycia** | `analyses`, `test_cases`, `storage_bytes`, `files_per_analysis` — egzekwowane per plan. |
| **Live region (aria-live)** | Region ogłaszający zmiany czytnikom ekranu bez zmiany fokusu. |
| **Luka (gap)** | Rozbieżność między wymaganie a implementacją: missing / different / extra / inconsistent. |

## N—P

| Termin | Definicja |
|---|---|
| **Missing** | Typ luki: wymaganie istnieje, kod nie zawiera odpowiadającego bytu. |
| **MinIO** | Object storage (S3-compatible): pliki projektów, wizerunki, faktury (bucket `testgen-invoices`). |
| **Monorepo** | Jedno repozytorium: `backend/` + `frontend/` + `mobile/` (ADR-001). |
| **Multi-tenancy** | Izolacja danych firm (tenantów) — wiersze z `tenant_id` + polityki RLS (ADR-002). |
| **MFA / TOTP** | Drugi składnik uwierzytelnienia — kody jednorazowe na podstawie czasu (opcjonalny). |
| **NVD / OSV** | Bazy podatności: NIST National Vulnerability Database / Open Source Vulnerabilities. |
| **Okres rozliczeniowy** | Miesięczne okno subskrypcji; w jego granicach liczone są limity. |
| **OpenAPI** | Specyfikacja REST API generowana z FastAPI (`/openapi.json`, Swagger UI `/docs`). |
| **OWASP Top 10** | Lista najczęstszych ryzyk aplikacji webowych (2021) — kategorie znalezisk bezpieczeństwa. |
| **Owner / User / Admin** | Role: Owner zarządca tenanta, User użytkownik, Admin platforma. |
| **Panel Transakcyjny** | Strona tpay, gdzie płatnik wybiera metodę (BLIK/karta/przelew) i autoryzuje płatność. |
| **PaymentToken** | Zapisana metoda płatności: token karty lub alias BLIK (szyfrowany per-tenant). |
| **Plan (Freemium/Basic/Premium)** | Poziom subskrypcji decydujący o limitach i dostępnych modułach analizy. |
| **Playwright** | Framework testów E2E frontendu (`frontend/e2e/`). |
| **PoC** | Proof of Concept — bezpieczny dowód istnienia podatności (filtr `poc_safety`). |
| **Proration** | Rozliczenie proporcjonalne przy upgrade: dopłata = różnica cen × pozostałe dni okresu. |
| **Progi powiadomień** | 80 / 90 / 100% limitu — powiadomienie in-app + email, dedup per okres. |
| **Prognoza limitu** | Ekstrapolacja dziennego zużycia (≥7 dni danych) — ostrzeżenie przed wyczerpaniem limitu. |
| **Priority** | Kolejność naprawy (P1 najwyższy dla luk; 1 najwyższy dla bezpieczeństwa) — wyliczana przez risk engine. |
| **Prometheus** | Metryki (m.in. `webhook_processed_total`) + alerty operacyjne. |
| **Raport dwupoziomowy** | Executive summary (zarząd) + szczegóły techniczne (QA) z jednego zbioru wyników (FR44). |

## R—S

| Termin | Definicja |
|---|---|
| **RabbitMQ** | Broker komunikatów dla Celery (ADR-004). |
| **Reconciliation** | Jednorazowe dopytanie tpay o status transakcji, gdy lokalny status zbyt długo wisi na „oczekująca". |
| **Redis** | Cache + backend wyników Celery + postęp zadań. |
| **Rekomendacja** | Actionable sugestia naprawy luki/podatności: priority, confidence, akcja, effort. |
| **Replay webhooka** | Ponowne przetwarzanie zapisanej notyfikacji tpay przez admina (rozjazd stanu po awarii). |
| **Requirement** | Wymaganie wyciągnięte z dokumentacji (ID np. REQ-ANL-004) — podstawa porównania z kodem. |
| **RLS** | Row Level Security — izolacja wierszy per tenant w PostgreSQL; admin ma politykę bypass. |
| **Sandbox tpay** | Środowisko testowe tpay (kwoty sterujące scenariuszami) — runbook w troubleshooting. |
| **Sanitizer** | Funkcja neutralizująca skażenie dla określonego typu sinka (`html.escape` chroni HTML, nie SQL). |
| **SAST** | Static Application Security Testing — analiza statyczna kodu (reguły wzorców). |
| **SBOM** | Software Bill of Materials — inwentarz komponentów (CycloneDX, SPDX). |
| **SCA** | Software Composition Analysis — analiza zależności pod kątem znanych podatności. |
| **Severity** | Powaga: CRITICAL / HIGH / MEDIUM / LOW / INFO. |
| **Signals** | Reaktywny stan Angulara (`signal()`, `computed()`) — podstawa stanu UI. |
| **Sink** | Niebezpieczna operacja na danych (np. `cursor.execute`, `eval`). |
| **Skeleton code** | Stub implementacji dla luki `missing` (Jinja2 + tree-sitter; `NotImplementedError`). |
| **Skip-link** | Link „Przejdź do treści" — pierwszy fokus strony (WCAG 2.4.1). |
| **Source** | Punkt wejścia niezaufanych danych (np. `request.GET`, `argv`). |
| **Source (znaleziska)** | Silnik, który wykrył znalezisko/rekomendację. |
| **Spider** | Faza ZAP odkrywająca powierzchnię ataku (URL-e, formularze). |
| **SQLi** | SQL Injection — wstrzyknięcie do zapytania SQL (CWE-89). |
| **Standalone component** | Komponent Angular bez NgModule — sam deklaruje zależności. |
| **Snapshot danych fakturowych** | Kopia danych sprzedawcy/nabywcy w fakturze w chwili wystawienia — niezmienna. |
| **Taint analysis** | Śledzenie przepływu niezaufanych danych od source do sink. |
| **Tenant** | Firma (organizacja) — jednostka rozliczeniowa i izolacji danych. |

## T—Ż

| Termin | Definicja |
|---|---|
| **TF-IDF cosine** | Podobieństwo wektorów term-frequency — trzeci algorytm dopasowania luk. |
| **TMS** | Test Management System (TestRail, Xray, Zephyr) — cel eksportu test case'ów (CSV/XML). |
| **Tokenizacja karty** | Zapis karty u tpay bez obciążenia — platforma dostaje token zamiast numeru. |
| **tpay** | Jedyny provider płatności (decyzja CR 2026-08-28): BLIK, karta, przelew; webhooki JWS. |
| **Traceability** | Powiązanie wymaganie ↔ test ↔ kod — macierz pokrycia (E3). |
| **Tree-sitter** | Parser AST wielu języków — analiza kodu i walidacja skeletonów (ADR-005). |
| **Troubleshooting** | Sekcja runbooków i rozwiązywania problemów (`troubleshooting/`). |
| **Unified diff** | Format patcha (`git apply`) z kontekstem i numerami linii. |
| **Vitest / ng test** | Runner testów komponentowych frontendu (builder `@angular/build:unit-test`). |
| **WCAG 2.1 AA** | Web Content Accessibility Guidelines — standard dostępności całego UI. |
| **Webhook** | Notyfikacja HTTP od tpay o zdarzeniu płatności — podpisana JWS; aktywuje plan. |
| **WebView** | Osadzona przeglądarka w aplikacji natywnej — sposób działania powłoki Flutter. |
| **Widoczne-zablokowane** | Zasada FR71: moduł poza planem widoczny z kłódką (nie ukryty), backend odpowiada 402. |
| **Wysoki kontrast** | Motyw czarno-biały z kontrastem tekstu ≥ 7:1 (AAA) — klasa `high-contrast`. |
| **XSS** | Cross-Site Scripting — wstrzyknięcie skryptu do wyjścia HTML (CWE-79). |
| **Zaplanowany downgrade** | Zmiana na niższy plan skuteczna na koniec bieżącego okresu (lokalna, bez zwrotów). |
| **Zasoby (usage)** | Liczniki zużycia per tenant — dashboard, historia, prognoza. |
| **md5sum** | Dodatkowa suma kontrolna notyfikacji transakcyjnych tpay. |
