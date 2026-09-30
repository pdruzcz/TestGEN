"""Input-validation remediation templates — Epic 4, Story 4.9.

Covers command/code injection, path traversal and insecure deserialization — all
classes whose fix centres on validating/whitelisting untrusted input.
"""

from app.services.security_scan.recommendation_templates.registry import Template, register

# --- Command injection (CWE-78) ---------------------------------------------
_CMD_PROBLEM = (
    "Dane wejściowe użytkownika trafiają do polecenia powłoki, więc atakujący może "
    "doprzyczepić własne polecenia systemowe."
)
_CMD_RISK = "Atakujący może wykonać dowolne polecenia na serwerze (RCE), przejąć kontrolę nad systemem."
_CMD_FIX = "Nie wywołuj powłoki z danymi użytkownika; przekazuj argumenty jako listę i waliduj je."

register(
    "command_injection",
    "python",
    None,
    Template(
        problem_description=_CMD_PROBLEM,
        risk_description=_CMD_RISK,
        fix_description=_CMD_FIX + " W Pythonie używaj subprocess z listą argumentów i shell=False.",
        fixed_code_snippet='subprocess.run(["ping", "-c", "1", host], shell=False, check=True)',
        language="python",
    ),
)

register(
    "command_injection",
    "generic",
    None,
    Template(
        problem_description=_CMD_PROBLEM,
        risk_description=_CMD_RISK,
        fix_description=_CMD_FIX,
        fixed_code_snippet="exec(cmd, args=[validatedArg], shell=false)",
        language="generic",
    ),
)

# --- Code injection (CWE-94) ------------------------------------------------
_CODE_PROBLEM = (
    "Dane wejściowe są przekazywane do dynamicznej ewaluacji kodu (eval/exec), "
    "więc atakujący może wstrzyknąć własny kod aplikacji."
)
_CODE_RISK = "Atakujący może wykonać dowolny kod w kontekście aplikacji (RCE)."
_CODE_FIX = "Nie używaj eval/exec na danych użytkownika; zastąp je bezpiecznym parserem lub mapą dozwolonych operacji."

register(
    "code_injection",
    "python",
    None,
    Template(
        problem_description=_CODE_PROBLEM,
        risk_description=_CODE_RISK,
        fix_description=_CODE_FIX + " Do danych literalnych użyj ast.literal_eval().",
        fixed_code_snippet=(
            "import ast\n"
            "value = ast.literal_eval(user_input)"
        ),
        language="python",
    ),
)

register(
    "code_injection",
    "generic",
    None,
    Template(
        problem_description=_CODE_PROBLEM,
        risk_description=_CODE_RISK,
        fix_description=_CODE_FIX,
        fixed_code_snippet="// zastąp eval() jawną mapą dozwolonych operacji",
        language="generic",
    ),
)

# --- Path traversal (CWE-22) ------------------------------------------------
_PATH_PROBLEM = (
    "Ścieżka pliku jest budowana z danych użytkownika bez normalizacji, więc atakujący "
    "może użyć '../', aby wyjść poza dozwolony katalog."
)
_PATH_RISK = "Atakujący może odczytać lub nadpisać dowolne pliki na serwerze (np. /etc/passwd, konfiguracje)."
_PATH_FIX = "Normalizuj ścieżkę i sprawdź, że mieści się w dozwolonym katalogu bazowym."

register(
    "path_traversal",
    "python",
    None,
    Template(
        problem_description=_PATH_PROBLEM,
        risk_description=_PATH_RISK,
        fix_description=_PATH_FIX + " W Pythonie użyj Path.resolve() i porównaj z katalogiem bazowym.",
        fixed_code_snippet=(
            "from pathlib import Path\n"
            "base = Path('/data').resolve()\n"
            "target = (base / user_path).resolve()\n"
            "if not target.is_relative_to(base):\n"
            "    raise ValueError('Niedozwolona ścieżka')"
        ),
        language="python",
    ),
)

register(
    "path_traversal",
    "generic",
    None,
    Template(
        problem_description=_PATH_PROBLEM,
        risk_description=_PATH_RISK,
        fix_description=_PATH_FIX,
        fixed_code_snippet="if not normalize(base + userPath).startsWith(base): deny()",
        language="generic",
    ),
)

# --- Insecure deserialization (CWE-502) -------------------------------------
_DESER_PROBLEM = (
    "Niezaufane dane są deserializowane mechanizmem, który potrafi tworzyć dowolne "
    "obiekty (np. pickle), co umożliwia wykonanie kodu podczas wczytywania."
)
_DESER_RISK = "Atakujący może spreparować ładunek, który wykona kod przy deserializacji (RCE)."
_DESER_FIX = "Nie deserializuj niezaufanych danych formatami wykonywalnymi; użyj bezpiecznego formatu (JSON)."

register(
    "insecure_deserialization",
    "python",
    None,
    Template(
        problem_description=_DESER_PROBLEM,
        risk_description=_DESER_RISK,
        fix_description=_DESER_FIX + " W Pythonie zastąp pickle modułem json.",
        fixed_code_snippet=(
            "import json\n"
            "data = json.loads(raw_input)"
        ),
        language="python",
    ),
)

register(
    "insecure_deserialization",
    "generic",
    None,
    Template(
        problem_description=_DESER_PROBLEM,
        risk_description=_DESER_RISK,
        fix_description=_DESER_FIX,
        fixed_code_snippet="data = json.parse(rawInput)",
        language="generic",
    ),
)
