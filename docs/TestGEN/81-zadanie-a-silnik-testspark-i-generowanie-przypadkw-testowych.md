# **8.1.** Zadanie A - Silnik TestSpark i generowanie przypadków testowych

### **8.1.1.** Szczegóły zadania

**Termin realizacji:** 2 stycznia 2026 - 31 maja 2026 (5 miesięcy)

**Cel:** Zaprojektowanie i implementacja kluczowego komponentu systemu
TestGEN, tj. silnika TestSpark.

Celem zadania jest zaprojektowanie i implementacja kluczowego komponentu
systemu TestGEN, tj. silnika TestSpark. Silnik ten, wykorzystując
zaawansowane algorytmy sztucznej inteligencji, umożliwi pełną
automatyzację analizy dokumentacji technicznej, kodu źródłowego,
diagramów UML oraz ekranów GUI, generując na tej podstawie przypadki
testowe oraz odpowiadający im kod testów. Projekt ma na celu znaczące
ograniczenie pracy manualnej w procesie testowania i zwiększenie
efektywności oraz pokrycia testowego. Podjęte zostaną następujące
kluczowe czynności w ramach realizacji zadania.

1\. Prace rozpoczną się od analizy danych wejściowych -- kodu
źródłowego, dokumentacji użytkownika, diagramów UML oraz zrzutów ekranów
GUI. Dane te zostaną sklasyfikowane i zamodelowane zgodnie z ich
strukturą oraz przeznaczeniem.

Celem jest opracowanie ujednoliconej reprezentacji danych,
umożliwiającej ich dalsze przetwarzanie przez systemy AI.

2\. Kolejnym krokiem będzie zaprojektowanie i wdrożenie komponentów
ekstrakcji informacji. W tym celu zastosowane zostaną metody NLP (np.
NER czy modeli typu transformer), pozwalające na identyfikację
kluczowych pojęć, funkcji, warunków brzegowych i wyników opisanych w
dokumentacji. W przypadku kodu źródłowego wykorzystane zostaną techniki
statycznej analizy, umożliwiające wyodrębnienie struktur logicznych,
punktów wejścia i zależności między komponentami. Diagramy UML zostaną
przetworzone w celu wydobycia przepływów sterowania i logiki biznesowej,
natomiast analiza GUI pozwoli na określenie interaktywnych elementów
interfejsu i możliwych ścieżek działania użytkownika.

3\. Na podstawie przetworzonych danych, opracowane zostaną mechanizmy
automatycznego generowania różnorodnych przypadków testowych.
Rozwiązanie będzie uwzględniać zidentyfikowane przepływy biznesowe,
zależności między funkcjonalnościami, warunki brzegowe oraz potencjalne
ścieżki wykonania. Uwzględnione zostaną scenariusze testowe -- np.
pozytywne, negatywne i brzegowe -- jak również zidentyfikowane przepływy
biznesowe, zależności i warunki wykonania. Wygenerowane przypadki
testowe będą posiadały ustrukturyzowaną formę, zawierającą kroki, dane
wejściowe, oczekiwane rezultaty i warunki wstępne.

4\. Ostatni etap obejmuje stworzenie modułu generowania kodu testów. Na
podstawie opisów przypadków testowych oraz danych źródłowych, silnik
będzie mógł dla wybranych przypadków utworzyć kod dla frameworku
testowego (np. JUnit, NUnit, pytest). W tym celu wykorzystane zostaną
techniki szablonowe oraz inteligentne rozwiązania mapujące scenariusze
testowe na konkretne instrukcje kodu. Generowane testy będą gotowe do
uruchomienia i dostosowane do specyfiki interfejsów systemu (API, GUI).

Rezultatem zadania będzie w pełni funkcjonalny silnik TestSpark
automatycznie generujący przypadki testowe i kod. Ocena obejmie jego
zdolność do wygenerowania co najmniej 10 unikalnych przypadków testowych
na podstawie dostarczonych danych (dokumentacja, kod, UML, GUI). Każdy
przypadek testowy zawiera jasno określone kroki, dane wejściowe oraz
oczekiwane rezultaty. Wygeneruje dla wybranych przyp. szkielet kodu
testowego w wybranym frameworku (np. JUnit). Rezultaty zostaną ocenione
manualnie pod kątem poprawności i jakości wygenerowanych artefaktów.
Sprawdzona będzie ich adekwatność względem danych wejściowych.
Dodatkowym wynikiem będzie dokumentacja projektowa opisująca
architekturę silnika, zastosowane algorytmy, proces przetwarzania danych
oraz wyniki testów prototypu

### **8.1.2.** Kluczowe milestone\'y

+------------------------+------------+------------------------------------+
| **Milestone**          | **Data**   | **Deliverables**                   |
+========================+============+====================================+
| M1.1: Projekt          | 31.01.2026 | - Diagram architektury silnika     |
| architektury           |            |   TestSpark                        |
|                        |            |                                    |
|                        |            | - Specyfikacja API wewnętrznych    |
|                        |            |                                    |
|                        |            | - Wybór modeli AI/ML               |
+------------------------+------------+------------------------------------+
| M1.2: Moduł analizy    | 28.02.2026 | - Parser AST dla 5+ języków        |
| kodu                   |            |                                    |
|                        |            | - Ekstraktor metadanych            |
|                        |            |                                    |
|                        |            | - Prototyp analizy                 |
+------------------------+------------+------------------------------------+
| M1.3: Moduł analizy    | 31.03.2026 | - NLP pipeline                     |
| dokumentacji           |            |                                    |
|                        |            | - Ekstrakcja wymagań               |
|                        |            |                                    |
|                        |            | - Klasyfikator dokumentów          |
+------------------------+------------+------------------------------------+
| M1.4: Moduł analizy    | 30.04.2026 | - Parser UML (XMI, PlantUML)       |
| UML/GUI                |            |                                    |
|                        |            | - Analiza wizualna GUI (OCR + CNN) |
|                        |            |                                    |
|                        |            | - Rekonstrukcja user flows         |
+------------------------+------------+------------------------------------+
| M1.5: Generator testów | 31.05.2026 | - Generowanie opisowych test cases |
|                        |            |                                    |
|                        |            | - Generowanie kodu (pytest, JUnit, |
|                        |            |   Selenium)                        |
|                        |            |                                    |
|                        |            | - Integracja wszystkich modułów    |
|                        |            |                                    |
|                        |            | - Dokumentacja techniczna          |
+------------------------+------------+------------------------------------+

### **8.1.3.** Kryteria akceptacji Zadania A

**Kryteria sukcesu:**

- Silnik TestSpark generuje minimum 10 unikalnych przypadków testowych
  na podstawie dostarczonych danych

- Każdy przypadek testowy zawiera jasno określone kroki, dane wejściowe
  oraz oczekiwane rezultaty

- System generuje szkielet kodu testowego w wybranym frameworku (np.
  JUnit, pytest)

- Rezultaty są weryfikowane manualnie pod kątem poprawności i jakości

- Sprawdzona adekwatność względem danych wejściowych

- Dokumentacja projektowa opisująca architekturę, algorytmy i wyniki
  testów
