# Taint analyzer — analiza przepływu danych

Plik: `app/services/security_scan/taint_analyzer.py`
Klasa publiczna: `TaintAnalyzer`

## 1. Cel

Taint analyzer śledzi przepływ niezaufanych danych od **źródła** (source, np.
`request.GET`) do **niebezpiecznej operacji** (sink, np. `cursor.execute`) i
raportuje podatność, jeśli dane docierają do sinka bez adekwatnej sanityzacji.
Analiza jest „forward”, w kolejności linii, w zakresie pojedynczego pliku.

## 2. Interfejs

```python
def analyze_code(code: str, language: str | None, file_path=None) -> list[TaintPath]
async def run_taint_analysis(project_id, tenant_id, scan_id) -> list[SecurityFinding]
```

## 3. Struktury danych

- **TaintPathStep** — jeden krok ścieżki: `file_path`, `line`, `variable`,
  `operation` (fragment kodu), `node_type` ∈ {source, transform, sanitizer,
  sink}.
- **TaintPath** — kompletny przepływ source→sink: `source_name`, `sink_name`,
  `sink_type`, `taint_type`, `vulnerability_type`, `cwe_id`, `severity`,
  `variable`, `steps[]`, `sanitizer_name`, `sanitizer_adequate`, zakres
  linii.
- **_TaintState** (wewn.) — stan skażenia zmiennej: `source_name`,
  `taint_type`, `steps[]`, `protected_against` (frozenset typów sinków, przed
  którymi chroni zastosowany sanitizer), `sanitizer_name`.

## 4. Algorytm

1. Pobierz definicje taint dla języka (sources / sinks / sanitizers — patrz
   [taint-definitions](../02-katalog-regul/08-taint-definitions.md)).
2. Przejście „forward” po liniach:
   - **Sink first** — jeśli linia zawiera sink i dociera do niego skażona
     zmienna bez adekwatnego sanitizera → zapisz znalezisko.
   - **Source** — jeśli linia zawiera source, propaguj skażenie do zmiennej
     po lewej stronie przypisania (nowy `TaintPathStep`).
   - **Propagacja** — jeśli prawa strona jest już skażona, propaguj skażenie;
     jeśli zastosowano sanitizer, oznacz, dla jakich `sink_type` skażenie jest
     usunięte.
3. Confidence: **0.55** gdy sanitizer istnieje, ale jest nieadekwatny; **0.7**
   gdy brak sanitizera.
4. Pełna ścieżka (source→transforms→sink) trafia do
   `finding_metadata.taint_path` jako JSON.

## 5. Detekcja przypisań

- `_ASSIGN_RE` dopasowuje pojedyncze `=` (nie `==`, `+=` itd.) z opcjonalnymi
  modyfikatorami (`let`, `var`, `public` …).
- `_IDENT_RE` ekstrahuje nazwę zmiennej.
- Dopasowanie źródła: `NamedTaintSource.matches(rhs)`.

## 6. Nieadekwatna sanityzacja

Kluczowa właściwość: sanitizer chroni tylko przed określonymi typami sinków
(`protects_against`). Np. `html.escape` chroni przed sinkiem `html`, ale NIE
przed sinkiem `sql`. Jeśli dane są „sanityzowane” niewłaściwym sanitizerem dla
danego sinka, ścieżka jest flagowana z `sanitizer_adequate = False`.

## 7. Zależności

- `taint_definitions/` (`sources_for_language`, `sinks_for_language`,
  `sanitizers_for_language`)
- `rules/` (`owasp_for`)
- `models/security_finding.py`
