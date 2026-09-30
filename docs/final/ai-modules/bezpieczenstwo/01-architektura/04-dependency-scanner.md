# Dependency scanner — skaner zależności (SCA)

Plik: `app/services/security_scan/dependency_scanner.py`
Klasa publiczna: `DependencyScanner`

## 1. Cel

Software Composition Analysis (SCA): parsuje manifesty zależności pięciu
ekosystemów, dopasowuje pakiety do bazy CVE i generuje SBOM (CycloneDX + SPDX).

## 2. Obsługiwane ekosystemy i parsery

| Ekosystem | Pliki | Parser |
|---|---|---|
| pypi | `requirements*.txt`, `pyproject.toml` | `_parse_requirements_txt`, `_parse_pyproject_toml` |
| npm | `package.json`, `package-lock.json` | `_parse_package_json`, `_parse_package_lock` |
| maven | `pom.xml`, `build.gradle` | `_parse_pom_xml`, `_parse_build_gradle` |
| nuget | `*.csproj`, `packages.config` | `_parse_csproj`, `_parse_packages_config` |
| composer | `composer.json` | `_parse_composer_json` |

Dopasowanie pliku idzie od najbardziej specyficznego wzorca (requirements*,
pyproject.toml, package-lock.json, package.json, pom.xml, build.gradle,
.csproj, packages.config, composer.json).

## 3. Interfejs

```python
def parse_file(filename: str, content: str) -> list[Dependency]
async def scan_dependencies(project_id, tenant_id, scan_id) -> tuple[list[SecurityFinding], dict]
def generate_cyclonedx_sbom(dependencies, cve_map) -> dict
def generate_spdx_sbom(dependencies, cve_map) -> dict
```

`scan_dependencies` zwraca krotkę `(findings, sbom_payload)`, gdzie
`sbom_payload = {"cyclonedx": {...}, "spdx": {...}}`.

## 4. Struktury danych

- **Dependency** — `name`, `version | None`, `ecosystem`, `is_direct`,
  `license | None`.
- **CVEEntry** — `cve_id`, `cvss_score`, `description`, `affected_versions`,
  `fixed_version`, `source_db` ∈ {osv, nvd, snyk}.
- **CVEProvider** (Protocol) — `async query(name, version, ecosystem)`.
  - `LocalCacheCVEProvider` — czyta z tabeli `cve_database` (offline, domyślny).
  - `NullCVEProvider` — pusta lista (fallback testowy).

## 5. Algorytm

1. Wykryj ekosystem po nazwie pliku → wywołaj właściwy parser.
2. Dla każdej zależności odpytaj `CVEProvider`.
3. Deduplikuj CVE po ID, zachowaj najwyższy CVSS i znane wersje naprawcze.
4. Filtruj CVE z CVSS **≥ 4.0** (`_FINDING_CVSS_THRESHOLD`).
5. Mapuj CVSS na severity: ≥9.0 critical, ≥7.0 high, ≥4.0 medium, reszta low.
6. Wygeneruj SBOM (CycloneDX + SPDX) z komponentami, wersjami, PURL i
   referencjami do podatności.
7. Auto-rekomendacja: „Zaktualizuj {pkg} z {old} do {fixed}” lub „Brak
   poprawki… rozważ zamiennik”.

## 6. Pasma severity (CVSS)

| Pasmo | Severity |
|---|---|
| [9.0, 10.0] | critical |
| [7.0, 9.0) | high |
| [4.0, 7.0) | medium |
| [0, 4.0) | low |

## 7. Tryb offline

Domyślny `LocalCacheCVEProvider` korzysta wyłącznie z lokalnej tabeli
`cve_database` (zasilanej przez [CVE pipeline](../04-pipeline-cve/01-zrodla-danych.md)),
dzięki czemu skan jest powtarzalny i nie wymaga sieci.

## 8. Zależności

- SQLAlchemy (`CVEDatabase`), `ElementTree` (XML), `tomllib` (TOML), `json`.
- `models/security_finding.py`.
