# **4.1.** Moduł generowania przypadków testowych z kodu źródłowego

### **4.1.1.** Opis ogólny modułu

Moduł generowania przypadków testowych na bazie kodów źródłowych jest
odpowiedzialny za automatyczną analizę kodu aplikacji i generowanie na
jej podstawie kompleksowych zestawów testów. Moduł
wykorzystuje zaawansowane techniki analizy statycznej kodu oraz
algorytmy sztucznej inteligencji.

**Technologie:** Realizacja modułu może wykorzystać technologie
takie jak AST parsers i linters, SonarQube, Checkstyle i PMD.

### **4.1.2.** Funkcjonalność automatyzacji analizy kodu źródłowego

#### **4.1.2.1.** Opis funkcjonalności

Silnik TestSpark wykorzystuje metody Natural Language Processing
(NLP) w celu automatycznej analizy kodu źródłowego testowanego
oprogramowania, aby na jego podstawie automatycznie wygenerować
przypadki testowe dopasowane do specyfiki danej aplikacji. Jest to pełna
automatyczna analiza kodu.

**REQ-MOD-CODE-001:** System musi automatycznie rozpoznawać język
programowania i framework aplikacji.

**REQ-MOD-CODE-002:** System musi wspierać co najmniej następujące
języki: Java, Python, JavaScript, .NET, PHP, SQL, C#, C++, HTML,
Kotlin, Swift.

#### **4.1.2.2.** Szczegółowy przepływ działania

Do uwzględnienia w dokumentacji, może się okazać że implementacja
realizująca będzie jednak przekazywać via API do jakiegoś LLM z prośbą o
generację takich przypadków

Proces analizy kodu składa się z następujących etapów:

##### Etap A: Wczytanie i parsowanie kodu źródłowego

**Detekcja technologii i struktury projektu:**

System TestGEN automatycznie rozpoznaje:

- **Język programowania** - Java, Python, JavaScript, .NET, PHP, SQL,
  C#, C++, HTML, Kotlin, Swift itd.

- **Framework** - np. Django, React, Angular, Spring Boot, .NET,
  Flutter, Android SDK

- **Strukturę katalogów** - pliki źródłowe, testowe, konfiguracyjne,
  manifesty

Wykorzystuje analizę sygnatur plików (requirements.txt, package.json,
pom.xml, build.gradle, csproj, setup.py, itp.).

GUI TestGEN powinno zawierać jakąś formę np. lista check-box z opcją
wyboru, do jakiego z tych konkretnych frameworków generować ma się kod i
przykładowe dane testowe. Przekazać ją do LLM by ten na tej podstawie
wygeneruje coś takiego

##### Etap B: Parsowanie kodu i budowa modelu semantycznego

Kod jest analizowany przy użyciu parserów AST (Abstract Syntax Tree) i
narzędzi statycznej analizy (np. tree-sitter, astroid, javalang,
Esprima, Roslyn). Na tej podstawie system tworzy model semantyczny
aplikacji, zawierający:

- Klasy, metody, funkcje, zmienne, parametry, typy zwracane, zależności

- Strukturę kontrolną (if/else, pętle, wyjątki)

- Punkty wejścia aplikacji (routy, endpointy, kontrolery, komponenty UI,
  akcje użytkownika)

Dzięki temu TestGEN „rozumie\" logikę aplikacji, jej funkcje i przepływy
danych.

##### Etap C: Analiza logiki biznesowej i przepływów użytkownika

**1. Identyfikacja funkcji aplikacji**

System wykrywa:

- Publiczne metody API, endpointy REST/GraphQL, kontrolery MVC

- Komponenty interfejsu użytkownika (np. Button, Input, Form, View,
  Page)

- Funkcje reagujące na zdarzenia (onClick, handleSubmit, onChange)

- Klasy biznesowe (np. OrderService, PaymentProcessor, UserManager)

Każdy z tych elementów staje się **kandydatem na przypadek testowy**.

**2. Analiza przepływu danych (data flow)**

System analizuje:

- Zależności między metodami

- Wartości wejściowe/wyjściowe

