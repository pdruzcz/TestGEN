# Katalog reguł — CSRF (CWE-352)

Plik reguł: `app/services/security_scan/rules/csrf_rules.py`
OWASP: A01:2021-Broken Access Control · CWE: CWE-352

## Opis klasy podatności

Cross-Site Request Forgery: atakujący zmusza uwierzytelnionego użytkownika do
wykonania niezamierzonej operacji zmieniającej stan. Detekcja liniowa nie może
udowodnić braku tokena CSRF w całym formularzu/handlerze, więc reguły celują w
**jawne wyłączenie lub obejście** ochrony CSRF (sygnały wysokiej pewności).

## Reguły

### PY-CSRF-DISABLED (Python, high, conf 0.7)
```
@csrf_exempt|csrf_exempt\s*\(|WTF_CSRF_ENABLED\s*=\s*False|CSRF_ENABLED\s*=\s*False
```

### JAVA-CSRF-DISABLED (Java, high, conf 0.75)
```
\.csrf\s*\(\s*\)\s*\.\s*disable\s*\(|csrf\(\)\.ignoringAntMatchers
```

### JS-CSRF-DISABLED (JS/TS, medium, conf 0.55)
```
csrf\s*:\s*false|ignoreMethods\s*:\s*\[[^\]]*POST
```

## Przykład podatny (Django)

```python
@csrf_exempt
def transfer_funds(request):
    ...
```

## Przykład naprawiony

```python
def transfer_funds(request):  # ochrona CSRF aktywna (bez @csrf_exempt)
    ...
```

## Rekomendacja

Nie wyłączaj CSRF dla endpointów zmieniających stan. W Spring pozostaw ochronę
CSRF; w Express włącz middleware CSRF i dołączaj token do POST/PUT/DELETE.
