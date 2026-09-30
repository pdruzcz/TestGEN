"""Wspólne stałe i pomocniki eksportu raportów — Story 6.7."""

SEVERITY_PL: dict[str, str] = {
    "critical": "Krytyczny",
    "high": "Wysoki",
    "medium": "Średni",
    "low": "Niski",
}

SOURCE_PL: dict[str, str] = {
    "security": "Skan bezpieczeństwa",
    "gap": "Analiza luk",
}

REPORT_TYPE_PL: dict[str, str] = {
    "executive": "Podsumowanie wykonawcze",
    "technical": "Szczegóły techniczne",
    "both": "Raport pełny",
}

SEVERITY_ORDER: list[str] = ["critical", "high", "medium", "low"]


def severity_pl(value: str | None) -> str:
    return SEVERITY_PL.get((value or "").lower(), value or "")


def source_pl(value: str | None) -> str:
    return SOURCE_PL.get((value or "").lower(), value or "")


def kpi_rows(report: dict) -> list[tuple[str, str]]:
    """Wiersze tabeli wskaźników (polskie etykiety) używane przez PDF/HTML/Excel."""
    kpis = report.get("kpis") or {}

    def pct(value) -> str:
        return f"{round(value)}%" if value is not None else "—"

    return [
        ("Zgodność z dokumentacją", pct(kpis.get("compliance_score"))),
        ("Pokrycie wymagań", pct(kpis.get("coverage_percentage"))),
        ("Wykryte problemy (łącznie)", str(kpis.get("total_findings", 0))),
        ("Problemy krytyczne", str(kpis.get("critical_count", 0))),
        ("Problemy ważne", str(kpis.get("high_count", 0))),
        ("Problemy umiarkowane", str(kpis.get("medium_count", 0))),
        ("Problemy drobne", str(kpis.get("low_count", 0))),
        ("Przypadki testowe (łącznie)", str(kpis.get("test_cases_total", 0))),
        ("Przypadki gotowe do uruchomienia", str(kpis.get("test_cases_ready", 0))),
        ("Przypadki zakończone pozytywnie", str(kpis.get("test_cases_passed", 0))),
    ]