- Miejsca walidacji danych i obsługi błędów

- Komunikację między modułami (np. API → DB, UI → backend)

Na tej podstawie można tworzyć testy integracyjne i systemowe (np.
*\"Sprawdź, czy dodanie produktu do koszyka zapisuje się w bazie i
aktualizuje UI\"*).

**3. Rekonstrukcja ścieżek użytkownika**

Jeśli kod dotyczy aplikacji interaktywnej (np. webowej lub mobilnej),
TestGEN rekonstruuje potencjalne **user flows** - np.:

LoginPage

→

Dashboard

→

Settings

→

Logout

TestGEN może wywołać prompt do komercyjnego modelu i zasugerować aby analizując
dokumentację, UML etc starał się zrekonstruować ścieżki użytkownika.
Mogą one potem być nie używane przez inne moduły.

#### **4.1.2.3.** Przebiegi funkcjonalności

**Przebieg pozytywny:**

System po przeanalizowaniu dostępnych fragmentów systemu, takich jak kod
źródłowy (minimum), dokumentacja, diagramy UML będzie w stanie
przygotować opisowe przypadki testowe dla „wyłapanych\" elementów
systemu (funkcjonalności, funkcje, procedury), a tam gdzie to możliwe
kod do ich uruchamiania w popularnych frameworkach.

**Przebieg negatywny:**

Wczytany kod, dokumentacja i inne elementy będą niepoprawne (np. nie
będzie kodem w języku programowania) lub niepełne, w związku z czym
system nie będzie w stanie go przeanalizować.

### **4.1.3.** Funkcjonalność generowania przypadków testowych i kodu testowego (dla back-endu, API)

Do uwzględnienia w dokumentacji, może się okazać że implementacja
realizująca będzie jednak przekazywać via API do jakiegoś LLM z prośbą o
generację takich przypadków

#### **4.1.3.1.** Opis funkcjonalności

Na podstawie wczytanych danych w postaci kodu źródłowego system będzie w
stanie generować przypadki testowe oraz kod testowy tam gdzie to możliwe
dla popularnych frameworków, takich jak JUnit, NUnit czy pytest.

**REQ-MOD-CODE-003:** System musi generować przypadki testowe w formacie
opisowym (readable test cases) zawierające: ID, cel, warunki wstępne,
kroki, dane wejściowe, oczekiwane rezultaty, typ testu.

**REQ-MOD-CODE-004:** System musi generować kod testowy dla
frameworków: JUnit, NUnit, pytest, Mocha, Playwright, Selenium,
Appium.

#### **4.1.3.2.** Klasyfikacja testów

Z zebranych informacji TestGEN tworzy pełną specyfikację testową,
obejmującą:

- **Testy jednostkowe** - dla każdej funkcji/metody o czystych
  zależnościach

- **Testy integracyjne** - dla metod wywołujących inne moduły

- **Testy systemowe** - dla endpointów, komponentów UI,
  przepływów użytkownika

- **Testy regresyjne** - dla istniejących przypadków w
  repozytorium (jeśli system znajdzie pliki test\_\*)

- **Testy bezpieczeństwa / walidacji** - automatycznie dla
  miejsc walidacji danych, logowania, ról użytkowników

GUI TestGEN powinno zawierać jakąś formę np. lista check-box z opcją
wyboru, które typy przypadków chcemy wygenerować i dodatkowo opcję
wyboru czy chcemy generować kod do uruchamiania w w/w frameworkach .
Przekazać ją do LLM by ten na tej podstawie wygeneruje coś takiego

#### **4.1.3.3.** Generacja przypadków w formie opisowej

Każdy przypadek testowy zawiera:

- ID testu (np. TC_API_001)

- Nazwę i opis funkcji

- Warunki wstępne

- Dane wejściowe

- Kroki testowe

- Oczekiwany rezultat

- Typ testu i priorytet

**Przykład:**

**TC_UI_003: Logowanie z niepoprawnym hasłem**\
**Cel:** Sprawdzić komunikat o błędzie przy logowaniu z błędnymi
danymi.\
**Warunki:** Użytkownik na stronie /login\
**Kroki:**\
1. Wpisz email test@example.com\
2. Wpisz hasło \"12345\"\
3. Kliknij Zaloguj\
**Oczekiwany rezultat:** pojawia się komunikat \"Nieprawidłowy login lub
hasło\"\
**Typ:** Negatywny, Funkcjonalny

TestGEN wysyłając do LLM prośbę o wygenerowanie przypadku uwzględnia powyższe
parametry i zawiera je jako wymagane w wygenerowanym przypadku 

#### **4.1.3.4.** Eksport przypadków

Przypadki mogą być eksportowane do:

- CSV, Excel, PDF

- TestRail, Jira XRay, Zephyr

- YAML/JSON dla generowania testów automatycznych

TestGEN po wygenerowaniu przypadków system dawał możliwość ich eksportu
do tych formatów

#### **4.1.3.5.** Kompatybilność z CI/CD

**REQ-MOD-CODE-005:** System musi umożliwiać wybór frameworka CI/CD i
generować kod zgodny z: Jenkins, Azure DevOps, GitHub Actions, GitLab
CI.

Wymaga implementacji funkcji wyboru dla jakiego CI/CD ma być generowany
kod, aby było łatwo go wykorzystać wraz z popularnymi systemami CI/CD
oraz narzędziami systemami CI/CD (Jenkins, Azure DevOps, GitHub ) oraz
narzędziami testerskimi, takimi jak JUnit, Selenium, NUnit czy
TestComplete.

TestGEN daje możliwość wyboru aby przypadki testowe / kod do
uruchamiania był zgodny z tymi frameworkami i na tej podstawie buduje
odpowiedni prompt do LLM

#### **4.1.3.6.** Generacja kodu testowego

Na podstawie wygenerowanych przypadków i kodu źródłowego TestGEN
generuje **test suites** w popularnych frameworkach:

  ----------------------------------------------------------------------
  |**Typ           | **Framework testowy**  |           **Przykładowy  |
  |aplikacji**     |                        |           język**        |
  ----------------------------------------------------------------------
  |Web             | Selenium, Playwright,  |          Python / JS / TS|
  |                | Cypress                |                          |
  ----------------------------------------------------------------------
  |API / backend   |  PyTest, JUnit, Mocha  |       Python / Java / JS |
  ----------------------------------------------------------------------
  |Mobile          | Appium, Espresso,      |          Java / Kotlin / |
  |                | XCUITest               |          Swift           |
  ----------------------------------------------------------------------
  |Desktop / GUI   | SikuliX, PyAutoGUI,    |          Python / Java   |
  |                | WinAppDriver           |                          |
  ----------------------------------------------------------------------
  |Low-code tests  | Robot Framework        |          dowolny         |
  ----------------------------------------------------------------------

TestGEN daje możliwość wyboru frameworka na GUI i na tej podstawie
buduje odpowiedni prompt do LLM

##### Tworzenie szkieletów testowych

Każdy przypadek opisowy jest przekształcany w kod testu:

- Automatycznie wypełniane są dane wejściowe i oczekiwane wyniki

- Dodawane są asercje

- Wstawiane są selektory / endpointy z kodu źródłowego

##### Generacja Page Objectów (dla UI)

Dla aplikacji webowych/mobilnych system buduje **Page Object Model
(POM)** - pliki zdefiniowane dla każdego widoku.

Jeśli TestGEN wygeneruje POM podczas generowania przypadków dla wersji
mobilnej powinien go uwzględnić w prompcie i wysyłce do LLM

**Przykład (Python + Selenium):**

class LoginPage: def \_\_init\_\_(self, driver): self.email =
driver.find_element(By.ID, \"email\") self.password =
driver.find_element(By.ID, \"password\") self.submit =
driver.find_element(By.ID, \"login-btn\") def login(self, email,
password): self.email.send_keys(email) self.password.send_keys(password)
self.submit.click()

##### Generacja testu z użyciem POM

def test_login_invalid_password(driver): page = LoginPage(driver)
page.login(\"test@example.com\", \"12345\") assert \"Nieprawidłowy
login\" in driver.page_source

##### Analiza pokrycia kodu

Po wygenerowaniu testów TestGEN:

- Analizuje, które fragmenty kodu są pokryte testami (coverage mapping)

- Generuje raport (np. w formacie HTML lub JSON)

- Proponuje dodatkowe testy dla niepokrytych ścieżek logicznych

#### **4.1.3.7.** Artefakty końcowe

Po przetworzeniu kodu źródłowego TestGEN generuje:

- **Kompletny zestaw opisowych przypadków testowych** - funkcjonalnych,
  integracyjnych, regresyjnych, bezpieczeństwa i UI

- **Kod automatycznych testów** - w wybranym frameworku (np. PyTest,
  JUnit, Playwright, Appium)

- **Struktura projektu testowego** - gotowa do uruchomienia w CI/CD
  (Jenkins, GitHub Actions, GitLab CI)

- **Raporty pokrycia i analizy ryzyka** - co zostało pokryte testami, a
  które fragmenty kodu wymagają dopisania scenariuszy

#### Przykładowy przepływ techniczny

#### Poniższy iagram musi zostać uwzględniony w dokumentacji

**Przepływ przetwarzania w silniku TestSpark:**

\[Źródła kodu\]

↓

\[Analiza AST + Model semantyczny\]

↓

\[Identyfikacja funkcji i ścieżek użytkownika\]

↓

\[Generacja przypadków testowych (opisowych)\]

↓

\[Generacja kodu testów w wybranym frameworku\]

↓

\[Analiza pokrycia i raport końcowy\]

### **4.1.4.** Funkcjonalność testów regresji kodu i GUI

#### **4.1.4.1.** Opis funkcjonalności

TestGEN umożliwia automatyczne wykrywanie zmian wskazując potencjalne
błędy regresji analizując aplikację identyfikując ewentualne
niespójności między wersjami kodu lub ekranu użytkownika (porównywanie
obrazów).

**REQ-MOD-CODE-006:** System musi porównywać dwie wersje kodu źródłowego
i identyfikować zmiany na poziomie semantycznym.

**REQ-MOD-CODE-007:** System musi generować testy regresyjne dla
zidentyfikowanych zmian.

**Testy regresji mają sprawdzić, czy wprowadzone zmiany w nowej wersji
kodu nie spowodowały błędów w funkcjonalnościach, które wcześniej
działały poprawnie.**

#### **4.1.4.2.** Testy regresji kodu - szczegółowy przepływ

System TestGEN ma za zadanie:

- Porównać dwie wersje kodu źródłowego

- Zidentyfikować zmienione, dodane lub usunięte elementy

- Automatycznie dobrać lub wygenerować odpowiednie testy regresyjne

- Uruchomić je (lub przygotować kod do uruchomienia)

- Porównać wyniki i wygenerować raport zmian w zachowaniu aplikacji

##### ETAP 1: Analiza różnic między wersjami kodu

**1. Pobranie obu wersji projektu**

Wersja nice to have.

System pobiera:

- **Poprzednią wersję** (np. z repozytorium Git, tag v1.0)

- **Aktualną wersję** (np. z gałęzi develop lub main)

Wersja must:

System prosi o przekazanie plików:

- **Poprzednią wersję**

- **Aktualną wersję**

**2. Analiza różnic (diff analysis)**

TestGEN wykonuje **porównanie semantyczne** kodu (nie tylko tekstowe):

- Wykrywa zmiany w klasach, metodach, funkcjach, komponentach UI,
  endpointach API, plikach konfiguracyjnych, bazach danych

- Oznacza każdy element jako:

  - 🟢 *nowy* (dodany w nowej wersji)

  - 🔵 *zmodyfikowany* (zmieniona logika, parametry, typ zwracany,
    walidacja)

  - 🔴 *usunięty* (brak w nowej wersji)

**3. Mapowanie zależności**

System analizuje wpływ zmian na resztę kodu:

- Które funkcje/metody zależą od zmienionych modułów

- Które testy jednostkowe/integracyjne były powiązane z tymi fragmentami

- Które pliki interfejsu użytkownika (np. komponenty React, kontrolery)
  odwołują się do zmienionego kodu

Na tej podstawie powstaje **mapa wpływu (impact map)** - pokazująca,
które obszary należy przetestować ponownie.

Analiza może odbyć się poprzez przekazanie zmiany do LLM i poproszenie o
wygenerowanie takiej mapy

##### ETAP 2: Wybór i generacja testów regresyjnych

**1. Odtworzenie wcześniejszych przypadków testowych**

TestGEN odnajduje przypadki testowe wygenerowane wcześniej dla wersji
v1.0:

- Testy funkcjonalne

- Testy integracyjne

- Testy UI

- Testy API

Wersja nice to have system sam znajduje przypadki

Wersja must za pomocą GUI są przekazywane do TestGEN przypadki

**2. Automatyczne klasyfikowanie testów**

System dzieli istniejące testy na kategorie:

- ✅ niezmienione obszary - mogą być ponownie uruchomione bez
  modyfikacji

- ⚙️ dotknięte zmianami - wymagają aktualizacji danych testowych lub
  selektorów

- 🆕 nowe funkcjonalności - brak testów, trzeba je wygenerować

- ❌ usunięte funkcje - testy można oznaczyć jako nieaktualne

**3. Generacja nowych testów regresyjnych**

Dla wszystkich fragmentów oznaczonych jako *zmodyfikowane* lub
*nowe*:

- TestGEN analizuje zmienioną logikę, parametry, walidacje, UI

- Generuje zaktualizowane przypadki testowe (opisowe)

- Tworzy kod testów automatycznych z użyciem istniejących frameworków
  (PyTest, JUnit, Selenium, Playwright, itp.)

**Przykład:**

Zmieniono endpoint /api/orders - dodano parametr discountCode\
→ TestGEN wygeneruje nowe przypadki:\
- TC_API_145: \"Utworzenie zamówienia z kodem rabatowym\"\
- TC_API_146: \"Utworzenie zamówienia z nieprawidłowym kodem rabatowym\"

##### ETAP 3: Uruchomienie testów regresyjnych

1.  TestGEN uruchamia istniejące testy z poprzedniej wersji przeciwko
    nowej (o ile framework i środowisko na to pozwalają).

2.  Dla testów niedziałających z powodu zmian selektorów, API lub
    parametrów - TestGEN automatycznie proponuje poprawki (np.
    aktualizację selektorów, parametrów wejściowych).

3.  W przypadku zmian w UI - może uruchomić tryb **image-based
    comparison** (porównanie wyglądu ekranów v1.0 i v1.1).

TestGEN powinien w wyniku dać pliki gotowe do uruchomienia w jakimś
frameworku a nie samoczynnie uruchamiać testy

##### ETAP 4: Porównanie wyników testów

System porównuje wyniki wykonania testów w obu wersjach:

- Które testy przeszły wcześniej i teraz się nie powiodły

- Które nowe testy ujawniły błędy

- Jakie elementy aplikacji zmieniły się wizualnie lub logicznie

Wyniki są prezentowane w **raporcie regresji**:

  ------------------------------------------------------------------------------
  **Test ID**   **Status   **Status   **Zmiana**   **Uwagi**
                v1.0**     v1.1**                  
  ------------- ---------- ---------- ------------ -----------------------------
  TC_UI_101     PASS       FAIL       🔴           Błąd walidacji emaila po
                                                   zmianie regexu

  TC_API_145    NEW        PASS       🟢           Nowy endpoint działa
                                                   poprawnie

  TC_UI_080     PASS       PASS       🟢           Bez zmian

  TC_FUNC_203   PASS       SKIP       ⚪           Funkcja została usunięta
  ------------------------------------------------------------------------------

#### **4.1.4.3.** Testy regresji GUI

Testy regresji GUI mają wykryć, czy zmiany w kodzie lub komponentach
frontendu (np. HTML, CSS, React, Vue, Angular, Flutter) **wpłynęły
negatywnie na zachowanie, wygląd lub interakcyjność interfejsu
użytkownika**.

TestGEN automatycznie porównuje poprzednią i nową wersję interfejsu,
aby:

- Zidentyfikować zmienione elementy (przyciski, formularze, widoki,
  komunikaty)

- Zaktualizować istniejące testy lub wygenerować nowe

- Przygotować kod automatyzujący: skrypty startowe (np. Selenium /
  Playwright / Appium / Robot Framework / SikuliX / AutoHotkey /
  PyAutoGUI) lub krótkie makra - zależnie od docelowego środowiska

##### ETAP 1: Wczytanie i analiza zmian w GUI

**1. Źródła danych wejściowych**

System przyjmuje jednocześnie:

- Kod źródłowy interfejsu (HTML, JSX, TSX, CSS, Vue, XML itp.)

- Dane o strukturze komponentów (np. hierarchia React, routing w
  Angularze)

- Poprzednią wersję GUI (z repozytorium)

- Aktualną wersję GUI (po zmianach)

- Ewentualnie zrzuty ekranów lub makiety

**2. Porównanie struktur interfejsu**

TestGEN analizuje różnice w strukturze DOM / drzewie komponentów:

- Dodane, usunięte lub zmienione elementy (np. nowe pola formularzy,
  przyciski, modale)

- Zmienione atrybuty (np. id, class, placeholder, aria-label)

- Zmodyfikowane style (np. kolor, rozmiar, widoczność)

- Nowe logiki interakcji (np. eventy onClick, onSubmit, onChange)

Wynik: **mapa różnic GUI (GUI Diff Map)**, opisująca precyzyjnie, które
elementy interfejsu uległy zmianie.

TestGEN powinien wybrać 1-2 elementy i zaszyć w promptcie co ma losowo
porównywać

##### ETAP 2: Identyfikacja wpływu zmian na testy

Jeżeli istnieją testy GUI z poprzedniej wersji (np. testy Selenium lub
Playwrighta) odnoszą się do zmienionych elementów TestGEN je analizuje i
oznacza

Dla każdego testu automatycznie określa status:

- ✅ niezmieniony - test może zostać ponownie uruchomiony

- ⚙️ do aktualizacji - zmienił się selektor, etykieta lub zachowanie
  elementu

- 🆕 do wygenerowania nowy test - dodano nowe funkcjonalności lub widoki

- ❌ do usunięcia - element GUI został wycofany

##### ETAP 3: Generacja przypadków testowych GUI

Na podstawie wykrytych zmian TestGEN tworzy zestaw **nowych lub
zaktualizowanych przypadków testowych regresji GUI**.

Każdy przypadek zawiera:

- **Opis testu** (opisowy przypadek testowy) - w języku naturalnym

- **Kroki testowe** (automatycznie wygenerowane z analizy kodu GUI)

- **Oczekiwany wynik**

- **Powiązanie z elementami GUI** (np. data-testid, aria-label, id)

Prompt przy pomocy którego TestGEN będzi generowane takie przypadki musi
uwzględniać ten schemat

**Przykład:**

**TC_GUI_205:** Użytkownik może dodać produkt do koszyka po dodaniu
nowego przycisku \"Kup teraz\"\
\
**Kroki testowe:**\
1. Otwórz widok \"Lista produktów\"\
2. Kliknij przycisk \"Kup teraz\" przy dowolnym produkcie\
3. Sprawdź, czy produkt został dodany do koszyka\
4. Zweryfikuj, że wyświetla się komunikat \"Produkt dodano do koszyka\"\
\
**Oczekiwany wynik:** komunikat jest widoczny, a stan koszyka się
zmienia

##### ETAP 4: Generacja kodu testów automatycznych GUI

Na podstawie opisowych przypadków TestGEN generuje kod testów
automatycznych w wybranym frameworku.

TestGEN na podstawie przygotowanych przypadków kieruje prompt do LLM w
wyniku, którym będzie kod który można wrzucić do frameworku

**Przykład (Playwright, TypeScript):**

test(\'Użytkownik może dodać produkt do koszyka\', async ({ page }) =\>
{ await page.goto(\'/products\'); await page.click(\'button:text(\"Kup
teraz\")\'); await
expect(page.locator(\'.cart-notification\')).toHaveText(\'Produkt dodano
do koszyka\'); });

**Przykład (Selenium, Python):**

def test_add_to_cart(driver):
driver.get(\"https://app.example.com/products\")
driver.find_element(By.XPATH, \"//button\[contains(text(), \'Kup
teraz\')\]\").click() message = driver.find_element(By.CLASS_NAME,
\"cart-notification\").text assert \"Produkt dodano do koszyka\" in
message

##### ETAP 5: Raport regresji GUI

System generuje **raport testów regresji GUI**, który zawiera:

- Zestawienie wszystkich przypadków (nowych, zmienionych, usuniętych)

- Miniatury ekranów \"przed\" i \"po\"

- Opis różnic wizualnych i logicznych

- Kod wygenerowanych testów automatycznych

- Rekomendacje napraw (np. \"zaktualizować selektor przycisku X\")

#### **4.1.4.4.** Przebiegi funkcjonalności

**Przebieg pozytywny:**

System będzie w stanie wyłapać różnice w kodzie i przygotować opisowe
przypadków testowych do wykonania testów regresji jak i ewentualny kod
do przetestowania danego testu.

**Przebieg negatywny:**

Np. w przypadku wczytania takiego samego kodu system nie będzie w stanie
przygotować testów regresji wskazując, że wczytano ten sam kod.

### **4.1.5.** Wykorzystane mechanizmy i technologie

#### **4.1.5.1.** Architektura modułu

Architektura systemu definiująca:

- **Strukturę danych** - ujednolicone reprezentacje kodu w różnych
  językach

- **Logikę przetwarzania kodu źródłowego** - analiza kodu w różnych
  językach programowania (np. Java, Python, C#)

Zastosowane zostaną narzędzia do statycznej analizy kodu (np. AST
parsers i linters), umożliwiające identyfikację funkcji, klas
oraz zależności. Nawet jeżeli poszczególne moduły w
swojej implementacja nie będzie z nich korzystać, a kierować zapytanai
do LLM

**Przykładowe narzędzia AST:**

- Python: ast, astroid

- JavaScript: Esprima, Acorn, Babel Parser

- Java: JavaParser, Eclipse JDT

- C#: Roslyn

- Multi-language: tree-sitter

#### **4.1.5.2.** Technologia AI do automatycznej generacji przypadków testowych

Część silnika TestSpark wykorzystująca modele uczenia maszynowego i
transformery (np. GPT, BERT) do:

- Przewidywania scenariuszy testowych

- Klasyfikacji scenariuszy

- Przypisania odpowiednich danych wejściowych i oczekiwanych rezultatów

- Wydzielania logiki biznesowej z kodu źródłowego, aby testy
  odzwierciedlały rzeczywiste działanie systemu

Nawet jeżeli później nie będzie to wykorzystywane

#### **4.1.5.3.** Podmoduł generujący kod testowy

Część silnika TestSpark generująca przypadki testowe i kod testowy
gotowy do uruchamiania we frameworkach testowych, np. JUnit, pytest czy
NUnit.

Ta część silnika powinna automatycznie tworzyć pełne klasy testowe,
uwzględniając:

- **Adnotacje** - odpowiednie dla danego frameworka (@Test,
  \@BeforeEach, \@pytest.fixture, itp.)

- **Metody testujące** - z logiką testową i asercjami

- **Dane testowe** - fixtures, parametryzacja, test data builders

Całość zostanie przygotowana jako skalowalna usługa backendowa z
możliwością integracji z komponentami TestGEN.

#### **4.1.5.4.** Diagram działania modułu

Poniższy schemat graficzny przedstawia proces (diagram blokowy lub
procesowy TestGEN) pokazujący jak przepływa analiza od kodu po testy
automatyczne:

Do uwzględnienia w dokumentacji

![Wygenerowany obraz](media/image1.png){width="3.654166666666667in"
height="5.48125in"}

*Rysunek 4.1: Schemat przepływu przetwarzania w module analizy kodu
źródłowego*
