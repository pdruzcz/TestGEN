# Formaty dokumentacji — macierz możliwości (Epic 2)

Obsługiwane formaty dokumentacji, ich możliwości ekstrakcji, detekcja nagłówków,
limity i biblioteki parsujące. Ścieżka natywna. Źródło pipeline'u:
[document-analysis.md](./document-analysis.md).

## Możliwości ekstrakcji per format

| Format | Tekst | Tabele | Nagłówki | Listy | Metadane | Biblioteka |
|--------|-------|--------|----------|-------|----------|------------|
| PDF    | tak (warstwa tekstowa; skan → OCR) | nie | tak (numerowane/ALL-CAPS) | tak (linia) | liczba stron, `has_ocr` | PyPDF2 (+PyMuPDF/Tesseract) |
| DOCX   | tak | tak (style tabel) | tak (`Heading N`) | tak (akapity) | liczba akapitów/tabel | python-docx |
| HTML   | tak | tak (`<table>`) | tak (`<h1>`–`<h6>`) | tak (`<ul>/<ol>`) | — | BeautifulSoup4 |
| MD     | tak | tak (GFM) | tak (ATX `#`/Setext) | tak | liczba linii | regex (stdlib) |
| TXT    | tak | nie | nie (akapity) | nie | — | stdlib I/O |

> Tabele PDF nie są ekstrahowane w v1. PDF bez warstwy tekstowej (skan) jest
> OCR-owany realnie — PyMuPDF rasteryzuje strony, a współdzielony silnik
> `OCRService` (Tesseract → EasyOCR, reuse z Epic 3) ekstrahuje tekst — gdy
> dostępne zależności z grupy `imaging`. Bez nich parser degraduje się łagodnie
> do warstwy tekstowej PyPDF2 (`has_ocr=false`), bez awarii.

## Detekcja nagłówków per format

| Format | Sygnał nagłówka | Poziom |
|--------|-----------------|--------|
| PDF    | Linia ALL-CAPS (`isupper()`, bez interpunkcji) | 1 |
| PDF    | `N. Tytuł` / `N.N` / `N.N.N` / cyfry rzymskie | 1–4 |
| DOCX   | Styl `Heading 1`–`Heading 6` | 1–6 |
| HTML   | Tagi `<h1>`–`<h6>` | 1–6 |
| MD     | ATX (`#`–`######`) / Setext (podkreślenie) | 1–6 |
| TXT    | brak (akapity > 50 znaków, poziom 0) | 0 |

Preprocesor czyści tytuły z wiodącej numeracji (`"2. Wymagania"` → `"Wymagania"`)
i buduje drzewo parent-child wg poziomów.

## Limity

| Format | Maks. stron | Kodowanie |
|--------|-------------|-----------|
| PDF    | 500 (`PDFParser.MAX_PAGES`) | UTF-8 / Latin-2 |
| DOCX/HTML/MD | — | UTF-8 |
| TXT    | — | UTF-8 / Windows-1250 |

Maks. rozmiar pliku wg konfiguracji uploadu. Preprocesor normalizuje polskie
znaki i usuwa artefakty.

## Znane ograniczenia

- **PDF skanowany** — brak warstwy tekstowej; dokument z < 100 znaków tekstu →
  OCR (PyMuPDF → Tesseract/EasyOCR, gdy deps `imaging`) → realny tekst, sekcje
  zbudowane z OCR, `has_ocr=true`. Bez deps `imaging` → degradacja do warstwy
  PyPDF2 (`has_ocr=false`); przy pustym tekście dalszy preprocessing może
  zgłosić `ValueError` → plik `failed` (niezależne ograniczenie preprocessora).
- **OCR PDF — jakość i język** — rasteryzacja 300 DPI; Tesseract w trybie
  domyślnym, EasyOCR (`pl+en`) jako fallback; polskie diakrytyki mogą być
  zniekształcone. Jakość zależy od rozdzielczości i czystości skanu.
- **PDF — układ wielokolumnowy** — tekst może być w nieoczekiwanej kolejności
  (ograniczenie ekstrakcji liniowej PyPDF2).
- **HTML z JavaScript** — dynamiczna treść niewykonana (BeautifulSoup parsuje
  statyczny DOM).
- **MD — tabele zagnieżdżone** — obsługiwane tabele GFM; zagnieżdżenia w
  komórkach ograniczone.
- **TXT** — nagłówki niewykrywalne; segmentacja po akapitach.
- **DOCX** — makra VBA nieparsowane.

## Fabryka parserów

`get_document_parser(file_path)` (`app/services/analysis/document/__init__.py`)
wybiera parser po rozszerzeniu (`.pdf`, `.docx`, `.md`/`.markdown`,
`.html`/`.htm`, `.txt`). Nieobsługiwane rozszerzenie → `ValueError`.

| Format | Moduł |
|--------|-------|
| PDF    | `app/services/analysis/document/pdf_parser.py` |
| DOCX   | `app/services/analysis/document/docx_parser.py` |
| HTML   | `app/services/analysis/document/html_parser.py` |
| MD     | `app/services/analysis/document/markdown_parser.py` |
| TXT    | `app/services/analysis/document/txt_parser.py` |
