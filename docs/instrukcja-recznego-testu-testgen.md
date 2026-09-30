# TestGEN — instrukcja ręcznego testu funkcjonalności (GUI + golden data)

> Rozbudowa ściągawki demo (`backend/tests/golden_data/DEMO-CHEATSHEET.md`)
> na pełny zestaw ręcznych testów platformy: **funkcjonalność → jak
> wywołać w GUI → które dane golden → oczekiwany rezultat**.
> Wszystkie ścieżki golden są względem `backend/tests/golden_data/`
> (starsze fixtury: `backend/tests/fixtures/golden/`).
> Szczegóły ekranów: podręcznik `docs/final/user-guide/` (rozdz. 1-17).

---

## 0. Przygotowanie

- **Konto demo**: `anna.demo@testgen.nexio.pl` / `Qa-Demo-2026!Podrecznik`,
  projekt „Sklep internetowy (demo)". Osobne konto admina do sekcji L.
- **Limity planu** (10 analiz/basic): reset —
  `docker compose exec backend python scripts/reset_demo.py reset-quota --plan basic --yes`
  (status: `…reset_demo.py status`; pełny reset z historią: `reset`).
- **Imaging/OCR jest image-gated** (GUI, UML wizualne, OCR PDF): wymaga
  `pip install -e ".[imaging]"` + Tesseract w kontenerze. Sprawdź:
  `docker compose exec backend python -c "import cv2, pytesseract"`.
  Bez stacku pomiń scenariusze oznaczone ⚠️.
- **Routing modułu ustala ekran wgrywania, nie zawartość pliku**
  (ten sam PNG = UML lub GUI, PDF = dokument lub UML). Cztery ekrany:

| Ekran w UI | Endpoint | Co przyjmuje |
|---|---|---|
| **Kod źródłowy** | `/projects/{id}/upload` | `.py .java .js .ts .cs .php .kt …` + `.zip/.tar.gz` |
| **Dokumenty** | `/projects/{id}/upload-documents` | `.pdf .docx .md .html .txt` |
| **Diagramy UML** | `/projects/{id}/uml/upload` | `.puml .xmi .xml .svg .pdf .png .jpg` |
| **Zrzuty GUI** | `/projects/{id}/gui/upload` | `.png .jpg .jpeg .bmp .tif .webp` |
| **GUI z HTML/DOM** | `/projects/{id}/gui/dom/upload` | `.html .htm` (+ `a11y.json`) |

Nie przejdzie nigdzie: `.sql`, `.csv`, `.yaml`, `.json` (poza `a11y.json`), `.xlsx`.

---

## A. Konto i dostęp (rozdz. 2, 14)

| Funkcjonalność | Jak w GUI | Oczekiwany rezultat |
|---|---|---|
| Rejestracja | „Zarejestruj się" (formularz + wybór firmy/tenanta) | konto + tenant; Argon2id po stronie BE |
| Logowanie + wybór firmy | „Zaloguj się" → selektor tenanta | lista projektów; HttpOnly cookie |
| MFA (TOTP) ⚙ | Ustawienia → „Weryfikacja dwuetapowa" → skan QR | kod 6-cyfrowy wymagany przy logowaniu |
| Role RBAC | Ustawienia → „Użytkownicy firmy" (Owner); admin: panel admina | User widzi projekt; Owner zarządza; Admin — całą platformę |
| Wylogowanie / wygasanie | menu profilu | sesja zakończona |

⚙ MFA wymaga aplikacji TOTP (np. Microsoft/Google Authenticator).

## B. Projekty i materiały (rozdz. 3-4)

| Funkcjonalność | Jak w GUI | Golden | Oczekiwany rezultat |
|---|---|---|---|
| CRUD projektu | „Projekty" → „Nowy projekt"; edycja/archiwizacja na karcie | — | projekt na liście (filtry, sortowanie) |
| Upload kodu | karta projektu → „Kod źródłowy" | patrz §C | licznik plików; ZIP rozpakowany |
| Członkowie i role | karta projektu → „Członkowie" | — | zaproszenia/role w projekcie |
| Retencja/czyszczenie kodu | Ustawienia projektu → retencja | — | pliki klienta usuwane po polityce |

## C. Analiza kodu źródłowego (rozdz. 4)

