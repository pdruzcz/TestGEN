# Katalog reguł — walidacja wejścia i injection

Plik reguł: `app/services/security_scan/rules/input_validation_rules.py`

Grupuje rodzinę „niebezpieczna operacja na niezaufanym wejściu”: command
injection, code injection, path traversal, insecure deserialization i weak
cryptography.

## Reguły

### PY-OS-SYSTEM (Python, command_injection, CWE-78, critical, conf 0.75)
```
os\.system\s*\(|subprocess\.[a-z_]+\([^)]*shell\s*=\s*True
```

### JS-CHILD-PROCESS (JS/TS, command_injection, CWE-78, critical, conf 0.7)
```
child_process\.exec\s*\(|\bexec\s*\(\s*[`"'].*\$\{
```

### PY-EVAL-EXEC (Python, code_injection, CWE-95, high, conf 0.7)
```
\b(eval|exec)\s*\(
```

### JS-EVAL (JS/TS, code_injection, CWE-95, high, conf 0.7)
```
\beval\s*\(|new\s+Function\s*\(
```

### PATH-TRAVERSAL (wszystkie języki, path_traversal, CWE-22, medium, conf 0.5)
```
open\s*\(\s*[^)]*\+|os\.path\.join\s*\([^)]*request|new\s+File\s*\([^)]*\+
```

### PY-PICKLE (Python, insecure_deserialization, CWE-502, high, conf 0.65)
```
pickle\.loads?\s*\(|yaml\.load\s*\((?![^)]*Loader)
```

### WEAK-HASH (wszystkie języki, weak_cryptography, CWE-327, medium, conf 0.6)
```
\b(md5|sha1)\s*\(|hashlib\.(md5|sha1)\b|MessageDigest\.getInstance\(\s*["'](MD5|SHA-1)
```

## Przykład podatny (command injection)

```python
os.system("ping -c 1 " + user_host)
```

## Przykład naprawiony

```python
subprocess.run(["ping", "-c", "1", user_host], shell=False)
```

## Rekomendacje skrótem

- Command injection: przekazuj argumenty listą, bez `shell=True`; użyj
  `execFile`/`spawn`.
- Code injection: unikaj `eval`/`exec`; użyj `ast.literal_eval`/`JSON.parse`.
- Path traversal: waliduj i normalizuj ścieżki; ogranicz do katalogu bazowego.
- Deserializacja: `json` lub `yaml.safe_load`.
- Krypto: SHA-256+ lub bcrypt/argon2 dla haseł.
