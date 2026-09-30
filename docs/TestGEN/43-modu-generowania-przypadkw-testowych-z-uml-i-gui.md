# **4.3.** Moduł generowania przypadków testowych z UML i GUI

### **4.3.1.** Opis ogólny modułu

Moduł będzie odpowiedzialny za generowanie przypadków testowych oraz
kodu do ich wykonywania na podstawie diagramów UML oraz ekranów
użytkownika (GUI). W tym celu będzie automatyzował proces
ekstrakcji informacji z wizualnych źródeł i ich przekształcenie w
scenariusze testowe gotowe do wykonania w środowiskach testowych.

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie
wystarczająca

**Technologie:** Moduł może wykorzystywać mechanizmy takie jak parsery
UML (np. PlantUML, GraphML) lub sieci transformer do rozpoznawania
diagramów. Dodatkowo może wykorzystywać technologie rozpoznawania obrazu
(OCR - np. Tesseract, OpenCV) oraz klasyfikatory wizualne - modele CNN
(Convolutional Neural Networks) lub sieci GPT.

### **4.3.2.** Funkcjonalność automatyzacji analizy diagramów UML i generowania opisowych przypadków testowych

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca
Musi natomiast być to opisane w dokumentacji nawet jeśli moduły TestGEN
nie będą z niego korzystać

#### **4.3.2.1.** Opis funkcjonalności

**REQ-MOD-UML-001:** System musi obsługiwać diagramy UML w formatach:
XMI, PlantUML, SVG, PDF, PNG/JPEG.

**REQ-MOD-UML-002:** System musi rozpoznawać następujące typy diagramów
UML: sekwencji, przypadków użycia, klas, aktywności, stanów,
komponentów.

Silnik TestSpark przetwarza diagramy UML (różne ich typy, np.:
sekwencji, przypadków użycia) i na ich podstawie generuje opisowe
przypadki testowe oraz gotowe szablony kodu testów.

#### **4.3.2.2.** Szczegółowy przepływ działania

##### 1. Wejście - co system przyjmuje na wejściu

System akceptuje:

- **Pliki UML w formatach strukturalnych** (XMI, PlantUML/text UML,
  Sparx/Enterprise Architect export)

- **Wektorowe diagramy** (SVG, PDF) zawierające obiekty UML

- **Rasterowe obrazy diagramów** (PNG/JPEG) - wtedy używa OCR +
  rozpoznawania kształtów

Dzięki temu może działać zarówno na \"maszynowych\" reprezentacjach UML
(łatwe do sparsowania), jak i na obrazach wygenerowanych ręcznie.

TestGEN do poszczególnych faz używa API LLM i tak je generuje

##### Faza 1 - wczytanie i normalizacja diagramu

**Kroki działania silnika:**

- **Detekcja formatu** - jeśli to XMI/PlantUML: bezpośrednie parsowanie;
  jeśli SVG/PDF: parsowanie XML/SVG; jeśli raster (PNG/JPEG): pipeline
  obraz → OCR na tekst etykiet → wykrywanie kształtów i krawędzi
  (nodes/connectors) → rekonstrukcja grafu UML.

- **Normalizacja modelu** - wszystkie diagramy konwertowane są do
  jednego wewnętrznego modelu (np. JSON/UML-IR) z unikalnymi ID
  elementów, typami
  (Class/Actor/UseCase/Message/State/Activity/Component), atrybutami i
  metadanymi (np. linia, numer strony).

- **Wykrycie spójnych flow** - gdy dostarczono kilka diagramów, system
  łączy elementy powiązane (np. klasa Order z sekwencją PlaceOrder) i
  buduje wspólny model funkcjonalny.

##### 3. Faza 2 - syntaktyczna i semantyczna analiza UML

**Co system wydobywa z poszczególnych typów diagramów:**

- **Diagram sekwencji:** lifelines, komunikaty
  synchroniczne/asynchroniczne, alternatywne ścieżki (alt), pętle
  (loop), warunki → bezpośrednie kroki scenariuszy E2E i integracyjnych.

- **Use-case / Actor:** aktorzy i cele → scenariusze akceptacyjne (user
  stories → acceptance tests).

- **Diagram klas:** atrybuty, metody, relacje (agregacja, kompozycja,
  dziedziczenie) → testy jednostkowe dla każdej klasy/metody publicznej.

- **Diagram aktywności:** przepływy decyzyjne (decision nodes), akcje
  równoległe (fork/join) → testy ścieżek, boundary conditions.

- **Diagram stanów:** stany, przejścia, eventy, guardy → testy state
  machine (np. lifecycle obiektu Order).

Dla każdego wykrytego elementu system tworzy model semantyczny:
wymaganie (co), prewarunek (kiedy), postwarunek (jakie zmiany), wyjątki.

