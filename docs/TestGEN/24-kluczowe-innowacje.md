# **2.4.** Kluczowe innowacje

### **2.4.1.** Innowacja produktowa

TestGEN to uniwersalne narzędzie testerskie, które dzięki zastosowaniu
sztucznej inteligencji, uczenia maszynowego oraz technologii analizy
kodu umożliwia automatyczne generowanie i uruchamianie testów bez
konieczności ich manualnego przygotowywania. System będzie analizował
kod źródłowy, dokumentację techniczną, diagramy UML, interfejsy
użytkownika (GUI) oraz strukturę API, tworząc spójne, zoptymalizowane
scenariusze testowe.

### **2.4.2.** Wyróżniki konkurencyjne

Rozwiązanie wyróżnia się na tle dostępnych narzędzi kilkoma kluczowymi
aspektami:

- **Zaawansowana analiza** **kodu** - TestGEN automatycznie
  identyfikuje rozbieżności względem dokumentacji, co pozwala wykrywać
  potencjalne błędy przed wdrożeniem systemu. Bazując na
  wywołaniu i odpowiedzi jakiegoś płatnego LLMa

- **Automatyczna generacja testów API, GUI i aplikacji** - system
  generuje testy jednostkowe, systemowe, integracyjne i
  regresji dla różnorodnych środowisk.

- **Moduł analizy bezpieczeństwa** - wykrywa podatności, takie jak SQL
  injection, XSS, błędy autoryzacji.

- **Mechanizmy podpowiedzi dotyczące błędów i** **nowych
  funkcjonalności** - TestGEN nie tylko wykrywa błędy, ale sugeruje ich
  optymalne rozwiązania oraz potencjalne ulepszenia aplikacji.
  TestGEN przygotowuje raport takich sugestii które zbiera z zapytania
  jakiegoś płatnego LLM np. Claude

- **Integracja z systemami CI/CD** - automatyzacja testowania w
  procesie wdrażania, zapewniająca płynne aktualizacje: GitHub Actions,
  Jenkins, Azure DevOps. Aktualizacja taka powinna być w formacie danego
  systemu, aby można było łatwo ją przenieść o np.. Do ADO Test Plans.
  Automatyczna integracja jest nice to have

- **Elementy dostępności zgodne z WCAG 2.1** - m.in. możliwość
  kontrastowania i powiększania czcionki, ułatwiająca korzystanie osobom
  niedowidzącym.

### **2.4.3.** Analiza konkurencji

TestGEN znacząco różni się od dostępnych rozwiązań zarówno w Polsce, jak
i na świecie. W przeciwieństwie do klasycznych narzędzi testowych,
takich jak Selenium, JUnit, TestComplete, Ranorex czy Tosca, TestGEN nie
ogranicza się jedynie do testowania interfejsu użytkownika czy
jednostkowych testów kodu.

+------------------+-------------------------------+--------------------------+
| **Narzędzie**    | **Główne funkcje**            | **Ograniczenia**         |
+==================+===============================+==========================+
| **Selenium**     | - Automatyzacja testów        | Brak analizy kodu, brak  |
|                  |   webowych                    | testowania               |
|                  |                               | bezpieczeństwa           |
|                  | - WebDriver                   |                          |
|                  |                               |                          |
|                  | - Multi-browser support       |                          |
+------------------+-------------------------------+--------------------------+
| **JUnit**        | - Testy jednostkowe Java      | Brak analizy             |
|                  |                               | dokumentacji, brak       |
|                  | - Parametryzacja testów       | analizy bezpieczeństwa   |
|                  |                               |                          |
|                  | - Integracja CI/CD            |                          |
+------------------+-------------------------------+--------------------------+
| **TestComplete** | - Testy UI (desktop, web,     | Wymaga licencji, brak    |
|                  |   mobile)                     | analizy kodu             |
|                  |                               |                          |
|                  | - Keyword-driven testing      |                          |
|                  |                               |                          |
|                  | - Integracja DevOps           |                          |
+------------------+-------------------------------+--------------------------+
| **GitHub Copilot | - Asystent AI                 | Brak analizy systemowej, |
| X**              |                               | brak testów              |
|                  | - Generowanie testów          | bezpieczeństwa           |
|                  |   jednostkowych               |                          |
+------------------+-------------------------------+--------------------------+
| **TestGEN**      | - Kompleksowa analiza kodu,   | \-                       |
|                  |   dokumentacji, UML, GUI      |                          |
|                  |                               |                          |
|                  | - Automatyczne generowanie    |                          |
|                  |   testów wszystkich typów     |                          |
|                  |                               |                          |
|                  | - Zaawansowana analiza        |                          |
|                  |   bezpieczeństwa              |                          |
|                  |                               |                          |
|                  | - Wykrywanie luk              |                          |
|                  |   funkcjonalnych              |                          |
|                  |                               |                          |
|                  | - Inteligentne rekomendacje   |                          |
+------------------+-------------------------------+--------------------------+

### **2.4.4.** Przewaga TestGEN

TestGEN wyróżnia się dzięki zastosowaniu zaawansowanych technik uczenia
maszynowego, w tym rozproszonych agentów SLM.
Agenci muszą być opisani na poziomie dokumentacji systemu ale nie muszą
być faktycznie zaimplementowani. Dopuszczalne jest rozwiązanie w którym
to np. klasy, które się będą kompilować, (np. jako kod zaproponowany
przez model) ale nigdy nie będą wywoływane. System generuje przypadki
testowe zarówno dla backendu (API), jak i frontend (GUI), co czyni go
bardziej wszechstronnym niż konkurencja.

Dodatkowo analizuje szerokie spektrum danych wejściowych, takich jak:

- Kod źródłowy systemu

- Dokumentacja techniczna i użytkownika (np. diagramy UML)

- Przykładowe dane wejściowe i wyjściowe

- Makiety GUI lub ekrany działającego interfejsu

TestGEN nie tylko generuje przypadki testowe i ew. kod do ich
uruchamiania ale także:

- testuje kod

- ale także usprawnia rozwój oprogramowania

  - identyfikując luki

  - sugerując poprawki oraz nowe funkcjonalności

- oferuje automatyzację testowania

- analizuje kodu

- usprawnia testy bezpieczeństwa
