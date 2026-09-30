"""CWE / OWASP Top 10 (2021) mapping per vulnerability type — Epic 4, Story 4.2.

Single source of truth for the canonical CWE id, OWASP category, default
severity and a short Polish description per ``vulnerability_type``. Rule modules
reference these so a finding's classification stays consistent regardless of the
language that produced it.
"""

CWE_OWASP_MAPPING: dict[str, dict[str, str]] = {
    "sql_injection": {
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021-Injection",
        "severity_default": "critical",
        "description": "Wstrzyknięcie SQL — zapytanie budowane z niezaufanych danych.",
    },
    "xss": {
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021-Injection",
        "severity_default": "high",
        "description": "Cross-Site Scripting — niesanityzowane dane w wyjściu HTML.",
    },
    "csrf": {
        "cwe_id": "CWE-352",
        "owasp_category": "A01:2021-Broken Access Control",
        "severity_default": "high",
        "description": "Brak ochrony CSRF dla operacji zmieniających stan.",
    },
    "broken_authz": {
        "cwe_id": "CWE-862",
        "owasp_category": "A01:2021-Broken Access Control",
        "severity_default": "high",
        "description": "Brak kontroli autoryzacji przed operacją (w tym IDOR).",
    },
    "idor": {
        "cwe_id": "CWE-639",
        "owasp_category": "A01:2021-Broken Access Control",
        "severity_default": "high",
        "description": "Bezpośrednie odwołanie do obiektu po ID bez kontroli właściciela.",
    },
    "input_validation": {
        "cwe_id": "CWE-20",
        "owasp_category": "A03:2021-Injection",
        "severity_default": "medium",
        "description": "Brak walidacji / sanityzacji danych wejściowych.",
    },
    "command_injection": {
        "cwe_id": "CWE-78",
        "owasp_category": "A03:2021-Injection",
        "severity_default": "critical",
        "description": "Wstrzyknięcie poleceń systemowych z niezaufanego inputu.",
    },
    "code_injection": {
        "cwe_id": "CWE-95",
        "owasp_category": "A03:2021-Injection",
        "severity_default": "high",
        "description": "Wykonanie dowolnego kodu (eval/exec) na danych wejściowych.",
    },
    "path_traversal": {
        "cwe_id": "CWE-22",
        "owasp_category": "A01:2021-Broken Access Control",
        "severity_default": "medium",
        "description": "Budowanie ścieżki pliku z danych wejściowych bez walidacji.",
    },
    "insecure_deserialization": {
        "cwe_id": "CWE-502",
        "owasp_category": "A08:2021-Software and Data Integrity Failures",
        "severity_default": "high",
        "description": "Deserializacja niezaufanych danych (pickle/yaml.load).",
    },
    "weak_cryptography": {
        "cwe_id": "CWE-327",
        "owasp_category": "A02:2021-Cryptographic Failures",
        "severity_default": "medium",
        "description": "Użycie słabej funkcji kryptograficznej (MD5/SHA1).",
    },
    "hardcoded_secret": {
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021-Identification and Authentication Failures",
        "severity_default": "high",
        "description": "Zakodowany na stałe sekret w kodzie źródłowym.",
    },
}


def severity_for(vulnerability_type: str, default: str = "medium") -> str:
    entry = CWE_OWASP_MAPPING.get(vulnerability_type)
    return entry["severity_default"] if entry else default


def cwe_for(vulnerability_type: str) -> str | None:
    entry = CWE_OWASP_MAPPING.get(vulnerability_type)
    return entry["cwe_id"] if entry else None


def owasp_for(vulnerability_type: str) -> str | None:
    entry = CWE_OWASP_MAPPING.get(vulnerability_type)
    return entry["owasp_category"] if entry else None