**GUI**: karta projektu → „Uruchom analizę" → **Parametry analizy**
(moduły: Analiza kodu / Generowanie testów / Analiza UML / Analiza GUI;
**Framework testowy**: „— Automatyczny —" lub jawny wybór —
pytest, unittest, JUnit, TestNG, NUnit, MSTest, Mocha/Jest, Cypress,
Selenium, Playwright, Appium) → „Analizuj". Postęp: pasek + krok
(preparsowanie → AST → analiza → testy). Wyniki: struktury logiczne,
punkty wejścia, zależności, przepływ danych.

| Scenariusz | Golden (wgraj na ekranie Kod) | Oczekiwany rezultat |
|---|---|---|
| Analiza Python (AST → przypadki) | `code_samples/python/auth_handler.py` | przypadki testowe unit dla klas/funkcji |
| Analiza Java / C# | `code_samples/java/…`, `code_samples/csharp/…` | j.w. dla języka |
| PHP legacy (Laravel/traits) | `fixtures/golden/php/LaravelController.php` | kontroler sparsowany (traits/enums) |
| **Auto-detekcja frameworka** (1-57) | `code_samples/python/calculator.py` **+ własny `requirements.txt` z `unittest`**; `java/Calculator.java` + `pom.xml` (testng); `csharp/Calculator.cs` + `.csproj` (MSTest) | Framework przypadków = **unittest / testng / mstest** (nie pytest/JUnit/NUnit) |
| Wybór jawny nadpisuje detekcję | j.w. + Framework = „JUnit" | kod JUnit mimo testng w pom |
| Testy regresji kodu (4.7) | dwie wersje pliku `user_service.py` → porównanie | zestaw testów regresji |

Snippety konfiguracji detekcji (dodać do uploadu):
`requirements.txt`: `unittest` · `pom.xml`: zależność `org.testng:testng` ·
`.csproj`: `<PackageReference Include="MSTest.TestFramework" … />`.

## D. Przypadki testowe (rozdz. 8.1-8.4)

