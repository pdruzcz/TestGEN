# Katalog reguł — macierz języków

Stałe językowe (`rules/base.py`):

- `PY` = {python}
- `JS` = {javascript, typescript}
- `JAVA` = {java}
- `CS` = {csharp, c#}
- `C` = {c, cpp, c++}
- `ALL` = frozenset() (pusty zbiór = wszystkie języki)

Funkcja `rx(pattern)` kompiluje regex z flagą `re.IGNORECASE`.

## Macierz reguła → języki

| rule_id | typ | CWE | Python | JS/TS | Java | C# | Wszystkie |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| SQLI-STRING-CONCAT | sql_injection | 89 | | | | | ✓ |
| PY-CURSOR-FSTRING | sql_injection | 89 | ✓ | | | | |
| JAVA-STATEMENT-CONCAT | sql_injection | 89 | | | ✓ | | |
| JS-QUERY-CONCAT | sql_injection | 89 | | ✓ | | | |
| CS-SQLCOMMAND-CONCAT | sql_injection | 89 | | | | ✓ | |
| JS-DOM-SINK | xss | 79 | | ✓ | | | |
| JS-FRAMEWORK-RAW-HTML | xss | 79 | | ✓ | | | |
| PY-TEMPLATE-RAW | xss | 79 | ✓ | | | | |
| JAVA-RESPONSE-WRITE | xss | 79 | | | ✓ | | |
| CS-RESPONSE-RAW | xss | 79 | | | | ✓ | |
| PY-CSRF-DISABLED | csrf | 352 | ✓ | | | | |
| JAVA-CSRF-DISABLED | csrf | 352 | | | ✓ | | |
| JS-CSRF-DISABLED | csrf | 352 | | ✓ | | | |
| PY-IDOR-LOOKUP | idor | 639 | ✓ | | | | |
| PY-AUTH-BYPASS | broken_authz | 862 | ✓ | | | | |
| JAVA-IDOR-LOOKUP | idor | 639 | | | ✓ | | |
| JS-AUTH-BYPASS | broken_authz | 862 | | ✓ | | | |
| PY-OS-SYSTEM | command_injection | 78 | ✓ | | | | |
| JS-CHILD-PROCESS | command_injection | 78 | | ✓ | | | |
| PY-EVAL-EXEC | code_injection | 95 | ✓ | | | | |
| JS-EVAL | code_injection | 95 | | ✓ | | | |
| PATH-TRAVERSAL | path_traversal | 22 | | | | | ✓ |
| PY-PICKLE | insecure_deserialization | 502 | ✓ | | | | |
| WEAK-HASH | weak_cryptography | 327 | | | | | ✓ |
| SECRET-HARDCODED | hardcoded_secret | 798 | | | | | ✓ |
| SECRET-PRIVATE-KEY | hardcoded_secret | 798 | | | | | ✓ |
| SECRET-AWS-KEY | hardcoded_secret | 798 | | | | | ✓ |
| SECRET-JWT | hardcoded_secret | 798 | | | | | ✓ |

## Podsumowanie pokrycia

- **26 reguł** w 6 kategoriach (SQLi 5, XSS 5, CSRF 3, authz 4, input
  validation 7, secrets 4 — łącznie z PATH/PICKLE/WEAK-HASH liczonymi w input
  validation).
- **12 CWE:** 20, 22, 78, 79, 89, 95, 327, 352, 502, 639, 798, 862.
- **OWASP 2021:** A01 (6 reguł), A02 (2), A03 (14), A07 (3), A08 (1).

## Rejestr reguł (`rules/registry.py`)

Kolejność agregacji `ALL_RULES`: SQLI → XSS → CSRF → AUTHZ →
INPUT_VALIDATION → SECRETS. `RuleRegistry` udostępnia `get_rules(language)`,
`get_rule_by_id(id)`, `get_rules_by_cwe(cwe)`. Singleton przez
`get_registry()`; kompatybilność: `rules_for_language(language)`.
