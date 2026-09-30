"""Serwis uzytkownikow — przyklad z DB i walidacja."""


class UserService:
    """Zarzadzanie uzytkownikami z walidacja."""

    def __init__(self, db_connection=None):
        self.db = db_connection
        self.users: dict[str, dict] = {}

    def create_user(self, username: str, email: str) -> dict:
        """Utworz nowego uzytkownika."""
        if not username or len(username) < 3:
            raise ValueError("Nazwa uzytkownika musi miec co najmniej 3 znaki")
        if "@" not in email:
            raise ValueError("Nieprawidlowy adres email")
        if username in self.users:
            raise ValueError(f"Uzytkownik '{username}' juz istnieje")

        user = {"username": username, "email": email, "active": True}
        self.users[username] = user
        return user

    def get_user(self, username: str) -> dict | None:
        """Pobierz uzytkownika po nazwie."""
        return self.users.get(username)

    def deactivate_user(self, username: str) -> bool:
        """Deaktywuj uzytkownika."""
        user = self.users.get(username)
        if not user:
            return False
        user["active"] = False
        return True

    def list_active_users(self) -> list[dict]:
        """Lista aktywnych uzytkownikow."""
        return [u for u in self.users.values() if u.get("active")]

    def count_users(self) -> int:
        """Liczba uzytkownikow."""
        return len(self.users)
