# **6.4.** Frameworki testowe wspierane przez TestGEN

TestGEN musi wspierać wszystkie frameworki opisane w tym rozdziale. Oznacza to,
że zapytania do wybranych LLM komercyjnych muszą być tak skonstruowane na poziomie
propmtów, aby jeśli użytkownik o to poprosi dawały w wyniku „kod" do uruchomienia
w unitest lub przypadki to wstawienia w Cypress lub Selenium. Jeśli testujemy kod
API, to zgodnie z poniższym przypadek powinien być do odpalenia np. w SuperTest
lub Postman/Newman etc

### **6.4.1.** Frameworki testowe backend

  ----------------------------------------------------------------------------
  **Framework**   **Język**       **Typ testów**       **Wspierane w TestGEN**
  --------------- --------------- -------------------- -----------------------
  pytest          Python          Unit, Integration,   ✅ Pełne wsparcie
                                  E2E                  

  unittest        Python          Unit                 ✅ Pełne wsparcie

  JUnit 5         Java            Unit, Integration    ✅ Pełne wsparcie

  TestNG          Java            Unit, Integration,   ✅ Pełne wsparcie
                                  E2E                  

  NUnit           C#              Unit, Integration    ✅ Pełne wsparcie

  xUnit           C#              Unit, Integration    ✅ Pełne wsparcie

  Jest            JavaScript/TS   Unit, Integration    ✅ Pełne wsparcie

  Mocha + Chai    JavaScript      Unit, Integration    ✅ Pełne wsparcie

  RSpec           Ruby            Unit, Integration    ⚠️ Ograniczone wsparcie

  PHPUnit         PHP             Unit, Integration    ⚠️ Ograniczone wsparcie
  ----------------------------------------------------------------------------

### **6.4.2.** Frameworki testowe frontend/E2E

  -----------------------------------------------------------------------
  **Framework**        **Typ**          **Wspierane w TestGEN**
  -------------------- ---------------- ---------------------------------
  Selenium WebDriver   Web E2E          ✅ Pełne wsparcie (Python, Java,
                                        JS)

  Playwright           Web E2E          ✅ Pełne wsparcie (Python, TS,
                                        JS)

  Cypress              Web E2E          ✅ Pełne wsparcie (JavaScript)

  Puppeteer            Web E2E          ✅ Pełne wsparcie (JavaScript)

  TestCafe             Web E2E          ⚠️ Ograniczone wsparcie

  Appium               Mobile E2E       ✅ Pełne wsparcie (iOS, Android)

  Espresso             Android E2E      ✅ Pełne wsparcie

  XCUITest             iOS E2E          ✅ Pełne wsparcie

  Robot Framework      Keyword-driven   ✅ Pełne wsparcie
  -----------------------------------------------------------------------

### **6.4.3.** API Testing Frameworks

  ------------------------------------------------------------------------
  **Framework**          **Język**           **Wspierane w TestGEN**
  ---------------------- ------------------- -----------------------------
  REST Assured           Java                ✅ Pełne wsparcie

  requests + pytest      Python              ✅ Pełne wsparcie

  SuperTest              JavaScript/TS       ✅ Pełne wsparcie

  Postman/Newman         JSON collections    ✅ Eksport kolekcji

  Karate DSL             Gherkin-style       ⚠️ Ograniczone wsparcie
  ------------------------------------------------------------------------
