# **3.1.** Silnik TestSpark - komponenty podstawowe

Silnik TestSpark stanowi rdzeń systemu TestGEN i jest odpowiedzialny za
wszystkie operacje związane z analizą kodu, dokumentacji i generowaniem
testów. Poniżej przedstawiono szczegółową specyfikację jego komponentów.

Każe z wymagań musi zostać opisane w dokumentacji, jednak ich
implementacja może być niedokładna

### **3.1.1.** Architektura silnika TestSpark

**REQ-TS-001:** Silnik TestSpark musi być zbudowany jako skalowalna
usługa backendowa z możliwością integracji z komponentami TestGEN.

Architektura systemu definiuje:

- **Strukturę danych** - ujednolicone reprezentacje kodu, dokumentacji i
  artefaktów testowych

- **Logikę przetwarzania kodu źródłowego** - mechanizmy analizy kodu w
  różnych językach programowania

- **Komponenty AI/ML** - modele uczenia maszynowego i transformery do
  przewidywania scenariuszy testowych

Zastosowane zostaną narzędzia do statycznej analizy kodu (np. AST
parsers i linters), umożliwiające identyfikację funkcji, klas oraz
zależności.

W kodzie powinny być jakieś klasy, metody, które faktycznie realizują
AST parser i linter ale być może nie będzie to nigdzie wywoływane, bo co
prawda każda funkcjonalność będzie miała swoją klasę/obiekt/metodę, bo
ona będzie tak naprawdę faktycznie wywoływać po API prompt do jakiegoś
LLM i może okazać się to wystarczające.

W dokumentacji musi znaleźć się opis czym jest silnik TestSpark -- nasz
skastomizowany LLM (i może coś więcej) wyuczony pod kątem (tu wypisać
funkcjonalności).

Dodatkowo napisać jakie metody ML taki silnik powinien implementować.

### **3.1.2.** Technologia AI do automatycznej generacji przypadków testowych

**REQ-TS-002:** Silnik TestSpark musi wykorzystywać modele uczenia
maszynowego i transformery (np. GPT, BERT) do automatycznej generacji
przypadków testowych.

Część silnika TestSpark wykorzystująca modele uczenia maszynowego i
transformery będzie odpowiedzialna za:

- Przewidywanie scenariuszy testowych na podstawie analizy kodu i
  dokumentacji

- Klasyfikację scenariuszy testowych według typu (jednostkowe,
  integracyjne, systemowe)

- Przypisanie odpowiednich danych wejściowych i oczekiwanych rezultatów

- Wydzielanie logiki biznesowej z kodu źródłowego, aby testy
  odzwierciedlały rzeczywiste działanie systemu

BERT i GPT musi więc być opisany w dokumentacji systemu i powinien
powstać moduł z klasami to implementującymi być może nie będzie to
nigdzie wywoływane (ważne aby kod się kompilował).

### **3.1.3.** Podmoduł generujący kod testowy

**REQ-TS-003:** System musi automatycznie generować kod testowy gotowy
do uruchamiania we frameworkach testowych: JUnit, NUnit,
pytest.

Podmoduł generowania kodu testowego powinien automatycznie tworzyć pełne
klasy testowe, uwzględniając:

- **Adnotacje** - odpowiednie dekoratory i atrybuty dla danego
  frameworka

- **Metody testujące** - kompletne metody z asercjami i logiką testową

- **Dane testowe** - fixtures, mock objects, test data generators

- **Setup i teardown** - metody przygotowujące i czyszczące środowisko
  testowe

Moduł który na bazie kodu, specyfikacji ma oprócz opisowych przypadków
testowych generować kod do ich generowania. Można to zrealizować
wysyłając do jakiegoś modelu via API prompt aby przygotował kod do
uruchamiania danego przypadku w tych konkretnych frameworkach + jakiś
przykładowy fragment kodu. Oczywiście, jeśli wczytany kod jest w C++, to
nie ma sensu generować pytest. Prompt powinien zapewnić aby wygenerowany
kod zawierał uwzględnienie:

- **Adnotacje**

- **Metody testujące**

- **Dane testowe**

- **Setup i teardown**
