# Dokumentacja architektury TestGEN — C4 i diagramy

> **Wersja:** 1.0 · **Ostatnia aktualizacja:** 2026-09 · **Grupa docelowa:** Architekci, deweloperzy, DevOps

---

## Spis treści

1. [Wprowadzenie](#1-wprowadzenie)
2. [C4 Level 1 — Diagram kontekstowy (Context)](#2-c4-level-1--diagram-kontekstowy-context)
3. [C4 Level 2 — Diagram kontenerów (Container)](#3-c4-level-2--diagram-kontenerów-container)
4. [C4 Level 3 — Diagramy komponentów (Component)](#4-c4-level-3--diagramy-komponentów-component)
5. [C4 Level 4 — Diagramy kodu (Code)](#5-c4-level-4--diagramy-kodu-code)
6. [Diagramy przepływu danych](#6-diagramy-przepływu-danych)
7. [Diagramy wdrożeniowe (Deployment)](#7-diagramy-wdrożeniowe-deployment)
8. [Diagramy sekwencji](#8-diagramy-sekwencji)
9. [Decyzje architektoniczne (ADR)](#9-decyzje-architektoniczne-adr)
10. [Konwencje diagramów](#10-konwencje-diagramów)

---

## 1. Wprowadzenie

### 1.1. Cel dokumentu

Dokument przedstawia architekturę platformy TestGEN na czterech poziomach szczegółowości zgodnie z modelem C4 (Context, Container, Component, Code). Uzupełniają go diagramy przepływu danych, diagramy wdrożeniowe oraz diagramy sekwencji kluczowych przepływów.

### 1.2. Czym jest TestGEN

TestGEN to platforma SaaS B2B do automatycznego generowania przypadków testowych i kodu testowego z wykorzystaniem sztucznej inteligencji. System analizuje kod źródłowy, dokumentację, diagramy UML i zrzuty GUI, a następnie generuje kompletne zestawy testów z priorytetyzacją i kodem gotowym do uruchomienia.

### 1.3. Stos technologiczny

| Warstwa | Technologia | Wersja |
|---------|-------------|--------|
| Frontend (SPA) | Angular, Material 3, Standalone Components | 21 |
| Frontend (mobile/desktop) | Flutter WebView | 3.x |
| Backend (API) | Python, FastAPI, SQLAlchemy 2.0 async | 3.12 |
| Zadania asynchroniczne | Celery | 5.x |
| Baza danych | PostgreSQL (Row-Level Security) | 16 |
| Broker wiadomości | RabbitMQ | 3.12 |
| Cache / Result Backend | Redis | 7 |
| Magazyn obiektowy | MinIO (S3-compatible) | — |
| Monitoring | Prometheus + Grafana + Loki + Alertmanager | — |
| Parsowanie kodu | tree-sitter (adaptery per język) | — |
| Szablony testów | Jinja2 | — |
| Uwierzytelnianie | Argon2id (hasła) + RS256 JWT (tokeny) | — |
| Płatności | tpay (BLIK, karta, przelew) | — |

### 1.4. Model C4

Model C4 definiuje cztery poziomy abstrakcji:

| Poziom | Nazwa | Co pokazuje |
|--------|-------|-------------|
| 1 | Context | System w kontekście użytkowników i systemów zewnętrznych |
| 2 | Container | Kontenery wdrożeniowe (aplikacje, bazy, kolejki) |
| 3 | Component | Moduły wewnętrzne per kontener |
| 4 | Code | Klasy, interfejsy, wzorce projektowe |

### 1.5. Pliki źródłowe diagramów

Wszystkie diagramy przechowywane są w formacie PlantUML (`.puml`) w katalogu `diagrams/`. Renderowanie do PNG/SVG wymaga narzędzia `plantuml` lub wtyczki IDE.

```
docs/final/architecture/diagrams/
├── c4-context.puml              # C4 Level 1
├── c4-container.puml            # C4 Level 2
├── c4-component-m1.puml         # C4 Level 3 — M1 Analiza kodu
├── c4-component-m2.puml         # C4 Level 3 — M2 Analiza dokumentacji
├── c4-component-m3.puml         # C4 Level 3 — M3 Analiza UML
├── c4-component-m4.puml         # C4 Level 3 — M4 Analiza GUI
├── c4-component-m5.puml         # C4 Level 3 — M5 Generowanie testów
├── c4-component-m6.puml         # C4 Level 3 — M6 Bezpieczeństwo
├── c4-code-engine.puml          # C4 Level 4 — Dual-path engine
├── c4-code-pipeline.puml        # C4 Level 4 — Pipeline przetwarzania
├── c4-code-parsers.puml         # C4 Level 4 — Parsery języków
├── flow-end-to-end.puml         # Przepływ end-to-end
├── flow-analiza-kodu.puml       # Przepływ — analiza kodu
├── flow-bezpieczenstwo.puml     # Przepływ — bezpieczeństwo
├── deploy-single-node.puml      # Wdrożenie — Docker Compose
├── deploy-multi-node.puml       # Wdrożenie — Kubernetes
├── seq-rejestracja.puml         # Sekwencja — rejestracja
├── seq-analiza-kodu.puml        # Sekwencja — analiza kodu
├── seq-generowanie-testow.puml  # Sekwencja — generowanie testów
├── seq-platnosc.puml            # Sekwencja — płatność
└── seq-webhook.puml             # Sekwencja — webhook
```

---

## 2. C4 Level 1 — Diagram kontekstowy (Context)

> **Źródło PlantUML:** [`diagrams/c4-context.puml`](diagrams/c4-context.puml)

### 2.1. Opis

Diagram kontekstowy przedstawia TestGEN jako centralny system w otoczeniu użytkowników (aktorów) i systemów zewnętrznych.

### 2.2. Aktorzy

| Aktor | Opis | Interakcja |
|-------|------|------------|
| **Analityk QA (Anna)** | Główny użytkownik platformy | Tworzy projekty, przesyła pliki, uruchamia analizy, generuje testy, eksportuje raporty |
| **Administrator (Marek)** | Administrator platformy / Owner firmy | Zarządza firmami, użytkownikami, konfiguracją, monitoruje system |

### 2.3. Systemy zewnętrzne

| System | Protokół | Kierunek | Cel integracji |
|--------|----------|----------|----------------|
| **GitHub / GitLab** | HTTPS, Git | Dwukierunkowy | Klonowanie repozytoriów, odbiór webhooków (push, merge) |
| **tpay** | HTTPS REST API | Dwukierunkowy | Obsługa płatności: checkout, webhooki, tokenizacja kart/BLIK |
| **TestRail** | HTTPS REST API | Wychodzący | Eksport przypadków testowych do zewnętrznego TMS |
| **Jira / Azure DevOps** | HTTPS REST API | Dwukierunkowy | Synchronizacja wyników analiz, tworzenie zadań, integracja per projekt |
| **Serwer SMTP** | SMTP/TLS | Wychodzący | Wysyłka e-maili: weryfikacja konta, zaproszenia, alerty, faktury |
| **API LLM (Anthropic / OpenAI)** | HTTPS REST API | Wychodzący | Modele językowe: analiza semantyczna kodu/dokumentacji, generowanie testów |
| **NVD / GitHub Advisory / OSV** | HTTPS REST API | Wychodzący | Bazy podatności CVE: aktualizacja reguł skanowania bezpieczeństwa |

### 2.4. Kluczowe wnioski

- TestGEN jest systemem **samodzielnym** — nie zależy od dostępności systemów zewnętrznych (poza LLM w trybie `llm`/`hybrid`)
- Tryb `native` działa w pełni offline (bez wywołań API LLM)
- Integracje (Jira, TestRail, GitHub) są **opcjonalne** — konfigurowane per projekt
- Płatności obsługiwane wyłącznie przez tpay (polska bramka)

---

## 3. C4 Level 2 — Diagram kontenerów (Container)

> **Źródło PlantUML:** [`diagrams/c4-container.puml`](diagrams/c4-container.puml)

### 3.1. Opis

Diagram kontenerów przedstawia wszystkie kontenery wdrożeniowe platformy TestGEN i ich wzajemne relacje.

### 3.2. Kontenery

| Kontener | Technologia | Rola | Port |
|----------|-------------|------|------|
| **Frontend (SPA)** | Angular 21, nginx | Interfejs użytkownika — standalone components, Material 3, routing, formularze | 80 (nginx) |
| **Shell Flutter** | Flutter WebView | Opakowanie SPA w aplikację natywną (mobile: Android/iOS, desktop: macOS/Windows/Linux) | — |
| **Backend API** | Python 3.12, FastAPI | REST API `/api/v1` — autoryzacja JWT, logika domenowa, walidacja, RLS per tenant | 8000 |
| **Celery Workers** | Python 3.12, Celery 5 | Zadania asynchroniczne: analiza kodu, dokumentacji, UML, GUI; generowanie testów; skanowanie bezpieczeństwa; eksport raportów | — |
| **Celery Beat** | Python 3.12, Celery 5 | Harmonogram zadań periodycznych: odnowienia subskrypcji (03:30), snapshoty użycia (00:00), czyszczenie plików tymczasowych | — |
| **PostgreSQL** | PostgreSQL 16 | Relacyjna baza danych z Row-Level Security — dane biznesowe, wyniki analiz (JSONB), audyt | 5432 |
| **RabbitMQ** | RabbitMQ 3.12 | Broker wiadomości AMQP — kolejki: `default`, `analysis`, `export`, `security` | 5672 |
| **Redis** | Redis 7 | Cache sesji, result backend Celery, rate limiting, tymczasowe dane | 6379 |
| **MinIO** | MinIO | Magazyn obiektowy S3 — pliki źródłowe, dokumenty, raporty PDF, faktury VAT, zrzuty GUI | 9000 |

### 3.3. Protokoły komunikacji

| Źródło | Cel | Protokół | Opis |
|--------|-----|----------|------|
| Frontend → Backend | REST | HTTP/HTTPS | JWT w HttpOnly cookie, format JSON |
| Backend → PostgreSQL | SQL | asyncpg (binary) | Asynchroniczne połączenia, RLS context per żądanie |
| Backend → RabbitMQ | AMQP | AMQP 0-9-1 | Kolejkowanie zadań Celery |
| Backend → Redis | Redis protocol | TCP 6379 | Cache, sesje, rate limiting |
| Backend → MinIO | S3 API | HTTP | Przechowywanie i pobieranie plików |
| RabbitMQ → Workers | AMQP | AMQP 0-9-1 | Dostarczanie zadań asynchronicznych |
| Workers → PostgreSQL | SQL | asyncpg | Zapis wyników analiz |
| Workers → Redis | Redis protocol | TCP 6379 | Zapis wyników zadań (result backend) |
| Workers → MinIO | S3 API | HTTP | Odczyt plików źródłowych, zapis raportów |
| Workers → API LLM | REST | HTTPS | Wywołania modeli językowych |

### 3.4. Kolejki Celery

| Kolejka | Przeznaczenie | Priorytet |
|---------|---------------|-----------|
| `default` | Zadania ogólne (e-mail, czyszczenie, notyfikacje) | Normalny |
| `analysis` | Analiza kodu, dokumentacji, UML, GUI | Wysoki |
| `export` | Generowanie raportów PDF/HTML/Excel | Normalny |
| `security` | Skanowanie bezpieczeństwa, aktualizacja CVE | Normalny |

---

## 4. C4 Level 3 — Diagramy komponentów (Component)

### 4.1. Moduł M1 — Analiza kodu

> **Źródło PlantUML:** [`diagrams/c4-component-m1.puml`](diagrams/c4-component-m1.puml)

**Odpowiedzialność:** Parsowanie i analiza kodu źródłowego — ekstrakcja struktury, zależności, logiki biznesowej.

**Komponenty:**

| Komponent | Technologia | Rola |
|-----------|-------------|------|
| Upload Handler | FastAPI route | Odbiera pliki kodu, waliduje format i rozmiar, zapisuje w MinIO |
| AST Parser | tree-sitter | Parsuje kod do drzewa składniowego (Abstract Syntax Tree) |
| Adaptery językowe | tree-sitter-{lang} | Ekstrakcja klas, funkcji, importów per język (Python, Java, JS/TS, C#, C/C++, PHP) |
| Native Analysis | Python | Analiza deterministyczna: złożoność cyklomatyczna, zależności modułów, struktury logiczne, przepływ danych |
| LLM Analysis | Python + API LLM | Analiza semantyczna via model językowy: logika biznesowa, przepływy, przypadki krawędziowe |
| LLM Gateway | Python | Abstrakcja dostawcy LLM (Anthropic / OpenAI) — routing, retry, rate limiting |
| Result Merger | Python | Scalanie wyników native + LLM: deduplikacja, priorytetyzacja, rozwiązywanie konfliktów |
| Analysis Storage | Python + SQLAlchemy | Zapis wyników do PostgreSQL (JSONB) i MinIO (pliki tymczasowe) |

**Obsługiwane języki programowania:**

| Język | Parser | Adapter |
|-------|--------|---------|
| Python | tree-sitter-python | `ast/python_adapter.py` |
| Java | tree-sitter-java | `ast/java_adapter.py` |
| JavaScript | tree-sitter-javascript | `ast/javascript_adapter.py` |
| TypeScript | tree-sitter-typescript | `ast/typescript_adapter.py` |
| C# | tree-sitter-c-sharp | `ast/csharp_adapter.py` |
| C / C++ | tree-sitter-c / tree-sitter-cpp | `ast/c_adapter.py`, `ast/cpp_adapter.py` |
| PHP | tree-sitter-php | `ast/php_adapter.py` |

**Przepływ:**
1. Użytkownik przesyła pliki → Upload Handler → MinIO + DB
2. Parser AST wykrywa język i parsuje kod
3. Adapter językowy ekstrahuje elementy (klasy, funkcje, importy)
4. Zależnie od `engine_mode`:
   - `native` → analiza deterministyczna
   - `llm` → wywołanie API LLM
   - `hybrid` → oba + scalenie
5. Wyniki zapisywane w PostgreSQL (JSONB `analysis_results.result_data`)

---

### 4.2. Moduł M2 — Analiza dokumentacji

> **Źródło PlantUML:** [`diagrams/c4-component-m2.puml`](diagrams/c4-component-m2.puml)

**Odpowiedzialność:** Parsowanie dokumentów i ekstrakcja wymagań — funkcjonalnych i niefunkcjonalnych.

**Komponenty:**

| Komponent | Technologia | Rola |
|-----------|-------------|------|
| Document Upload | FastAPI route | Odbiera dokumenty w formatach PDF, DOCX, HTML, MD, TXT |
| Document Classifier | Python | Klasyfikacja typu dokumentu: specyfikacja, wymagania, podręcznik, notatki |
| PDF Parser | pdfplumber | Ekstrakcja tekstu, tabel i metadanych z plików PDF |
| DOCX Parser | python-docx | Ekstrakcja tekstu, struktury nagłówków i tabel z Word |
| HTML/MD Parser | BeautifulSoup / markdown | Ekstrakcja tekstu ze stron HTML i Markdown |
| Requirement Extractor | Python NLP | Ekstrakcja wymagań: identyfikacja zdań wymaganiowych, priorytet, kategoria |
| Glossary Extractor | Python NLP | Ekstrakcja terminów i definicji — budowanie glosariusza projektu |
| Inconsistency Detector | Python | Wykrywanie niespójności między dokumentami — sprzeczne wymagania, brakujące definicje |
| LLM Document Analyzer | Python + API LLM | Semantyczna analiza dokumentów: rozumienie kontekstu, intencji, relacji |

**Obsługiwane formaty:** PDF, DOCX, HTML, Markdown, TXT

---

### 4.3. Moduł M3 — Analiza UML

> **Źródło PlantUML:** [`diagrams/c4-component-m3.puml`](diagrams/c4-component-m3.puml)

**Odpowiedzialność:** Parsowanie diagramów UML i ekstrakcja elementów modelowych.

**Komponenty:**

| Komponent | Technologia | Rola |
|-----------|-------------|------|
| XMI Parser | Python lxml | Parsowanie diagramów w formacie XMI (eksport z narzędzi UML) |
| PlantUML Parser | Python regex | Parsowanie diagramów w formacie PlantUML |
| Visual Parser | Python + OCR/CV | Rozpoznawanie diagramów z obrazów (SVG, PNG) — OCR + computer vision |
| Class Diagram Analyzer | Python | Analiza klas: atrybuty, metody, relacje, dziedziczenie |
| Sequence Diagram Analyzer | Python | Analiza sekwencji: przepływy, komunikaty, aktorzy |
| Use-Case Analyzer | Python | Analiza przypadków użycia: aktorzy, scenariusze, inkluzje |
| State Machine Analyzer | Python | Analiza maszyn stanów: przejścia, warunki, akcje |
| Cross-Diagram Analyzer | Python | Korelacja między diagramami: spójność, pokrycie, brakujące elementy |
| LLM UML Analyzer | Python + API LLM | Semantyczna rekonstrukcja przepływów z diagramów |

**Obsługiwane formaty:** XMI, PlantUML, SVG, PNG (z OCR)

---

### 4.4. Moduł M4 — Analiza GUI

> **Źródło PlantUML:** [`diagrams/c4-component-m4.puml`](diagrams/c4-component-m4.puml)

**Odpowiedzialność:** Rozpoznawanie elementów interfejsu graficznego i rekonstrukcja przepływów użytkownika.

**Komponenty:**

| Komponent | Technologia | Rola |
|-----------|-------------|------|
| OCR Engine | Tesseract | Rozpoznawanie tekstu z elementów GUI |
| DOM Extractor | Selenium | Ekstrakcja struktury DOM ze stron webowych (live) |
| Component Detector | Computer Vision | Identyfikacja elementów UI: przyciski, formularze, tabele, menu |
| Flow Reconstructor | Python | Rekonstrukcja przepływów użytkownika z sekwencji ekranów |
| Visual Regression | pixelmatch | Porównanie wizualne: wykrywanie zmian UI między wersjami |
| LLM GUI Analyzer | Python + API LLM | Semantyczna identyfikacja elementów i interakcji |

---

### 4.5. Moduł M5 — Generowanie testów

> **Źródło PlantUML:** [`diagrams/c4-component-m5.puml`](diagrams/c4-component-m5.puml)

**Odpowiedzialność:** Generowanie przypadków testowych i kodu testowego na podstawie wyników analiz.

**Komponenty:**

| Komponent | Rola |
|-----------|------|
| Test Case Generator | Orkiestracja generowania — wybór strategii (native/LLM/hybrid) |
| Native Generator | Szablonowe generowanie przypadków na podstawie reguł (Jinja2) |
| LLM Generator | Semantyczne generowanie przypadków via model AI |
| Prioritizer | Priorytetyzacja testów: krytyczny / wysoki / średni / niski |
| Gherkin / BDD | Generowanie scenariuszy Given-When-Then |
| Code Generator | Renderowanie kodu testowego per framework (wzorzec strategii) |

**Obsługiwane frameworki testowe:**

| Kategoria | Framework | Język |
|-----------|-----------|-------|
| Jednostkowe | pytest | Python |
| Jednostkowe | JUnit 5 | Java |
| Jednostkowe | NUnit | C# |
| Jednostkowe | Mocha / Jest | JavaScript/TypeScript |
| Jednostkowe | PHPUnit | PHP |
| E2E Web | Playwright | Python / JS / TS |
| E2E Web | Cypress | JavaScript |
| E2E Web | Selenium | Python / Java / C# |
| E2E Mobile | Appium | Python / Java |
| Desktop GUI | SikuliX | Java (image-based) |
| Bazy danych | Database tests | SQL |

---

### 4.6. Moduł M6 — Analiza bezpieczeństwa

> **Źródło PlantUML:** [`diagrams/c4-component-m6.puml`](diagrams/c4-component-m6.puml)

**Odpowiedzialność:** Skanowanie bezpieczeństwa kodu — SAST, taint analysis, skanowanie zależności, raportowanie podatności.

**Komponenty:**

| Komponent | Rola |
|-----------|------|
| Dual-Path Orchestrator | Orkiestracja skanowania: reguły deterministyczne + LLM |
| SAST Scanner | Statyczna analiza kodu (reguły Semgrep/Bandit) |
| Taint Analysis | Śledzenie przepływu danych: SQL injection, XSS, path traversal |
| Dependency Scanner | Skanowanie zależności: bazy CVE, ocena ryzyka |
| Config Scanner | Analiza konfiguracji: sekrety w kodzie, hardening |
| CVE Pipeline | Automatyczna aktualizacja bazy CVE (NVD, GitHub Advisory, OSV) |
| CVSS Calculator | Obliczanie wyników CVSS per podatność |
| LLM SAST | Semantyczna analiza bezpieczeństwa via AI |
| Security Report | Raport podatności: klasyfikacja Critical/High/Medium/Low |
| SBOM Generator | Software Bill of Materials (CycloneDX / SPDX) |

**Bramka funkcji:** moduł bezpieczeństwa dostępny wyłącznie w planie Premium.

---

### 4.7. Moduł płatności

**Odpowiedzialność:** Obsługa subskrypcji, płatności, faktur VAT i limitów.

**Komponenty:**

| Komponent | Rola |
|-----------|------|
| Checkout Service | Tworzenie transakcji tpay, generowanie URL płatności |
| Webhook Processor | Odbiór i przetwarzanie webhooków tpay (JWS) |
| Subscription Service | Zarządzanie subskrypcjami: tworzenie, odnowienie, dunning |
| Invoice Service | Generowanie faktur VAT (PDF) → MinIO |
| Quota Service | Egzekwowanie limitów: analizy/mies., test case'y/mies., storage |
| Feature Gating Service | Bramki funkcji: weryfikacja dostępu per plan |
| Payment Token Store | Przechowywanie tokenów płatniczych (BLIK alias, karta) |

---

### 4.8. Moduł integracji

**Odpowiedzialność:** Integracja z systemami zewnętrznymi (per projekt).

**Komponenty:**

| Komponent | System | Rola |
|-----------|--------|------|
| Jira Adapter | Jira Cloud | Tworzenie zadań, synchronizacja statusów |
| Azure DevOps Adapter | Azure DevOps | Tworzenie work items, integracja z pipeline'ami |
| TestRail Exporter | TestRail | Eksport przypadków testowych |
| Jira XRay Exporter | Jira XRay | Eksport testów w formacie XRay |

---

## 5. C4 Level 4 — Diagramy kodu (Code)

### 5.1. Dual-Path Engine — wzorzec strategii

> **Źródło PlantUML:** [`diagrams/c4-code-engine.puml`](diagrams/c4-code-engine.puml)

**Opis:** Centralny wzorzec architektoniczny TestGEN — silnik analizy obsługujący trzy tryby przetwarzania.

**Klasy:**

| Klasa | Odpowiedzialność |
|-------|-----------------|
| `AnalysisStrategy` (interfejs) | Kontrakt: `analyze(source_files, config) → AnalysisResult` |
| `NativeStrategy` | Analiza deterministyczna — AST + reguły + heurystyki (bez API LLM, zero kosztów) |
| `LLMStrategy` | Analiza semantyczna — wywołanie modelu językowego (Anthropic / OpenAI) |
| `HybridStrategy` | Oba podejścia + scalenie wyników (ResultMerger) |
| `AnalysisEngine` | Orkiestrator — wybiera strategię na podstawie `engine_mode` z konfiguracji |
| `ResultMerger` | Scalanie wyników: deduplikacja, priorytetyzacja, rozwiązywanie konfliktów |

**Enum `EngineMode`:**
- `NATIVE` — tylko analiza deterministyczna
- `LLM` — tylko model językowy
- `HYBRID` — oba + scalenie

**Wzorzec ten stosowany jest w:**
- Analiza kodu (M1) — `services/analysis/native_analysis.py` + `llm_analysis.py`
- Analiza dokumentacji (M2) — `services/analysis/document/requirement_extractor.py` + `llm_analysis.py`
- Generowanie testów (M5) — `services/test_generation/` (native Jinja2 + LLM)
- Skanowanie bezpieczeństwa (M6) — `services/security_scan/dual_path_orchestrator.py`
- Gap Analysis — `services/gap_analysis/dual_path_orchestrator.py`

---

### 5.2. Pipeline przetwarzania — wzorzec potoku

> **Źródło PlantUML:** [`diagrams/c4-code-pipeline.puml`](diagrams/c4-code-pipeline.puml)

**Opis:** Przetwarzanie analiz odbywa się sekwencyjnie przez kroki potoku (pipeline), z kontekstem przekazywanym między krokami.

**Klasy:**

| Klasa | Odpowiedzialność |
|-------|-----------------|
| `PipelineStep` (interfejs) | Kontrakt: `execute(context) → PipelineContext` |
| `PipelineContext` | Obiekt przenoszący stan: pliki, wyniki parsowania, wyniki analiz, test case'y, błędy |
| `ParseStep` | Parsowanie plików (AST, dokumenty, UML, GUI) |
| `AnalyzeStep` | Uruchomienie dual-path analizy |
| `GenerateStep` | Generowanie przypadków testowych i kodu |
| `SecurityStep` | Skanowanie bezpieczeństwa |
| `StoreStep` | Zapis wyników do bazy i magazynu plików |
| `AnalysisPipeline` | Orkiestrator — sekwencyjne wykonanie kroków z obsługą błędów |

**Przepływ:**
```
ParseStep → AnalyzeStep → GenerateStep → SecurityStep → StoreStep
```

Każdy krok otrzymuje `PipelineContext` i zwraca wzbogacony kontekst. Błąd w dowolnym kroku jest rejestrowany w `context.errors`, a przetwarzanie może kontynuować (graceful degradation) lub zatrzymać się (fail-fast), zależnie od konfiguracji.

---

### 5.3. Parsery języków — wzorzec strategii

> **Źródło PlantUML:** [`diagrams/c4-code-parsers.puml`](diagrams/c4-code-parsers.puml)

**Opis:** Każdy obsługiwany język programowania ma dedykowany parser oparty na tree-sitter.

**Klasy:**

| Klasa | Odpowiedzialność |
|-------|-----------------|
| `BaseParser` (abstrakcyjna) | Wspólna logika parsowania: inicjalizacja tree-sitter, ekstrakcja klas/funkcji/importów |
| `PythonParser` | Dodatkowa ekstrakcja: dekoratory, docstringi, type hints |
| `JavaParser` | Dodatkowa ekstrakcja: adnotacje, pakiety, interfejsy |
| `TypeScriptParser` | Dodatkowa ekstrakcja: interfejsy, typy, generyki |
| `CSharpParser` | Dodatkowa ekstrakcja: namespace'y, atrybuty, LINQ |
| `CppParser` | Dodatkowa ekstrakcja: nagłówki, szablony, makra |
| `PHPParser` | Dodatkowa ekstrakcja: traity, namespace'y |

**Zasada:** Nowy język = nowa klasa dziedzicząca `BaseParser` + odpowiednia gramatyka tree-sitter.

---

## 6. Diagramy przepływu danych

### 6.1. Przepływ end-to-end

> **Źródło PlantUML:** [`diagrams/flow-end-to-end.puml`](diagrams/flow-end-to-end.puml)

Kompletny przepływ od przesłania plików do eksportu raportów:

```
Użytkownik
  │
  ├── 1. Tworzy projekt
  ├── 2. Przesyła pliki (kod, dokumentacja, UML, GUI)
  │
  ▼
Backend API
  │
  ├── 3. Walidacja i zapis plików (MinIO)
  ├── 4. Rejestracja metadanych (PostgreSQL)
  ├── 5. Kolejkowanie zadania (RabbitMQ)
  │
  ▼
Celery Worker
  │
  ├── 6. Analiza (M1-M4): kod, dokumentacja, UML, GUI
  ├── 7. Scalenie wyników
  ├── 8. Generowanie testów (M5): przypadki + kod
  ├── 9. Skanowanie bezpieczeństwa (M6)
  ├── 10. Gap Analysis: wymagania vs implementacja vs testy
  ├── 11. Zapis wyników (PostgreSQL)
  │
  ▼
Użytkownik
  │
  ├── 12. Przegląd wyników
  ├── 13. Edycja i zatwierdzenie testów
  └── 14. Eksport raportów (PDF/HTML/Excel/CSV/JSON)
```

### 6.2. Przepływ analizy kodu

> **Źródło PlantUML:** [`diagrams/flow-analiza-kodu.puml`](diagrams/flow-analiza-kodu.puml)

**Etapy:**
1. Przesłanie plików → walidacja → MinIO + PostgreSQL
2. Kolejkowanie zadania → RabbitMQ (kolejka `analysis`)
3. Celery Worker pobiera pliki z MinIO
4. Wykrywanie języka i frameworka
5. Rozgałęzienie wg `engine_mode`:
   - **native:** parsowanie AST (tree-sitter) → analiza deterministyczna (złożoność, zależności, logika, przepływ danych)
   - **llm:** przygotowanie promptu → wywołanie API LLM → parsowanie odpowiedzi
   - **hybrid:** native + LLM + scalenie (ResultMerger)
6. Zapis wyników → PostgreSQL (JSONB) + aktualizacja statusu
7. Powiadomienie użytkownika

### 6.3. Przepływ skanowania bezpieczeństwa

> **Źródło PlantUML:** [`diagrams/flow-bezpieczenstwo.puml`](diagrams/flow-bezpieczenstwo.puml)

**Etapy:**
1. Sprawdzenie bramki funkcji (plan Premium wymagany)
2. Kolejkowanie → RabbitMQ (kolejka `security`)
3. Równoległe skanery: SAST, Taint Analysis, Dependency Scan, Config Scan
4. Obliczenie wyników CVSS per podatność
5. Klasyfikacja: Critical / High / Medium / Low
6. Opcjonalnie: LLM SAST (semantyczna weryfikacja)
7. Generowanie raportu + SBOM (CycloneDX/SPDX)
8. Zapis wyników → PostgreSQL

---

## 7. Diagramy wdrożeniowe (Deployment)

### 7.1. Single-node — Docker Compose

> **Źródło PlantUML:** [`diagrams/deploy-single-node.puml`](diagrams/deploy-single-node.puml)

**Scenariusz:** Jeden serwer, wszystkie kontenery na jednej maszynie.

**Wymagania minimalne:**
- 4 vCPU, 16 GB RAM, 100 GB SSD
- Ubuntu 22.04+ / Debian 12+
- Docker 24+ z Compose v2

**Kontenery:**

| Kontener | Obraz | Porty | Wolumeny |
|----------|-------|-------|----------|
| nginx | nginx:alpine | 80, 443 | certyfikaty SSL |
| frontend | testgen-frontend | — (proxy przez nginx) | — |
| backend | testgen-backend | 8000 | — |
| celery-worker | testgen-backend | — | — |
| celery-beat | testgen-backend | — | — |
| flower | mher/flower | 5555 | — |
| postgres | postgres:16-alpine | 5432 | `pg-data` |
| redis | redis:7-alpine | 6379 | `redis-data` |
| rabbitmq | rabbitmq:3.12-management | 5672, 15672 | `rabbitmq-data` |
| minio | minio/minio | 9000, 9001 | `minio-data` |

**Sieć:** `testgen-net` (bridge) — izolacja kontenerów.

**Szczegóły konfiguracji:** [Dokumentacja wdrożeniowa — instalacja](../deployment-guide/01-instalacja.md)

---

### 7.2. Multi-node — Kubernetes / Helm

> **Źródło PlantUML:** [`diagrams/deploy-multi-node.puml`](diagrams/deploy-multi-node.puml)

**Scenariusz:** Klaster Kubernetes z wieloma node'ami, skalowanie horyzontalne.

**Przestrzenie nazw (Namespaces):**

| Namespace | Komponenty |
|-----------|-----------|
| `testgen` | frontend (Deployment), backend (Deployment), celery-worker (Deployment), celery-beat (Deployment) |
| `testgen-data` | PostgreSQL (StatefulSet + PVC), PgBouncer (Deployment), Redis + Sentinel (StatefulSet), RabbitMQ Cluster (StatefulSet), MinIO Distributed (StatefulSet + PVC) |
| `monitoring` | Prometheus, Grafana, Loki, Alertmanager |

**Skalowanie (HPA):**

| Komponent | Min replik | Max replik | Metryka wyzwalająca |
|-----------|-----------|-----------|---------------------|
| Frontend | 2 | 4 | CPU > 70% |
| Backend API | 2 | 6 | CPU > 70% |
| Celery Workers | 2 | 8 | Głębokość kolejki > 100 |
| Celery Beat | 1 | 1 | Singleton |

**Baza danych:**
- PostgreSQL Primary (zapis + odczyt) + Replica (tylko odczyt, streaming replication)
- PgBouncer: connection pooling, `pool_mode=transaction`, `max_client_conn=400`

**Wysoka dostępność:**
- Redis Sentinel: automatyczny failover
- RabbitMQ: klaster 3 node'ów, quorum queues
- MinIO: tryb rozproszony (4+ node'y)

**Szczegóły konfiguracji:** [Dokumentacja wdrożeniowa — instalacja (Kubernetes)](../deployment-guide/01-instalacja.md) i [operacje (skalowanie)](../deployment-guide/02-operacje.md)

---

## 8. Diagramy sekwencji

### 8.1. Rejestracja użytkownika

> **Źródło PlantUML:** [`diagrams/seq-rejestracja.puml`](diagrams/seq-rejestracja.puml)

**Aktorzy:** Użytkownik, Frontend (Angular), Backend API (FastAPI), PostgreSQL, SMTP

**Przepływ:**
1. Użytkownik wypełnia formularz rejestracji (e-mail, hasło, nazwa firmy)
2. Frontend wysyła `POST /api/v1/auth/register`
3. Backend waliduje dane, sprawdza unikalność e-maila
4. W jednej transakcji tworzone są: tenant (firma), user (konto), user_tenant (powiązanie z rolą Owner), subscription (plan Freemium)
5. Hasło haszowane algorytmem Argon2id
6. Generowany jest token weryfikacyjny (JWT, 24h) → e-mail
7. Użytkownik klika link → `POST /api/v1/auth/verify-email` → konto aktywowane

**Kluczowe aspekty:**
- Atomowość: wszystkie wpisy tworzony w jednej transakcji
- Bezpieczeństwo: hasło nigdy nie trafia do bazy w postaci jawnej
- Audyt: rejestracja i weryfikacja logowane w `audit_logs`

---

### 8.2. Analiza kodu

> **Źródło PlantUML:** [`diagrams/seq-analiza-kodu.puml`](diagrams/seq-analiza-kodu.puml)

**Aktorzy:** Użytkownik, Frontend, Backend API, RabbitMQ, Celery Worker, PostgreSQL, MinIO, API LLM

**Przepływ:**
1. Użytkownik przesyła pliki kodu → `POST /api/v1/projects/{id}/uploads`
2. Backend: walidacja → sprawdzenie kwot → zapis w MinIO → rejestracja w DB → kolejkowanie zadania
3. Odpowiedź 202 Accepted z `task_id`
4. Celery Worker: pobranie plików → wykrywanie języka → analiza (native/LLM/hybrid) → zapis wyników
5. Frontend odpytuje status (`GET /api/v1/tasks/{task_id}`) co 3 sekundy
6. Po zakończeniu: wyświetlenie wyników

**Kluczowe aspekty:**
- Asynchroniczność: analiza odbywa się w Celery Worker, nie blokuje API
- Quota enforcement: sprawdzenie limitów przed kolejkowaniem
- Polling: frontend odpytuje status zadania (alternatywa: WebSocket)

---

### 8.3. Generowanie testów

> **Źródło PlantUML:** [`diagrams/seq-generowanie-testow.puml`](diagrams/seq-generowanie-testow.puml)

**Przepływ:**
1. Użytkownik wybiera ukończoną analizę → `POST /api/v1/projects/{id}/test-cases/generate`
2. Backend: walidacja → bramka funkcji → kolejkowanie
3. Celery Worker: pobranie wyników analizy → generowanie (native/LLM/hybrid) → priorytetyzacja → zapis test case'ów → renderowanie kodu per framework
4. Wyniki: test case'y (status `draft`) + kod testowy per framework

**Workflow statusów test case'ów:**
```
draft → review → approved → exported
```

---

### 8.4. Płatność (checkout + webhook)

> **Źródło PlantUML:** [`diagrams/seq-platnosc.puml`](diagrams/seq-platnosc.puml)

**Przepływ — checkout:**
1. Owner wybiera plan → `POST /api/v1/billing/checkout`
2. Backend tworzy transakcję w tpay → `POST /transactions`
3. Użytkownik przekierowywany na stronę płatności tpay (BLIK/karta/przelew)

**Przepływ — webhook:**
1. tpay wysyła webhook (`POST /api/v1/billing/webhooks/tpay`) z podpisem JWS
2. Backend weryfikuje podpis → zapisuje zdarzenie → klasyfikuje
3. Transakcja `paid` → aktualizacja planu + generowanie faktury VAT + zapis w MinIO
4. Tokenizacja → zapis tokenu płatniczego do automatycznych odnowień

**Przepływ — odnowienie (Celery Beat, 03:30):**
1. Pobranie subskrypcji do odnowienia
2. Obciążenie zapisanego tokenu
3. Sukces → przedłużenie + faktura; Porażka → okres łaski (7 dni) → downgrade

---

### 8.5. Przetwarzanie webhooków (ogólny)

> **Źródło PlantUML:** [`diagrams/seq-webhook.puml`](diagrams/seq-webhook.puml)

**Wzorzec uniwersalny** stosowany dla wszystkich webhooków (tpay, GitHub):

1. Odbiór podpisanego payloadu
2. Weryfikacja podpisu (JWS / HMAC-SHA256)
3. Zapis surowego zdarzenia w `webhook_events` (z `idempotency_key`)
4. Sprawdzenie idempotentności — duplikaty ignorowane (200 OK)
5. Klasyfikacja zdarzenia (`WebhookProcessor.classify()`)
6. Przetwarzanie: synchroniczne (proste aktualizacje) lub asynchroniczne (Celery)
7. Aktualizacja statusu zdarzenia → `processed`

**Gwarancje:**
- **Idempotentność:** wielokrotne dostarczenie tego samego webhooka nie powoduje podwójnego efektu
- **Audytowalność:** każde zdarzenie zapisane w bazie
- **Bezpieczeństwo:** weryfikacja podpisu odrzuca sfałszowane żądania

---

## 9. Decyzje architektoniczne (ADR)

Kluczowe decyzje architektoniczne udokumentowane w [adr/](adr/):

| ADR | Decyzja | Uzasadnienie |
|-----|---------|-------------|
| [ADR-001](adr/ADR-001-custom-monorepo.md) | Monorepo (backend + frontend + flutter) | Współdzielenie konfiguracji, atomowe commity, jeden CI pipeline |
| [ADR-002](adr/ADR-002-multi-tenancy-rls.md) | Multi-tenancy via PostgreSQL RLS | Izolacja danych na poziomie DB, brak logiki filtrowania w kodzie |
| [ADR-003](adr/ADR-003-argon2id-rs256-jwt.md) | Argon2id + RS256 JWT | Najsilniejszy algorytm haszowania + asymetryczne JWT |
| [ADR-004](adr/ADR-004-celery-rabbitmq.md) | Celery + RabbitMQ | Niezawodne kolejkowanie, routing po typie zadania, retry z backoff |
| [ADR-005](adr/ADR-005-tree-sitter-parser.md) | tree-sitter jako parser AST | Incremental parsing, 40+ języków, C-level wydajność |
| [ADR-006](adr/ADR-006-jinja2-template-engine.md) | Jinja2 do szablonów testów | Elastyczność, dziedziczenie szablonów, makra |
| [ADR-007](adr/ADR-007-e2e-frameworks.md) | Frameworki E2E (Playwright/Cypress/Selenium) | Pokrycie różnych potrzeb: modern, cross-browser, legacy |
| [ADR-008](adr/ADR-008-golden-data.md) | Golden data (wzorcowe dane testowe) | Deterministyczne testy integracyjne, reproducibility |
| [ADR-009](adr/ADR-009-code-review-workflow.md) | Workflow code review | Zapewnienie jakości kodu, blokujące review |
| [ADR-010](adr/ADR-010-audit-logging.md) | Audit logging | Śledzenie operacji wrażliwych, compliance |
| [ADR-011](adr/ADR-011-uml-visual-tier2.md) | UML Tier 2 (visual parsing) | Rozpoznawanie diagramów z obrazów (OCR + CV) |
| [ADR-012](adr/ADR-012-sikulix-image-based.md) | SikuliX (testy GUI desktop) | Testy oparte na obrazach dla aplikacji desktopowych |
| [ADR-013](adr/ADR-013-traceability-proxy.md) | Traceability proxy | Śledzenie powiązań: wymagania ↔ implementacja ↔ testy |

---

## 10. Konwencje diagramów

### 10.1. Style PlantUML

Diagramy C4 korzystają z biblioteki `C4-PlantUML` (GitHub: plantuml-stdlib/C4-PlantUML):

- **Niebieskie:** komponenty wewnętrzne TestGEN
- **Szare:** systemy zewnętrzne
- **Postacie:** aktorzy (użytkownicy)
- **Cylindry:** bazy danych i magazyny
- **Prostokąty z zaokrąglonymi rogami:** kolejki wiadomości

### 10.2. Nazewnictwo plików

| Prefiks | Typ diagramu |
|---------|-------------|
| `c4-context-` | C4 Level 1 |
| `c4-container-` | C4 Level 2 |
| `c4-component-` | C4 Level 3 |
| `c4-code-` | C4 Level 4 |
| `flow-` | Przepływ danych |
| `deploy-` | Diagram wdrożeniowy |
| `seq-` | Diagram sekwencji |

### 10.3. Renderowanie

```bash
# Renderowanie pojedynczego diagramu
plantuml -tpng diagrams/c4-context.puml

# Renderowanie wszystkich diagramów do SVG
plantuml -tsvg diagrams/*.puml

# Renderowanie z Custom Theme
plantuml -tpng -theme C4_blue diagrams/*.puml
```

Wyrenderowane pliki umieść w `diagrams/render/` (katalog nie jest wersjonowany w repozytorium — generowany ad hoc).

---

## Powiązane dokumenty

- [system.md](system.md) — uproszczony opis architektury (tekst + ASCII art)
- [conventions.md](conventions.md) — konwencje kodu i dokumentacji
- [workflows.md](workflows.md) — przepływy pracy deweloperskiej
- [adr/](adr/) — decyzje architektoniczne (ADR)
- [api/overview.md](api/overview.md) — przegląd API REST
- [billing/](billing/) — architektura modułu płatności
- [interfejs-webowy/](interfejs-webowy/) — architektura frontend
- [Dokumentacja wdrożeniowa](../deployment-guide/) — instalacja i operacje
- [Podręcznik administratora](../admin-guide/admin-guide.md) — operacje administracyjne