##### 4. Faza 3 - identyfikacja punktów testowalnych i ryzyka

System analizuje:

- **Punkty decyzyjne** (if/alt/guards) → generuje warianty testów dla
  każdej ścieżki

- **Pętle / multiplicities** → generuje testy brzegowe (0, 1, max,
  \>max)

- **Wartości walidacyjne** (typy/regex w atrybutach) → testy walidacji

- **Zależności zewnętrzne** → plan mocków i testów integracyjnych

- **Obsługę błędów i wyjątki** → testy negatywne

Na wyniku obliczana jest miara ryzyka/priorytetu (np. krytyczność
funkcji, złożoność ścieżki), aby zasugerować, które testy są
priorytetowe do uruchomienia najpierw.

##### 5. Faza 4 - generowanie opisowych przypadków testowych

Dla każdej wykrytej funkcji/flow system generuje zestaw opisowy.

Każdy przypadek testowy zawiera:

- ID (np. TC_SEQ_Login_001)

- Tytuł

- Opis celu

- Warunki wstępne

- Kroki testowe (sekwencja kroków krok→akcja→dane)

- Oczekiwany rezultat

- Typ testu
  (jednostkowy/integracyjny/systemowy/akceptacyjny/negatywny)

- Priorytet i wiążące elementy UML (odniesienie do ID elementu w
  modelu)

