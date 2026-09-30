# Pipeline CVE — źródła danych

Plik: `app/services/security_scan/cve_pipeline.py`
Klasa publiczna: `CVEPipeline`

## 1. Cel

Pipeline CVE okresowo zasila lokalną tabelę `cve_database` danymi z trzech
publicznych źródeł, dzięki czemu [dependency scanner](../01-architektura/04-dependency-scanner.md)
może działać offline z aktualną wiedzą o podatnościach.

## 2. Źródła danych

| Źródło | URL | Metoda |
|---|---|---|
| NVD (NIST) | `https://services.nvd.nist.gov/rest/json/cves/2.0` | REST v2.0, opcjonalny `nvd_api_key` |
| OSV.dev | `https://api.osv.dev/v1/query` | query per ekosystem |
| GitHub Advisory | `https://api.github.com/advisories` | bearer `github_token` |

Ekosystemy odpytywane w OSV: `PyPI`, `npm`, `Maven`, `NuGet`, `Packagist`.

## 3. Parametry NVD

`pubStartDate`, `pubEndDate`, `resultsPerPage=2000`, `startIndex`
(paginacja). Nagłówek z kluczem API opcjonalny (podnosi limity rate).

## 4. Struktury danych

- **CVERecord** — `cve_id`, `package_name`, `ecosystem`, `cvss_score`,
  `description`, `severity`, `affected_versions`, `fixed_version`,
  `published_date`, `source_db`. Metoda `key() = (cve_id, package_name)`.
- **SourceStatus** — `source`, `ok`, `fetched`, `error`.
- **CVEUpdateResult** — `total_new`, `total_updated`, `affected_projects`,
  `sources_status`, `errors`.

## 5. Metody pobierania

```python
async def _fetch_nvd_updates(since) -> list[CVERecord]
async def _fetch_osv_updates(since) -> list[CVERecord]
async def _fetch_github_advisories(since) -> list[CVERecord]
```

Pobieranie z trzech źródeł odbywa się równolegle. Parsery
(`_parse_nvd`, `_parse_osv`, `_parse_github`) są czyste/statyczne.

## 6. Deduplikacja i scalanie

`_merge_and_deduplicate(by_source)` — klucz `(cve_id, package_name)`,
priorytet: wyższy CVSS wygrywa; kolejność źródeł NVD > OSV > GitHub.

## 7. Persistencja

`_save_to_database(records, db)` upsertuje do `CVEDatabase` i zwraca
`(new_count, updated_count)`.
