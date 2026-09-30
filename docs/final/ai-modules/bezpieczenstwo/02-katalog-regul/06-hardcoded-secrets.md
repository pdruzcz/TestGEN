# Katalog reguł — Hardcoded Secrets (CWE-798)

Plik reguł: `app/services/security_scan/rules/secrets_rules.py`
OWASP: A07:2021-Identification and Authentication Failures (część — A02 dla
klucza prywatnego)

## Opis klasy podatności

Zakodowane na stałe sekrety (hasła, klucze API, tokeny, klucze prywatne) w
kodzie źródłowym są łatwe do wykrycia w repozytorium i prowadzą do przejęcia
dostępu.

## Reguły

### SECRET-HARDCODED (wszystkie języki, high, conf 0.55)
```
(password|passwd|pwd|secret|api[_-]?key|apikey|token|access[_-]?key)\s*[:=]\s*["'][^"'\s]{6,}["']
```
Sekret przypisany literałem ≥6 znaków.

### SECRET-PRIVATE-KEY (wszystkie języki, critical, conf 0.9)
```
-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----
```

### SECRET-AWS-KEY (wszystkie języki, critical, conf 0.85)
```
\bAKIA[0-9A-Z]{16}\b
```

### SECRET-JWT (wszystkie języki, high, conf 0.7)
```
\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+
```

## Przykład podatny

```python
DB_PASSWORD = "Sup3rS3cr3tP@ss"
```

## Przykład naprawiony

```python
DB_PASSWORD = os.environ["DB_PASSWORD"]
```

## Rekomendacja

Przenieś sekrety do zmiennych środowiskowych / menedżera sekretów. Wykryty
sekret należy **usunąć z repozytorium i zrotować** (sama zmiana nie wystarczy —
wartość pozostaje w historii git).
