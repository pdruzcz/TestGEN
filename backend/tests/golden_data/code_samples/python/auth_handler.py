"""Obsluga autoryzacji — przyklad z bezpieczenstwem, wyjatkami i HTTP."""

import hashlib
import secrets


class AuthHandler:
    """Obsluga autoryzacji i hashowania hasel."""

    def __init__(self, secret_key: str = "default-secret"):
        self.secret_key = secret_key
        self.sessions: dict[str, str] = {}

    def hash_password(self, password: str) -> str:
        """Zahashuj haslo uzywajac SHA-256."""
        if len(password) < 8:
            raise ValueError("Haslo musi miec co najmniej 8 znakow")
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{hashed}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Zweryfikuj haslo przeciwko stored hash."""
        if ":" not in stored_hash:
            return False
        salt, expected = stored_hash.split(":", 1)
        actual = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return actual == expected

    def create_session(self, username: str) -> str:
        """Utworz sesje uzytkownika."""
        token = secrets.token_urlsafe(32)
        self.sessions[token] = username
        return token

    def validate_session(self, token: str) -> str | None:
        """Zwaliduj token sesji, zwroc username lub None."""
        return self.sessions.get(token)

    def destroy_session(self, token: str) -> bool:
        """Zniszcz sesje."""
        if token in self.sessions:
            del self.sessions[token]
            return True
        return False
