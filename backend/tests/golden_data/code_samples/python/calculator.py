"""Prosty kalkulator — przyklad kodu Python do generowania testow pytest."""


class Calculator:
    """Kalkulator z podstawowymi operacjami matematycznymi."""

    def __init__(self):
        self.history: list[float] = []

    def add(self, a: float, b: float) -> float:
        """Dodaj dwie liczby."""
        result = a + b
        self.history.append(result)
        return result

    def subtract(self, a: float, b: float) -> float:
        """Odejmij dwie liczby."""
        result = a - b
        self.history.append(result)
        return result

    def multiply(self, a: float, b: float) -> float:
        """Pomnoz dwie liczby."""
        result = a * b
        self.history.append(result)
        return result

    def divide(self, a: float, b: float) -> float:
        """Podziel dwie liczby. Rzuca ZeroDivisionError dla b=0."""
        if b == 0:
            raise ZeroDivisionError("Nie mozna dzielic przez zero")
        result = a / b
        self.history.append(result)
        return result

    def reset(self) -> None:
        """Wyczysc historie."""
        self.history.clear()

    def get_last(self) -> float | None:
        """Zwroc ostatni wynik."""
        return self.history[-1] if self.history else None
