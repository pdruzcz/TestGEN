"""Treść status checków i komentarzy na PR/MR — Epic 8, Story 8.3.

Moduł jest czysty: bierze policzone findings i konfigurację, oddaje stan
i tekst. Zapytania do bazy i wywołania API zostają w tasku i w klientach
dostawców, dzięki czemu decyzja „przepuścić czy zablokować merge" jest
testowalna bez infrastruktury — a to ona blokuje ludziom pracę, więc musi
być jednoznaczna.

Stany są tu neutralne (``pending``/``success``/``failure``); na słownik
konkretnego dostawcy tłumaczą je ``github_service`` i ``gitlab_service``,
bo GitLab nazywa je inaczej (``running``/``failed``).
"""

from dataclasses import dataclass, field
from typing import Any

# Skala rosnąca — indeks wyznacza „co najmniej tak poważne jak".
SEVERITY_ORDER: tuple[str, ...] = ("info", "low", "medium", "high", "critical")
ALLOWED_THRESHOLDS: tuple[str, ...] = ("critical", "high", "medium")
DEFAULT_THRESHOLD = "critical"

# Nazwa widoczna w PR-ze i w regułach ochrony gałęzi (AC4) — zmiana tej
# stałej zerwie skonfigurowane u klientów required status checks.
STATUS_CONTEXT = "TestGEN / Code Analysis"

PENDING_DESCRIPTION = "Analiza TestGEN w toku..."

_SEVERITY_LABELS_PL = {
    "critical": ("krytyczny", "krytyczne", "krytycznych"),
    "high": ("wysoki", "wysokie", "wysokich"),
    "medium": ("średni", "średnie", "średnich"),
    "low": ("niski", "niskie", "niskich"),
    "info": ("informacyjny", "informacyjne", "informacyjnych"),
}

# CodeError ma własną, trzystopniową skalę (critical/warning/info); żeby
# jeden próg rządził całym status checkiem, sprowadzamy ją do skali findings.
CODE_ERROR_SEVERITY_MAP = {
    "critical": "critical",
    "error": "high",
    "warning": "high",
    "info": "low",
}

# GitHub obcina description do 140 znaków; przycinamy sami, żeby zamiast
# ucięcia w połowie słowa zobaczyć sensowny tekst.
_MAX_DESCRIPTION = 140


@dataclass
class FindingSummary:
    """Pojedyncze znalezisko w formie potrzebnej do komentarza."""

    severity: str
    title: str
    file_path: str | None = None
    line: int | None = None


@dataclass
class AnalysisOutcome:
    """Wynik analizy sprowadzony do tego, co trafia na PR."""

    counts: dict[str, int] = field(default_factory=dict)
    top_findings: list[FindingSummary] = field(default_factory=list)
    pipeline_status: str = "completed"

    def count_at_or_above(self, threshold: str) -> int:
        """Ile znalezisk jest co najmniej tak poważnych jak ``threshold``."""
        cutoff = severity_rank(threshold)
        return sum(n for sev, n in self.counts.items() if severity_rank(sev) >= cutoff)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def severity_rank(severity: str) -> int:
    """Pozycja na skali; nieznane wartości traktujemy najłagodniej."""
    try:
        return SEVERITY_ORDER.index((severity or "").lower())
    except ValueError:
        return 0


def normalize_threshold(value: str | None) -> str:
    """Sprowadza próg z konfiguracji do dozwolonej wartości."""
    candidate = (value or "").lower()
    return candidate if candidate in ALLOWED_THRESHOLDS else DEFAULT_THRESHOLD


def _plural_pl(count: int, forms: tuple[str, str, str]) -> str:
    """Polska odmiana: 1 krytyczny, 2 krytyczne, 5 krytycznych."""
    singular, few, many = forms
    if count == 1:
        return singular
    last_two = count % 100
    if 12 <= last_two <= 14:
        return many
    return few if count % 10 in (2, 3, 4) else many


def _describe_counts(counts: dict[str, int], severities: tuple[str, ...]) -> str:
    parts = []
    for severity in severities:
        n = counts.get(severity, 0)
        if n:
            parts.append(f"{n} {_plural_pl(n, _SEVERITY_LABELS_PL[severity])}")
    return ", ".join(parts)


