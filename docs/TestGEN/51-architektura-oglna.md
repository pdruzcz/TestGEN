# **5.1.** Architektura ogólna

### **5.1.1.** Model architektoniczny

System TestGEN jest zbudowany w oparciu o architekturę mikroserwisową,
która zapewnia:

- **Skalowalność** - możliwość niezależnego skalowania poszczególnych
  komponentów

- **Niezawodność** - izolacja awarii w ramach pojedynczych serwisów

- **Elastyczność technologiczną** - możliwość wykorzystania różnych
  technologii dla różnych modułów

- **Łatwość wdrażania** - niezależne deployment poszczególnych serwisów

**REQ-ARCH-001:** System musi być zbudowany w architekturze
mikroserwisowej z wykorzystaniem konteneryzacji (Docker).

**REQ-ARCH-002:** System musi wspierać zarówno deployment w chmurze
(SaaS) jak i on-premises.

### **5.1.2.** Diagram architektury wysokopoziomowej

**Architektura wysokopoziomowa systemu TestGEN:**

┌─────────────────────────────────────────────────────────────┐

│ WARSTWA PREZENTACJI │

│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │

│ │ Web UI │ │ Mobile App │ │ CLI Tool │ │

│ │ (React) │ │ (Flutter) │ │ (Python) │ │

│ └──────────────┘ └──────────────┘ └──────────────┘ │

└─────────────────────────────────────────────────────────────┘

↓

┌─────────────────────────────────────────────────────────────┐

│ API GATEWAY │

│ (Kong / AWS API Gateway) │

│ Authentication, Rate Limiting, Load Balancing │

└─────────────────────────────────────────────────────────────┘

↓

┌─────────────────────────────────────────────────────────────┐

│ WARSTWA USŁUG BIZNESOWYCH │

│ ┌────────────┐ ┌────────────┐ ┌────────────┐ │

│ │ Code │ │ Doc │ │ UML/GUI │ │

│ │ Analysis │ │ Analysis │ │ Analysis │ │

│ │ Service │ │ Service │ │ Service │ │

│ └────────────┘ └────────────┘ └────────────┘ │

│ ┌────────────┐ ┌────────────┐ ┌────────────┐ │

│ │ Security │ │ Func Gap │ │ Test Gen │ │

│ │ Analysis │ │ Analysis │ │ Service │ │

│ └────────────┘ └────────────┘ └────────────┘ │

└─────────────────────────────────────────────────────────────┘

↓

┌─────────────────────────────────────────────────────────────┐

│ SILNIK TESTSPARK (CORE) │

│ ┌──────────────────────────────────────────────────────┐ │

│ │ AI/ML Engine (LLM, NLP, AST Analysis) │ │

│ │ - Transformers (BERT, GPT) │ │

│ │ - Code Analysis (tree-sitter, AST parsers) │ │

│ │ - Pattern Recognition │ │

│ └──────────────────────────────────────────────────────┘ │

└─────────────────────────────────────────────────────────────┘

↓

┌─────────────────────────────────────────────────────────────┐

│ WARSTWA DANYCH I STORAGE │

│ ┌────────────┐ ┌────────────┐ ┌────────────┐ │

│ │PostgreSQL │ │ MongoDB │ │ Redis │ │

│ │(Metadata) │ │(Documents) │ │(Cache) │ │

│ └────────────┘ └────────────┘ └────────────┘ │

│ ┌────────────┐ ┌────────────┐ │

│ │ S3/Blob │ │ Elastic │ │

│ │ Storage │ │ Search │ │

│ └────────────┘ └────────────┘ │

└─────────────────────────────────────────────────────────────┘

↓

┌─────────────────────────────────────────────────────────────┐

│ INTEGRACJE ZEWNĘTRZNE │

│ ┌────────────┐ ┌────────────┐ ┌────────────┐ │

│ │ GitHub │ │ Jira │ │ CI/CD │ │

│ │ GitLab │ │ TestRail │ │ (Jenkins, │ │

│ │ │ │ │ │ Actions) │ │

│ └────────────┘ └────────────┘ └────────────┘ │

└─────────────────────────────────────────────────────────────┘

### **5.1.3.** Główne warstwy systemu

#### Warstwa prezentacji

Odpowiedzialna za interakcję z użytkownikami poprzez:

- **Web UI** - aplikacja webowa React z Material-UI

- **Mobile App** - aplikacja mobilna Flutter (iOS/Android)

- **CLI Tool** - narzędzie linii poleceń Python dla integracji CI/CD

#### API Gateway

Centralny punkt dostępu do wszystkich serwisów, zapewniający:

- Uwierzytelnianie i autoryzację (OAuth 2.0 / JWT)

- Rate limiting i throttling

- Load balancing

- Request routing

- API versioning

#### Warstwa usług biznesowych

Mikroserwisy realizujące poszczególne funkcjonalności systemu:

- **Code Analysis Service** - analiza kodu źródłowego

- **Documentation Analysis Service** - analiza dokumentacji

- **UML/GUI Analysis Service** - analiza diagramów i interfejsów

- **Security Analysis Service** - analiza bezpieczeństwa

- **Functional Gap Analysis Service** - analiza luk funkcjonalnych

- **Test Generation Service** - generowanie testów

#### Silnik TestSpark (Core)

Centralny komponent AI/ML zawierający:

- Modele transformerów (BERT, GPT) do analizy języka naturalnego

- Parsery AST dla różnych języków programowania

- Mechanizmy pattern recognition

- Taint analysis engine

- Knowledge graphs

#### Warstwa danych

Rozproszona warstwa przechowywania danych:

- **PostgreSQL** - metadata, konfiguracja, użytkownicy

- **MongoDB** - dokumenty, raporty, przypadki testowe

- **Redis** - cache, sesje, kolejki zadań

- **S3/Blob Storage** - pliki źródłowe, artefakty

- **Elasticsearch** - full-text search, logi, analityka

#### Integracje zewnętrzne

Konektory do systemów zewnętrznych:

- Systemy kontroli wersji (GitHub, GitLab, Bitbucket)

- Systemy zarządzania testami (Jira, TestRail, Zephyr)

- Systemy CI/CD (Jenkins, GitHub Actions, Azure DevOps)

- Systemy płatności (Stripe, PayPal)
