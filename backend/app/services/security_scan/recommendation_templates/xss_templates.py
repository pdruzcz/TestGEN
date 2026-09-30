"""Cross-site scripting (XSS) remediation templates — Epic 4, Story 4.9.

Output-encoding / sanitisation fixes per framework.
"""

from app.services.security_scan.recommendation_templates.registry import Template, register

_VULN = "xss"

_PROBLEM = (
    "Dane wejściowe użytkownika trafiają do strony bez kodowania/sanityzacji, "
    "więc przeglądarka interpretuje je jako kod HTML/JavaScript."
)
_RISK = (
    "Atakujący może wstrzyknąć skrypt, który wykona się w przeglądarce ofiary: "
    "kradzież sesji/ciasteczek, podszywanie się pod użytkownika, defacement strony."
)
_FIX = "Koduj dane wyjściowe (output encoding) lub sanityzuj HTML przed renderowaniem."


register(
    _VULN,
    "javascript",
    "react",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W React unikaj dangerouslySetInnerHTML; jeśli musisz, sanityzuj DOMPurify.",
        fixed_code_snippet=(
            "import DOMPurify from 'dompurify';\n"
            "<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userInput) }} />"
        ),
        language="javascript",
        framework="react",
    ),
)

register(
    _VULN,
    "javascript",
    "vue",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Vue używaj interpolacji {{ }} / v-text zamiast v-html.",
        fixed_code_snippet="<span v-text=\"userInput\"></span>",
        language="javascript",
        framework="vue",
    ),
)

register(
    _VULN,
    "javascript",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W czystym JS ustawiaj textContent zamiast innerHTML.",
        fixed_code_snippet="element.textContent = userInput;",
        language="javascript",
    ),
)

register(
    _VULN,
    "python",
    "django",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Django szablony autoescapują; nie wyłączaj autoescape i unikaj mark_safe.",
        fixed_code_snippet="{{ user_input|escape }}",
        language="python",
        framework="django",
    ),
)

register(
    _VULN,
    "python",
    "flask",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Flask/Jinja2 korzystaj z autoescapingu lub markupsafe.escape().",
        fixed_code_snippet=(
            "from markupsafe import escape\n"
            "return f\"<p>{escape(user_input)}</p>\""
        ),
        language="python",
        framework="flask",
    ),
)

register(
    _VULN,
    "python",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Pythonie koduj HTML za pomocą html.escape().",
        fixed_code_snippet=(
            "import html\n"
            "safe = html.escape(user_input)"
        ),
        language="python",
    ),
)

register(
    _VULN,
    "java",
    "jsp",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W JSP używaj <c:out>, który koduje encje HTML.",
        fixed_code_snippet='<c:out value="${input}"/>',
        language="java",
        framework="jsp",
    ),
)

register(
    _VULN,
    "java",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Javie koduj wyjście biblioteką OWASP Java Encoder.",
        fixed_code_snippet="String safe = Encode.forHtml(userInput);",
        language="java",
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
        fixed_code_snippet="output = htmlEncode(userInput)",
        language="generic",
    ),
)
