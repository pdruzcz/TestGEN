# **4.5.** Moduł analizy luk funkcjonalnych w kodzie i generowania inteligentnych rekomendacji rozszerzeń

### **4.5.1.** Opis ogólny modułu

Moduł analizy luk funkcjonalnych w kodzie i generowania inteligentnych
rekomendacji rozszerzeń dla oprogramowania aplikacyjnego oraz
wbudowanego ma za zadanie nie tylko identyfikację niespójności w
testowanym oprogramowaniu, ale także aktywny udział w jego rozwoju
poprzez proponowanie brakujących funkcji, które powinny zostać wdrożone
dla poprawy spójności i użyteczności biznesowej.

**Technologie:** Wykorzystane zostaną technologie NLP, techniki
mapowania semantycznego oraz analizy ontologicznej.

**REQ-MOD-FUNC-001:** System musi identyfikować rozbieżności między
kodem a dokumentacją biznesową i techniczną.

**REQ-MOD-FUNC-002:** System musi generować rekomendacje nowych
funkcjonalności na podstawie analizy wieloźródłowej.

Moduł wykorzysta zintegrowaną analizę z wielu źródeł, np. kodu
źródłowego, dokumentacji technicznej, diagramów UML oraz przypadków
testowych, aby zidentyfikować niewdrożone funkcjonalności, luki w
procesach oraz pominięte elementy, które nie zostały uwzględnione na
etapie implementacji.

### **4.5.2.** Funkcjonalność analizy zgodności kodu z dokumentacją

#### **4.5.2.1.** Opis funkcjonalności

Analiza struktury kodu źródłowego i jego zgodności z dokumentacją -
TestGEN automatycznie identyfikuje niespójności między kodem a
dokumentacją. Jeśli do TestGEN wgra się kod oprogramowania oraz
dokumentację, to system powinien sprawdzić, czy w kodzie są odwołania do
funkcji.

Audyt bezpieczeństwa kodu (identyfikacja podatności) pod kątem analizy
zgodności z dokumentacją np. czy w kodzie są funkcje/procedury o nazwach
wspomnianych w dokumentacji.

- Porównywanie dokumentacji technicznej z implementacją kodu

- Generowanie raportów wskazujących brakujące funkcjonalności i
  zalecenia dotyczące poprawy jakości oprogramowania

#### **4.5.2.2.** Szczegółowy przepływ działania

**Przykładowy przepływ:**

\[Wczytanie dokumentacji i kodu\]

↓

\[Analiza dokumentacji → ekstrakcja wymagań funkcjonalnych\]

↓

\[Analiza kodu → ekstrakcja struktury i funkcji\]

↓

\[Porównanie semantyczne LLM\]

↓

\[Identyfikacja braków i niespójności\]

↓

\[Raport + rekomendacje + testy automatyczne\]

Celem modułu Analizy Zgodności Kod--Dokumentacja w systemie TestGEN
jest:

- sprawdzenie, czy implementacja odpowiada temu, co opisano w
  dokumentacji technicznej lub projektowej,

- wykrycie brakujących lub nadmiarowych funkcji,

- identyfikacja potencjalnych luk bezpieczeństwa lub błędów w logice,
  wynikających z rozbieżności między dokumentacją a kodem.

Proces można podzielić na sześć logicznych etapów:

##### Etap 1: Wczytanie danych wejściowych

Użytkownik (np. QA Engineer lub Software Architect) wgrywa do TestGEN:

- Dokumentację techniczną lub projektową (np. pliki .md, .pdf, .docx,
  .txt, .html)

- Kod źródłowy projektu (np. repozytorium ZIP, link do Git, folder z
  .py, .js, .java itp.)

- Opcjonalnie: diagramy UML lub pliki OpenAPI / Swagger, jeśli
  istnieją

System rozpoznaje język programowania, strukturę projektu i format
dokumentacji.

##### Etap 2: Ekstrakcja informacji z dokumentacji

Moduł LLM Document Analyzer analizuje treść dokumentacji i wyodrębnia z
niej:

- Listę funkcji, klas, modułów i API, które powinny istnieć

- Opisy ich parametrów, typów danych, efektów działania, wyjątków, ról
  użytkowników, poziomów autoryzacji

