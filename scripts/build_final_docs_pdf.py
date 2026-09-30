"""Zbuduj PDF-y z zestawów markdown w docs/final (pandoc → HTML → Chrome).

Użycie:  python scripts/build_final_docs_pdf.py [--only podrecznik-uzytkownika]

Pipeline per dokument:
1. scala md w kanonicznej kolejności (indeks README + pliki główne + podkatalogi
   alfabetycznie), przepisując względne ścieżki obrazków na ścieżki z korzenia
   docs/final,
2. pandoc (gfm) → samodzielny HTML z wbudowanymi zasobami (--embed-resources)
   i spisem treści,
3. Chrome headless --print-to-pdf (A4, bez nagłówka/stopki przeglądarki),
4. liczy strony (pypdf) i wypisuje podsumowanie.

Wymaga: pandoc ≥ 3, chrome.exe, pypdf (w venv). Wyniki w docs/final/pdf/.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FINAL = REPO / "docs" / "final"
OUT = FINAL / "pdf"
BUILD = OUT / "_build"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]

# Kanoniczna kolejność plików. „+GLOB" = pozostałe .md z podkatalogów, alfabetycznie.
DOCS: dict[str, dict] = {
    "podrecznik-uzytkownika": {
        "title": "Podręcznik użytkownika TestGEN",
        "files": [
            "user-guide/00-spis-tresci.md",
            "user-guide/01-wprowadzenie.md",
            "user-guide/02-projekty-i-analiza.md",
            "user-guide/03-testy-bezpieczenstwo-eksport.md",
            "user-guide/04-integracje-ustawienia-faq.md",
            "user-guide/interfejs-webowy/01-nawigacja-i-ekrany.md",
            "user-guide/interfejs-webowy/02-projekty-i-upload.md",
            "user-guide/interfejs-webowy/03-wyniki-i-test-case-y.md",
            "user-guide/interfejs-webowy/04-raporty-i-eksport.md",
            "user-guide/interfejs-webowy/05-dostepnosc.md",
            "user-guide/billing/01-plany-i-zakup.md",
            "user-guide/billing/02-zarzadzanie-subskrypcja.md",
            "user-guide/billing/03-metody-platnosci.md",
            "user-guide/billing/04-faktury-i-dane-fakturowe.md",
            "user-guide/billing/05-zuzycie-i-powiadomienia.md",
            "user-guide/billing/06-faq.md",
            "user-guide/bezpieczenstwo/01-uruchamianie-skanu.md",
            "user-guide/bezpieczenstwo/02-interpretacja-wynikow.md",
            "user-guide/bezpieczenstwo/03-priorytetyzacja-napraw.md",
            "user-guide/bezpieczenstwo/04-rekomendacje-i-patche.md",
            "user-guide/bezpieczenstwo/05-faq-bezpieczenstwa.md",
            "user-guide/luki-funkcjonalne/01-uruchamianie-analizy.md",
            "user-guide/luki-funkcjonalne/02-interpretacja-wynikow.md",
            "user-guide/luki-funkcjonalne/03-compliance-i-priorytetyzacja.md",
            "user-guide/luki-funkcjonalne/04-rekomendacje-i-skeleton.md",
            "user-guide/luki-funkcjonalne/05-integracje-trackery.md",
            "user-guide/luki-funkcjonalne/06-faq.md",
            "user-guide/indeks-terminow.md",
            "glosariusz.md",
        ],
    },
    "podrecznik-administratora": {
        "title": "Podręcznik administratora TestGEN",
        "files": [
            "admin-guide/README.md",
            "admin-guide/admin-guide.md",
            "admin-guide/panel-administracyjny.md",
        ],
    },
    "moduly-ai": {
        "title": "Moduły analizy TestGEN (AI)",
        "files": [
            "ai-modules/README.md",
            "ai-modules/ai-modules.md",
            "+GLOB:ai-modules",
        ],
    },
    "przewodnik-wdrozeniowy": {
        "title": "Przewodnik wdrożeniowy TestGEN",
        "files": [
            "deployment-guide/README.md",
            "deployment-guide/getting-started.md",
            "deployment-guide/environment-setup.md",
            "deployment-guide/01-instalacja.md",
            "deployment-guide/02-operacje.md",
            "+GLOB:deployment-guide",
        ],
    },
    "rozwiazywanie-problemow": {
        "title": "Rozwiązywanie problemów — TestGEN",
        "files": [
            "troubleshooting/README.md",
            "troubleshooting/troubleshooting.md",
            "troubleshooting/tpay-sandbox-runbook.md",
        ],
    },
    "release-notes": {
        "title": "Release notes — TestGEN",
        "files": ["release-notes/release-notes.md", "release-notes/CHANGELOG.md"],
    },
    "architektura": {
        "title": "Architektura systemu TestGEN",
        "files": [
            "architecture/README.md",
            "architecture/architecture.md",
            "architecture/system.md",
            "architecture/conventions.md",
            "architecture/workflows.md",
            "+GLOB:architecture",
        ],
    },
    "instrukcja-manualna-golden-data": {
        "title": "Instrukcja manualnego badania funkcjonalności TestGEN (golden data)",
        "files": ["testing/instrukcja-manualna-golden-data.md"],
    },
}

PRINT_CSS = """
@page { size: A4; margin: 20mm 16mm; }
html { -webkit-print-color-adjust: exact; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.45; color: #1a1a1a; margin: 0; }
header#title-block-header h1.title { font-size: 24pt; border: none; margin-bottom: 4px; }
p.subtitle, p.author, p.date { color: #475569; margin: 2px 0; }
h1 { page-break-before: always; font-size: 19pt; color: #1e3a8a;
     border-bottom: 2px solid #1e40af; padding-bottom: 5px; margin-top: 0; }
nav#TOC { page-break-after: always; }
nav#TOC::before { content: 'Spis treści'; display: block; font-size: 16pt;
                  font-weight: 700; color: #1e3a8a; margin-bottom: 8px; }
nav#TOC ul { list-style: none; padding-left: 14px; margin: 2px 0; }
nav#TOC a { color: #1e40af; text-decoration: none; }
h2 { font-size: 14pt; color: #1e40af; margin-top: 18px; }
h3 { font-size: 12pt; color: #334155; }
img { max-width: 100%; height: auto; page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 8px 0; }
th, td { border: 1px solid #cbd5e1; padding: 4px 6px; text-align: left;
         vertical-align: top; }
th { background: #f1f5f9; }
tr { page-break-inside: avoid; }
code { background: #f1f5f9; padding: 1px 3px; border-radius: 3px; font-size: 9pt; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px;
      padding: 8px; white-space: pre-wrap; word-break: break-word;
      page-break-inside: avoid; font-size: 8.5pt; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #93c5fd; margin: 8px 0; padding: 2px 12px;
             color: #475569; background: #f8fafc; }
a { color: #1e40af; text-decoration: none; }
hr { border: none; border-top: 1px solid #e2e8f0; }
"""

MD_IMG = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)([^)]*\))")
HTML_IMG = re.compile(r'(<img[^>]+src=")([^"]+)(")')


def _is_external(url: str) -> bool:
    return bool(re.match(r"^(https?:|data:|#|mailto:|/)", url))


def _rewrite_images(md: str, base_dir: str) -> str:
    """Relatywne ścieżki obrazków → ścieżki z korzenia docs/final."""
    prefix = f"{base_dir}/" if base_dir else ""

    def sub_md(m: re.Match) -> str:
        url = m.group(2)
        if _is_external(url):
            return m.group(0)
        return f"{m.group(1)}{prefix}{url}{m.group(3)}"

    def sub_html(m: re.Match) -> str:
        url = m.group(2)
        if _is_external(url):
            return m.group(0)
        return f'{m.group(1)}{prefix}{url}{m.group(3)}'

    return HTML_IMG.sub(sub_html, MD_IMG.sub(sub_md, md))


def resolve_files(spec: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for entry in spec:
        if entry.startswith("+GLOB:"):
            root = FINAL / entry.removeprefix("+GLOB:")
            explicit_dirs = {p.parent for p in resolved if root in p.parents}
            extra = sorted(
                p
                for p in root.rglob("*.md")
                if p.name != "_template.md" and p.parent not in explicit_dirs
                and not any(p == r for r in resolved)
            )
            resolved.extend(extra)
        else:
            path = FINAL / entry
            if not path.exists():
                raise FileNotFoundError(path)
            resolved.append(path)
    return resolved


def build(name: str, spec: dict, chrome: Path) -> int:
    files = resolve_files(spec["files"])
    combined = "\n\n".join(
        _rewrite_images(p.read_text(encoding="utf-8"), p.parent.relative_to(FINAL).as_posix())
        for p in files
    )
    BUILD.mkdir(parents=True, exist_ok=True)
    md_path = BUILD / f"{name}.md"
    md_path.write_text(combined, encoding="utf-8")

    html_path = BUILD / f"{name}.html"
    header = BUILD / "_print_header.html"
    header.write_text(f"<style>{PRINT_CSS}</style>", encoding="utf-8")
    subprocess.run(
        [
            "pandoc",
            "--from=gfm+raw_html",
            "--to=html5",
            "--standalone",
            "--embed-resources",
            "--toc",
            "--toc-depth=2",
            f"--metadata=title:{spec['title']}",
            f"--include-in-header={header}",
            f"--output={html_path}",
            str(md_path),
        ],
        cwd=FINAL,
        check=True,
    )

    pdf_path = OUT / f"{name}.pdf"
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )

    from pypdf import PdfReader

    return len(PdfReader(str(pdf_path)).pages)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows: konsola cp1250 vs ✓/—
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="buduj tylko ten dokument (nazwa z DOCS)")
    args = parser.parse_args()

    chrome = next((c for c in CHROME_CANDIDATES if c.exists()), None)
    if chrome is None:
        print("Nie znaleziono chrome.exe — dodaj ścieżkę do CHROME_CANDIDATES.")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    selected = {args.only: DOCS[args.only]} if args.only else DOCS
    total = 0
    rows: list[tuple[str, int]] = []
    for name, spec in selected.items():
        pages = build(name, spec, chrome)
        rows.append((name, pages))
        total += pages
        print(f"✓ {name}.pdf — {pages} stron")

    width = max(len(n) for n, _ in rows)
    print("\n── Podsumowanie ──────────────────────────────")
    for name, pages in rows:
        print(f"{name:<{width}}  {pages:>4} stron")
    print(f"{'RAZEM':<{width}}  {total:>4} stron")
    print(f"\nKatalog: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
