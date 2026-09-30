"""Cross-site request forgery (CSRF) remediation templates — Epic 4, Story 4.9."""

from app.services.security_scan.recommendation_templates.registry import Template, register

_VULN = "csrf"

_PROBLEM = (
    "Operacja zmieniająca stan jest akceptowana bez tokenu anty-CSRF, więc nie da się "
    "odróżnić żądania użytkownika od żądania podrobionego przez inną stronę."
)
_RISK = (
    "Atakujący może nakłonić zalogowaną ofiarę do wykonania niezamierzonej akcji "
    "(zmiana hasła, przelew, usunięcie danych) bez jej wiedzy."
)
_FIX = "Wymagaj tokenu anty-CSRF dla żądań zmieniających stan i waliduj go po stronie serwera."


register(
    _VULN,
    "python",
    "django",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Django włącz CsrfViewMiddleware i {% csrf_token %} w formularzu.",
        fixed_code_snippet='<form method="post">{% csrf_token %} ... </form>',
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
        fix_description=_FIX + " W Flask użyj Flask-WTF (CSRFProtect).",
        fixed_code_snippet=(
            "from flask_wtf import CSRFProtect\n"
            "csrf = CSRFProtect(app)"
        ),
        language="python",
        framework="flask",
    ),
)

register(
    _VULN,
    "java",
    "spring",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Spring Security ochrona CSRF jest domyślna; nie wyłączaj jej dla form.",
        fixed_code_snippet="http.csrf(Customizer.withDefaults());",
        language="java",
        framework="spring",
    ),
)

register(
    _VULN,
    "javascript",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " Wysyłaj token CSRF w nagłówku i weryfikuj go na serwerze.",
        fixed_code_snippet="fetch('/api/action', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });",
        language="javascript",
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
        fixed_code_snippet="// dołącz i zweryfikuj token anty-CSRF dla żądań POST/PUT/DELETE",
        language="generic",
    ),
)