- Powiązania między komponentami (np. \"Moduł UserService korzysta z
  AuthManager\")

**Wynikiem tego etapu może być struktura danych w formacie:**

{ \"functions_expected\": \[ { \"name\": \"authenticate_user\",
\"description\": \"Waliduje dane logowania użytkownika i zwraca token
JWT\", \"params\": \[\"username\", \"password\"\], \"returns\": \"JWT
token\", \"security\": \[\"check_password_hash\", \"CSRF token
required\"\] }, { \"name\": \"reset_password\", \"description\":
\"Wysyła e-mail resetujący hasło użytkownika\", \"params\":
\[\"user_email\"\], \"returns\": \"status_code\" } \] }

##### Etap 3: Analiza kodu źródłowego

Moduł Code Analyzer dokonuje analizy kodu w następujący sposób:

- Parsuje składnię i strukturę AST (Abstract Syntax Tree) dla każdego
  pliku źródłowego

- Ekstraktuje listę funkcji, metod, klas, endpointów API i procedur SQL
  wraz z ich sygnaturami, komentarzami i atrybutami bezpieczeństwa

- Tworzy lokalną reprezentację kodu

{ \"functions_found\": \[ {\"name\": \"authenticate_user\", \"params\":
\[\"username\", \"password\"\], \"returns\": \"token\"}, {\"name\":
\"reset_password_v2\", \"params\": \[\"email\"\], \"returns\":
\"bool\"}, {\"name\": \"get_user\", \"params\": \[\"id\"\], \"returns\":
\"UserObject\"} \] }

- Wyszukuje odwołania do funkcji, które pojawiają się w dokumentacji -
  zarówno pod względem nazwy, jak i semantyki (LLM potrafi rozpoznać
  funkcje o podobnym znaczeniu mimo różnic w nazwie, np. reset_password
  vs reset_user_password)

##### Etap 4: Porównanie kodu z dokumentacją

LLM łączy obie struktury (z dokumentacji i kodu) i przeprowadza
semantyczne porównanie:

- **Zgodność nazw funkcji:** Czy wszystkie funkcje wymienione w
  dokumentacji rzeczywiście istnieją w kodzie?

- **Zgodność parametrów:** Czy funkcje mają takie same parametry, typy i
  nazwy jak opisano?

- **Zgodność logiki działania (opis vs implementacja):** Czy funkcja
  wykonuje operacje zgodne z opisem (np. w dokumentacji: \"sprawdza
  uprawnienia\", a w kodzie brak sprawdzania autoryzacji)? Czy kod
  implementuje wszystkie kroki opisane w dokumentacji?

- **Zgodność komponentów:** Czy struktura klas, modułów i zależności
  (np. UserService → DatabaseManager) jest zgodna z projektowaną
  architekturą?

- **Zgodność API:** Czy endpointy REST/GraphQL zgodne są z opisanymi w
  dokumentacji (metoda, ścieżka, schemat odpowiedzi)?

- **Zgodność bezpieczeństwa:** Czy funkcje, które powinny uwzględniać
  np. CSRF, XSS czy walidację wejścia, rzeczywiście mają to
  zaimplementowane w kodzie?

##### Etap 5: Wykrywanie niespójności i luk

Na tym etapie TestGEN identyfikuje różne typy problemów:

  ------------------------------------------------------------------------------
  **Typ niespójności**     **Opis przykładowy**                  **Priorytet**
  ------------------------ ------------------------------------- ---------------
  🔴 Brak funkcji opisanej Dokumentacja wspomina reset_password, Krytyczny
  w dokumentacji           ale funkcja nie istnieje              

  🟠 Funkcja istnieje, ale reset_password_v2(email) zamiast      Wysoki
  różni się sygnaturą      reset_password(user_email)            

  🟡 Brak weryfikacji      Dokumentacja zakłada walidację        Wysoki
  bezpieczeństwa           tokenu, ale kod jej nie zawiera       

  🟢 Funkcja nadmiarowa    Kod zawiera funkcję, której nie ma w  Średni
                           dokumentacji                          

  🔵 Rozbieżność logiczna  Dokumentacja opisuje zapis do DB, ale Średni
                           kod tylko zwraca dane                 
  ------------------------------------------------------------------------------

##### Etap 6: Generowanie raportu zgodności

System generuje raport w formacie HTML / PDF / JSON:

**Raport zgodności kodu z dokumentacją**\
\
**Projekt:** AuthService v2.3\
**Data analizy:** 2025-10-13\
**Analizowane pliki:** 27\
**Język:** Python\
\
**Podsumowanie:**\
✅ 14 funkcji zgodnych z dokumentacją\
❌ 3 funkcje brakujące\
⚠️ 2 funkcje rozbieżne logicznie\
➕ 4 funkcje nadmiarowe

**Przykład niespójności:**

  -------------------------------------------------------------------------------
  **Dokumentacja**             **Kod**        **Typ problemu** **Rekomendacja**
  ---------------------------- -------------- ---------------- ------------------
  reset_password(user_email)   brak           Funkcja          Dodać
                                              brakująca        implementację
                                                               resetowania hasła

  authenticate_user() - wymaga brak walidacji Luka             Dodać
  walidacji CSRF               tokena         bezpieczeństwa   csrf_protect()

  get_user_by_id(id)           get_user(id)   Rozbieżność      Ujednolicić nazwy
                                              semantyczna      i opis
  -------------------------------------------------------------------------------

System w raporcie niespójności wskazuje rekomendacje:

- Propozycje implementacji brakujących funkcji (np. szkielety kodu w
  Pythonie/JavaScript)

- Sugestie poprawy dokumentacji, jeśli implementacja jest poprawna, ale
  dokumentacja nieaktualna

- Zalecenia dot. bezpieczeństwa, np. dodanie walidacji danych
  wejściowych, obsługi błędów, lub tokenów CSRF

- Automatyczne generowanie testów jednostkowych / integracyjnych
  sprawdzających zgodność implementacji z opisem dokumentacji

### **4.5.3.** Funkcjonalność podpowiedzi dotyczących błędów

### W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca

### Musi natomiast zostać uwzględnione w dokumentacji

#### **4.5.3.1.** Opis funkcjonalności

Moduł Analizy błędów kodu i podpowiedzi napraw ma pomóc w:

- Szybkim wykrywaniu błędów składniowych, logicznych i semantycznych

- Wykrywaniu niezgodności z dokumentacją techniczną lub standardami
  projektu

- Sugerowaniu konkretnych poprawek (z gotowym kodem lub fragmentem do
  wklejenia)

- Edukacyjnym wyjaśnianiu, dlaczego dany błąd powstał i jak go unikać w
  przyszłości

**Przykładowy przebieg:**

\[Wczytanie kodu + dokumentacji\]

↓

\[Analiza składniowa → błędy formalne\]

↓

\[Analiza semantyczna → błędy logiczne\]

↓

\[Porównanie z dokumentacją → brakujące funkcje / niezgodności\]

↓

\[Generacja raportu i sugestii poprawek\]

↓

\[Integracja z CI/CD lub IDE → automatyczne komentarze i poprawki\]

#### **4.5.3.2.** Szczegółowy przepływ działania

##### 1. Wejście systemu

System TestGEN przyjmuje jako dane wejściowe:

- Kod źródłowy projektu (np. pojedyncze pliki .py, .js, .java, .cpp lub
  cały folder repozytorium)

- Dokumentację techniczną (opcjonalnie, aby lepiej zrozumieć kontekst
  biznesowy i standardy kodowania)

- Reguły stylu lub konfigurację lintera, jeśli projekt korzysta z takich
  (np. .pylintrc, .eslintrc, .editorconfig)

##### 2. Analiza składniowa (syntactic analysis)

**Cel:** Wykrycie błędów formalnych w kodzie, takich jak:

- Brak średnika, nawiasu, cudzysłowu

- Źle zagnieżdżone bloki

- Literówki w nazwach zmiennych/funkcji

- Niezamknięte komentarze

- Błędne formatowanie (np. mieszanie tabów i spacji)

**Mechanizm:**

- TestGEN tworzy drzewo składniowe AST (Abstract Syntax Tree) dla
  każdego pliku

- Jeśli parser napotka błędy, LLM analizuje komunikat
  kompilatora/interpretera i fragment kodu, w którym wystąpił błąd

**Silnik TestSpark (LLM):**

- Rozumie kontekst języka

- Wykrywa, gdzie brakuje elementu składniowego (np. średnika)

- Sugeruje poprawkę, podając fragment poprawionego kodu

**Przykład:**

Kod:

function add(a, b) { return a + b } console.log(add(3,4))

Raport:

**Błąd:** Brak średnika po instrukcji \'return a + b\'.\
\
**Sugestia naprawy:**

function add(a, b) { return a + b; }

##### 3. Analiza semantyczna (logiczna)

**Cel:** Wykrycie błędów nie w składni, ale w sensie działania kodu,
np.:

- Użycie niezdefiniowanej zmiennej

- Błędne przekazanie parametrów do funkcji

- Błędy typów danych (np. dodanie liczby do łańcucha znaków)

- Błędne użycie API, brak obsługi wyjątków

**Mechanizm:**

- System wykonuje statyczną analizę kodu (data flow) - śledzi zależności
  między zmiennymi, wywołaniami funkcji i zwracanymi wartościami

- LLM ocenia poprawność logiki na podstawie kontekstu:

  - np. \"funkcja divide(a, b) nie sprawdza, czy b != 0\"

  - \"instrukcja await użyta poza funkcją async\"

- Na tej podstawie generuje opisowy raport oraz sugestię poprawki

**Przykład:**

Kod:

def divide(a, b): return a / b

Raport TestGEN:

**Błąd logiczny:** Funkcja divide nie sprawdza, czy b != 0.\
\
**Sugestia naprawy:**

def divide(a, b): if b == 0: raise ValueError(\"Division by zero\")
return a / b

##### 4. Analiza zgodności z dokumentacją i konwencjami

Jeśli system ma dostęp do dokumentacji (np. pliku API Spec, README,
opisów klas):

- LLM porównuje deklaracje funkcji i parametrów w kodzie z tymi
  opisanymi w dokumentacji

- Wykrywa:

  - Brakujące lub nadmiarowe parametry

  - Niezgodność typów zwracanych danych

  - Brak docstringów lub komentarzy wymaganych przez standard projektu

  - Nieprzestrzeganie naming convention (np. camelCase zamiast
    snake_case)

- Na tej podstawie tworzy raport zgodności i rekomendacje

**Przykład:**

Dokumentacja:

Funkcja get_user powinna zwracać obiekt typu User z polem email

Kod:

def get_user(id): return id

Raport TestGEN:

**Niezgodność z dokumentacją:**\
- Funkcja \`get_user\` powinna zwracać obiekt \`User\`, ale zwraca
wartość typu int.\
\
**Sugestia:**

return User(id=id, email=\...)

##### 5. Generowanie raportu błędów i sugestii

Po zakończeniu analizy, TestGEN generuje kompletny raport błędów i
poprawek w formatach:

- HTML / PDF (czytelny raport dla dewelopera)

- JSON (dla integracji z CI/CD)

- Markdown (do commit message lub pull requestu)

**Struktura raportu:**

  ---------------------------------------------------------------------------------------------------------------------------------------------------------
  **[ID]**   **[Plik]**          **[Linia]**   **[Typ błędu]** **[Opis]**      **[Sugestia]**         **[Poziom naprawy]**   
  ----------------- -------------------------- -------------------- ---------------------- ---------------------- ------------------- ---------------------
  [001]      [main.js]           [12]          [Syntax]        [Brak średnika]   [Dodaj ; po         [Niski]
                                                                                 return      

  [002]     [auth.py]            [44]          [Logic]         [Brak obsługi     [Dodaj if b ==      [Wysoki]
                                                               dzielenia przez   0:]          
                                                               zero]                               

  [003]      [user_service.py]   [17]          [Conformance]   [Zwracany typ    [Zwróć obiekt       [Średni]
                                                               niezgodny z      User]        
                                                               dokumentacją]                       
  ---------------------------------------------------------------------------------------------------------------------------------------------------------

### **4.5.4.** Funkcjonalność podpowiedzi dotyczących nowych funkcjonalności

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca
Musi natomiast zostać uwzględnione w dokumentacji

#### **4.5.4.1.** Opis funkcjonalności

TestGEN nie tylko testuje oprogramowanie, ale także aktywnie wspiera
jego rozwój, identyfikując niewdrożone funkcjonalności, luki w procesach
oraz pominięte elementy.

System analizuje dostępne materiały takie jak kod źródłowy, dokumentację
techniczną, diagramy UML, oraz przypadki testowe, aby wskazać brakujące
funkcje i sugeruje potencjalne ulepszenia aplikacji po analizie
dokumentacji.

Celem modułu jest proaktywne wspieranie rozwoju systemu IT poprzez
analizę kodu, dokumentacji i istniejących testów, aby:

- Wykrywać brakujące lub niezaimplementowane funkcjonalności

- Sugerować ulepszenia na poziomie produktu, architektury lub logiki
  aplikacji

- Usprawniać proces projektowania i wdrażania zmian poprzez automatyczne
  raporty z rekomendacjami

#### **4.5.4.2.** Szczegółowy przepływ działania

##### 1. Wczytanie i przygotowanie danych wejściowych

System przyjmuje zestaw danych źródłowych:

- **Kod źródłowy** (z różnych modułów aplikacji)

- **Dokumentację techniczną i funkcjonalną** (przynajmniej pliki
  Markdown, Confluence export, PDF)

- **Diagramy UML** (przynajmniej use case, class, activity,
  sequence)

- **Zestaw przypadków testowych** (przynajmniej w formacie Gherkin,
  test plans, test suites)

Powyższe formaty są must have można pokusić się o większą ilość

Na tym etapie TestGEN dokonuje:

- Ujednolicenia formatu danych

- Ekstrakcji kluczowych informacji (np. nazw klas, funkcji, endpointów,
  komponentów UI, opisów funkcji biznesowych)

- Stworzenia semantycznego modelu aplikacji, łączącego kod i
  dokumentację

##### 2. Analiza zgodności funkcjonalnej (feature mapping)

Silnik TestSpark (LLM) analizuje powiązania między:

- Funkcjami wymienionymi w dokumentacji a rzeczywistymi metodami w
  kodzie

- Przypadkami użycia (UML) a ich implementacjami

- Planowanymi funkcjonalnościami (np. \"powiadomienia push\") a ich
  śladami w repozytorium kodu

System wykrywa:

- Funkcje opisane w dokumentacji, ale brakujące w kodzie

- Funkcje zaimplementowane w kodzie, ale nieopisane w dokumentacji

- Przerwane lub niekompletne przepływy (np. brak implementacji obsługi
  błędów, walidacji, logowania)

##### 3. Analiza heurystyczna i semantyczna

Na podstawie wzorców projektowych i wiedzy o typowych komponentach
aplikacji (np. e-commerce, CRM, ERP, SaaS), TestGEN:

- Wykrywa obszary wymagające rozwoju, np.:

  - Brak systemu powiadomień

  - Brak historii zmian

  - Brak walidacji danych

  - Brak mechanizmów backupu

- Porównuje projekt z bazą wiedzy o najlepszych praktykach (np. OWASP,
  ISO/IEC 25010, Clean Architecture, UX heuristics)

- Analizuje użycie API i zależności między modułami, szukając
  niezaadresowanych wymagań biznesowych (np. brak logiki dla rzadkich
  scenariuszy użytkownika)

##### 4. Generowanie raportu z rekomendacjami

System tworzy czytelny raport, który może zawierać sekcje:

TestGen generuje poniższe raporty poprzez wysłanie do LLM poprzez API
odpowiednich promptów

**🔹 \"Brakujące funkcjonalności\"**

Lista funkcjonalności opisanych w dokumentacji, ale **niewystępujących w
kodzie**.

Każda pozycja zawiera:

- Nazwę funkcji lub modułu

- Odniesienie do fragmentu dokumentacji

- Sugerowane miejsce w kodzie, gdzie można ją zaimplementować

**🔹 \"Potencjalne ulepszenia\"**

Na podstawie analizy kodu i znanych wzorców system proponuje:

- Nowe funkcje, które zwiększyłyby wartość aplikacji (np. logowanie
  działań użytkownika, cache danych, dark mode)

- Usprawnienia architektury (np. wydzielenie modułu autoryzacji, poprawa
  bezpieczeństwa API)

- Rekomendacje UX/UI, jeśli analizowano ekrany użytkownika

**🔹 \"Uzasadnienie\"**

Dla każdej propozycji system generuje opis:

- Dlaczego dana funkcjonalność jest potrzebna

- Jakie problemy rozwiązuje

- Jakie ryzyka eliminuje

- Na jakie standardy lub praktyki się powołuje

##### 5. Możliwość automatycznego wdrożenia rekomendacji

Na życzenie użytkownika TestGEN może:

- Wygenerować szkielet kodu dla nowych funkcjonalności (np. puste
  metody, endpointy, klasy)

- Dodać nowe przypadki testowe w formacie Gherkin lub unittest do
  przyszłej implementacji

- Zintegrować raport z systemami zarządzania zadaniami (np. Jira, Azure
  DevOps), tworząc automatyczne backlogi z rekomendacjami

Po wygenerowaniu raportu powinno pojawić się jakieś okienko tak/nie i po
wyborze tak TestGEN wysłanie do LLM poprzez API prompta z prośbą o
generację powyższych

**[Przykładowy raport rekomendacji:]**

  ----------------------------------------------------------------------------------------------------------------------------------------------
  **[Kategoria]**          **[Funkcjonalność]**        **[Status]**            **[Rekomendacja]**    **[Uzasadnienie]**
  ------------------------ ----------------------------- ------------------------------ ---------------------------- ---------------------------
  [Dokumentacja vs         [Eksport raportów CSV       [Brak implementacji]    [Dodać moduł          [Funkcja opisana w
  kod]                                                                         export_reports()]     dokumentacji §4.2, brak w
                                                                                                     repozytorium]

  [Usprawnienie            [Obsługa błędów               [Częściowo           [Uzupełnić o           [Brak pełnej obsługi błędów
  architektury]            logowania]                    zaimplementowana]    komunikaty U]X         w UI]

  [Nowa                    [Historia zmian w             [Niezaimplementowana   [Dodać tabelę        [Poprawia zgodność z RODO i
  funkcjonalność]          profilu]                                             \"user_audit_log\"]  kontrolę operacji użytkownika]
  ----------------------------------------------------------------------------------------------------------------------------------------------

### **4.5.5.** Wykorzystane mechanizmy i technologie

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły
mogą ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca
Musi natomiast zostać uwzględnione w dokumentacji

#### **4.5.5.1.** Parser wieloźródłowy

Parser umożliwi przetwarzanie danych wejściowych w różnych formatach
(np. Markdown, PDF, DOCX, UML). Informacje te zostaną ujednolicone
poprzez rozwiązanie semantyczne i technologie NLP, co pozwoli na ich
analizę w jednolitym kontekście.

**Przykładowe narzędzia parsowania:**

- Apache Tika - uniwersalny ekstraktor treści

- Pandoc - konwerter formatów dokumentów

- python-docx, PyPDF2 - specjalistyczne parsery

- XMI parsers - dla diagramów UML

Przygotowane być klasy i metody powinny odnosić się do tych bibliotek
być może należy je dodać do kodu.

#### **4.5.5.2.** Mechanizm detekcji niespójności

Umożliwia zestawienie funkcji opisanych w dokumentacji z rzeczywistą
implementacją oraz istniejącymi testami. Wykorzystane zostaną techniki
mapowania semantycznego oraz analizy ontologicznej, które pozwolą na
precyzyjne wykrycie brakujących lub niedoprecyzowanych funkcjonalności.

#### **4.5.5.3.** Mechanizm rekomendowania nowych funkcjonalności

Automatyczne sugerowanie elementów, które powinny zostać wdrożone, takie
jak:

- Brakujące walidacje

- Pominięte przypadki brzegowe

- Niepełne ścieżki alternatywne

- Niedoprecyzowane procesy biznesowe

Sugestie zostaną przedstawione w formie czytelnych raportów oraz
artefaktów testowych, które mogą zostać bezpośrednio wykorzystane przez
programistów.
