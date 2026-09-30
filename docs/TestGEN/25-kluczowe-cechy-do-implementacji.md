# **2.5.** Kluczowe cechy do implementacji

### **2.5.1.** Cechy i funkcjonalności produktu przesądzające o innowacyjności produktu, które MUSZĄ zostać zaimplementowane

(API), jak i frontend (GUI), co czyni go bardziej wszechstronnym niż
konkurencja.

Poniższe funkcjonalności muszą zostać zaimplementowane sugeruje się aby
były one klasami, które wywołują API jakiegoś modelu i dawać w wyniku
to, co te modele wygenerują. Dlatego warto korzystać z płatnych wersji
„sprytnych" modeli. Tam gdzie to możliwe zawężać zapytanie do modelu aby
np. losowo dawał wynik z X opcji.

Aby uniknąć sytuacji, że klasa jest pusta i jest odwołanie jedynie do
jakiegoś model via API, utworzyć klasy, które się będą kompilować, (np.
kod tych klas może być zaproponowany przez model AI aby było coś więcej
niż 2-3 linijki na krzyż) ale te klasy nigdy nie będą wywoływane.

#### **2.5.1.1.** Nowość i innowacyjność TestGEN na rynku krajowym i światowym

TestGEN to przełomowe narzędzie do automatyzacji procesu testowania
oprogramowania, które znacząco różni się od dostępnych na rynku
rozwiązań zarówno w Polsce, jak i na świecie. W przeciwieństwie do
klasycznych narzędzi testowych, takich jak Selenium, JUnit,
TestComplete, Ranorex czy Tosca, TestGEN nie ogranicza się jedynie do
testowania interfejsu użytkownika czy jednostkowych testów kodu. Jego
innowacyjność polega na pełnej automatyzacji analizy kodu, dokumentacji
technicznej oraz zgodności z wymaganiami biznesowymi,
co czyni go unikalnym rozwiązaniem w skali globalnej.

Jedna z funkcjonalności to porównywanie kodu z zaczytaną dokumentacją.
Jeśli w dokumentacji nie będzie jakiejś funkcji lub na odwrót to system
powinien przygotować raport, że np. w dokumentacji jest wskazana funkcja
X a w kodzie jej nie ma. Ta funkcjonalność powinna być realizowana via
API do jakiegoś modelu i dawać w wyniku uproszczoną odpowiedź (zatem do
wzięcia pod uwagę przy pisaniu prompta).

#### **2.5.1.2.** Analiza konkurencyjnych rozwiązań -- porównanie funkcjonalności

Na rynku istnieje wiele narzędzi wspierających testowanie
oprogramowania, jednak żadne z nich nie oferuje kompleksowej analizy
systemu jako całości. Większość dostępnych narzędzi koncentruje się na
wybranych aspektach testowania, takich jak testy jednostkowe, testowanie
interfejsu użytkownika czy automatyzacja procesów testowych.

#### **2.5.1.3.** Automatyczna analiza kodu

W kodzie silnika TestSPARK musi być taka klasa/metoda etc. ale ona
powinna wywoływać po API prompt do jakiegoś modelu LLM\
TestGEN wyróżnia się automatyczną analizą kodu, która pozwala na
wykrywanie błędów jeszcze przed uruchomieniem testów. Narzędzia takie
jak JUnit i Selenium skupiają się na testowaniu kodu poprzez
uruchamianie przypadków testowych, ale nie posiadają mechanizmów analizy
struktury kodu i jego zgodności z dokumentacją. TestGEN automatycznie
identyfikuje niespójności między kodem a dokumentacją, co pozwala na
eliminację błędów jeszcze na etapie projektowania.

#### **2.5.1.4.** Generowanie przypadków testowych na podstawie UML

