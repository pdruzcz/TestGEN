# Katalog reguł — Cross-Site Scripting (CWE-79)

Plik reguł: `app/services/security_scan/rules/xss_rules.py`
OWASP: A03:2021-Injection · CWE: CWE-79

## Opis klasy podatności

XSS powstaje, gdy niesanityzowane dane użytkownika trafiają do wyjścia HTML.
Wyróżniamy: reflected (odbity), stored (trwały) i DOM-based.

## Reguły

### JS-DOM-SINK (JS/TS, high, conf 0.55)
```
\.innerHTML\s*=|\.outerHTML\s*=|document\.write\s*\(|\$\([^)]*\)\.html\s*\(|insertAdjacentHTML\s*\(
```
Niebezpieczny sink DOM (innerHTML/document.write/$.html).

### JS-FRAMEWORK-RAW-HTML (JS/TS, high, conf 0.6)
```
dangerouslySetInnerHTML|v-html\s*=|bypassSecurityTrust(Html|Script)
```
Surowy HTML w React/Vue/Angular.

### PY-TEMPLATE-RAW (Python, high, conf 0.55)
```
render_template_string\s*\(|\bMarkup\s*\(|\|\s*safe\b|autoescape\s*=\s*False
```

### JAVA-RESPONSE-WRITE (Java, high, conf 0.5)
```
getWriter\s*\(\s*\)\s*\.\s*(write|print)|out\.print(ln)?\s*\(
```

### CS-RESPONSE-RAW (C#, high, conf 0.55)
```
Response\.Write\s*\(|Html\.Raw\s*\(
```

## Przykład podatny (JavaScript, DOM-based)

```javascript
element.innerHTML = location.hash.substring(1);
```

## Przykład naprawiony

```javascript
element.textContent = location.hash.substring(1);
// lub: element.innerHTML = DOMPurify.sanitize(userInput);
```

## Rekomendacja

Używaj `textContent` zamiast `innerHTML`; sanityzuj (DOMPurify); włącz
auto-escaping w szablonach; w Java użyj OWASP Encoder; w C# `HtmlEncode`.