def build_status_description(
    outcome: AnalysisOutcome,
    threshold: str = DEFAULT_THRESHOLD,
    *,
    fail_on_threshold: bool = True,
) -> tuple[str, str]:
    """Zwraca ``(state, description)`` dla zakończonej analizy (AC1/AC3).

    ``fail_on_threshold=False`` pozostawia status zielony niezależnie od
    znalezisk — zespół chce wtedy widzieć liczby, ale nie blokować merge'a.
    """
    threshold = normalize_threshold(threshold)
    blocking = outcome.count_at_or_above(threshold)

    if outcome.pipeline_status == "failed":
        return "failure", "Analiza TestGEN nie powiodła się"

    if blocking:
        above = tuple(
            s for s in reversed(SEVERITY_ORDER) if severity_rank(s) >= severity_rank(threshold)
        )
        detail = _describe_counts(outcome.counts, above)
        description = f"Znaleziono {detail} {_plural_pl(blocking, ('problem', 'problemy', 'problemów'))}"
        state = "failure" if fail_on_threshold else "success"
        if not fail_on_threshold:
            description = f"{description} (próg nie blokuje merge'a)"
        return state, _truncate(description)

    if outcome.total:
        return "success", _truncate(
            f"Brak problemów powyżej progu „{threshold}”; pozostałe znaleziska: {outcome.total}"
        )

    if outcome.pipeline_status == "partial_failure":
        return "success", "Analiza zakończona częściowo — brak problemów krytycznych"

    return "success", "Analiza zakończona — brak problemów krytycznych"


def _truncate(text: str) -> str:
    if len(text) <= _MAX_DESCRIPTION:
        return text
    return text[: _MAX_DESCRIPTION - 1].rstrip() + "…"


def build_pr_comment(
    outcome: AnalysisOutcome,
    report_url: str,
    *,
    threshold: str = DEFAULT_THRESHOLD,
) -> str:
    """Komentarz w Markdownie: podsumowanie, trzy najpoważniejsze, link (AC5).

    Markdown jest wspólny dla GitHuba i GitLaba — oba renderują tabele
    i listy w komentarzach tak samo.
    """
    threshold = normalize_threshold(threshold)
    lines = ["## Analiza TestGEN", ""]

    if not outcome.total:
        lines.append("Nie znaleziono żadnych problemów. :tada:")
    else:
        lines.append("| Waga | Liczba |")
        lines.append("| --- | ---: |")
        for severity in reversed(SEVERITY_ORDER):
            n = outcome.counts.get(severity, 0)
            if n:
                label = _SEVERITY_LABELS_PL[severity][1].capitalize()
                lines.append(f"| {label} | {n} |")
        lines.append("")

        blocking = outcome.count_at_or_above(threshold)
        if blocking:
            lines.append(
                f"**Próg blokujący: `{threshold}`** — {blocking} "
                f"{_plural_pl(blocking, ('znalezisko', 'znaleziska', 'znalezisk'))} na tym poziomie lub wyżej."
            )
        else:
            lines.append(f"Brak znalezisk na poziomie `{threshold}` lub wyżej.")
        lines.append("")

    if outcome.top_findings:
        lines.append("### Najpoważniejsze znaleziska")
        lines.append("")
        for finding in outcome.top_findings[:3]:
            location = ""
            if finding.file_path:
                location = f" — `{finding.file_path}`"
                if finding.line:
                    location += f":{finding.line}"
            label = _SEVERITY_LABELS_PL.get(finding.severity, (finding.severity,) * 3)[0]
            lines.append(f"- **[{label}]** {finding.title}{location}")
        lines.append("")

    lines.append(f"[Pełny raport w TestGEN]({report_url})")
    return "\n".join(lines)


def outcome_from_rows(
    security_rows: list[Any],
    code_error_rows: list[Any],
    pipeline_status: str = "completed",
) -> AnalysisOutcome:
    """Składa ``AnalysisOutcome`` z wierszy ``SecurityFinding`` i ``CodeError``.

    Obie tabele trafiają na jedną skalę wag: inaczej próg musiałby być
    konfigurowany osobno dla każdego źródła, a użytkownik oczekuje jednego
    „nie wpuszczaj krytycznych".
    """
    counts: dict[str, int] = {}
    summaries: list[FindingSummary] = []

    for row in security_rows:
        severity = getattr(row.severity, "value", row.severity)
        counts[severity] = counts.get(severity, 0) + 1
        summaries.append(
            FindingSummary(
                severity=severity,
                title=getattr(row, "vulnerability_type", None) or "Znalezisko bezpieczeństwa",
                file_path=getattr(row, "file_path", None),
                line=getattr(row, "line_start", None),
            )
        )

    for row in code_error_rows:
        raw = getattr(row.severity, "value", row.severity) or ""
        severity = CODE_ERROR_SEVERITY_MAP.get(raw.lower(), "low")
        counts[severity] = counts.get(severity, 0) + 1
        summaries.append(
            FindingSummary(
                severity=severity,
                title=getattr(row, "message", None) or "Błąd w kodzie",
                file_path=getattr(row, "file_path", None),
                line=getattr(row, "line_start", None),
            )
        )

    summaries.sort(key=lambda f: severity_rank(f.severity), reverse=True)
    return AnalysisOutcome(counts=counts, top_findings=summaries[:3], pipeline_status=pipeline_status)
