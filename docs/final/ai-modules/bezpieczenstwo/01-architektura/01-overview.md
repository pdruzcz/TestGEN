# Architektura modułów bezpieczeństwa — przegląd

> Moduły bezpieczeństwa TestGEN (Epic 4).
> Wersja odpowiada implementacji w `backend/app/services/security_scan/`.

## 1. Cel modułu

Moduł bezpieczeństwa TestGEN realizuje kompleksowy, wielowarstwowy pipeline
analizy bezpieczeństwa kodu źródłowego, zależności i konfiguracji
infrastruktury. Silniki są deterministyczne (oparte na regułach i analizie
przepływu danych): działają offline, bez zależności od usług zewnętrznych,
z gwarancją powtarzalności wyników.

## 2. Diagram pipeline'u

```
                          ┌──────────────────────────┐
                          │   Źródła wejściowe        │
                          │  kod / manifesty / konfig │
                          └────────────┬─────────────┘
                                       │
        ┌──────────────┬───────────────┼───────────────┬───────────────┐
        ▼              ▼               ▼               ▼               ▼
   ┌─────────┐   ┌──────────┐   ┌─────────────┐  ┌──────────┐   ┌──────────┐
   │  SAST   │   │  TAINT   │   │ DEPENDENCY  │  │  CONFIG  │   │   DAST   │
   │ engine  │   │ analyzer │   │  scanner    │  │ scanner  │   │  runner  │
   │(reguły) │   │(dataflow)│   │ (SCA/CVE)   │  │(IaC)     │   │(OWASP ZAP)│
   └────┬────┘   └────┬─────┘   └──────┬──────┘  └────┬─────┘   └────┬─────┘
        │             │                │              │              │
        └─────────────┴────────┬───────┴──────────────┴──────────────┘
                               ▼
                   ┌────────────────────────┐
                   │  FindingAggregator      │
                   │  deduplikacja +         │
                   │  korelacja + confidence │
                   └───────────┬─────────────┘
                               ▼
                   ┌────────────────────────┐
                   │  RiskEngine             │
                   │  CVSS v3.1 + eskalacja  │
                   │  + effort + priorytet   │
                   └───────────┬─────────────┘
                               ▼
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
  ┌──────────────┐    ┌────────────────┐     ┌────────────────┐
  │Recommendation│    │ PatchGenerator │     │  PoCGenerator  │
  │  Engine      │    │ (unified diff) │     │ (+ poc_safety) │
  └──────────────┘    └────────────────┘     └────────────────┘
```

## 3. Moduły i ich odpowiedzialności

| Moduł | Plik | Rola |
|---|---|---|
| SAST engine | `sast_engine.py` | Statyczna analiza wzorców (reguły regex per język) |
| Taint analyzer | `taint_analyzer.py` | Analiza przepływu danych source→sink |
| Dependency scanner | `dependency_scanner.py` | SCA — parsowanie manifestów, dopasowanie CVE, SBOM |
| Config scanner | `config_scanner.py` + `config_scanners/` | Docker / Kubernetes / Terraform |
| DAST runner | `dast_runner.py` | Dynamiczna analiza przez OWASP ZAP |
| Finding aggregator | `finding_aggregator.py` | Deduplikacja, korelacja, scoring zaufania |
| Risk engine | `risk_engine.py` | CVSS, eskalacja, szacowanie wysiłku, priorytetyzacja |
| CVSS calculator | `cvss_calculator.py` | Czysty kalkulator CVSS v3.1 |
| CVE pipeline | `cve_pipeline.py` | Aktualizacja bazy CVE z NVD/OSV/GitHub |
| Recommendation engine | `recommendation_engine.py` | Rekomendacje naprawcze |
| Patch generator | `patch_generator.py` | Generowanie patchy git-apply |
| PoC generator | `poc_generator.py` + `poc_safety.py` | Bezpieczne PoC |

## 4. Wspólne typy wyników

Wszystkie silniki produkują rekordy `SecurityFinding` (model
`app/models/security_finding.py`) o ujednoliconej strukturze: typ podatności,
severity, CWE, kategoria OWASP, lokalizacja (plik/linia), confidence (0.0–1.0),
źródło oraz metadane (np. ścieżka taint, payload PoC).

## 5. Przepustowość i ograniczenia

- SAST/Taint: limit 2 MB na plik (`_MAX_CONTENT_BYTES = 2_000_000`).
- Config: limit 1 MB na plik.
- DAST: domyślny limit skanu 1800 s (30 min).

## 6. Powiązane dokumenty

- [02 — SAST engine](02-sast-engine.md)
- [03 — Taint analyzer](03-taint-analyzer.md)
- [04 — Dependency scanner](04-dependency-scanner.md)
- [05 — Config scanner](05-config-scanner.md)
- [06 — DAST runner](06-dast-runner.md)
- [07 — Agregator i risk engine](07-agregator-i-risk-engine.md)
- [09 — Modele danych](09-modele-danych.md)
