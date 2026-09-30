"""Eksport CSV — Story 6.7, AC3.

UTF-8 z BOM, separator średnikowy (polski standard Excela), polskie nagłówki.
Escapowanie średników/cudzysłowów zapewnia moduł csv (QUOTE_MINIMAL).
"""

import csv
import io

from app.services.export.common import severity_pl, source_pl

CSV_HEADERS = [
    "Lp.",
    "Źródło",
    "Tytuł",
    "Opis",
    "Istotność",
    "CWE",
    "CVSS",
    "Plik",
    "Linia",
    "Rekomendacja",
]


def render(report: dict, report_type: str = "both") -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for i, finding in enumerate(report.get("findings") or [], start=1):
        writer.writerow(
            [
                i,
                source_pl(finding.get("source")),
                finding.get("title") or "",
                finding.get("description") or "",
                severity_pl(finding.get("severity")),
                finding.get("cwe_id") or "",
                finding.get("cvss_score") if finding.get("cvss_score") is not None else "",
                finding.get("file_path") or "",
                finding.get("line_start") if finding.get("line_start") is not None else "",
                finding.get("recommendation") or "",
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
