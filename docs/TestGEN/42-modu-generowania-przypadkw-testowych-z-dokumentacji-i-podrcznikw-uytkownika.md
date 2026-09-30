# **4.2.** Moduł generowania przypadków testowych z dokumentacji i podręczników użytkownika

### **4.2.1.** Opis ogólny modułu

Moduł generowania przypadków testowych na podstawie dokumentacji i
podręczników użytkownika wykorzystuje przetwarzanie języka naturalnego
(NLP) oraz techniki uczenia maszynowego do automatycznej ekstrakcji
wymagań i scenariuszy testowych z dokumentacji technicznej i biznesowej.

**Technologie:** Python, HuggingFace Transformers, spaCy, TensorFlow,
FastAPI, Docker oraz narzędzia CI/CD do automatyzacji testowania i
wdrożeń. Mogą zostać wykorzystane modele typu transformer (np. BERT) lub
techniki NER (Named Entity Recognition) i klasyfikacji tekstu, reguły
heurystyczne.

### **4.2.2.** Funkcjonalność automatyzacji analizy dokumentacji technicznej i biznesowej

#### **4.2.2.1.** Opis funkcjonalności

Celem jest automatyczne wykrywanie rozbieżności pomiędzy wizją biznesową
a implementacją techniczną. System porównuje \"co miało być zrobione\"
(w dokumentacji biznesowej) z \"co zostało zaprojektowane lub
zaimplementowane\" (w dokumentacji technicznej).

Na potrzeby testów tego rozwiązania dobrze wygenerować kilka par:
dokumentacja biznesowa i techniczna z rozbieżnościami i bez. Aby
pokazać, że jeśli były rozbieżności to system to wykryje.

TestGEN może to zrealizować poprzez napisania prompta, który sprawdza,
czy w dok. biznesowej są opisane funkcje, które mają swój odpowiednik w
dok. systemowej. Zatem porównywanie ustrukturyzowanych dokumentów

**REQ-MOD-DOC-001:** System musi automatycznie analizować dokumentację
techniczną i biznesową w formacie: PDF, DOCX, TXT, MD, HTML.

**REQ-MOD-DOC-002:** System musi identyfikować rozbieżności między
dokumentacją biznesową a techniczną.

Dzięki temu:

- Można wykryć braki funkcjonalne (np. brak opisanej funkcji w kodzie
  lub projekcie technicznym)

- Można wykryć nadmiar funkcjonalny (np. funkcja w kodzie, której nie
  ma w wymaganiach biznesowych)

- Można zidentyfikować niespójności logiczne, terminologiczne i
  procesowe

- Oraz wcześnie ostrzec o potencjalnych błędach projektowych, zanim
  system przejdzie do testów lub wdrożenia

TestGEN automatycznie identyfikuje rozbieżności względem dokumentacji,
co pozwala wykrywać potencjalne błędy przed wdrożeniem systemu. Jest to
pełna automatyczna analiza dokumentacji z wymaganiami technicznymi.

#### **4.2.2.2.** Szczegółowy przepływ działania

##### ETAP 1: Wczytanie i klasyfikacja dokumentów

System wczytuje wszystkie źródła wiedzy dotyczące projektu, np.:

