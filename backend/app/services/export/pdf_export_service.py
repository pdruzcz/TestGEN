"""Eksport PDF — Story 6.7, AC1.

ReportLab (platypus): nagłówki, tabele KPI/modułów, wykres słupkowy severity
(kolor + paski o różnej gęstości — WCAG, nie tylko kolor), ustalenia z
fragmentami kodu. Polskie znaki: rejestracja fontu TTF z glifami PL
(DejaVu/Arial), z degradacją do Helvetica gdy font niedostępny.
"""

import io
import logging
import os
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.export.common import (
    REPORT_TYPE_PL,
    SEVERITY_ORDER,
    kpi_rows,
    severity_pl,
    source_pl,
)

logger = logging.getLogger(__name__)

# Kandydaci fontów z polskimi glifami: Linux (obraz Docker), Windows (dev).
_FONT_CANDIDATES: list[tuple[str, str, str]] = [
    (
        "DejaVuSans",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "DejaVuSans",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ),
    ("ArialPL", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]

_fonts: tuple[str, str] | None = None

SEVERITY_HEX = {
    "critical": "#c62828",
    "high": "#ef6c00",
    "medium": "#f9a825",
    "low": "#2e7d32",
}

SEVERITY_COLORS = {sev: colors.HexColor(hex_) for sev, hex_ in SEVERITY_HEX.items()}

# Gęstość pasków per severity — rozróżnienie bez koloru (WCAG).
SEVERITY_STRIPE_STEP = {"critical": 4, "high": 8, "medium": 12, "low": 0}


def _register_fonts() -> tuple[str, str]:
    """Zwraca (font, font_bold); rejestruje TTF z polskimi glifami jeśli dostępny."""
    global _fonts
    if _fonts is not None:
        return _fonts
    for name, regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            try:
                pdfmetrics.registerFont(TTFont(name, regular))
                bold_name = name
                if os.path.exists(bold):
                    bold_name = f"{name}-Bold"
                    pdfmetrics.registerFont(TTFont(bold_name, bold))
                _fonts = (name, bold_name)
                return _fonts
            except Exception:  # pragma: no cover — uszkodzony plik fontu
                logger.warning("Nie udało się zarejestrować fontu %s", regular)
    logger.warning("Brak fontu TTF z polskimi glifami — PDF użyje fontu Helvetica")
    _fonts = ("Helvetica", "Helvetica-Bold")
    return _fonts


def _severity_chart(counts: dict, font: str) -> Drawing:
    """Poziomy wykres słupkowy severity: kolor + paski o różnej gęstości."""
    entries = [(sev, counts.get(sev, 0)) for sev in SEVERITY_ORDER if counts.get(sev, 0) > 0]
    max_count = max([c for _, c in entries] + [1])
    row_h, gap, label_w, bar_max = 16, 8, 90, 280
    height = len(entries) * (row_h + gap)
    drawing = Drawing(420, height)

    for i, (sev, count) in enumerate(entries):
        y = height - (i + 1) * (row_h + gap) + gap
        bar_w = max(3, (count / max_count) * bar_max)
        drawing.add(
            String(0, y + 4, severity_pl(sev), fontName=font, fontSize=9)
        )
        drawing.add(
            Rect(label_w, y, bar_w, row_h, fillColor=SEVERITY_COLORS[sev], strokeColor=None)
        )
        step = SEVERITY_STRIPE_STEP[sev]
        if step:
            x = label_w + step
            while x < label_w + bar_w:
                drawing.add(
                    Line(x, y, x, y + row_h, strokeColor=colors.Color(1, 1, 1, alpha=0.6), strokeWidth=1.2)
                )
                x += step
        drawing.add(
            String(label_w + bar_w + 6, y + 4, str(count), fontName=font, fontSize=9)
        )
    return drawing


def render(report: dict, report_type: str = "both") -> bytes:
    font, font_bold = _register_fonts()

    h1 = ParagraphStyle("h1", fontName=font_bold, fontSize=16, leading=20, textColor=colors.HexColor("#1a237e"))
    h2 = ParagraphStyle(
        "h2", fontName=font_bold, fontSize=12, leading=16, spaceBefore=12, textColor=colors.HexColor("#1a237e")
    )
    body = ParagraphStyle("body", fontName=font, fontSize=9.5, leading=13)
    meta = ParagraphStyle("meta", fontName=font, fontSize=8.5, leading=11, textColor=colors.HexColor("#616161"))
    code_style = ParagraphStyle("code", fontName="Courier", fontSize=7.5, leading=9.5, backColor=colors.HexColor("#f5f5f5"))

    table_style = TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdbdbd")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )

    story = [
        Paragraph(f"{REPORT_TYPE_PL.get(report_type, REPORT_TYPE_PL['both'])} — TestGEN", h1),
        Paragraph(
            f"Wygenerowano: {report.get('generated_at') or ''} • Projekt: {report.get('project_id') or ''}",
            meta,
        ),
        Spacer(1, 6 * mm),
        Paragraph("Kluczowe wskaźniki", h2),
        Table([["Wskaźnik", "Wartość"], *kpi_rows(report)], colWidths=[100 * mm, 60 * mm], style=table_style),
        Paragraph("Kluczowe wnioski", h2),
    ]
    for conclusion in report.get("conclusions") or []:
        story.append(Paragraph(f"• {escape(str(conclusion))}", body))

    counts = report.get("severity_counts") or {}
    if any(counts.get(sev, 0) for sev in SEVERITY_ORDER):
        story.append(Paragraph("Rozkład problemów", h2))
        story.append(_severity_chart(counts, font))

    modules = report.get("module_scores") or []
    if modules:
        story.append(Paragraph("Zgodność według modułów", h2))
        rows = [["Moduł (plik)", "Zgodność [%]", "Problemy"]]
        for m in modules:
            rows.append([m.get("file_path") or "", str(round(m.get("score") or 0)), str(m.get("total_findings", 0))])
        story.append(Table(rows, colWidths=[110 * mm, 25 * mm, 25 * mm], style=table_style))

    if report_type in ("technical", "both"):
        findings = report.get("findings") or []
        story.append(Paragraph(f"Szczegółowe ustalenia ({len(findings)})", h2))
        for f in findings:
            severity = (f.get("severity") or "low").lower()
            badges = [severity_pl(severity), source_pl(f.get("source"))]
            if f.get("cwe_id"):
                badges.append(f["cwe_id"])
            if f.get("cvss_score") is not None:
                badges.append(f"CVSS {f['cvss_score']}")
            location = f.get("file_path") or ""
            if location and f.get("line_start"):
                location = f"{location}:{f['line_start']}"

            story.append(Spacer(1, 3 * mm))
            badge_color = SEVERITY_HEX.get(severity, SEVERITY_HEX["low"])
            story.append(
                Paragraph(
                    f'<font color="{badge_color}"><b>{escape(" • ".join(badges))}</b></font>', meta
                )
            )
            story.append(
                Paragraph(escape(f.get("title") or ""), ParagraphStyle("ft", parent=body, fontName=font_bold))
            )
            if f.get("description"):
                story.append(Paragraph(escape(str(f["description"])), body))
            if location:
                story.append(Paragraph(f"Powiązanie: {escape(location)}", meta))
            if f.get("code_snippet"):
                story.append(Preformatted(str(f["code_snippet"]), code_style, maxLineLength=100))
            if f.get("recommendation"):
                story.append(Paragraph(f"Rekomendacja: {escape(str(f['recommendation']))}", body))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Raport TestGEN",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    doc.build(story)
    return buffer.getvalue()
