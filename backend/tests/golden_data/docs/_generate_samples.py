"""Generator próbek golden data dla modułu dokumentacji — Story 2.11.

Tworzy 10 dokumentów referencyjnych (4x PDF/reportlab, 3x DOCX/python-docx,
2x Markdown, 1x HTML) w języku polskim, zaprojektowanych pod **natywną** ścieżkę
analizy: tytuły/sekcje pasujące do reguł klasyfikatora, wymagania sformułowane
pod wzorce ekstraktora (``WYM-NNN`` + ``System musi …``), sekcje glosariusza
oraz celowe, łatwo wykrywalne niespójności (duplikaty >0,85 podobieństwa,
brakujące referencje ``UC-NNN``) w próbkach oznaczonych jako rozbieżne.

Skrypt jednorazowy / konserwacyjny — uruchamiany ręcznie, NIE jest testem
(prefiks ``_`` → pytest ignoruje). Binaria (PDF/DOCX) są reprodukowalne z tego
źródła, co umożliwia code review treści.

Uruchomienie::

    cd backend
    python -m tests.golden_data.docs._generate_samples

Zależności: ``reportlab`` (dev dep), ``python-docx`` (dep główny).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).parent

# Domyślne fonty reportlab (Helvetica/StandardEncoding) NIE wspierają polskich
# znaków diakrytycznych (ąćęłńóśźż) — PyPDF2 wyodrębnia je jako ■. Rejestrujemy
# TTF Arial (Windows; Latin-Extended), dzięki czemu generowane PDF-y mają poprawną
# warstwę tekstową i parser odzyskuje polski tekst. Binaria są regenerowane na
# maszynie deweloperskiej (Windows); CI jedynie parsuje commitowane pliki.
_UNICODE_FONT = "TestGenUnicode"


def _ensure_unicode_font() -> str:
    """Zarejestruj TTF z obsługą polskich znaków; zwróć nazwę fontu."""
    if _UNICODE_FONT in pdfmetrics.getRegisteredFontNames():
        return _UNICODE_FONT
    for candidate in (
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont(_UNICODE_FONT, candidate))
            return _UNICODE_FONT
    raise RuntimeError(
        "Nie znaleziono TTF z obsługą polskich znaków (arial.ttf/DejaVuSans.ttf). "
        "Generator PDF wymaga fontu Latin-Extended — zainstaluj Arial lub DejaVuSans."
    )


# Typ bloku treści: (rodzaj, tekst). Rodzaj: h1/h2/h3 (nagłówek), p (akapit).
Block = tuple[str, str]


# ── Renderery formatów ──────────────────────────────────────────────────────


def _pdf(path: Path, title: str, blocks: list[Block]) -> None:
    """PDF z numerowanymi nagłówkami (``1. …`` → L2 w PDFParser)."""
    font = _ensure_unicode_font()
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle("h", parent=styles["Heading2"], fontName=font, fontSize=13, spaceBefore=10, spaceAfter=4)
    p_style = ParagraphStyle("p", parent=styles["BodyText"], fontName=font, fontSize=10, leading=14, spaceAfter=4)
    title_style = ParagraphStyle("t", parent=styles["Title"], fontName=font, fontSize=18, spaceAfter=14)

    flow: list = [Paragraph(title.upper(), title_style)]
    for kind, text in blocks:
        if kind in ("h1", "h2", "h3"):
            # ALL-CAPS bez numeracji → PDFParser._detect_header_level zwraca L1,
            # dzięki czemu nagłówki są top-level (sections[:3] widzi tytuły →
            # wzorce klasyfikatora pasują). Numerowane "1. …" dawały L2 i gniazdowanie
            # pod "Untitled", co obniżało pewność klasyfikacji PDF.
            flow.append(Paragraph(text.upper(), h_style))
        else:
            flow.append(Paragraph(text, p_style))
        flow.append(Spacer(1, 2))

    doc = SimpleDocTemplate(str(path), pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(flow)


def _docx(path: Path, title: str, blocks: list[Block]) -> None:
    """DOCX z prawdziwymi stylami Heading N (niezawodne dla DOCXParser)."""
    doc = Document()
    h = doc.add_heading(title, level=0)
    for run in h.runs:
        run.font.size = Pt(20)
    for kind, text in blocks:
        if kind == "h1":
            doc.add_heading(text, level=1)
        elif kind == "h2":
            doc.add_heading(text, level=2)
        elif kind == "h3":
            doc.add_heading(text, level=3)
        else:
            doc.add_paragraph(text)
    doc.save(str(path))


def _markdown(path: Path, title: str, blocks: list[Block]) -> None:
    lines = [f"# {title}", ""]
    for kind, text in blocks:
        if kind == "h1":
            lines += [f"## {text}", ""]
        elif kind == "h2":
            lines += [f"### {text}", ""]
        elif kind == "h3":
            lines += [f"#### {text}", ""]
        else:
            lines += [text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _html(path: Path, title: str, blocks: list[Block]) -> None:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="pl">',
        "<head><meta charset='utf-8'><title>" + title + "</title></head>",
        "<body>",
        "<article>",
        f"<h1>{title}</h1>",
    ]
    open_section = False
    for kind, text in blocks:
        if kind == "h1":
            if open_section:
                parts.append("</section>")
            parts.append("<section>")
            parts.append(f"<h2>{text}</h2>")
            open_section = True
        elif kind == "h2":
            parts.append(f"<h3>{text}</h3>")
        elif kind == "h3":
            parts.append(f"<h4>{text}</h4>")
        else:
            parts.append(f"<p>{text}</p>")
    if open_section:
        parts.append("</section>")
    parts += ["</article>", "</body>", "</html>"]
    path.write_text("\n".join(parts), encoding="utf-8")


# ── Treści próbek ───────────────────────────────────────────────────────────
# Wymagania frazowane pod wzorce: ID ``WYM-NNN`` (+30 conf), ``System musi …``
# (+15 pattern), w sekcji ``Wymagania funkcjonalne`` (+15 section).


def _srs_system_logowania() -> tuple[str, list[Block]]:
    title = "Specyfikacja wymagań systemu logowania"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        (
            "p",
            "Niniejszy dokument jest specyfikacją wymagań dla systemu logowania. "
            "Opisuje wymagania funkcjonalne oraz niefunkcjonalne.",
        ),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: System musi umożliwiać logowanie za pomocą adresu email i hasła."),
        ("p", "WYM-002: Hasło musi zawierać minimum dwanaście znaków, w tym wielką literę, cyfrę i znak specjalny."),
        ("p", "WYM-003: System musi blokować konto po pięciu nieudanych próbach logowania na trzydzieści minut."),
        ("p", "WYM-004: Sesja użytkownika musi wygasać po sześćdziesięciu minutach nieaktywności."),
        ("p", "WYM-005: System musi obsługiwać uwierzytelnianie wieloskładnikowe za pomocą algorytmu TOTP."),
        ("h1", "Wymagania niefunkcjonalne"),
        (
            "p",
            "WYM-010: System musi zapewniać dostępność na poziomie co najmniej dziewięćdziesięciu dziewięciu procent.",
        ),
        ("p", "WYM-011: Czas odpowiedzi operacji logowania nie może przekraczać dwóch sekund."),
        ("h1", "Glosariusz"),
        ("p", "MFA: Uwierzytelnianie wieloskładnikowe, wymagające dwóch niezależnych czynników."),
        ("p", "TOTP: Algorytm jednorazowych haseł opartych na czasie."),
        ("p", "Sesja: Okres aktywnego uwierzytelnienia użytkownika po zalogowaniu."),
    ]
    return title, blocks


def _srs_platnosci() -> tuple[str, list[Block]]:
    # Z celowymi niespójnościami: duplikat (WYM-005 ≈ WYM-006) + brakująca referencja (UC-999).
    title = "Specyfikacja wymagań modułu płatności"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Specyfikacja wymagań dla modułu płatności internetowych."),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: System musi akceptować płatności kartami Visa oraz Mastercard."),
        ("p", "WYM-002: System musi przetwarzać zwroty środków w ciągu czternastu dni."),
        ("p", "WYM-003: System musi importować dane użytkowników zgodnie ze standardem UC-999."),
        ("p", "WYM-004: System musi generować potwierdzenie płatności w formacie PDF."),
        (
            "p",
            "WYM-005: System musi umożliwiać resetowanie hasła użytkownika poprzez wysłanie linku resetującego na adres email.",
        ),
        (
            "p",
            "WYM-006: System musi umożliwiać resetowanie hasła użytkownika poprzez wysłanie linku resetującego na adres email.",
        ),
        ("h1", "Wymagania niefunkcjonalne"),
        ("p", "WYM-010: System musi zapewniać bezpieczeństwo danych kartowych przez szyfrowanie."),
        ("h1", "Glosariusz"),
        ("p", "Płatność: Operacja przekazania środków w zamian za produkt lub usługę."),
        ("p", "Zwrot: Procedura oddania środków klientowi po anulowanej transakcji."),
    ]
    return title, blocks


def _srs_raporty() -> tuple[str, list[Block]]:
    title = "Specyfikacja wymagań modułu raportów"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Specyfikacja wymagań dla modułu generowania raportów."),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: System musi generować raporty w formacie PDF oraz Excel."),
        ("p", "WYM-002: Użytkownik może eksportować raport do pliku CSV."),
        ("p", "WYM-003: System musi harmonogramować generowanie raportów okresowych."),
        ("p", "WYM-004: System musi filtrować dane raportu według zakresu dat."),
        ("p", "WYM-005: System musi zapisywać raporty w repozytorium plików."),
        ("h1", "Wymagania niefunkcjonalne"),
        ("p", "WYM-010: Generowanie raportu musi trwać nie dłużej niż trzydzieści sekund."),
        ("h1", "Glosariusz"),
        ("p", "Raport: Uporządkowane zestawienie danych w formie dokumentu."),
        ("p", "Eksport: Zapisanie danych do pliku zewnętrznego formatu."),
    ]
    return title, blocks


def _brd_system_logowania() -> tuple[str, list[Block]]:
    # Z celowymi niespójnościami: duplikat (WYM-004 ≈ WYM-005) + brakująca referencja (UC-888).
    title = "Biznesowe wymagania systemu logowania"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Biznesowy dokument wymagań dla systemu logowania."),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: System musi wspierać logowanie klientów za pomocą poświadczeń."),
        ("p", "WYM-002: System musi integrować się z zewnętrznym dostawcą tożsamości."),
        ("p", "WYM-003: System musi rejestrować wszystkie zdarzenia logowania do audytu."),
        (
            "p",
            "WYM-004: System musi umożliwiać zmianę hasła użytkownika poprzez wysłanie jednorazowego kodu na adres email.",
        ),
        (
            "p",
            "WYM-005: System musi umożliwiać zmianę hasła użytkownika poprzez wysłanie jednorazowego kodu na adres email.",
        ),
        ("p", "WYM-006: System musi synchronizować konta zgodnie z procedurą UC-888."),
        ("h1", "Wymagania niefunkcjonalne"),
        ("p", "WYM-010: System musi zapewniać bezpieczeństwo danych uwierzytelniających."),
        ("h1", "Glosariusz"),
        ("p", "Audyt: Systematyczna weryfikacja zapisanych zdarzeń systemowych."),
    ]
    return title, blocks


def _brd_platnosci() -> tuple[str, list[Block]]:
    title = "Biznesowe wymagania modułu płatności"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Biznesowy dokument wymagań dla modułu płatności."),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: System musi obsługiwać płatności jednorazowe kartą."),
        ("p", "WYM-002: System musi realizować zwroty środków na żądanie klienta."),
        ("p", "WYM-003: System musi walidować status płatności przed wydaniem produktu."),
        ("p", "WYM-004: System musi generować fakturę po zaksięgowaniu płatności zgodnie ze standardem UC-666."),
        (
            "p",
            "WYM-005: System musi konsolidować salda konta klienta po każdej zakończonej transakcji płatniczej w danym dniu.",
        ),
        (
            "p",
            "WYM-006: System musi konsolidować salda konta klienta po każdej zakończonej transakcji płatniczej w danym dniu.",
        ),
        ("h1", "Wymagania niefunkcjonalne"),
        ("p", "WYM-010: System musi zapewniać dostępność usługi płatności przez całą dobę."),
        ("h1", "Glosariusz"),
        ("p", "Faktura: Dokument księgowy potwierdzający transakcję sprzedaży."),
        ("p", "Transakcja: Pojedyncza operacja finansowa w systemie."),
    ]
    return title, blocks


def _frd_modul_uzytkownikow_pdf() -> tuple[str, list[Block]]:
    # Z celową niespójnością: duplikat (WYM-003 ≈ WYM-004).
    title = "Funkcjonalne wymagania modułu użytkowników"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Funkcjonalny dokument wymagań dla modułu zarządzania użytkownikami."),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: System musi tworzyć konta użytkowników z przypisaną rolą."),
        ("p", "WYM-002: System musi dezaktywować konto użytkownika na żądanie administratora."),
        (
            "p",
            "WYM-003: System musi przypisywać nową rolę użytkownikowi podczas tworzenia konta w panelu administracyjnym systemu.",
        ),
        (
            "p",
            "WYM-004: System musi przypisywać nową rolę użytkownikowi podczas tworzenia konta w panelu administracyjnym systemu.",
        ),
        ("p", "WYM-005: System musi zapraszać nowych użytkowników wiadomością email zgodnie z procedurą UC-777."),
        ("h1", "Wymagania niefunkcjonalne"),
        ("p", "WYM-010: System musi zapewniać bezpieczeństwo danych osobowych użytkowników."),
        ("h1", "Glosariusz"),
        ("p", "Rola: Zbiór uprawnień przypisany grupie użytkowników."),
        ("p", "Uprawnienie: Prawo wykonania określonej operacji w systemie."),
    ]
    return title, blocks


def _frd_modul_uzytkownikow_html() -> tuple[str, list[Block]]:
    title = "Funkcjonalne wymagania profilu użytkownika"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Funkcjonalny dokument wymagań dla profilu użytkownika."),
        ("h1", "Wymagania funkcjonalne"),
        ("p", "WYM-001: Użytkownik może edytować dane swojego profilu."),
        ("p", "WYM-002: Użytkownik może zmienić hasło do swojego konta."),
        ("p", "WYM-003: System musi pozwalać na wgranie zdjęcia profilowego."),
        ("p", "WYM-004: Użytkownik może ustawić preferowany język interfejsu."),
        ("h1", "Wymagania niefunkcjonalne"),
        ("p", "WYM-010: System musi zapewniać wydajność ładowania profilu poniżej jednej sekundy."),
        ("h1", "Glosariusz"),
        ("p", "Profil: Zbiór danych opisujących użytkownika w systemie."),
        ("p", "Preferencja: Ustawienie wybrane przez użytkownika."),
    ]
    return title, blocks


def _podrecznik_administratora() -> tuple[str, list[Block]]:
    title = "Podręcznik administratora systemu"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        (
            "p",
            "Podręcznik przeznaczony dla administratora systemu. Opisuje obsługę interfejsu oraz ekranów administracyjnych.",
        ),
        ("h1", "Zarządzanie użytkownikami"),
        ("p", "Aby dodać użytkownika, kliknij przycisk Dodaj użytkownika na ekranie listy użytkowników."),
        ("p", "Aby zmienić rolę, wybierz użytkownika z listy i kliknij przycisk Zmień rolę."),
        ("h1", "Konfiguracja"),
        (
            "p",
            "Ekran konfiguracji pozwala ustawić parametry systemu. Kliknij menu Konfiguracja, aby otworzyć formularz.",
        ),
        ("h1", "Glosariusz"),
        ("p", "Administrator: Użytkownik z pełnymi uprawnieniami do zarządzania systemem."),
        ("p", "Interfejs: Zbiór ekranów i przycisków umożliwiających obsługę systemu."),
    ]
    return title, blocks


def _podrecznik_operatora() -> tuple[str, list[Block]]:
    # Z celową niespójnością: duplikat (WYM-003 ≈ WYM-004). Treść operacyjna.
    title = "Podręcznik operatora systemu"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Podręcznik dla operatora systemu. Opisuje obsługę codziennych operacji oraz ekranów monitoringu."),
        ("h1", "Procedury operacyjne"),
        ("p", "WYM-001: Operator może uruchamiać codzienne raporty z ekranu operacji."),
        ("p", "WYM-002: Operator może potwierdzać alarmy z listy zdarzeń."),
        (
            "p",
            "WYM-003: System musi generować raport dzienny podsumowujący wszystkie operacje systemu przeprowadzone po zakończeniu każdego dnia roboczego.",
        ),
        (
            "p",
            "WYM-004: System musi generować raport dzienny podsumowujący wszystkie operacje systemu przeprowadzone po zakończeniu każdego dnia roboczego.",
        ),
        ("h1", "Obsługa alarmów"),
        ("p", "Kliknij przycisk Potwierdź na karcie alarmu, aby uznać alarm za obsłużony."),
        ("h1", "Glosariusz"),
        ("p", "Operator: Użytkownik wykonujący codzienne operacje systemu."),
        ("p", "Alarm: Sygnał o zdarzeniu wymagającym uwagi operatora."),
    ]
    return title, blocks


def _instrukcja_instalacji() -> tuple[str, list[Block]]:
    title = "Instrukcja instalacji systemu"
    blocks: list[Block] = [
        ("h1", "Wprowadzenie"),
        ("p", "Instrukcja techniczna instalacji oraz konfiguracji systemu."),
        ("h1", "Warunki systemowe"),
        ("p", "Instalacja wymaga serwera z systemem operacyjnym zgodnym z architekturą."),
        ("p", "Wdrożenie wymaga bazy danych oraz skonfigurowanej infrastruktury sieciowej."),
        ("h1", "Instalacja"),
        ("p", "Konfiguracja rozpoczyna się od wdrożenia obrazów kontenerów na serwerze docelowym."),
        ("p", "Po instalacji należy zweryfikować połączenie z bazą danych."),
        ("h1", "Glosariusz"),
        ("p", "Wdrożenie: Proces instalacji systemu w środowisku docelowym."),
        ("p", "Infrastruktura: Zbiór zasobów sprzętowych i sieciowych systemu."),
    ]
    return title, blocks


# ── Orkiestracja ────────────────────────────────────────────────────────────

SAMPLES: list[tuple[str, str, str, tuple[str, list[Block]]]] = [
    # (podkatalog, nazwa_pliku, format, (title, blocks))
    ("srs", "srs_system_logowania.pdf", "pdf", _srs_system_logowania()),
    ("srs", "srs_platnosci.docx", "docx", _srs_platnosci()),
    ("srs", "srs_raporty.md", "md", _srs_raporty()),
    ("brd", "brd_system_logowania.pdf", "pdf", _brd_system_logowania()),
    ("brd", "brd_platnosci.docx", "docx", _brd_platnosci()),
    ("frd", "frd_modul_uzytkownikow.pdf", "pdf", _frd_modul_uzytkownikow_pdf()),
    ("frd", "frd_profil_uzytkownika.html", "html", _frd_modul_uzytkownikow_html()),
    ("manual", "podrecznik_administratora.docx", "docx", _podrecznik_administratora()),
    ("manual", "podrecznik_operatora.md", "md", _podrecznik_operatora()),
    ("instruction", "instrukcja_instalacji.pdf", "pdf", _instrukcja_instalacji()),
]


def generate() -> None:
    """Wygeneruj wszystkie 10 próbek do golden_data/docs/<typ>/<plik>."""
    for subdir, filename, fmt, (title, blocks) in SAMPLES:
        target_dir = OUT / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        if fmt == "pdf":
            _pdf(path, title, blocks)
        elif fmt == "docx":
            _docx(path, title, blocks)
        elif fmt == "md":
            _markdown(path, title, blocks)
        elif fmt == "html":
            _html(path, title, blocks)
        else:
            raise ValueError(f"Nieobsługiwany format: {fmt}")
        print(f"  wygenerowano: {path.relative_to(OUT)}")


if __name__ == "__main__":
    generate()
    print(f"Gotowe — {len(SAMPLES)} próbek w {OUT}")