- Słowa kluczowe (np. \"auth\", \"payment\", \"boundary\")

- Proponowane dane testowe (przykładowe wartości, payloady
  JSON)

- Wymagane mocki/usługi zewnętrzne

TestGEN generuje taki opis poprzez wysłanie do LLM poprzez API
odpowiedniego prompta. Promp powinien uwzględnić powyższe parametry aby
były one uwzględnione w wyniku pracy LLM

**Przykładowy opisowy TC (z sekwencji logowania):**

**ID:** TC_SEQ_Login_001\
**Tytuł:** Logowanie - prawidłowe dane\
**Opis:** Użytkownik przesyła poprawne dane logowania, system tworzy
sesję i przekierowuje do dashboard.\
**Warunki:** Użytkownik istnieje w systemie; konto aktywne.\
**Kroki:**\
1. Otwórz POST /login z payload {\"email\": \"u@test.com\",
\"password\": \"Haslo1\"}\
2. Oczekuj HTTP 200 i token w odpowiedzi\
3. Po użyciu tokena GET /dashboard → status 200 i zawartość dashboard\
\
**Oczekiwane:** Token JWT w odpowiedzi; dashboard dostępny.\
**Typ:** Integracyjny/API. **Priorytet:** Wysoki.\
**Powiązanie UML:** Sequence/LoginFlow message 1..3

##### 6. Faza 5 - generowanie kodu testów (szkielety) i artefaktów

System może wygenerować gotowe szablony testów w wybranych frameworkach.
Typowe elementy:

- **Unit tests:** generowane z diagramu klas → testy metod publicznych;
  generowanie stubów i mocków zależności (np. z
  Mockito/pytest-mocker).

- **Integration/API tests:** generowane z endpointów wykrytych w
  sekwencjach → requests + asercje (PyTest, JUnit + RestAssured,
  Mocha/Chai).

- **E2E UI tests:** z sekwencji/aktivities/use-case → Page Objects +
  testy Playwright/Selenium/Cypress.

- **State tests:** z diagramów stanów → testy sprawdzające, że na
  określony event następuje oczekiwane przejście
  (unit/integration).

- **BDD/acceptance:** wygenerowanie Gherkin .feature.

- **Test harness / CI:** minimalne pliki konfiguracyjne (pytest.ini,
  playwright.config.js, GitHub Actions workflow do uruchomienia
  testów).

TestGEN oprócz prośby o opis prosi o wygenerowanie takie testy o ile LLM
który je generuje będzie w stanie je wygenerować na podstawie
przekazanych danych i wygenerowanego opisu

**Przykłady generowanych artefaktów:**

**Gherkin (z sekwencji logowania):**

Feature: Authentication Scenario: Successful login Given a registered
user with email \"u@test.com\" and password \"Haslo1\" When the user
submits credentials to /login Then the response status is 200 and a JWT
token is returned And accessing /dashboard with token returns status 200

**PyTest + Playwright (UI E2E skeleton):**

from playwright.sync_api import Page

def test_login_success(page: Page):

> page.goto(\"https://app.example.com/login\")
>
> page.fill(\"#email\", \"u@test.com\")
>
> page.fill(\"#password\", \"Haslo1\")
>
> page.click(\"button\[type=submit\]\")
>
> page.wait_for_selector(\".dashboard-header\")
>
> assert \"Witaj\" in page.text_content(\".dashboard-header\")

**JUnit + RestAssured (API):**

\@Test public void loginSuccess() { given()
.contentType(\"application/json\")
.body(\"{\\\"email\\\":\\\"u@test.com\\\",\\\"password\\\":\\\"Haslo1\\\"}\")
.when() .post(\"/login\") .then() .statusCode(200) .body(\"token\",
notNullValue()); }

**Page Object (python selenium):**

class LoginPage: def \_\_init\_\_(self, driver): self.driver = driver
self.email = \"#email\" self.password = \"#password\" self.submit =
\"button\[type=submit\]\" def login(self, email, pwd):
self.driver.find_element_by_css_selector(self.email).send_keys(email)
self.driver.find_element_by_css_selector(self.password).send_keys(pwd)
self.driver.find_element_by_css_selector(self.submit).click()

##### 7. Faza 6 - dane testowe, mocki i środowisko

System automatycznie generuje:

- Dane testowe (pozytywne/negatywne, boundary)

- Definicje mocków dla usług zewnętrznych (np. fake auth, fake payment
  gateway)

- Konfiguracje środowiska testowego (Docker compose skeleton, baza
  testowa z seedami)

- Skrypty uruchamiania (make, scripts, CI pipeline fragment)

TestGEN generuje powyższe poprzez wysłanie do LLM poprzez API
odpowiednich promptów.

##### 8. Faza 7 - mapowanie (traceability) i raportowanie

Każdy test zostaje powiązany z elementem UML (ID). System eksportuje:

- Macierz śledzenia: UML element ↔ wygenerowane przypadki testowe ↔
  wygenerowany kod testu

- Raporty pokrycia logicznego: które sekwencje/transition/branch są
  testowane, które nie

- Lista ryzyk i rekomendacje: brak testów dla wyjątkowo krytycznych
  ścieżek, propozycja rozszerzeń

**Przykładowy wiersz CSV macierzy:**

uml_id,uml_type,tc_id,tc_type,test_file,priority
SEQ_01,message_Login,TC_SEQ_Login_001,Integration,tests/api/test_login.py,High

##### 9. Faza 8 - walidacja, niepewność i human-in-the-loop

System przypisuje score ufności (np. 0-1) dla każdego wygenerowanego
testu zależnie od jakości diagramu/kompletności informacji (np. diagram
bez guardów → low confidence dla wartości boundary).

Testy powinny być kompletne i działające, jednak mogą zawierać braki,
niezgodności z prawdziwym procesem które wymagają doprecyzowania

System generuje suggested clarifications i zaznacza miejsca gdzie
potrzebna jest walidacja człowieka (np. \"nie określono, czy login
powinien wymuszać złożoność hasła\").

Udostępnia interfejs do akceptacji/edycji testów przed eksportem (review
UI), ale sam generuje kompletny zestaw bez konieczności od razu
zadawania pytań.

**Przykład:** konwersja prostego diagramu sekwencji → testy

Dla prostego diagramu sekwencji:

User -\> LoginPage : submits(email,password)

LoginPage -\> AuthService : POST /auth

AuthService -\> DB : verify(user)

AuthService \--\> LoginPage : 200 + token / 401

LoginPage -\> Dashboard : redirect on 200

Mogą zostać wygenerowane poniższe testy (przykładowo):

• TC1: Logowanie poprawne → oczekuj 200 + token → dostęp do dashboard.
(E2E + API)

• TC2: Logowanie --- złe hasło → oczekuj 401 i komunikat.

• TC3: Logowanie --- brak pól → oczekuj 400 + walidacja.

• TC4: Sesja wygasa → token expired → oczekuj 401 przy GET /dashboard.

Gherkin + PyTest snippets pokazane wcześniej są dobrym przykładem jak to
zostanie przekształcone w kod.

TestGEN waliduje testy poprzez wysłanie do LLM poprzez API odpowiednich
promptów

A ich wynik prezentuje w GUI

##### 10. Artefakty końcowe

Po zakończeniu procesu system dostarcza:

- Plik/zbiór opisowych przypadków testowych
  (CSV/Excel/JSON/PDF)

- Folder projektu testowego z wygenerowanymi testami
  (pytest/junit/robot/playwright), PageObjects, mockami, fixtures,
  configs, README z instrukcjami uruchomienia

- Macierz traceability (UML ↔ test)

- Raport pokrycia logicznego i propozycję minimalnego zestawu
  regression suite

- Listę pytań/niejasności do weryfikacji (opcjonalnie)

TestGEN generuje powyższe poprzez wysłanie do LLM poprzez API
odpowiednich promptów

### **4.3.3.** Funkcjonalność automatyzacji analizy interfejsów użytkownika (GUI) i generowania przypadków testowych (opisowych lub kodu makra do automatycznego testu) 

#### **4.3.3.1.** Opis funkcjonalności

**REQ-MOD-GUI-001:** System musi analizować zrzuty ekranów w formatach:
PNG, JPEG, PDF.

**REQ-MOD-GUI-002:** System musi identyfikować komponenty UI:
przyciski, pola tekstowe, listy rozwijane, checkboxy, radiobuttons,
menu, modale.

Silnik TestSpark przetwarza ekrany GUI i generuje na ich podstawie
przypadki testowe oraz kod automatyzujący testy interfejsu.

TestGEN analizuje obrazy poprzez wysłanie do LLM poprzez API
odpowiednich promptów i plików. Wybierając model najbardziej sprawny w
analizie obrazów. Wskazanie takiego modelu może być zaszyte w
konfiguracji i zmienione w procesie aktualizacji. Każdy z etapów jest
realizowany poprzez wysłanie do LLM poprzez API odpowiednich promptów.
Wybrany LLM może różnić się między etapami.

#### **4.3.3.2.** Szczegółowy przepływ działania

##### ETAP 1: Wczytanie i wstępna analiza ekranów

Po przesłaniu zrzutów ekranu:

**1. Analiza wizualna interfejsu**

- Rozpoznanie typu widoku (ekran logowania, dashboard, formularz, lista,
  popup, itp.)

- Identyfikacja głównych komponentów UI: pola tekstowe, przyciski,
  przełączniki, ikony, menu, listy rozwijane, komunikaty błędów,
  elementy nawigacji

- Oznaczanie możliwych stanów (np. aktywne/nieaktywne przyciski,
  pojawienie się komunikatu po błędzie)

**2. Identyfikacja kontekstu biznesowego**

- Na podstawie etykiet, tekstów i nazw elementów (np. \"Zaloguj\",
  \"Zarejestruj się\", \"Wyślij\", \"Koszyk\", \"Zapisz zmiany\")
  rekonstrukcja celu ekranu i jego powiązanie z innymi

- Dla kilku ekranów - rozpoznanie ścieżki użytkownika (user flow), np.:
  *Ekran 1 (Logowanie) → Ekran 2 (Panel główny) → Ekran 3 (Profil
  użytkownika)*

**3. Identyfikacja punktów interakcji**

- Zaznaczanie potencjalnych punktów akcji: kliknięcia, wprowadzanie
  tekstu, wybory z list, przełączniki, drag&drop itp.

- Grupowanie ich w sekwencje, które mogą tworzyć pojedynczy przypadek
  testowy

##### ETAP 2: Synteza funkcjonalności i generowanie przypadków testowych

Na podstawie zidentyfikowanych elementów i flow silnik TestSpark:

**1. Tworzy listę funkcjonalności użytkownika**

Każda funkcja (np. logowanie, filtrowanie wyników, dodanie produktu do
koszyka) staje się grupą testów.

**2. Generuje przypadki testowe**

Dla każdej funkcji powstaje zestaw przypadków, w tym:

- **Testy pozytywne** (prawidłowe dane i scenariusze sukcesu)

- **Testy negatywne** (puste pola, błędne dane, nieprawidłowe
  kolejności akcji)

- **Testy brzegowe** (np. maksymalna długość pól, ograniczenia
  walidacyjne)

- **Testy UI/UX** (czy przyciski są widoczne, poprawnie podpisane,
  działają stany hover/disabled)

**3. Tworzenie struktury przypadków w czytelnym formacie**

Każdy przypadek ma:

- ID testu

- Nazwę (np. *TC-001: Logowanie z poprawnymi danymi*)

- Cel testu

- Warunki wstępne

- Kroki testowe

- Oczekiwany rezultat

- Priorytet

TestGEN generuje powyższe poprzez wysłanie do LLM poprzez API
odpowiednich promptów

**4. Opcjonalnie - generacja przypadków w formacie Gherkin (BDD)**

Feature: User Login Scenario: Successful login with valid credentials
Given user is on login page When user enters email \"test@example.com\"
And user enters password \"Haslo123\" And user clicks \"Login\" button
Then user should be redirected to dashboard And welcome message should
be displayed

### **4.3.4.** Funkcjonalność generowania przypadków testowych i kodu testowego (GUI)

#### **4.3.4.1.** Opis funkcjonalności

**REQ-MOD-GUI-003:** System musi generować kod testowy dla frameworków:
Selenium, Playwright, Cypress, Appium, SikuliX. Wybór dla jakich
frameworków ma zostać wygenerowany posiada użytkownik na GUI

- **Scenariusze testowe w formie opisowej** (np. krok → oczekiwany
  rezultat), priorytety, dane testowe, warunki wstępne i pożądane kroki
  odtworzenia błędów

- **Szablony przypadków testowych** (np. Gherkin / Given-When-Then) lub
  listy kontroli (checklist)

- **Przykładowy kod automatyzujący**: skrypty startowe (np. Selenium /
  Playwright / Appium / Robot Framework / SikuliX / AutoHotkey /
  PyAutoGUI), lub krótkie makra (AutoHotkey, VBA) - zależnie od
  docelowego środowiska

- **Tam gdzie to możliwe także pliki konfiguracyjne lub test-suite
  skeleton** (np. pytest + selenium, Playwright test, Robot Framework
  .robot)

TestGen generuje powyższe poprzez wysłanie do LLM poprzez API
odpowiednich promptów, jeśli Model odpowie że ma za mało danych aby
wygenerować pliki konfiguracyjne lub test-suite skeleton możliwe jest
nie przekazanie tak owych

**REQ-MOD-GUI-004:** System musi umożliwiać wybór frameworka CI/CD dla
generowanego kodu testowego.

**Wymgana jest kompatybilności z istniejącymi frameworkami testerskimi**
oraz możliwość wykorzystania systemów CI/CD w zależności od preferencji
użytkowników końcowych. Oznacza to **konieczność** implementacji funkcji
wybrania dla jakiego CI/CD ma być generowany kod aby było łatwo go
wykorzystać wraz z popularnymi systemami CI/CD oraz narzędziami
testerskimi, takimi jak JUnit, Selenium, NUnit czy TestComplete (ew.
GitHub, Azure DevOps).

TestGen generuje powyższe poprzez wysłanie do LLM poprzez API
jednak z warunkiem czy dany framework ma sens. Np. pomimo zaznaczenia
JUnit jeśli językiem aplikacji jest C++. Weryfikację sensowności TestGEN
pozostawia LLM.

#### **4.3.4.2.** Szczegółowy przepływ działania

Użytkownik wczytuje do systemu np. zrzuty ekranów w dobrej
rozdzielczości, zawierające cały ekran (lub kolejność ekranów/flow).

**Opcjonalnie może wczytać:**

- Krótki opis scenariuszy biznesowych / co użytkownik ma osiągnąć na
  danym ekranie

- Dostęp do DOM / id elementów / pliku APK/IPA lub kodu - w celu
  większej automatyzacji i stabilności (zamiast image-based)

**W wyniku system może wygenerować:**

**1. Przypadek testowy (opisowy)**

**Nazwa:** Logowanie z poprawnymi danymi\
\
**Krok 1:** Otwórz ekran logowania.\
**Krok 2:** Wprowadź email test@example.com.\
**Krok 3:** Wprowadź hasło Haslo123.\
**Krok 4:** Kliknij \"Zaloguj\".\
\
**Oczekiwany rezultat:** Użytkownik zostaje przekierowany do pulpitu
głównego, widoczny jest baner \"Witaj\".

**2. Fragment skryptu - Selenium (Python)**

from selenium import webdriver from selenium.webdriver.common.by import
By from selenium.webdriver.common.keys import Keys driver =
webdriver.Chrome() driver.get(\"https://twoja-aplikacja.example/login\")
driver.find_element(By.ID, \"email\").send_keys(\"test@example.com\")
driver.find_element(By.ID, \"password\").send_keys(\"Haslo123\")
driver.find_element(By.ID, \"login-button\").click() assert \"Witaj\" in
driver.page_source driver.quit()

**3. Fragment skryptu - SikuliX (pseudo-skrypt)**

\# Sikuli (Jython) click(\"images/login_button.png\")
type(\"images/email_field.png\", \"test@example.com\")
type(\"images/password_field.png\", \"Haslo123\")
click(\"images/submit_button.png\")
wait(\"images/dashboard_welcome.png\", 10)

Z otrzymanych przypadków silnik TestSpark automatycznie wygeneruje:

- **Listę przypadków testowych** (np. w Excel / CSV / PDF) - do importu
  w narzędziach typu TestRail, Jira XRay, Zephyr

- **Plan testów** - podsumowanie obszarów testowych, priorytetów, i
  zależności ekranów

- **Mapę przepływu ekranów (user flow diagram)** - pokazującą logiczne
  przejścia między widokami

### **4.3.5.** Funkcjonalność testów regresji GUI

#### **4.3.5.1.** Opis funkcjonalności

**REQ-MOD-GUI-005:** System musi porównywać dwie wersje interfejsu GUI i
identyfikować zmiany wizualne i funkcjonalne.

TestGEN umożliwia automatyczne wykrywanie zmian wskazując potencjalne
błędy regresji analizując aplikację identyfikując ewentualne
niespójności między wersjami kodu lub ekranu użytkownika (porównywanie
obrazów).

#### **4.3.5.2.** Szczegółowy przepływ działania

System po wczytaniu dwóch wersji kodu źródłowego lub dwóch różnych
wersji danego ekranu jest w stanie zrobić tzw. diff-a i wskazać
elementy, które się od siebie różnią. Następnie jest w stanie
przygotować opis przypadku testowego do wykonania testu regresji jak i
ewentualny kod do przetestowania GUI.

##### 1. Wejście (input)

System przyjmuje:

- **Para lub zestaw zrzutów ekranów** powiązanych logicznie: v1 (stara)
  oraz v2 (nowa). Mogą to być pojedyncze ekrany lub sekwencje ekranów
  (flow).

- **Metadane (opcjonalne):** rozdzielczość, device/emulator, timestamp,
  identyfikator builda, URL/ścieżka ekranu, informacje o DOM (jeśli
  dostępne).

- **Pliki referencyjne (opcjonalnie):** mapowanie elementów UI →
  unikalne ID/selektory (jeśli dostępne, daje dużo wyższą stabilność
  testów).

Formaty wejścia: PNG/JPEG/SVG, plus opcjonalne JSON z
metadanymi.

##### 2. Wstępne przygotowanie i normalizacja obrazów

**Kroki:**

- **Normalizacja rozdzielczości i skalowania** - dopasowanie DPI/skal do
  wspólnego układu (by zmniejszyć fałszywe różnice spowodowane
  skalowaniem)

- **Preprocessing** - filtrowanie szumów, ujednolicenie kolorów,
  opcjonalne usunięcie dynamicznych treści (np. znaczniki czasu) jeśli
  są rozpoznane

- **Segmentacja UI** - wykrycie regionów: nagłówek, formularz, lista,
  przyciski, bannery. Techniki: detekcja konturów, heurystyki layoutu,
  modele wykrywające komponenty (np. ML do rozpoznawania przycisku/pola)

- **OCR** - rozpoznanie tekstu na ekranie i powiązanie go z regionami
  (etykiety przycisków/placeholdery/komunikaty). To pozwala robić
  semantyczne porównania (np. \"Zaloguj\" → \"Sign In\")

Wynik: ustrukturyzowana reprezentacja ekranu (lista regionów z bounding
box, typem komponentu, ekstraktowanym tekstem).

##### 3. Porównanie wersji - diffing (visual + semantic)

System wykonuje dwie klasy analiz diferencyjnych:

**A. Visual diff (pixel/structural)**

- Obliczanie różnic piksel-po-piksel z adaptacyjnym progiem tolerancji
  (aby ignorować drobne anty-aliasing/skalowanie)

- Mapowanie regionów (region v1 ↔ najbliższy region v2) za pomocą IoU
  (intersection over union) i dopasowania kształtu

- Generowanie obrazu diff z podświetleniem zmian
  (added/removed/modified)

**B. Semantic diff (komponentowy)**

- Porównanie wykrytych komponentów po typie i tekście (np. przycisk z
  etykietą, pole input, komunikat walidacji)

- Rozpoznawanie zmiany: tekst zmieniony, element przesunięty, element
  usunięty/dodany, style/czcionka zmiana

- Jeśli dostępny DOM/selektory → porównanie selektorów i atrybutów (np.
  id, class, aria-\*)

TestGen generuje powyższe klasy poprzez wysłanie do LLM poprzez
API

**Wynik diffu**

Dla każdego wykrytego elementu system produkuje rekord:

{ element_id: optional, bbox_v1: \[\...\], bbox_v2: \[\...\], type:
\"button\|input\|label\|list\|image\|banner\|modal\", text_v1:
\"Zaloguj\", text_v2: \"Zaloguj się\", visual_change:
\"none\|moved\|resized\|style\|added\|removed\|significant\",
semantic_change: \"none\|text_changed\|type_changed\|present_absent\",
confidence: 0.87 }

##### 4. Klasyfikacja zmian (wpływ na funkcjonalność)

Dla każdego wykrytego różnicowego elementu system klasyfikuje wpływ na
zachowanie użytkownika:

- **Breaking / Behavioral change** - zmiana, która wpływa na działanie
  (np. przycisk usunięty, pole input zmienione na readonly, tekst \"Usuń
  konto\" zmieniony na \"Archiwizuj\")

- **UI-only / Cosmetic** - tylko wyglądowe (kolor, font, drobne
  przesunięcie) - zwykle niższy priorytet regresji

- **Potentially risky** - np. etykieta zmieniona na podobną (może być
  bug), element przeniesiony (może zmienić discoverability)

- **Unknown** - gdy OCR/segmentacja niska pewność

Reguły klasyfikacji opierają się na heurystykach + regułach (np.
usunięcie przycisku submit → Breaking).

TestGen generuje powyższe poprzez wysłanie do LLM poprzez API
prompt powinien zawierać opis powyższych klasyfikacji aby ułatwić LLM
uzyskanie prawidłowego wyniku

##### 5. Generowanie przypadków testów regresji - zasady

**Typy testów generowanych:**

- **Baseline check** - czy ekran renderuje (porównanie podstawowych
  elementów)

- **Functional regression** - testy, które sprawdzają, czy
  funkcjonalność związana z zmienionymi elementami działa tak jak
  wcześniej (np. kliknięcie przycisku powoduje oczekiwane
  przejście)

- **Negative / Validation** - sprawdzenie walidacji i błędów (zwłaszcza
  jeśli pola/domyślnie wymagane atrybuty zmieniły się)

- **Visual regression** - testy obrazkowe (pixel-diff) z
  tolerancjami

- **Accessibility/Label checks** - etykiety aria/tekst alternatywny
  (jeśli OCR/DOM wskazuje zmiany)

- **Exploratory hints** - sugestie do ręcznego przeglądu (np. \"sprawdź
  nowe CTA w headerze\")

Każdy testowy przypadek dostaje: ID, opis, kroki, dane wejściowe,
oczekiwany rezultat, typ (functional/visual/negative), priorytet,
powiązanie z rekordem diffu i score ufności.

TestGen generuje powyższe poprzez wysłanie do LLM poprzez API
dbając o to aby powyższe były w wyniku pracy LLM

##### 6. Generacja kodu testowego: krok po kroku

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca
Musi natomiast zostać uwzględnione w dokumentacji

1.  Wejście pary zrzutów → normalizacja i strukturalizacja (patrz etap
    2).

2.  Diffing → otrzymanie listy zmian z metadanymi i confidence.

3.  Filtracja → usuń zmiany poniżej minimalnego progu (np. confidence \<
    0.4) albo kosmetyczne jeśli użytkownik chce tylko functional.

4.  Mapowanie na scenariusze:

- Dla usuniętych elementów: generuj TC sprawdzający brak elementu i TC
  alternatywny sprawdzający czy funkcjonalność dostępna inaczej.

- Dla dodanych elementów: TC weryfikujący obecność i TC integracyjny,
  jeśli element inicjuje akcję.

- Dla tekst zmieniony: TC sprawdzający, że logika nie zależy od etykiety
  (np. poszukaj selektora bez tekstu) i TC akceptacyjny sprawdzający
  przekaz.

- Dla przesuniętych/resized: visual regression TC z tolerancją; e2e TC
  sprawdzający czy klik działa.

5.  Generacja kroków testowych --- krok → akcja → dane → asercja. Każdy
    krok powiązany z konkretnym regionem/selektorem lub wzorcem obrazu.

6.  Generacja danych testowych --- automatyczne przypisanie
    przykładowych danych lub wykorzystanie istniejącej bazy danych
    testowej/fixtures.

7.  Priorytetyzacja --- score = f(change_type, element_criticality,
    coverage_history). Krytyczne zmiany → wysoki priorytet.

8.  Output --- zestaw TC w formatach: CSV/Excel, Gherkin .feature, JSON
    (do integracji), i folder z kodem-skeletonami testów.

System generuje równolegle dwa rodzaje testów (jeśli to
możliwe):

**A. DOM-based** (najbardziej stabilne, gdy dostęp do selektorów / DOM
jest możliwy)

- Playwright (JS/TS/Python) - preferowany dla nowoczesnych webów,
  szybkie i multi-browser

- Selenium (Python/Java) - szerokie zastosowanie

**B. Image-based** (jeżeli nie ma DOM lub tylko screenshoty)

- SikuliX (Jython/Java) - dopasowanie obrazów (pattern matching)

- PyAutoGUI / OpenCV - prostsze makra/automatyzacja

**C. Desktop / Native**

- WinAppDriver / pywinauto dla Windows

- Appium dla aplikacji mobilnych

Dla każdego TC system generuje:

- Plik testowy (np. tests/test_login_regression.py)

- Page Object / locator map (jeśli DOM-based)

- Obrazy referencyjne + diff images (jeśli image-based)

- Fixtures/mocks (jeśli potrzebne)

- CI job skeleton (np. GitHub Actions YAML)

> TestGen generuje testy poprzez wysłanie do LLM poprzez API odpowiedni
> prompt dbając o to aby wynik zawierał wszystkie powyższe

##### 7. Przykładowe wygenerowane testy

**A. Playwright (Python) - DOM-based test sprawdzający, że zmieniony
przycisk działa:**

\# tests/test_regression_button_click.py from playwright.sync_api import
Page def test_cta_click_navigates_to_new_page(page: Page):
page.goto(\"https://app.example.com/some-screen\") \# locator
wygenerowany z DOM lub heurystyki (fallback: text) cta =
page.locator(\"button:has-text(\'Zaloguj się\')\") \# lub \"#cta-login\"
assert cta.is_visible() cta.click()
page.wait_for_url(\"\*\*/dashboard\") assert \"Witaj\" in
page.text_content(\"h1\")

**B. SikuliX (Jython) - image-based test sprawdzający, że przycisk
istnieje i działa:**

\# sikuli script (Jython) click(\"images/v2/cta_login.png\")
wait(\"images/v2/dashboard_header.png\", 10) assert
exists(\"images/v2/dashboard_header.png\")

**C. Playwright (visual regression) - pixel diff z tolerancją:**

def test_visual_regression_main_section(page: Page):
page.goto(\"https://app.example.com/some-screen\") screenshot =
page.locator(\"#main-section\").screenshot() \# porównanie z saved
baseline from PIL import Image, ImageChops baseline =
Image.open(\"images/baseline/main_section_v1.png\") current =
Image.open(screenshot_path) diff = ImageChops.difference(baseline,
current) \# Count non-zero pixels non_zero = sum(1 for px in
diff.getdata() if px != (0,0,0,0)) assert non_zero \< 500 \# threshold
wygenerowany automatycznie

**D. Gherkin feature (wyeksportowane):**

Feature: Regression test for Login screen Scenario: CTA \"Zaloguj się\"
still navigates to dashboard Given I open \"/some-screen\" When I click
the \"Zaloguj się\" button Then I should be on \"/dashboard\" And I
should see \"Witaj\" in header

#### **4.3.5.3.** Przebiegi funkcjonalności

**Przebieg pozytywny:**

System będzie w stanie wyłapać różnice w GUI i przygotować opisowe
przypadków testowych do wykonania testów regresji jak i ewentualny kod
do przetestowania GUI.

**Przebieg negatywny:**

Np. w przypadku wczytania identycznych ekranów system nie będzie w
stanie przygotować testów regresji wskazując, że wczytano te same
materiały.

### Wykorzystane mechanizmy i technologie

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły
mogą ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca
Musi natomiast zostać uwzględnione w dokumentacji

#### **4.3.6.1.** Mechanizm wczytywania i interpretacji diagramów UML

Mechanizm będzie odpowiedzialny za wczytywanie i interpretację diagramów
UML (takich jak diagramy przypadków użycia, aktywności czy sekwencji).
Do przetwarzania danych graficznych mogą zostać wykorzystane parsery UML
(np. PlantUML, GraphML) lub sieci transformer do rozpoznawania
diagramów, które pozwolą na identyfikację elementów kluczowych: aktorów,
akcji, zależności, warunków oraz przepływów sterowania. Te informacje
zostaną następnie przetworzone do postaci ustrukturyzowanej, możliwej do
dalszej analizy i interpretacji.

**Przykładowe narzędzia UML:**

- PlantUML - parsowanie tekstowych diagramów UML

- XMI parsers - przetwarzanie standardowego formatu wymiany UML

- Eclipse UML2 - biblioteka Java do pracy z modelami UML

- Papyrus - narzędzie modelowania z API

#### **4.3.6.2.** Mechanizm tworzenia opisowych przypadków dla GUI i UML

Mechanizm będzie umożliwiał analizę GUI, tj. ekranów użytkownika w
postaci zrzutów ekranowych lub struktury interfejsu np. z plików
graficznych lub XML.

Na podstawie wczytanych diagramów UML i/lub GUI zostaną przygotowane
przepływy użytkownika i działania systemu. W oparciu o te dane zostaną
wygenerowane przypadki testowe odzwierciedlające scenariusze biznesowe i
operacyjne. Dla nich zostaną utworzone opisy testów, przykładowe dane
wejściowe, kroki, warunki początkowe i końcowe oraz oczekiwane
rezultaty.

Tak jak w przypadku poprzednich modułów, testy mogą być klasyfikowane
np. jako pozytywne, negatywne lub brzegowe.

#### **4.3.6.3.** Mechanizm generowania kodu do uruchomienia testu GUI

Automatyczne generowanie kodu testowego dla wskazanych klas przypadków
identyfikując elementy GUI i przypisane im akcje. Zastosowane zostaną
algorytmy transformujące logikę przypadków testowych na kod wykonywalny.

**Techniki generacji kodu testowego:**

- Template-based generation - wykorzystanie szablonów kodu

- AST manipulation - manipulacja drzewem składniowym

- Code synthesis z LLM - wykorzystanie modeli językowych

- Pattern matching - dopasowywanie wzorców testowych

**UWAGA:** Niniejszy dokument przekroczył limit znaków dla jednej
odpowiedzi. Dokument będzie kontynuowany w kolejnej części, obejmującej
pozostałe rozdziały:

- 4.4. Moduł analizy bezpieczeństwa

- 4.5. Moduł analizy luk funkcjonalnych

- Rozdziały 5-10