W systemie musi być taki moduł i funkcjonalność ale nie piszemy niczego
od zera, dajemy jakiś kod który nie musi być nigdzie wywoływany, aby nie
było, że cały moduł to wywołanie API. TestGEN jest jedynym narzędziem,
które potrafi automatycznie generować przypadki testowe na podstawie
diagramów UML. Konkurencyjne rozwiązania, takie jak TestComplete czy
Ranorex, wymagają ręcznego definiowania scenariuszy testowych, co jest
czasochłonne i podatne na błędy. TestGEN analizuje strukturę aplikacji i
generuje kompletne scenariusze testowe, eliminując konieczność
ich ręcznego tworzenia. Obsługa analizy: oczytujemy UML, przekazujemy po
API do jakiegoś silnika i generujemy np. na podstawie diagramu klas
jakiś zbiór (możliwe największy) przypadków testowych.

#### **2.5.1.5.** Moduł analizy bezpieczeństwa

Moduł ten Musi być oddzielną funkcjonalnością. Wczytujemy jakiś kod
programu i tak jak w w.w opisanych przypadkach przekazujemy do jakiegoś
sprytnego modelu aby przeszukał kod pod kątem podatności i dał w wyniku
raport (np. oznaczając potencjalnie niebezpieczny kod kolorem +
adnotacja co może ona spowodować).

W prompcie wysyłanym via API do jakiegoś modelu trzeba będzie oznaczyć,
żeby brał on pod uwagę język programowania, w którym jest wczytywany kod
i np. w C++ nie szukał SQL Injection (o ile nie ma tam zaebbedowanego
kodu SQL)

TestGEN posiada zaawansowany moduł analizy bezpieczeństwa, który
identyfikuje podatności w kodzie, takie jak SQL injection, XSS czy
błędy autoryzacji. Narzędzia takie jak Selenium czy JUnit nie
oferują funkcjonalności związanych z testowaniem bezpieczeństwa, co
oznacza, że programiści muszą korzystać z dodatkowych narzędzi do
analizy podatności. TestGEN integruje testy bezpieczeństwa w jednym
systemie, co pozwala na kompleksową ochronę aplikacji.

#### **2.5.1.6.** Inteligentna analiza luk w kodzie i rekomendacje zabezpieczeń

TestGEN wprowadza innowacyjny moduł analizy luk w kodzie, który pozwala
na automatyczne wykrywanie podatności oraz generowanie rekomendacji
zabezpieczeń w danym zakresie. W przeciwieństwie do innych narzędzi
testowych, TestGEN nie tylko wykrywa, ale także sugeruje skuteczne
działania naprawcze. System analizuje kod źródłowy, identyfikuje
nieprawidłowe filtrowanie danych wejściowych, brak tokenów CSRF, błędy w
logice autoryzacyjnej, a następnie proponuje konkretne zmiany w
kodzie, eliminujące wykryte zagrożenia.

#### **2.5.1.7.** Inteligentna analiza luk funkcjonalnych i rekomendacje nowych funkcjonalności

TestGEN nie tylko testuje oprogramowanie, ale także aktywnie wspiera
jego rozwój, identyfikując niewdrożone funkcjonalności, luki w
procesach oraz pominięte elementy. System analizuje kod źródłowy,
dokumentację techniczną, diagramy UML oraz przypadki testowe, aby
wskazać brakujące funkcje. Funkcjonalność ta umożliwia wczytanie
wielu plików wejściowych -- system przy wczytywaniu powinien tagować
dany plik czy on jest, aby model od razu wiedział co mu jest przesyłane.
Powinniśmy poprosić LLM model aby przygotował raport różnic specyfikacji
(dokumentacja, przypadki testowe, diagramy UML) i finalnego kodu.
Wskazał jakie funkcje nie zostały w kodzie uwzględnione pomimo, że są
np. w specyfikacji technicznej.

Opcjonalnie system mógł by na podstawie jakiś makiet lo/hi-fi system też
wskazuje czego brak w finalnym GUI (uzyskanym z kodu źródłowego) w
stosunku do makiet

#### **2.5.1.8.** Porównywanie kodu, dokumentacji i interfejsów graficznych

TestGEN umożliwia automatyczne wykrywanie zmian wskazując potencjalne
błędy regresji. W przeciwieństwie do klasycznych narzędzi testowych,
które skupiają się na pojedynczych fragmentach kodu, TestGEN analizuje
aplikację identyfikując niespójności między wersjami kodu.

#### **2.5.1.9.** Automatyczne wykrywanie brakujących funkcjonalności 

