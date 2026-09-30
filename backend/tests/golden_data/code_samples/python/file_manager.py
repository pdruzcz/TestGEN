"""Zarzadzanie plikami — przyklad z operacjami IO i systemem plikow."""

from pathlib import Path


class FileManager:
    """Zarzadzanie plikami i katalogami."""

    def __init__(self, base_dir: str = "/tmp/testgen"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write_file(self, filename: str, content: str) -> str:
        """Zapisz zawartosc do pliku."""
        if not filename:
            raise ValueError("Nazwa pliku nie moze byc pusta")
        filepath = self.base_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def read_file(self, filename: str) -> str:
        """Odczytaj zawartosc pliku."""
        filepath = self.base_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {filename}")
        return filepath.read_text(encoding="utf-8")

    def delete_file(self, filename: str) -> bool:
        """Usun plik."""
        filepath = self.base_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def list_files(self, extension: str | None = None) -> list[str]:
        """Lista plikow w katalogu."""
        if extension:
            return [f.name for f in self.base_dir.glob(f"*.{extension}")]
        return [f.name for f in self.base_dir.iterdir() if f.is_file()]

    def file_exists(self, filename: str) -> bool:
        """Sprawdz czy plik istnieje."""
        return (self.base_dir / filename).exists()

    def get_file_size(self, filename: str) -> int:
        """Pobierz rozmiar pliku w bajtach."""
        filepath = self.base_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {filename}")
        return filepath.stat().st_size
