"""Hardcoded-secret remediation templates — Epic 4, Story 4.9.

Move secrets out of source into environment variables / a secret vault.
"""

from app.services.security_scan.recommendation_templates.registry import Template, register

_VULN = "hardcoded_secret"

_PROBLEM = (
    "Sekret (klucz API, hasło, token) jest zapisany na stałe w kodzie źródłowym. "
    "Trafia do repozytorium i jest widoczny dla każdego z dostępem do kodu."
)
_RISK = (
    "Atakujący z dostępem do repozytorium lub artefaktu może odczytać sekret "
    "i wykorzystać go do dostępu do usług, danych lub infrastruktury."
)
_FIX = "Przenieś sekret do zmiennych środowiskowych lub menedżera sekretów (vault) i wczytuj go w runtime."


register(
    _VULN,
    "python",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Pythonie użyj os.environ (opcjonalnie python-dotenv).",
        fixed_code_snippet=(
            "import os\n"
            'API_KEY = os.environ["API_KEY"]'
        ),
        language="python",
    ),
)

register(
    _VULN,
    "java",
    "spring",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Spring wstrzykuj wartość przez @Value z konfiguracji/Vault.",
        fixed_code_snippet='@Value("${api.key}")\nprivate String apiKey;',
        language="java",
        framework="spring",
    ),
)

register(
    _VULN,
    "java",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Javie czytaj sekret ze zmiennej środowiskowej.",
        fixed_code_snippet='String apiKey = System.getenv("API_KEY");',
        language="java",
    ),
)

register(
    _VULN,
    "javascript",
    "node",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Node użyj process.env (np. z pakietem dotenv).",
        fixed_code_snippet=(
            "require('dotenv').config();\n"
            "const apiKey = process.env.API_KEY;"
        ),
        language="javascript",
        framework="node",
    ),
)

register(
    _VULN,
    "javascript",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W JavaScript wczytuj sekret z process.env.",
        fixed_code_snippet="const apiKey = process.env.API_KEY;",
        language="javascript",
    ),
)

register(
    _VULN,
    "csharp",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W .NET użyj zmiennych środowiskowych lub Azure Key Vault.",
        fixed_code_snippet='var apiKey = Environment.GetEnvironmentVariable("API_KEY");',
        language="csharp",
    ),
)

register(
    _VULN,
    "generic",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX,
        fixed_code_snippet='api_key = getenv("API_KEY")',
        language="generic",
    ),
)
