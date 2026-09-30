# Katalog reguł — Broken Authorization / IDOR (CWE-862/639)

Plik reguł: `app/services/security_scan/rules/authz_rules.py`
OWASP: A01:2021-Broken Access Control

## Opis klasy podatności

Broken Access Control obejmuje brak kontroli autoryzacji (CWE-862) oraz IDOR —
Insecure Direct Object Reference (CWE-639), gdy obiekt jest pobierany po
identyfikatorze z requestu bez sprawdzenia właściciela. Autoryzacja jest
kontekstowa, więc reguły celują w jawne markery obejścia i bezpośrednie
odczyty obiektów kluczowane inputem.

## Reguły

### PY-IDOR-LOOKUP (Python, idor, CWE-639, high, conf 0.5)
```
objects\.(get|filter)\s*\([^)]*=\s*request\.|get_object_or_404\s*\([^)]*request\.|\.query\.get\s*\(\s*request\.
```

### PY-AUTH-BYPASS (Python, broken_authz, CWE-862, high, conf 0.55)
```
permission_classes\s*=\s*\[\s*AllowAny|authentication_classes\s*=\s*\[\s*\]
```

### JAVA-IDOR-LOOKUP (Java, idor, CWE-639, high, conf 0.45)
```
\.findById\s*\(\s*(request|@PathVariable|id\s*\))
```

### JS-AUTH-BYPASS (JS/TS, broken_authz, CWE-862, high, conf 0.4)
```
//\s*(TODO|FIXME)[^\n]*\bauth|requireAuth\s*:\s*false
```

## Przykład podatny (Django, IDOR)

```python
invoice = Invoice.objects.get(id=request.GET["invoice_id"])
```

## Przykład naprawiony

```python
invoice = Invoice.objects.get(pk=invoice_id)
if invoice.owner_id != request.user.id:
    raise PermissionDenied
```

## Rekomendacja

Weryfikuj własność/uprawnienia (np. `filter(owner=current_user)`); stosuj
zasadę domyślnego odrzucania; wymagaj uwierzytelnienia przed dostępem do
zasobu.
