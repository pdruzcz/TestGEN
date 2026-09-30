# Pipeline DAST — payloady i fuzzing

## 1. Mechanizm aktywnego skanu

Aktywny skan ZAP (active scan) automatycznie wstrzykuje payloady ataków do
wykrytych punktów wejścia (parametry GET/POST, nagłówki, ciasteczka),
zidentyfikowanych wcześniej w fazie spider (crawl). TestGEN korzysta z
wbudowanego zestawu reguł aktywnego skanowania ZAP.

## 2. Typy ataków wykrywanych dynamicznie

Aktywny skan ZAP pokrywa m.in.:

- SQL Injection (plugin 40018 → CWE-89)
- Reflected XSS (plugin 40012 → CWE-79)
- OS Command Injection (plugin 90020 → CWE-78)
- Path Traversal, Remote File Inclusion
- nagłówki bezpieczeństwa, ujawnienie informacji

Mapowanie plugin ZAP → CWE realizuje `_PLUGIN_TO_CWE` w `dast_runner.py`
(fallback, gdy alert nie zawiera własnego CWE).

## 3. Limity wydajności

| Limit | Wartość |
|---|---|
| Timeout active scan | 1800 s (30 min) |
| Timeout gotowości | 120 s |

Po przekroczeniu limitu skanu runner przerywa polling i przetwarza alerty
zebrane do tej pory, zamiast czekać w nieskończoność.

## 4. Faza spider

Przed aktywnym skanem uruchamiana jest faza spider, która odkrywa powierzchnię
ataku (URL-e, formularze). Tylko odkryte punkty są następnie poddawane
fuzzingowi w aktywnym skanie, co ogranicza zakres do rzeczywistej aplikacji.

## 5. Bezpieczeństwo payloadów

Payloady aktywnego skanu mają charakter wykrywający (detekcja podatności), nie
destrukcyjny. Skan należy uruchamiać wyłącznie na środowiskach testowych /
autoryzowanych celach projektu.
