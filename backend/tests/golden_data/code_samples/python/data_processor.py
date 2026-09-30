"""Przetwarzanie danych — przyklad z typami, wyjatkami i danymi."""

from typing import Any


class DataProcessor:
    """Przetwarzanie i transformacja danych."""

    def __init__(self):
        self.processed_count = 0

    def filter_positive(self, numbers: list[float]) -> list[float]:
        """Filtruj liczby dodatnie."""
        result = [n for n in numbers if n > 0]
        self.processed_count += 1
        return result

    def calculate_average(self, numbers: list[float]) -> float:
        """Oblicz srednia z listy liczb."""
        if not numbers:
            raise ValueError("Lista nie moze byc pusta")
        result = sum(numbers) / len(numbers)
        self.processed_count += 1
        return result

    def normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalizuj wartosc do przedzialu [0, 1]."""
        if max_val == min_val:
            return 0.0
        result = (value - min_val) / (max_val - min_val)
        self.processed_count += 1
        return result

    def group_by_key(self, items: list[dict[str, Any]], key: str) -> dict[str, list]:
        """Pogrupuj elementy wedlug klucza."""
        groups: dict[str, list] = {}
        for item in items:
            k = str(item.get(key, "unknown"))
            groups.setdefault(k, []).append(item)
        self.processed_count += 1
        return groups

    def get_stats(self) -> dict[str, int]:
        """Statystyki przetwarzania."""
        return {"processed_count": self.processed_count}
