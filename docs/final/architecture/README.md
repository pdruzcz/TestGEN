# Architektura — indeks

> Dokumentacja techniczna platformy. Wzorce, decyzje (ADR), API,
> architektury UI i modułu billingowego.

## Przegląd

- [architecture.md](architecture.md) — **kompletna dokumentacja architektury C4:** diagramy kontekstowe, kontenerów, komponentów (M1-M6), kodu (dual-path, pipeline, parsery), przepływy danych, wdrożenia (Docker Compose / K8s), sekwencje + 20 diagramów PlantUML
- [system.md](system.md) — skrócony opis architektury (ASCII art)
- [conventions.md](conventions.md) — konwencje repo/kodu/dokumentacji
- [workflows.md](workflows.md) — przepływy pracy (dev → review → release)
- [diagrams/](diagrams/) — pliki źródłowe PlantUML (`.puml`) — C4 L1-L4, przepływy, wdrożenia, sekwencje

## Decyzje architektoniczne (ADR)

[adr/](adr/) — 13 decyzji + szablon: monorepo (001), multi-tenancy RLS (002),
Argon2id+RS256 (003), Celery+RabbitMQ (004), tree-sitter (005), Jinja2 (006),
frameworki E2E (007), golden data (008), code review (009), audit log (010),
UML Tier 2 (011), SikuliX (012), traceability proxy (013).

## API

- [api/overview.md](api/overview.md) — przegląd API (`/api/v1`)
- [api/examples/](api/examples/) — przykłady żądań/odpowiedzi per obszar:
  auth, projects, analysis, test cases, documents, UML/GUI, audit

Dokumentacja żywa: platformowe `/docs` (OpenAPI 3.1 generowane z kodu).
Kompletne pokrycie API (Epic 8) — story 8-5/8-13, uzupełni ten katalog.

## Architektury obszarów

| Obszar | Dokumenty |
|---|---|
| Interfejs webowy | [interfejs-webowy/](interfejs-webowy/) — stack Angular 21, struktura core/shared/features, ekrany i przepływy, dostępność (WCAG fundamenty/motywy/ARIA), shell Flutter, strategia testowa |
| Billing | [billing/](billing/) — plany i limity, integracja tpay (checkout, webhooki, tokeny), zmiany planu i proration, limity/zużycie, powiadomienia i gating, faktury VAT, modele danych |

## Powiązane

- Szczegóły modułów analiz → [../ai-modules/README.md](../ai-modules/README.md)
- Wdrożenia/środowisko → [../deployment-guide/README.md](../deployment-guide/README.md)
