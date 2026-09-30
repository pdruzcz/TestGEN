# **6.3.** Narzędzia analizy kodu

### **6.3.1.** Parsery AST i analizatory statyczne

  ----------------------------------------------------------------------------
  **Język**        **Narzędzie**     **Funkcjonalność**
  ---------------- ----------------- -----------------------------------------
  Multi-language   tree-sitter       Uniwersalny parser dla wielu języków,
                                     inkrementalne parsowanie

  Python           ast, astroid\     AST parsing\
                   Bandit\           Security linting\
                   Pylint            Code quality

  JavaScript/TS    Esprima, Babel\   AST parsing\
                   ESLint\           Linting\
                   TypeScript        Type checking
                   Compiler API      

  Java             JavaParser\       AST parsing\
                   SpotBugs\         Bug detection\
                   PMD               Code quality

  C#               Roslyn\           AST parsing, semantic analysis\
                   SonarAnalyzer     Code quality, security

  C/C++            Clang\            AST parsing\
                   cppcheck          Static analysis
  ----------------------------------------------------------------------------

### **6.3.2.** Narzędzia SAST (Static Application Security Testing)

  ---------------------------------------------------------------------------
  **Narzędzie**   **Typ**           **Zastosowanie w TestGEN**
  --------------- ----------------- -----------------------------------------
  Semgrep         Open-source       Pattern-based code analysis, custom rules

  SonarQube       Commercial/Open   Code quality, security vulnerabilities,
                                    code smells

  Bandit          Open-source       Python security issues detection

  Brakeman        Open-source       Ruby on Rails security scanner

  FindSecBugs     Open-source       Java security vulnerabilities
  ---------------------------------------------------------------------------

### **6.3.3.** Narzędzia DAST (Dynamic Application Security Testing)

  --------------------------------------------------------------------------
  **Narzędzie**   **Typ**       **Zastosowanie**
  --------------- ------------- --------------------------------------------
  OWASP ZAP       Open-source   Web app security scanning, API testing

  Burp Suite      Commercial    Advanced web security testing, manual
                                testing tools

  sqlmap          Open-source   Automated SQL injection detection and
                                exploitation

  Nikto           Open-source   Web server scanning
  --------------------------------------------------------------------------

### **6.3.4.** Narzędzia SCA (Software Composition Analysis)

  -----------------------------------------------------------------------
  **Narzędzie**            **Zastosowanie**
  ------------------------ ----------------------------------------------
  Snyk                     Dependency vulnerability scanning, license
                           compliance

  OWASP Dependency-Check   Open-source dependency vulnerability scanner

  npm audit / pip-audit    Language-specific dependency scanners

  GitHub Dependabot        Automated dependency updates and security
                           alerts
  -----------------------------------------------------------------------