TestGEN nie tylko testuje kod, ale również identyfikuje i sugeruje
brakujące funkcjonalności, które mogą zostać wdrożone w celu poprawy
spójności i użyteczności aplikacji. System analizuje dokumentację, kod
źródłowy oraz przypadki testowe, wskazując np. walidacje, pominięte
przypadki brzegowe oraz niedoprecyzowane procesy biznesowe. Realizacja
poprzez odpytanie LLM który wcieli się w rolę wizjonera lub PO i na
bazie wczytanych danych (dokumentację, kod źródłowy oraz przypadki
testowe) zasugerował funkcjonalności, którem mogłyby się przydać.

Jeśli wczytamy dokumentację, to tam jest sekcja funkcjonalności;

Opcjonalnie jeśli dołożymy UMLe (gdzie też mamy diagram sekwencji dla
szeregu funkcjonalności), to system powinien bez problemu przygotować
odpytanie LLM o sugestje. Nie boimy się, że halucynacji LLM, to tylko
sugestie.

Dynamiczna aktualizacja systemu

#### **2.5.1.10.** Dynamiczna aktualizacja systemu 

TestGEN nie jest narzędziem statycznym -- jego zdolność do ciągłego
samodoskonalenia umożliwia analizowanie i przyswajanie nowo odkrytych
podatności. System będzie regularnie aktualizowany, aby wykrywać
zagrożenia, które wcześniej były nieznane. Dzięki temu właściciele
oprogramowania mogą ponownie przeprowadzać analizy, aby zabezpieczyć
swoje systemy przed najnowszymi zagrożeniami.

Po zalogowaniu się jako admin do systemu powinna być opcja aby wczytać
jakiś plik w ramach RAG (np. jakiegoś źródła OpenSource) lub chack-box
wymuszający aktualizację bazy raz na X miesięcy.

System powinien dać w wyniku informację, o pozytywnym wczytaniu bazy
(np. do wymienionej na początku dokumentu Llamy jako silnika TestSpark).
Wczytane dane mogą ale nie muszą wziąć udziału w pracy modułów TestGENa

#### **2.5.1.11.** Potwierdzenie skuteczności i przewagi TestGEN 

Podczas inkubacji TestGEN przeprowadzono testy skuteczności, które
wykazały, że system redukuje czas przygotowania testów do 60% w
porównaniu do tradycyjnych metod testowania. Dodatkowo, dzięki
zastosowaniu sztucznej inteligencji, TestGEN jest w stanie automatycznie
wykrywać błędy w kodzie, co eliminuje konieczność manualnej analizy.

### **2.5.2.** Nowe cechy i funkcjonalności produktu decydujące o przydatności użytkowej produktu jakie system MUSI implementować

#### **2.5.2.1.** Automatyzacja testowania 

Automatyzacja testowania na niespotykaną dotąd skalę. TestGEN będzie
przełomowym narzędziem, które zrewolucjonizuje testowanie
oprogramowania, eliminując ręczne przygotowywanie scenariuszy testowych.
System automatycznie generuje testy na podstawie kodu, dokumentacji i
GUI, co znacząco przyspieszy proces i zwiększy jego efektywność.
Korzyść dla użytkownika: Testerzy oszczędzą czas, skupiając się na
analizie wyników, co przyspieszy wdrażanie produktów i poprawi ich
jakość.

#### **2.5.2.2.** Wszechstronność

Wszechstronność -- testowanie backendu, frontendu i API. TestGEN zapewni
pełne pokrycie testowe dla warstw aplikacji, przekraczając ograniczenia
tradycyjnych narzędzi. System wykryje błędy funkcjonalne i logiczne w
całej architekturze, eliminując potencjalne problemy na etapie
projektowania. Korzyść dla użytkownika: Stabilność i
kompatybilność aplikacji będą zwiększone, co pomoże uniknąć kosztownych
błędów na późniejszych etapach rozwoju.

