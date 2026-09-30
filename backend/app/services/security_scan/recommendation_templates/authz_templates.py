"""Authorization (IDOR / broken access control) remediation templates — Story 4.9."""

from app.services.security_scan.recommendation_templates.registry import Template, register

_PROBLEM_IDOR = (
    "Obiekt jest pobierany wyłącznie po identyfikatorze z żądania, bez sprawdzenia, "
    "czy bieżący użytkownik ma do niego prawo (Insecure Direct Object Reference)."
)
_RISK_IDOR = (
    "Atakujący może podmienić identyfikator w żądaniu i uzyskać dostęp do cudzych "
    "danych lub zasobów (odczyt, modyfikacja, usunięcie)."
)
_FIX_IDOR = "Egzekwuj autoryzację na poziomie obiektu — wiąż zapytanie z właścicielem/uprawnieniami."

_PROBLEM_AUTHZ = (
    "Endpoint zmieniający stan lub zwracający wrażliwe dane nie weryfikuje uprawnień "
    "użytkownika (brak kontroli dostępu po stronie serwera)."
)
_RISK_AUTHZ = (
    "Atakujący bez wymaganej roli może wykonać uprzywilejowaną operację lub odczytać "
    "dane, do których nie powinien mieć dostępu."
)
_FIX_AUTHZ = "Dodaj serwerową kontrolę uprawnień (rola/właściciel) przed wykonaniem operacji."


register(
    "idor",
    "python",
    None,
    Template(
        problem_description=_PROBLEM_IDOR,
        risk_description=_RISK_IDOR,
        fix_description=_FIX_IDOR + " Filtruj zapytanie również po identyfikatorze właściciela.",
        fixed_code_snippet=(
            "obj = session.query(Document)\\\n"
            "    .filter(Document.id == doc_id, Document.owner_id == current_user.id)\\\n"
            "    .one_or_none()\n"
            "if obj is None:\n"
            "    raise PermissionError"
        ),
        language="python",
    ),
)

register(
    "idor",
    "java",
    "spring",
    Template(
        problem_description=_PROBLEM_IDOR,
        risk_description=_RISK_IDOR,
        fix_description=_FIX_IDOR + " W Spring użyj @PreAuthorize z weryfikacją właściciela.",
        fixed_code_snippet='@PreAuthorize("@docs.isOwner(#docId, authentication.name)")\npublic Document get(Long docId) { ... }',
        language="java",
        framework="spring",
    ),
)

register(
    "idor",
    "generic",
    None,
    Template(
        problem_description=_PROBLEM_IDOR,
        risk_description=_RISK_IDOR,
        fix_description=_FIX_IDOR,
        fixed_code_snippet="if resource.owner_id != current_user.id: deny()",
        language="generic",
    ),
)

register(
    "broken_authz",
    "python",
    None,
    Template(
        problem_description=_PROBLEM_AUTHZ,
        risk_description=_RISK_AUTHZ,
        fix_description=_FIX_AUTHZ + " Sprawdź rolę/uprawnienie na początku handlera.",
        fixed_code_snippet=(
            "if not current_user.has_permission('document:write'):\n"
            "    raise PermissionError('Brak uprawnień')"
        ),
        language="python",
    ),
)

register(
    "broken_authz",
    "java",
    "spring",
    Template(
        problem_description=_PROBLEM_AUTHZ,
        risk_description=_RISK_AUTHZ,
        fix_description=_FIX_AUTHZ + " W Spring zabezpiecz metodę adnotacją @PreAuthorize.",
        fixed_code_snippet='@PreAuthorize("hasRole(\'ADMIN\')")\npublic void deleteUser(Long id) { ... }',
        language="java",
        framework="spring",
    ),
)

register(
    "broken_authz",
    "generic",
    None,
    Template(
        problem_description=_PROBLEM_AUTHZ,
        risk_description=_RISK_AUTHZ,
        fix_description=_FIX_AUTHZ,
        fixed_code_snippet="if not user.is_authorized(action): deny()",
        language="generic",
    ),
)
