"""Błędy CLI i kody wyjścia — Story 8.10 (AC5).

Kod wyjścia jest kontraktem z pipeline'em CI/CD, więc rozróżniamy dwie rzeczy,
które łatwo pomylić:

* **1** — analiza się udała i znalazła problemy powyżej progu. To poprawne
  działanie narzędzia; build ma się zatrzymać.
* **2** — narzędzie nie zdołało wykonać zadania (brak sieci, złe poświadczenia,
  zły argument). To awaria integracji, wymagająca innej reakcji.

Zlanie ich w jeden kod sprawiłoby, że zespół nie odróżniłby „znaleźliśmy
podatność" od „zepsuł się klucz API".
"""

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


class CliError(Exception):
    """Błąd techniczny — kończy działanie kodem 2."""

    exit_code = EXIT_ERROR

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class AuthError(CliError):
    """Brak albo nieprawidłowe poświadczenia."""


class ConnectionFailed(CliError):
    """Nie udało się połączyć z serwerem TestGEN (AC6)."""

    def __init__(self, api_url: str, detail: str = "") -> None:
        super().__init__(
            "Brak połączenia z serwerem TestGEN. Sprawdź połączenie sieciowe i URL API.",
            hint=f"Adres: {api_url}" + (f" · {detail}" if detail else ""),
        )


class ThresholdExceeded(Exception):
    """Znaleziska powyżej progu — kończy działanie kodem 1."""

    exit_code = EXIT_FINDINGS

    def __init__(self, description: str) -> None:
        super().__init__(description)
        self.description = description