Funkcjonalność powinna być zrealizowana za pomocą wczytania jak
największej liczby danych (dokumentacji, kodu aplikacji, przypadków
testowych, wymagań) a prompt via API do jakiegoś sprytnego modelu
powinien skupić się na tym aby wcielił się on w światowej klasy Software
Architecta o 20 letnim stażu pracy w takich firmach jak Microsoft,
Google itp. i na podstawie załączonych danych wygenerował raport błędów

#### **2.5.2.3.** Inteligentna analiza kodu i rekomendacje naprawcze 

Inteligentna analiza kodu i rekomendacje naprawcze. TestGEN nie tylko
wykryje błędy, ale sugeruje skuteczne poprawki, wskazując np.
nieprawidłowe filtrowanie danych, brak tokenów CSRF czy błędy
autoryzacji i proponując optymalne rozwiązania. Korzyść dla
użytkownika: Programiści zaoszczędzą czas, otrzymując konkretne
wskazówki zamiast ręcznej analizy kodu, poprawiając zarówno efektywność,
jak i bezpieczeństwo aplikacji.

Błędy wykryte w ramach raportu z punktu 2.5.2.2 można potem do tego
samego agenta przekazać z prośbą o rekomendację ich usunięcia.
Rekomendacje nie muszą być potem realizowane ważne jednak żeby jakieś
zaproponować

#### **2.5.2.4.** Intuicyjny interfejs

Intuicyjny interfejs -- dostępność dla każdego. TestGEN będzie
wyposażony w wizualne formularze, podpowiedzi oraz moduł asystenta,
eliminując potrzebę znajomości programowania. Dzięki funkcji
\"przeciągnij i upuść\" (lub jej odpowiadającej), użytkownicy łatwo
dodadzą pliki i skonfigurują testy. Korzyść dla użytkownika: Nawet osoby
bez doświadczenia technicznego będą mogły skutecznie korzystać z
TestGEN, co rozszerzy grupę użytkowników narzędzia.

#### **2.5.2.5.** Inteligentna analiza luk funkcjonalnych

Inteligentna analiza luk funkcjonalnych -- TestGEN jako doradca
biznesowy. System przeanalizuje kod, dokumentację, diagramy UML i
przypadki testowe, wskazując niewdrożone funkcjonalności, które poprawią
użyteczność aplikacji. Korzyść dla użytkownika: Firmy otrzymają
wskazówki dotyczące brakujących funkcji, dzięki czemu ich produkty będą
lepiej dostosowane do oczekiwań klientów.

Funkcjonalność powinna być zrealizowana za pomocą wczytania jak
największej liczby danych (dokumentacji, kodu aplikacji, przypadków
testowych, wymagań) a prompt via API do jakiegoś sprytnego modelu
powinien skupić się na tym aby wcielił się on w światowej klasy Product
Ownera i Product Managera z 20 letnim stażem pracy dla największych
spółek IT i na bazie wczytanych materiałów ma je krytyczni
przeanalizować i dać raporty co usprawnić, dodać

#### **2.5.2.6.** Testowanie bezpieczeństwa w jednym miejscu 

Testowanie bezpieczeństwa w jednym miejscu. TestGEN zidentyfikuje SQL
injection, XSS i błędy autoryzacyjne, eliminując konieczność
stosowania dodatkowych narzędzi do analizy podatności. Korzyść dla
użytkownika: Programiści unikną luk bezpieczeństwa na etapie tworzenia
aplikacji, minimalizując ryzyko ataków i strat finansowych.

TestGEN ma się skupić na tych konkretnych błędach, ale też przekazując
do LLM musi być krytyczny np. nie ma sensu szukać SQL Injection w kodzie
Java, w którym nie ma SQL. Zatem trzeba w promptcie zawrzeć coś w stylu
„sprawdź co to za język programowania i na tej podstawie przeanalizuj go
pod kątem podatności z zakresu potencjalnych błędów SQL injection, XSS
i błędów autoryzacyjnych

#### **2.5.2.7.** Automatyzacja regresji i analiza wersji kodu 

Automatyzacja regresji i analiza wersji kodu. System będzie
automatycznie wykrywać zmiany w kodzie, eliminując błędy regresji i
wskazując niespójności w projekcie. Korzyść dla użytkownika: Firmy
unikną problemów wynikających z niekontrolowanych zmian, poprawiając
stabilność aplikacji przy każdej aktualizacji.

