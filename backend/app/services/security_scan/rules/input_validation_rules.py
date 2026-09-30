"""Input validation / injection rules (CWE-20/78/95/22/502/327) — Story 4.2.

Groups the "unsafe operation on untrusted input" family: OS command injection,
code injection (eval/exec), path traversal, insecure deserialization and weak
cryptography. These subsume the Story 4.1 baseline rules.
"""

from app.services.security_scan.rules.base import (
    ALL,
    JS,
    PY,
    RulePattern,
    VulnerabilityRule,
    rx,
)

INPUT_VALIDATION_RULES: list[VulnerabilityRule] = [
    VulnerabilityRule(
        id="PY-OS-SYSTEM",
        name="os.system / subprocess shell=True",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="os.system / subprocess z shell=True może prowadzić do wstrzyknięcia poleceń.",
        recommendation="Przekazuj argumenty jako listę i nie używaj shell=True.",
        base_confidence=0.75,
        patterns=(
            RulePattern(
                regex=rx(r"os\.system\s*\(|subprocess\.[a-z_]+\([^)]*shell\s*=\s*True"),
                languages=PY,
                node_hint="shell command execution",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JS-CHILD-PROCESS",
        name="child_process.exec z interpolacją",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="child_process.exec z interpolacją łańcucha umożliwia wstrzyknięcie poleceń.",
        recommendation="Użyj execFile/spawn z tablicą argumentów zamiast exec.",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"child_process\.exec\s*\(|\bexec\s*\(\s*[`\"'].*\$\{"),
                languages=JS,
                node_hint="child_process exec",
            ),
        ),
    ),
    VulnerabilityRule(
        id="PY-EVAL-EXEC",
        name="eval()/exec() (Python)",
        vulnerability_type="code_injection",
        cwe_id="CWE-95",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="Użycie eval()/exec() na danych wejściowych umożliwia wykonanie dowolnego kodu.",
        recommendation="Unikaj eval/exec; użyj ast.literal_eval lub jawnego parsowania.",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"\b(eval|exec)\s*\("),
                languages=PY,
                node_hint="dynamic code evaluation",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JS-EVAL",
        name="eval()/new Function() (JS/TS)",
        vulnerability_type="code_injection",
        cwe_id="CWE-95",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="eval()/Function() na danych użytkownika umożliwia wykonanie dowolnego kodu.",
        recommendation="Usuń eval/Function; parsuj dane jawnie (np. JSON.parse).",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"\beval\s*\(|new\s+Function\s*\("),
                languages=JS,
                node_hint="dynamic code evaluation",
            ),
        ),
    ),
    VulnerabilityRule(
        id="PATH-TRAVERSAL",
        name="Budowanie ścieżki z danych wejściowych",
        vulnerability_type="path_traversal",
        cwe_id="CWE-22",
        owasp_category="A01:2021-Broken Access Control",
        severity="medium",
        description="Budowanie ścieżki pliku z danych wejściowych bez walidacji.",
        recommendation="Waliduj i normalizuj ścieżki; ogranicz do katalogu bazowego.",
        base_confidence=0.5,
        patterns=(
            RulePattern(
                regex=rx(r"open\s*\(\s*[^)]*\+|os\.path\.join\s*\([^)]*request|new\s+File\s*\([^)]*\+"),
                languages=ALL,
                node_hint="filesystem path from input",
            ),
        ),
    ),
    VulnerabilityRule(
        id="PY-PICKLE",
        name="Niebezpieczna deserializacja (pickle/yaml)",
        vulnerability_type="insecure_deserialization",
        cwe_id="CWE-502",
        owasp_category="A08:2021-Software and Data Integrity Failures",
        severity="high",
        description="pickle.loads / yaml.load na niezaufanych danych umożliwia wykonanie kodu.",
        recommendation="Użyj json lub yaml.safe_load; nie deserializuj niezaufanych danych pickle.",
        base_confidence=0.65,
        patterns=(
            RulePattern(
                regex=rx(r"pickle\.loads?\s*\(|yaml\.load\s*\((?![^)]*Loader)"),
                languages=PY,
                node_hint="deserialization sink",
            ),
        ),
    ),
    VulnerabilityRule(
        id="WEAK-HASH",
        name="Słaba funkcja skrótu (MD5/SHA1)",
        vulnerability_type="weak_cryptography",
        cwe_id="CWE-327",
        owasp_category="A02:2021-Cryptographic Failures",
        severity="medium",
        description="Użycie słabej funkcji skrótu (MD5/SHA1) do celów bezpieczeństwa.",
        recommendation="Użyj SHA-256+ lub bcrypt/argon2 dla haseł.",
        base_confidence=0.6,
        patterns=(
            RulePattern(
                regex=rx(
                    r"\b(md5|sha1)\s*\(|hashlib\.(md5|sha1)\b|"
                    r"MessageDigest\.getInstance\(\s*[\"'](MD5|SHA-1)"
                ),
                languages=ALL,
                node_hint="weak hash function",
            ),
        ),
    ),
]