**GUI**: kafel „Przypadki testowe" — tabela Tytuł/Typ/Priorytet/Status,
szukajka, „Grupuj według" (Moduł/Priorytet/Typ); szczegóły: karty
„Metadane" (Typ, Priorytet, Framework, Język, Pewność, Plik źródłowy,
Funkcja) + „Kod testu" + „Historia wykonań"; edytor (Tytuł, Priorytet,
Status, Opis, Kroki z przeciąganiem, Oczekiwany wynik, Historia zmian).
Statusy: Szkic → Gotowy („Zatwierdź") → Zaliczony/Niezaliczony
(„Uruchom test"); Pominięty/Wyłączony. Operacje masowe: zaznacz wiele →
„Zmień status"/„Zmień priorytet"/„Eksportuj"/„Usuń".

Oczekiwane rezultaty: patrz rozdz. 8 podręcznika; brak golden (dane
powstają z analizy — §C).

## E. Generatory kodu testów (rozdz. 8.5; Stories 1-56/1-57)

**GUI**: Projekt → „Scenariusze Gherkin" → link **„Generator kodu
testowego"** (URL `/projects/{id}/codegen/cypress`).
Kroki: ① zaznacz przypadki ② **Framework** (8 opcji) ③ opcje warunkowe
(Cypress → „Bazowy URL"; Appium → „Platforma urządzenia":
Android—UiAutomator2 / iOS—XCUITest) ④ **„Generuj kod {nazwa}"**
⑤ komunikat „Generowanie uruchomione (zadanie: {id})" ⑥ sekcja „Pobierz
wygenerowany kod" → wklej UUID → „Pobierz kod" → **„Pobierz .py / .cy.ts
/ .spec.ts / .java / .cs"**.

| Framework | Plik | Oczekiwany rezultat |
|---|---|---|
| Cypress | `.cy.ts` | `cy.visit`/`cy.get` + asercje |
| SikuliX | `.py` + PNG | wzorce obrazowe wycięte bbox |
| Selenium | `.py` | Selenium WebDriver |
| Playwright | `.spec.ts` | `@playwright/test` |
| Appium | `.py` | AppiumBy + capabilities wg platformy |
| unittest | `.py` | klasa `…(unittest.TestCase)`, `self.assertEqual…`; lokalnie `python -m unittest` = OK |
| TestNG | `.java` | `@Test`/`@BeforeMethod`, `Assert.assertEquals` (Java 11+) |
| MSTest | `.cs` | `[TestClass]`/`[TestMethod]`, `Assert.AreEqual` (.NET 8) |

**Golden — oczekiwane wyjścia do porównania 1:1**
(po wgraniu `code_samples/{python,java,csharp}/Calculator…` i analizie):
- `codegen/unittest/input.json` + `expected_output.txt`
- `codegen/testng/input.json` + `expected_output.txt`
- `codegen/mstest/input.json` + `expected_output.txt`

**Generatory specjalistyczne** (osobne strony, link ze strony Gherkin):
- „Generator kodu testów bazodanowych" `/projects/{id}/codegen/database` —
  pytest warstwy danych z rollbackem (przypadki `test_type=database`);
- „Generator kodu testów PHP" `/projects/{id}/codegen/php` —
  przełącznik PHPUnit/Pest (wgraj `code_samples/php/Calculator.php`).

Walidacja: brak zaznaczenia → „Wybierz co najmniej jeden przypadek
testowy."; API `framework: "foo"` → 422.

## F. Analiza dokumentacji (rozdz. 5)

**GUI**: karta projektu → „Dokumenty" (upload) → analiza → Wymagania /
Niespójności / Glosariusz; porównanie z kodem = Luki funkcjonalne.

| Scenariusz | Golden (ekran Dokumenty) | Oczekiwany rezultat |
|---|---|---|
| BRD + niespójności | `docs/brd/brd_platnosci.docx` | klasyfikacja BRD; **celowe** duplikaty/braki wykryte |
| OCR skanu PDF ⚠️ | `docs/srs/srs_system_logowania.pdf` | tekst wyekstrahowany (Tesseract) |
| Luki funkcjonalne | `gap_analysis/python_auth_service.json`* | wymagania vs kod → brakujące funkcje, % pokrycia |

\* `.json` pomocniczy (dane testów) — na demo użyj własnego dokumentu
odpowiadającego scenariuszowi.

## G. Analiza UML i GUI (rozdz. 6)

**GUI UML**: karta projektu → „Diagramy UML" (upload) → widoki; „Analizuj
user flows" (cross-diagram); z flow → **Gherkin** (BDD).

| Scenariusz | Golden (ekran UML) | Oczekiwany rezultat |
|---|---|---|
| Klasy/dziedziczenie | `uml/class/class_inheritance.puml` | model domenowy |
| Sekwencja alt/loop | `uml/sequence/sequence_alt.puml` | przepływ wywołań |
| XMI | `uml/class/xmi_class_model.xmi` | model jak z PlantUML |
| UML wizualny (SVG) ⚠️ | `uml/visual/class_order.svg` | ekstrakcja wizją/OCR |
| Cross-diagram | `uml/cross_diagram/…` | user flows z wielu diagramów |

**GUI zrzuty**: karta projektu → „Analiza GUI" → upload PNG.
Regresja wizualna/self-healing: para baseline+comparison
(`visual_regression/pair_*.png`, statusy MATCH/MINOR_DIFF/MAJOR_DIFF —
`pair_form_removed_*` → MAJOR_DIFF, `pair_element_added_*` → MINOR_DIFF).
DOM+a11y: ekran „GUI z HTML/DOM", `fixtures/golden/dom/login_form.html`
(+ `a11y.json`) → komponenty + audyt WCAG.
⚠️ detekcja komponentów image-gated; próbki: `gui/forms/login_form.png`,
`gui/dashboards/analytics_dashboard.png`.

## H. Bezpieczeństwo (rozdz. 7)

**GUI**: karta projektu → „Bezpieczeństwo" → uruchom skan (SAST/taint/
zależności SBOM/misconfig) → wyniki z priorytetami → „Rekomendacje"
(latki/skeleton).

| Scenariusz | Golden (ekran Kod) | Oczekiwany rezultat |
|---|---|---|
| SQLi CWE-89 | `security/vulnerable_code/sqli/sqli_python.py` | podatność wykryta |
| Auto-patch | `security/patches/sqli_login.py` ↔ `…_fixed.py` | automatyczna łatka |

## I. Raporty i eksport (rozdz. 9)

**GUI**: „Raporty" (poziomy: projekt/moduł/przypadek; PDF/HTML/JSON)
oraz „Eksportuj" z listy przypadków → dialog „Eksport do TMS"
(TestRail CSV / Jira Xray XML / JSON; zakres; Mapowanie pól z „Przywróć
domyślne"). Plik `testgen_{projekt}_{data}_{format}`.
Golden: raport pokrycia — `security/…` + wyniki analiz (bez pliku wejścia).

## J. Integracje i API (rozdz. 10-11)

**GUI**: Ustawienia → Integracje (Jira / Azure DevOps — status);
API: klucze/limity wg rozdz. 11 (patrz podręcznik; curl/Python przykłady
11.6). Webhooks/klucze API/CLI = roadmapa (podręcznik 10.7, 11.7, 14.5).

## K. Rozliczenia (plansze: `docs/final/user-guide/billing/`)

**GUI**: menu → „Plany i zakup" / „Subskrypcja" / „Faktury" /
„Zużycie i powiadomienia"; checkout tpay (sandbox).

| Scenariusz | Jak w GUI | Oczekiwany rezultat |
|---|---|---|
| Plany 3-tier | strona planów | Freemium 0 / Basic 30 / Premium 50 PLN/mies. (tylko monthly) |
| Zakup (tpay sandbox) | „Wybierz plan" → checkout → płatność testowa | subskrypcja aktywna; e-mail z tpay (sandbox) |
| Limity 80/90/100% | „Zużycie" po zużyciu limitów | powiadomienia progowe; przy 100% → blokada/402 |
| Freemium gating | jako Freemium: funkcje płatne | kłódki + HTTP 402 |
| Dunning | wygaśnięcie płatności (sandbox) | ponaglenia → degradacja do Freemium |
| Faktury VAT | „Faktury" → dane fakturowe | faktura do pobrania po płatności |

## L. Administracja (rozdz. 13-14; konto Admin)

**GUI**: panel admina — użytkownicy/tenanci/platforma; Ustawienia →
profil, użytkownicy firmy, usuwanie konta; audyt operacji wrażliwych
(log — rozdz. 1.47). Oczekiwane rezultaty wg podręcznika część IV.

---

## Pełna mapa golden (referencja)

**`backend/tests/golden_data/`**
- `code_samples/` — python/java/csharp/js + php (`php/`), selenium/
  playwright/appium (`*.json` — flow E2E, dane testów, nie upload), js
- `codegen/` — **unittest / testng / mstest**: `input.json` +
  `expected_output.txt` (oczekiwane wyjście generatorów 1-57)
- `uml/` — 30 `.puml` + 5 `.xmi` + 5 `.svg` + `cross_diagram/` + GT
- `gui/` — 15 PNG (forms/dashboards/tables/navigation/modals) + GT
- `visual_regression/` — 5 par baseline/comparison + GT
- `docs/` — 10 dokumentów PL (5 spójnych + 5 z niespójnościami) + GT
- `security/` — SAST, taint, CVE, misconfig, patche + manifesty
- `gap_analysis/` — 12 próbek (wymagania vs kod)
- `golden/epic2/` (w `tests/`) — kanoniczny pipeline, 8 expected outputs

**`backend/tests/fixtures/golden/`** — starsze: `php/` (6), `db/`
(`.sql` — **niewgrywalne!**), `dom/` (HTML+a11y).
**`backend/tests/fixtures/uml/`** — ~40 realistycznych diagramów bez GT
(`ecommerce_full`, `banking_system`).

## Checklista zbiorcza

Demo „pięciominutowka" (z CHEATSHEET): UML `class_inheritance.puml` →
GUI `login_form.png` → DOCX `brd_platnosci.docx` → KOD `auth_handler.py`
→ self-healing `pair_form_removed_*`.

Ręczny test pełny: A1-A5 (konto) → B1-B4 (projekty) → C1-C6 (analiza
+ auto-detekcja) → D (przypadki: edycja/statusy/masowe) → E1-E12
(8 frameworków + golden compare unittest/testng/mstest + DB + PHP +
walidacje) → F (dokumenty + OCR ⚠️) → G (UML + GUI + DOM/a11y + regresja)
→ H (SQLi + patch) → I (raport + eksport TMS) → J (integracje) →
K1-K6 (billing sandbox) → L (admin/audyt).
