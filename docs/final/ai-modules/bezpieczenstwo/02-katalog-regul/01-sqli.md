# Katalog reguł — SQL Injection (CWE-89)

Plik reguł: `app/services/security_scan/rules/sqli_rules.py`
OWASP: A03:2021-Injection · CWE: CWE-89

## Opis klasy podatności

SQL Injection powstaje, gdy zapytanie SQL jest budowane przez konkatenację lub
interpolację z niezaufanymi danymi, zamiast przez zapytania parametryzowane.
Atakujący może zmodyfikować strukturę zapytania (np. `' OR '1'='1`).

## Reguły

### SQLI-STRING-CONCAT (wszystkie języki, critical, conf 0.65)
Wzorzec:
```
(?=.*["'])(?=.*\b(SELECT|INSERT|UPDATE|DELETE)\b)(?=.*(\+|\.format\s*\(|["']\s*%|f["']|\$\{|\{[A-Za-z_]))
```
Wykrywa SQL budowane przez konkatenację/format z danymi wejściowymi.

### PY-CURSOR-FSTRING (Python, critical, conf 0.7)
```
\.execute\s*\(\s*(f["']|["'][^)]*\+|["'][^)]*%[^,)]*$)
```
`cursor.execute` z f-stringiem/format zamiast parametrów.

### JAVA-STATEMENT-CONCAT (Java, critical, conf 0.7)
```
\.execute(Query|Update)?\s*\(\s*["'].*\+|createStatement\s*\(
```

### JS-QUERY-CONCAT (JS/TS, critical, conf 0.65)
```
\.query\s*\(\s*([`"'].*\$\{|["'].*\+)
```

### CS-SQLCOMMAND-CONCAT (C#, critical, conf 0.7)
```
new\s+SqlCommand\s*\(\s*["'].*\+|ExecuteReader\s*\(\s*["'].*\+
```

## Przykład podatny (Python)

```python
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

## Przykład naprawiony (Python)

```python
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

## Rekomendacja

Używaj zapytań parametryzowanych / ORM zamiast sklejania łańcuchów. W Java —
`PreparedStatement` z `?`; w C# — `SqlParameter`/parametry `@`.