- **Dokumentacja biznesowa** - analizy wymagań (BRD, User Stories, Use
  Case\'y, backlogi, makiety UX, opisy procesów)

- **Dokumentacja techniczna** - specyfikacje API, diagramy architektury,
  pliki konfiguracyjne, opisy modułów, komentarze kodu, instrukcje
  instalacji

- **Specyfikacje pośrednie** - np. FRD (Functional Requirements
  Document), SRS (Software Requirements Specification)

Po wczytaniu dokumenty są **zamieniane na jednolitą reprezentację
tekstową**, z zachowaniem ich struktury logicznej (nagłówki, tabele,
diagramy, sekcje).

System rozpoznaje, które fragmenty opisują:

- Funkcje użytkownika

- Procesy biznesowe

- Komponenty techniczne

- API / endpointy

- Reguły biznesowe

- Ograniczenia, parametry, warunki brzegowe

TestGEN uwzględnia powyższe elementy w promptcie do LLM aby były one
zawarte w raporcie

##### ETAP 2: Budowa modelu semantycznego dokumentacji

System wykorzystuje przetwarzanie języka naturalnego (NLP) i modele
semantyczne (LLM) do **wyodrębnienia kluczowych pojęć, relacji i akcji**
z obu typów dokumentacji.

Do implementacji chociaż może się okazać że moduły TestGEN nie będą
wywoływać tych klas.

Tworzy dwa modele wiedzy:

**Model Biznesowy (Business Knowledge Graph)**

Zawiera:

- Funkcje i cele biznesowe (np. \"Użytkownik może dodać produkt do
  koszyka\")

- Role użytkowników (np. \"Administrator\", \"Klient\")

- Procesy (np. \"Zamówienie\", \"Zwrot\", \"Płatność\")

- Reguły biznesowe (np. \"Rabat tylko dla zamówień powyżej 500 zł\")

**Model Techniczny (Technical Knowledge Graph)**

Zawiera:

- Komponenty systemu (np. CartService, PaymentModule, API /orders)

- Metody, endpointy, klasy, bazy danych

- Parametry, konfiguracje, przepływy danych

- Opisy logiki biznesowej w kodzie lub projektach UML

Każdy model jest zbudowany w formie grafu pojęć (knowledge graph), gdzie
węzły to pojęcia, a krawędzie - relacje między nimi (np. Użytkownik →
dodaje → Produkt).

##### ETAP 3: Porównanie modeli (Business vs. Technical Mapping)

System automatycznie **mapuje pojęcia i funkcje** z modelu biznesowego
na odpowiadające im elementy modelu technicznego.

TestGEN prosi o wygenerowanie takiej mapy via API jakiś LLM, mapa może
ale nie musi być dalej używana w procesie

**Przykład mapowania:**

  ----------------------------------------------------------------------------
  **Koncept biznesowy**   **Odpowiednik techniczny** **Status**
  ----------------------- -------------------------- -------------------------
  \"Zaloguj użytkownika\" POST /api/login            ✅ OK

  \"Zresetuj hasło\"      brak endpointu             ❌ Brak w dokumentacji
                                                     technicznej

  \"Generowanie raportu   ReportService.generate()   ✅ OK
  sprzedaży\"                                        

  \"Powiadomienia SMS\"   brak komponentu SmsService ⚠️ Niespójność

  brak w BRD              AuditLogger.saveEvent()    ⚠️ Nadmiar funkcjonalny
  ----------------------------------------------------------------------------

##### ETAP 4: Analiza rozbieżności

Po porównaniu system klasyfikuje różnice w następujących kategoriach:

**1. Braki funkcjonalne**

Funkcje opisane w dokumentacji biznesowej **nie mają odpowiedników
technicznych**.

**Przykład:** BRD mówi o \"śledzeniu przesyłki\", ale brak modułu
TrackingService w projekcie.

**2. Nadmiar funkcjonalny**

W dokumentacji technicznej znajdują się komponenty lub endpointy, które
**nie mają pokrycia w wymaganiach biznesowych**.

**Przykład:** w API występuje /internal/exportLogs, którego nie
przewidziano w BRD.

**3. Niespójności logiczne**

System wykrywa różnice w logice lub warunkach opisanych w obu
dokumentacjach.

**Przykład:**\
BRD: \"Zamówienie można anulować do momentu wysyłki.\"\
Specyfikacja techniczna: \"Zamówienie można anulować tylko w ciągu 30
minut od utworzenia.\"

**4. Różnice terminologiczne**

System wykrywa, że te same pojęcia są różnie nazywane.

**Przykład:** BRD: \"Użytkownik Premium\" - TechDoc:
\"AccountType.GOLD\".\
To nie błąd, ale wymaga standaryzacji słownika.

**5. Braki integracyjne**

Opisane w BRD przepływy między systemami **nie mają odwzorowania w
architekturze technicznej**.

**Przykład:**\
BRD: \"System wysyła dane do CRM.\"\
TechDoc: brak połączenia z API CRM.

##### ETAP 5: Generacja raportu rozbieżności

Po analizie system generuje **Raport Spójności Dokumentacji
(Documentation Consistency Report)**.

Zawiera on:

- Listę zidentyfikowanych różnic

- Poziom istotności (np. błąd krytyczny, ostrzeżenie, różnica
  terminologiczna)

- Odniesienia do konkretnych sekcji w dokumentach

- Rekomendacje działań naprawczych

TestGEN prosi o wygenerowanie takiego raportu via API jakiś LLM, ważne
aby w promcie uwzględnił powyższe punkty

**Przykład fragmentu raportu:**

  ------------------------------------------------------------------------------------
  **ID**   **Typ            **Opis**              **Wystąpienia**   **Rekomendacja**
           rozbieżności**                                           
  -------- ---------------- --------------------- ----------------- ------------------
  D-001    Brak             Funkcja \"Reset       BRD §3.2 vs brak  Dodać opis
           funkcjonalny     hasła\" nie występuje w TechDoc         implementacji lub
                            w dokumentacji                          uzupełnić API
                            technicznej                             

  D-004    Niespójność      W BRD limit płatności §4.1 vs §2.3      Ujednolicić limit
           logiczna         5000 zł, w TechDoc                      w obu dokumentach
                            3000 zł                                 

  D-007    Nadmiar          Endpoint /admin/debug brak w BRD        Sprawdzić
           funkcjonalny     nie występuje w                         zasadność
                            wymaganiach                             istnienia
                            biznesowych                             endpointu
  ------------------------------------------------------------------------------------

##### ETAP 6: Uczenie i aktualizacja modeli

System z każdą analizą:

- Uczy się terminologii specyficznej dla organizacji

- Tworzy słownik pojęć projektowych (glosariusz)

- Zapamiętuje reguły mapowania (np. \"klient\" = \"user\", \"produkt\" =
  \"item\")

Dzięki temu kolejne analizy są coraz dokładniejsze, a wykrywanie
rozbieżności coraz bardziej precyzyjne i mniej podatne na \"fałszywe
alarmy\".

#### **4.2.2.3.** Przebiegi funkcjonalności

**Przebieg pozytywny:**

Użytkownik wczytuje dwa dokumenty - dokumentację techniczną i biznesową.
Dokonuje analizy dokumentów pod kątem ich różnicy. Przygotowuje raport
wskazujący jakich funkcjonalności/funkcji/procedur nie ma w jednym
dokumencie, które zostały wskazane w drugim z krótkim opisem
rekomendującym uzupełnienie wybrakowanego dokumentu.

**Przebieg negatywny:**

Gdy wczytano puste dokumenty lub takie same materiały, system nie jest w
stanie wskazać różnic.

### **4.2.3.** Funkcjonalność generowania przypadków testowych na podstawie dokumentacji technicznej i dokumentacji biznesowej

#### **4.2.3.1.** Opis funkcjonalności

**REQ-MOD-DOC-003:** System musi automatycznie generować opisowe
przypadki testowe na podstawie dokumentacji technicznej i użytkownika.

System ma automatycznie tworzyć opisowe przypadki testowe (test cases)
na podstawie treści dokumentacji dostarczonej przez producenta lub
integratora oprogramowania.

Celem jest przekształcenie wiedzy zapisanej w dokumentach w zestaw
testów, które można wykorzystać w testach akceptacyjnych,
integracyjnych, funkcjonalnych, instalacyjnych lub
bezpieczeństwa.

#### **4.2.3.2.** Szczegółowy przepływ działania

##### ETAP 1: Wczytanie i klasyfikacja dokumentacji

System przyjmuje różne formaty plików:

- Dokumenty tekstowe (DOCX, PDF, ODT, TXT, MD)

- Dokumenty techniczne (np. UML, Swagger/OpenAPI, README, konfiguracje
  YAML, JSON)

- Instrukcje użytkownika

- Podręczniki administratora

- Instrukcje instalacyjne

- Specyfikacje wymagań (SRS, BRD, FRD)

**Proces:**

1.  Dokumenty są wczytywane i konwertowane do formatu tekstowego (OCR,
    ekstrakcja z PDF itp.).

2.  TestGEN-AI analizuje zawartość i automatycznie klasyfikuje fragmenty
    na typy:

    - \"Wymagania funkcjonalne\"

    - \"Wymagania niefunkcjonalne\"

    - \"Instrukcje obsługi / użytkowania\"

    - \"Instrukcje instalacji\"

    - \"Opis architektury / integracji\"

    - \"Opis błędów i wyjątków\"

    - \"Procedury konfiguracji / bezpieczeństwa\"

Ta klasyfikacja tworzy mapę semantyczną dokumentacji - czyli model, w
którym każdy fragment jest przypisany do odpowiedniej kategorii
testowalnych informacji.

TestGEN generuje taką mapę semantyczna. Może, ale nie musi być dalej
używana w procesie

##### ETAP 2: Ekstrakcja informacji testowalnych

Silnik TestSpark analizuje każdy akapit dokumentacji, aby wyłuskać
potencjalne punkty testowe.

System rozpoznaje m.in.:

- Akcje użytkownika (np. \"użytkownik wybiera opcję\", \"klika
  przycisk\", \"uruchamia moduł\")

- Oczekiwane rezultaty (np. \"system wyświetla komunikat\", \"zapisuje
  dane\", \"odrzuca żądanie\")

- Warunki brzegowe i zależności (np. \"jeśli użytkownik nie ma
  uprawnień\", \"jeżeli dane są niepoprawne\")

- Parametry techniczne i ograniczenia (np. porty, konfiguracje, wersje
  bibliotek)

- Scenariusze wyjątkowe i błędy (np. \"gdy serwer nie odpowiada\",
  \"błąd uwierzytelniania\")

Zidentyfikowane informacje są następnie ułożone w strukturę
przypominającą macierz wymagań testowych (Requirement-to-Test Matrix).

TestGEN generuje taką Macierz. Może, ale nie musi być dalej używana w
procesie

##### ETAP 3: Generacja logicznego modelu testów

System tworzy abstrakcyjny model testowy, który opisuje:

- Obiekty testowane (np. moduły, ekrany, funkcje API)

- Możliwe działania użytkownika lub systemu

- Dane wejściowe i oczekiwane wyniki

- Zależności między przypadkami

Model ten ma postać ontologii testowej - sieci pojęć i relacji między
funkcjami, wymaganiami i testami.

TestGEN generuje taki model. Może, ale nie musi być dalej używana w
procesie

**Przykład fragmentu modelu (w postaci logicznej):**

**Funkcja:** Logowanie użytkownika\
→ **Wymaganie:** Po poprawnym wprowadzeniu loginu i hasła użytkownik
zostaje zalogowany.\
→ **Scenariusz:** Użytkownik wprowadza poprawne dane.\
→ **Oczekiwany wynik:** Przekierowanie na ekran główny.

##### ETAP 4: Generacja opisowych przypadków testowych

Na podstawie modelu system automatycznie tworzy opisowe przypadki
testowe, w czytelnej formie narracyjnej.

Każdy przypadek zawiera:

- **Identyfikator testu** (np. TC_AUTH_001)

- **Nazwa testu**

- **Cel testu**

- **Warunki wstępne**

- **Kroki testowe** (zestaw czynności użytkownika lub systemu)

- **Dane wejściowe**

- **Oczekiwany rezultat**

- **Typ testu** (funkcjonalny, instalacyjny, integracyjny itp.)

- **Źródło** (odniesienie do fragmentu dokumentacji)

TestGEN prosi o wygenerowanie takiego przypaku via API jakiś LLM, ważne
aby w promcie uwzględnił powyższe punkty

**Przykład 1 (z dokumentacji użytkowej):**

**TC_GUI_05 - Dodanie nowego użytkownika**\
\
**Cel:** Sprawdzić, czy administrator może dodać nowego użytkownika z
panelu zarządzania.\
**Warunki wstępne:** Administrator jest zalogowany.

**Kroki testowe:**\
1. Otwórz zakładkę \"Użytkownicy\"\
2. Kliknij \"Dodaj użytkownika\"\
3. Wprowadź imię, nazwisko, e-mail i rolę\
4. Kliknij \"Zapisz\"\
\
**Oczekiwany rezultat:** Nowy użytkownik pojawia się na liście.\
**Źródło:** Instrukcja użytkownika, rozdział 4.3 \"Zarządzanie
użytkownikami\"

**Przykład 2 (z dokumentacji instalacyjnej):**

**TC_INST_02 - Weryfikacja poprawności instalacji bazy danych**\
\
**Cel:** Sprawdzić, czy baza danych została utworzona z prawidłową
strukturą.\
**Warunki wstępne:** Środowisko testowe skonfigurowane.\
**Kroki testowe:**\
1. Uruchom skrypt install_db.sql\
2. Sprawdź, czy utworzone zostały tabele USERS, ROLES, LOGS\
\
**Oczekiwany rezultat:** Wszystkie tabele są obecne i dostępne.\
**Źródło:** Dokumentacja instalacyjna, sekcja 2.1

##### ETAP 5: Weryfikacja spójności i kompletności

System analizuje, czy:

- Każde wymaganie z dokumentacji ma przypisany co najmniej jeden
  przypadek testowy

- Nie ma przypadków testowych bez źródła w dokumentacji

- Przypadki testowe pokrywają zarówno scenariusze pozytywne, jak i
  negatywne

- Opisy testów są spójne logicznie i językowo

TestGEN generuje taką tablicę poprzez wysłanie do LLM poprzez API
odpowiedniego prompta. Przekazując dokumentacje, przypadki testowe, kod
testów

Wynikiem jest **macierz śladowania (Traceability Matrix)**:

  ---------------------------------------------------------------------------
  **Wymaganie**   **Opis**            **Test Case**            **Status
                                                               pokrycia**
  --------------- ------------------- ------------------------ --------------
  FR-001          Logowanie           TC_AUTH_001, TC_AUTH_002 ✅ Pokryte
                  użytkownika                                  

  FR-002          Reset hasła         TC_AUTH_003              ⚠️ Częściowo

  NFR-001         Czas reakcji \< 2s  TC_PERF_001              ✅ Pokryte
  ---------------------------------------------------------------------------

##### ETAP 6: Generacja testów automatycznych (opcjonalna)

Na podstawie opisowych przypadków testowych TestGEN-AI może
automatycznie wygenerować szkielety testów automatycznych w wybranych
frameworkach, np.:

- **Playwright / Cypress / Selenium** (testy GUI)

- **Pytest / JUnit / NUnit** (testy jednostkowe i integracyjne)

- **Postman / RestAssured** (testy API)

- **Robot Framework** (testy wysokopoziomowe)

- **PowerShell / Bash** (testy instalacyjne)

Każdy kod zawiera odniesienia do przypadków testowych i danych
wejściowych.

TestGEN generuje takie testy poprzez wysłanie do LLM poprzez API
odpowiedniego prompta. Przekazując przypadki testowe wybór frameworka
pozostawia LLM jednak tylko z powyższej listy

##### ETAP 7: Raport i eksport wyników

System generuje:

- Raport testów w formacie PDF/HTML/Excel

- Plik eksportu przypadków testowych do narzędzi takich jak Jira,
  TestRail, Zephyr, Xray, qTest

- Opcjonalny plik JSON/XML z metadanymi testów (dla integracji
  CI/CD)

#### **4.2.3.3.** Przebiegi funkcjonalności

**Przebieg pozytywny:**

Użytkownik wczytuje dokumentację. System dokonuje analizy dokumentów i
generuje kompletny zestaw przypadków testowych wraz z macierzą
śladowania.

**Przebieg negatywny:**

Gdy wczytano puste dokumenty lub dokumenty bez testowalnych informacji,
system nie jest w stanie wygenerować przypadków testowych i informuje
użytkownika o braku odpowiednich danych wejściowych.

### **4.2.4.** Wykorzystane mechanizmy i technologie

#### **4.2.4.1.** Mechanizm importu i analizy tekstów źródłowych

Mechanizm powinien być w stanie zaimportować i analizować teksty
źródłowe w różnych formatach (np. PDF, DOC, HTML) przy
wykorzystaniu narzędzi do ekstrakcji treści, które umożliwią jednolite
przetwarzanie dokumentów, oczyszczanie ich z elementów nieistotnych (np.
nagłówki, stopki) oraz strukturyzację danych wejściowych.

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie
wystarczająca

**Przykładowe narzędzia:**

- PyPDF2, pdfplumber - ekstrakcja z PDF

- python-docx - przetwarzanie DOCX

- BeautifulSoup - parsowanie HTML

- Tesseract OCR - rozpoznawanie tekstu z obrazów

- Apache Tika - uniwersalny ekstraktor treści

#### **4.2.4.2.** Mechanizm analizy językowej dokumentacji

Mechanizm będzie identyfikował fragmenty zawierające opisy
funkcjonalności, kroków użytkownika, warunków brzegowych oraz
oczekiwanych rezultatów.

W tym celu zostaną przygotowane modele typu transformer (np.
BERT) lub techniki NER (Named Entity Recognition) i klasyfikacji
tekstu, które umożliwią wyodrębnienie istotnych encji, takich jak
operacje, parametry wejściowe czy komunikaty błędów.

Przewiduje się fine-tuning modeli na domenowych danych, co zwiększy
trafność ekstrakcji informacji.

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie
wystarczająca

**Przykładowe techniki NLP:**

- Named Entity Recognition (NER) - identyfikacja kluczowych pojęć

- Dependency Parsing - analiza zależności składniowych

- Text Classification - kategoryzacja fragmentów tekstu

- Semantic Similarity - wykrywanie podobieństw semantycznych

- Intent Recognition - rozpoznawanie intencji w tekście

#### **4.2.4.3.** Mechanizm tworzący strukturę przypadku testowego

Należy opisać w dokumentacji

Dla zidentyfikowanego scenariusza testowego mechanizm powinien być w
stanie utworzyć szkielet testu zawierający m.in. dane wejściowe,
oczekiwane wyniki, opis kroków oraz typ testu (np. funkcjonalny,
walidacyjny).

#### **4.2.4.4.** API integracyjne

Należy opisać w dokumentacji

Integracja mechanizmów z głównym silnikiem TestSpark oraz przygotowanie
API umożliwiającego przesyłanie dokumentacji i odbieranie gotowych
przypadków testowych oraz kodu.

**REQ-MOD-DOC-004:** Moduł musi udostępniać RESTful API do integracji z
zewnętrznymi systemami zarządzania testami.
