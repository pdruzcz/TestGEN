# SAST engine — silnik statycznej analizy

Plik: `app/services/security_scan/sast_engine.py`
Klasa publiczna: `SASTEngine`

## 1. Cel

SAST engine wykonuje statyczną analizę kodu opartą na wzorcach (reguły regex
per język). Wykrywa typowe klasy podatności (SQLi, XSS, CSRF, IDOR/authz,
hardcoded secrets, command/code injection, path traversal, weak crypto)
przeszukując kod linia po linii i dopasowując reguły z rejestru reguł.

## 2. Interfejs

```python
SASTEngine(db=None)

def scan_code(code: str, language: str | None, file_path: str | None=None) -> list[RawFinding]
async def run_sast(project_id, tenant_id, scan_id) -> list[SecurityFinding]
```

- `scan_code` — czysta, testowalna funkcja: wejście to surowy kod, wyjście to
  lista `RawFinding`. Nie wymaga DB ani sieci.
- `run_sast` — pełny przebieg: ładuje pliki projektu, uruchamia analizę
  regułową i zapisuje `SecurityFinding`.

## 3. Algorytm (ścieżka native)

1. Załaduj pliki źródłowe projektu (limit 2 MB/plik, filtrowanie po języku).
2. Dla każdej linii każdego pliku:
   - Pomiń komentarze/puste linie, chyba że reguła jawnie celuje w komentarze
     (gdy regex zawiera `#` lub `//`).
   - Przetestuj linię względem wszystkich reguł właściwych dla języka
     (`rules_for_language`).
   - Po dopasowaniu wzorca oblicz confidence: bazowa pewność reguły +
     `confidence_weight` wzorca + korekty kontekstowe.
   - Utwórz `RawFinding` z CWE, kategorią OWASP i (ewentualnym) override
     severity.
3. Zwróć listę znalezisk.

## 4. Korekty pewności (confidence)

- **+0.15** — obecność markerów danych użytkownika (`request`, `input`,
  `argv`, `params`, `req.`, `$_`).
- **−0.05** — linie z dużą liczbą literałów (mniejsze ryzyko).
- Wynik końcowy przycinany do zakresu **[0.1, 0.99]**.

## 5. Mapa override severity

| vulnerability_type | severity |
|---|---|
| command_injection | critical |
| sql_injection | critical |
| xss | high |
| weak_cryptography | medium |

## 6. Wejścia i wyjścia

- **Wejście:** kod źródłowy (str), język, ścieżka pliku.
- **Wyjście:** `list[RawFinding]` → mapowane na `SecurityFinding` przy
  zapisie (`_to_finding`).

## 7. Zależności

- `rules/` (rejestr reguł, `RawFinding`, `SEVERITY_ORDER`)
- `models/security_finding.py` (`SecurityFinding`, `ScanType`, `Severity`,
  `AnalysisSource`)

## 8. Wydajność

Analiza liniowa O(linie × reguły) z wczesnym pomijaniem komentarzy. Brak
parsowania AST w ścieżce krytycznej — reguły operują na regex, co zapewnia
przewidywalny, szybki przebieg offline. Szczegóły reguł:
[katalog reguł](../02-katalog-regul/01-sqli.md).