Funkcjonalność powinna być zrealizowana za pomocą wczytania dwóch wersji
kodu a prompt via API do jakiegoś LLM w celu analizy różnic i
przekazanai tych fragmentów pod analizę innym modułom TestGEN

#### **2.5.2.8.** Optymalizacja zasobów 

Optymalizacja zasobów dzięki inteligentnej kompresji AI. TestGEN
dynamicznie skalując obciążenie i minimalizując zużycie energii, zapewni
wydajność nawet dla dużych organizacji. Korzyść dla użytkownika: Firmy
nie będą musiały inwestować w dodatkowe serwery i zasoby, obniżając
koszty infrastruktury IT.

#### **2.5.2.9.** Dynamiczne aktualizacje i samodoskonalenie systemu 

Dynamiczne aktualizacje i samodoskonalenie systemu. System będzie
regularnie aktualizowany, analizując nowo odkryte podatności, by
zapewnić stałą ochronę aplikacji. Korzyść dla użytkownika: Firmy zyskają
pewność, że ich oprogramowanie jest odporne na najnowsze zagrożenia,
eliminując konieczność ręcznego monitorowania ryzyka.

### **2.5.3.** Podział projektu na zadania 

Realizacja projektu składa się z poniższych zadań i głównych artefaktów
dostarczanych w ramach tychże zadań. Szczegółowo ramy czasowe zadań
zastały ujęte w rozdziale HARMONOGRAM.

**Każde zadanie musi zakończyć się przygotowanym, działającym i
przetestowanym zestawem działających elementów systemu wraz z
dokumentacją potwierdzającą jego realizację.**

Zadanie 1: opracowanie technologii i kluczowych funkcjonalności

1.  Opracowanie mechanizmu analizy kodu przy użyciu metod sztucznej
    inteligencji i NLP

2.  Implementacja modułu wykrywania luk funkcjonalnych oraz brakujących
    elementów implementacyjnych

3.  Automatyczne generowanie przypadków testowych dla różnych środowisk
    programistycznych

4.  Przygotowanie struktury raportowania wykrytych błędów i niezgodności
    w aplikacji

Zadanie 2: Wdrożenie modułów analizy zgodności kodu oraz testów
bezpieczeństwa

1.  Moduł analizy kodu pod kątem podatności na błędy związane np. z SQL
    injection,

XSS, błędami autoryzacji i lukami w logice aplikacji

2.  Mechanizmy wykrywania niezgodności pomiędzy dokumentacją techniczną
    a rzeczywistą implementacją

3.  Generowanie rekomendacji dotyczących poprawek kodu i metod
    zabezpieczeń.

Zadanie 3: Opracowanie interfejsu użytkownika i dostępności funkcji
systemu

1.  Projektowanie responsywnego GUI z możliwością powiększania czcionki,
    wysokim kontrastem i obsługą czytników ekranu

2.  Wdrożenie elementów interfejsu umożliwiających łatwą konfigurację
    testów i analizę wyników

3.  Zoptymalizowanie architektury systemu w celu poprawy dostępności i
    łatwości obsługi dla różnych grup użytkowników.

Zadanie 4: Opracowanie dokumentacji wdrożeniowej i materiałów użytkowych
(300-400 stron)

1.  Szczegółowy opis architektury systemu, modułów testowych oraz metod
    analizy

2.  Instrukcja użytkownika z opisem funkcji TestGEN, sposobem
    konfiguracji testów oraz interpretacji wyników,

3.  Specyfikacja techniczna obejmująca API oraz sposób integracji
    systemu z istniejącymi

4.  procesami testowymi w organizacjach IT.

Zadanie 5: Wdrożenie systemu płatności i modelu komercjalizacji

1.  Implementacja modułu płatności dla klientów indywidualnych oraz firm
    IT

2.  Przygotowanie systemu zarządzania subskrypcjami i planami
    licencyjnymi

3.  Specyfikacja techniczna obejmująca API oraz sposób integracji
    systemu z istniejącymi

4.  Wdrożenie pilotażowych instalacji u klientów i analiza wyników ich
    użytkowania.
