# **4.4.** Moduł inteligentnej analizy luk w kodzie oprogramowania i generowania rekomendacji zabezpieczeń

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie
wystarczająca

Musi natomiast zostać uwzględnione w dokumentacji

**B. Rozbudowa silnika TestSpark pod kątem audytów bezpieczeństwa oraz
analizy zgodności kodu z dokumentacją**

**Termin realizacji: 1 czerwca 2026 - 30 września 2026**

> W ramach zadania 2 moduł TestSpark, kluczowy komponent systemu
> TestGEN, zostanie rozszerzony o innowacyjne mechanizmy analizy
> zgodności kodu i dokumentacji, zaawansowane testowanie bezpieczeństwa,
> a także możliwość badania istniejącego oprogramowania pod kątem
> podatności na zagrożenia. Dzięki temu TestGEN stanie się nie tylko
> narzędziem wspierającym projektowanie nowych systemów, ale również
> aktywnym audytorem bezpieczeństwa wdrożonych aplikacji. Jednym z
> kluczowych aspektów rozbudowy TestGEN będzie jego zdolność do ciągłego
> samodoskonalenia. System będzie mógł regularnie otrzymywać nowo
> odkryte podatności, analizując dane o cyberzagrożeniach i ucząc się
> nowych metod wykrywania luk. Dzięki temu będzie
>
> identyfikował zagrożenia, które wcześniej nie były znane.
>
> Zadanie 1: Mechanizm analizy zgodności i wykrywania luk funkcjonalnych
>
> TestGEN będzie automatycznie porównywał kod źródłowy, dokumentację
> techniczną, podręczniki użytkownika oraz diagramy UML, wykorzystując
> algorytmy AI do analizy spójności projektu. Zaawansowane
> techniki przetwarzania języka naturalnego pozwolą na ekstrakcję
> wymagań i ich zestawienie z implementacją aplikacji. System wykryje
> brakujące walidacje, niezaimplementowane operacje oraz niespójności
> między UML a dokumentacją, generując raport z zaleceniami. TestGEN nie
> tylko oznaczy te niezgodności, ale także zasugeruje brakujące
> funkcjonalności wynikające z dokumentacji systemu. Dzięki temu
> testowanie stanie się integralną częścią procesu programistycznego,
> eliminując błędy przed wdrożeniem, oszczędzając czas i zasoby.
>
> Zadanie 2: Testowanie bezpieczeństwa i zdolność do samodoskonalenia
>
> TestGEN przetestuje tworzone oprogramowanie, jak i pozwoli na analizę
> istniejących aplikacji. Po wgraniu kodu wdrożonego systemu
> przeprowadzi audyt bezpieczeństwa, wykrywając podatności i zalecając
> poprawki. TestGEN będzie mógł regularnie otrzymywać nowe dane o
> zagrożeniach, które zostaną przeanalizowane i wykorzystane do
> aktualizacji metod testowania. Metody analizy ryzyka pozwolą na
> identyfikację podatności, których nie wykrył wcześniej, stale
> podnosząc poziom ochrony systemów IT.
>
> Zadanie 3: Technologie i sposób realizacji
>
> W rozwoju modułu TestGEN zostaną zastosowane frameworki NLP, systemy
> analizy kodu, UML oraz mechanizmy analizy bezpieczeństwa, a także
> modele AI oraz algorytmy wykrywania luk.

### **4.4.1.** Opis ogólny modułu i wykorzystane technologie

Moduł inteligentnej analizy luk w kodzie oprogramowania i generowania
rekomendacji zabezpieczeń dla oprogramowania aplikacyjnego oraz
wbudowanego stanowi kluczowy komponent systemu TestGEN w zakresie
bezpieczeństwa. Jego głównym zadaniem jest automatyczne wykrywanie
podatności oraz sugerowanie skutecznych działań naprawczych, zarówno dla
nowo tworzonego, jak i już wdrożonego oprogramowania na podstawie kodu
źródłowego.

**Technologie:** Realizacja modułu może wykorzystać technologie takie
jak AST parsers i linters, SonarQube, Checkstyle i PMD.

Po wgraniu kodu źródłowego do TestGEN, użytkownik uzyskuje szczegółową
analizę podatności i zalecenia dotyczące ich eliminacji. Moduł ten
realizuje innowacyjne podejście do testów bezpieczeństwa, wykorzystując
mechanizmy analizy semantycznej oparte na sztucznej
inteligencji.

Realizacja modułu może wykorzystać technologie takie jak AST parsers i
linters, SonarQube, Checkstyle i PMD.

**REQ-MOD-SEC-001:** System musi wykrywać co najmniej następujące typy
podatności: SQL Injection, XSS, CSRF, błędy autoryzacji, niewłaściwe
zarządzanie sesjami, hardcoded secrets.

**REQ-MOD-SEC-002:** System musi generować konkretne rekomendacje
naprawcze z przykładami kodu dla każdej wykrytej podatności.

### **4.4.2.** Funkcjonalność analizy luk bezpieczeństwa kodu i generowanie przypadków testów bezpieczeństwa

#### **4.4.2.1.** Opis funkcjonalności

System jest w stanie wygenerować opisy przypadków testowych dla testów
bezpieczeństwa i ewentualny kod do ich uruchomienia dla
najpopularniejszych podatności.

System analizuje ewentualne luki w kodzie w automatyczny sposób i
wykrywa podatności oraz przygotowuje raport rekomendacji zabezpieczeń w
danym zakresie jeśli znajdzie jakąś lukę.

W ten sposób TestGEN nie tylko wykrywa błędy, ale także sugeruje
skuteczne działania naprawcze. System poprzez analizę kodu
źródłowego identyfikuje:

- SQLi

- XSS

- Nieprawidłowe filtrowanie danych wejściowych

- Brak tokenów CSRF

- Błędy w logice autoryzacyjnej

- Proponowanie konkretne zmiany w kodzie, eliminujące wykryte
  zagrożenia w postaci raportu z rekomendacjami

Wejście --- co TestGEN przyjmuje:

- Repozytorium kodu (git clone / archive) lub pojedyncze pliki źródłowe
  (wielojęzykowe).

- Opcjonalnie: pliki konfiguracyjne środowiska (docker-compose, k8s
  manifests), pliki IaC (Terraform), schematy DB, test data, środowisko
  uruchomieniowe (dev/staging).

- (Opcjonalnie) dostęp do running instance (staging) --- do testów
  dynamicznych (DAST).

- Metadane: zakres skanowania, polityka (które klasy luk ignorować),
  klucze API do narzędzi zewnętrznych.

#### **4.4.2.2.** Architektura modułu bezpieczeństwa

Architektura modułu bezpieczeństwa składa się z następujących głównych
komponentów:

- **Preprocessor + Detector technologii** - rozpoznaje język, framework,
  pliki zależności (package.json, requirements.txt, pom.xml)

- **SAST pipeline (static analysis)** - AST parsing, pattern/rule
  matching, semgrep/Sonar-like rules, custom rules

- **Taint / Data-flow analyzer** - śledzi przepływ danych (taint
  analysis) od źródeł wejścia do sinków (DB, eval, innerHTML, exec)

- **Dependency & supply-chain scanner** - sprawdza biblioteki i wersje
  (CVE, OSS advisories, Snyk/OSV DB)

- **Configuration & IaC scanner** - wykrywa błędne ustawienia (np. brak
  HTTPS, publiczne credentials)

- **DAST / Runtime tests** - uruchamianie OWASP ZAP, Burp, sqlmap,
  fuzzery przeciwko instancji testowej (jeśli dostępna)

- **Proof-of-Concept (PoC) generator** - generuje bezpieczne,
  kontrolowane POC / testy sprawdzające podatność (wykonywane tylko w
  autoryzowanym środowisku)

- **Fix generator** - sugeruje poprawki kodu (patch/diff), snippet\'y i
  bezpieczne wzorce

- **Prioritizer / Risk engine** - mapuje do CWE/CVSS, ocenia ryzyko,
  sugeruje kolejność napraw

- **Report & CI integrator** - raport, JIRA tickets, MR suggestions, Git
  hooks, CI joby

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie
wystarczająca

#### **4.4.2.3.** Szczegółowy workflow po wczytaniu kodu źródłowego

##### Krok A - wykrycie technologii i parsowanie

- Rozpoznanie języka i frameworku (np. React/Node, Django, Spring)

- Budowa AST (np. tree-sitter, Python ast, JavaParser)

- Wydobycie funkcji HTTP endpoints, kontrolerów, handlerów, miejsca
  gdzie przyjmowane są dane od użytkownika, zapytań do bazy i
  generowania HTML/JS

Powyższe zadania powinny być uwzględnione w promptach do LLM aby
nakierunkować model na oczekiwany wynik

##### Krok B - reguły SAST + pattern matching

Uruchomienie zestawu reguł typu semantic + regex (np. Semgrep-like):

- Wykrycie String concatenation w zapytaniach do bazy

- innerHTML przypisywanego z danymi użytkownika

- eval() w JavaScript

- Brak walidacji inputów przy wywołaniu API

Dla frameworków natywnych:

- Szukanie braków CSRF tokenów w formularzach (np. brak \@csrf_protect w
  Django view)

- Brak sprawdzania uprawnień w kontrolerach (np. brak sprawdzenia
  current_user.role)

Powyższe zadania powinny być uwzględnione w promptach do LLM aby
nakierunkować model na oczekiwany wynik

##### Krok C - taint / data-flow analysis

**Oznaczenie źródeł:** request params, headers, cookies, body, form
inputs

**Oznaczenie sinków:** zapytania do DB (raw SQL, ORM raw queries),
funkcje renderujące HTML (innerHTML, res.send() zawierające user data),
systemowe exec/OS calls, LDAP, LDAP injections, deserialization

**Śledzenie przepływu:** czy niesprawdzane dane trafiają do sinka bez
sanitization/encoding/parametrization? Jeśli tak → potencjalna podatność

**Rozpoznawanie sanitizers/encoders:**

- Presence of parameterized queries (PreparedStatement, parameterized
  ORM bindings)

- Output encoding libraries (e.g., escapeHtml)

- Input validation libs

##### Krok D - dependency & config scanning

- Zidentyfikowane biblioteki skanowane względem baz CVE/OSV/Snyk

- Wykrycie podatnych wersji, braków patcha, użycia insecure
  flags/configs (np. allow_remote=true)

- Searching for hardcoded secrets (regex for keys), misconfigured CORS
  (\*), cookies without Secure/HttpOnly, insecure TLS settings

##### Krok E - dynamic checks (jeśli staging dostępny)

- Uruchomienie kontrolowanych testów DAST: OWASP ZAP baseline scan, skan
  interaktywny

- Próby prostych payloadów SQLi/XSS

- Test CSRF by simulating form posts without token

- Fuzzing endpoints (bounded), testy sesji i role escalation
  (brute-force role change in REST calls)

- Zbieranie odpowiedzi HTTP, stack traces, headers, cookies

##### Krok F - agregacja dowodów i eliminacja false positives

- Połączenie wyników SAST + taint + DAST → podniesienie confidence gdy
  taint wykryje przepływ i DAST potwierdzi exploit

- Heurystyki redukujące FP: sprawdzanie użycia ORM safe APIs, wykrycie
  sanitizers, checking for prepared statements

- Nadanie score ufności i klasyfikacji (Confirmed / Likely / Possible)

#### Wykrywanie konkretnych rodzajów podatności

TestGen generuje poniższe poprzez wysłanie do LLM poprzez API jednak z
warunkiem czy dana podatność ma sens. Np. podatność SQL Injection nie ma
sensu w kodzie java w którym nie ma SQL ani integracji z bazą danych.
Weryfikację sensowności TestGEN pozostawia LLM

##### SQL Injection

**Jak wykrywane:**

Taint analysis: request.params.name → konkatenacja do stringa w
execute(\"SELECT \... \" + name) lub format() → sink:
db.execute(raw_sql).

**Testy wygenerowane:**

Testy jednostkowe i integracyjne z payloadami (np. \' OR \'1\'=\'1),
automatyzowane skrypty uruchamiające sqlmap lub curl z złośliwym
parametrem w staging.

**Rekomendowane poprawki:**

Parametryzacja (prepared statements / query parameters) lub korzystanie
z ORM bindingów.

**Przykładowa poprawka (Python / psycopg2):**

\# vulnerable cursor.execute(\"SELECT \* FROM users WHERE name = \'\" +
name + \"\'\") \# fixed cursor.execute(\"SELECT \* FROM users WHERE name
= %s\", (name,))

##### Cross-Site Scripting (XSS)

**Jak wykrywane:**

User input przepływa do HTML bez output encoding (np. res.send(\"

\" + req.body.comment + \"

\") lub element.innerHTML = userInput w frontend).

**Testy wygenerowane:**

Testy E2E imitujące payloady \<script\>alert(1)\</script\> i asercje że
w DOM nie pojawia się wykonywalny skrypt; DAST detects
reflected/persistent XSS.

**Rekomendacja:**

Output encoding przed renderowaniem, użycie template engines
automatycznie escapujących, CSP headers.

**Fix (Node/Express + template engine):**

// vulnerable res.send(\`

\${userInput}

\`); // fixed - using template engine with auto-escaping
res.render(\'template\', { data: userInput }); // template engine
escapes automatically // or manual escaping const escapeHtml =
require(\'escape-html\'); res.send(\`

\${escapeHtml(userInput)}

\`);

##### Brak CSRF (Cross-Site Request Forgery)

**Jak wykrywane:**

Mutujące POST/PUT/DELETE bez CSRF tokenów lub bez weryfikacji SameSite
cookie.

**Test:**

Wysłanie żądania POST z sesją użytkownika z innego źródła i oczekiwanie
braku akcji - test symuluje CSRF.

**Rekomendacja:**

Dodać CSRF middleware, generować tokeny per session/form, dodać
SameSite=strict i wymusić header Origin/Referer checks.

**Patch snippet (Flask-WTF):**

from flask_wtf import CSRFProtect csrf = CSRFProtect(app) \# In
templates

Początek formularza

{{ csrf_token() }}

Dół formularza

**Patch snippet (Python Django):**

\# ensure \@csrf_protect on view or have middleware enabled from
django.views.decorators.csrf import csrf_protect \@csrf_protect def
my_view(request): \# view logic pass

##### Błędy autoryzacji/logiki (Broken Access Control)

**Jak wykrywane:**

Endpoints performing sensitive actions without verifying the caller\'s
identity/role; direct object references without access checks (GET
/user/123/orders where user id from token not validated).

**Testy wygenerowane:**

Role-escalation tests: call endpoints as user A for resources of user B
and expect 403. Automated scripts alter JWT sub claims or use different
tokens.

**Rekomendacja:**

Centralize authorization checks, use middleware/policies, enforce
object-level checks.

**Fix (pseudo):**

\# check ownership if resource.owner_id != current_user.id: raise
Forbidden() \# or use decorator \@require_ownership def
get_resource(resource_id): return Resource.get(resource_id)

##### Nieprawidłowe filtrowanie / walidacja danych

**Jak wykrywane:**

Absence of schema validation on input; reliance on client-side
validation.

**Testy wygenerowane:**

Fuzzing with boundary and malformed inputs; schema-based tests using
JSON schema validators.

**Rekomendacja:**

Validate at server-side (schema validation e.g., AJV for Node, pydantic
for Python FastAPI).

\# Python with Pydantic from pydantic import BaseModel, EmailStr,
validator class UserInput(BaseModel): email: EmailStr age: int
\@validator(\'age\') def age_must_be_positive(cls, v): if v \< 0 or v \>
150: raise ValueError(\'Age must be between 0 and 150\') return v \# Use
in endpoint \@app.post(\"/user\") def create_user(user: UserInput): \#
user is already validated pass

#### **4.4.2.5.** Generowanie przypadków testów bezpieczeństwa

TestGen generuje poniższe poprzez wysłanie do LLM poprzez API

Dla każdej wykrytej podatności TestGEN wygeneruje:

##### a. Opisowy przypadek testowy (readable)

Cel, warunki, kroki, dane, oczekiwane rezultaty, priorytet.

**TC_SEC_SQLI_001:** \"POST /search - SQL injection attempt via q
parameter\"\
\
**Kroki:**\
1. POST body q: \"\' OR \'1\'=\'1\"\
2. Oczekuj HTTP 200 or empty results; no stack trace; no DB error leak\
\
**Oczekiwane:** 4xx lub pusta odpowiedź, brak ujawnienia błędów DB\
**Typ:** Security/Negative\
**Priorytet:** Krytyczny

##### b. Automatyczny skrypt testowy

Np. pytest + requests (API), Playwright (jeśli endpoint wywoływany z
UI), lub sqlmap wrapper.

import requests def test_sql_injection_protection(): \"\"\"Test that SQL
injection is prevented\"\"\" payload = {\"q\": \"\' OR \'1\'=\'1\"}
response = requests.post(\"https://api.example.com/search\",
json=payload) \# Should not return all results assert
response.status_code in \[400, 403, 422\] \# Should not leak database
errors assert \"sql\" not in response.text.lower() assert \"syntax
error\" not in response.text.lower()

##### c. DAST script / ZAP policy

Konfiguracja skanu ataku dla konkretnych endpointów.

##### d. Unit / Integration tests

Checks for input validation and sanitizers.

##### e. PoC (bezpieczny, kontrolowany)

Krótkie, jasno oznaczone, z limitem (sleep, timeouts) i wymaganiem
explicit consent do uruchomienia.

##### f. Regression tests

Przygotowanie sugestii i danie możliwości użytkownikowi podjęcia decyzji
o

dodaniu do repo tests/security/ i CI, aby zapobiec regresji.

Przykład opisowego TC + pytest (API SQLi), opisowy TC:

ID: TC_SEC_API_SQLI_001

Cel: Zweryfikować, że parametr \`username\` w POST /users/search nie
jest podatny na SQLi.

Warunki: staging instance z test DB

Kroki:

1\. POST /users/search { \"username\": \"\' OR \'1\'=\'1\" }

2\. Sprawdź status odpowiedzi i zawartość (nie powinno zwrócić
wszystkich użytkowników ani błędu DB)

Oczekiwane: 400 lub 200 z pustym/odfiltrowanym wynikiem; brak stack
trace.

#### **4.4.2.6.** Rekomendacje naprawcze

Dla każdej klasy podatności system generuje:

- **Krótkie wyjaśnienie** (co się stało i dlaczego jest to
  niebezpieczne)

- **Konkretne sugestie kodowe** z fragmentami poprawionego kodu (dla
  wykrytego języka)

- **Alternatywy projektowe** (np. użycie ORM zamiast ręcznych query,
  wprowadzenie centralnego middleware autoryzacji)

- **Lista testów regresyjnych** które należy dodać po wprowadzeniu
  poprawki

- **Priorytety i estimated effort** (szacunek trudności
  naprawy)

- **Mapowanie do standardów** (OWASP Top10, powiązane CWE), co ułatwia
  komunikację z audytorami

**Przykłady rekomendacji:**

  ------------------------------------------------------------------------------------
  **Podatność**   **Rekomendacja**                                     **Priorytet**
  --------------- ---------------------------------------------------- ---------------
  SQLi            Użyj PreparedStatement/parametrów; waliduj i castuj  Krytyczny
                  typy; ogranicz przywileje DB                         

  XSS             Encoduj kontekstowo; CSP; HttpOnly cookie,           Wysoki
                  sanitycznie renderuj JSON w responses                

  CSRF            Dodać CSRF tokens, wymuszanie SameSite i             Wysoki
                  referer/origin checks                                

  AuthZ           Przenieść checks do warstwy service + centralny      Krytyczny
                  policy enforcer (RBAC/ABAC)                          
  ------------------------------------------------------------------------------------

#### **4.4.2.7.** Raport końcowy i traceability

System generuje raport końcowy zawierający:

- **Executive summary** (najwyższe ryzyka, CI build id, data)

- **Szczegółowa lista znalezionych problemów** (ID, severity, CWE/OWASP
  tag, plik:linia, trace of dataflow)

- **Zalecane zmiany i automatyczne patch snippets**

- **Wygenerowane testy** (ścieżki plików) i instrukcje uruchomienia

- **SBOM + lista zależności z CVE**

- **Macierz traceability:** vuln ↔ test ↔ patch ↔ CI job

- **Lista pytań / niepewności** gdzie wymagana jest manualna weryfikacja
  (human-in-loop)

#### **4.4.2.8.** Integracja w CI/CD i workflow naprawczy

System generuje joby do CI (GitHub Actions/GitLab CI/Jenkins)
uruchamiające:

- SAST

- Dependency scan

- Generated security tests (DAST/pytest)

- Report aggregation

TestGen generuje powyższe poprzez wysłanie do LLM poprzez API z prośbą o
wygenerowanie joby i opisy tekstowe jak je uruchomić.

Przy wykryciu krytycznego problemu:

- generuje opisowe kroki, jak zgłosić ticket, np. w Jira z opisem, patch
  snippet, i linkiem do PR suggestion

Po wprowadzeniu patcha:

- generuje opisowe kroki, jak uruchmoić regression tests (w tym
  wygenerowane security tests) i oznacza status FIXED / NOT FIXED

#### **4.4.2.9.** Human-in-the-loop, scoring i ograniczenia

- Każda automatyczna sugestia zawiera score ufności. Niskie score\'y
  trafiają do reviewerów bezpieczeństwa.

- Dla krytycznych zmian (np. auth bypass), wymagana ręczna walidacja i
  code review.

- Ograniczenia: analiza może generować false positives (zwłaszcza przy
  dynamicznych językach i metaprogramowaniu) --- dlatego rekomenduję
  połączenie: SAST + DAST + IAST + manual review.

- Nie generuję publicznego exploitu --- POC są defensywne i zakładają
  środowisko testowe.

TestGen generuje powyższe poprzez wysłanie do LLM poprzez API

#### **4.4.2.10.** Przykład end-to-end: wykrycie SQLi i ścieżka naprawy

**Scenariusz:**\
1. TestGEN przetwarza repo → znajduje searchController.js gdzie query
budowane jest \"\... WHERE name LIKE \'%\" + q + \"%\'\"\
2. Taint analysis: req.query.q → buildQuery → db.exec. Confidence:
wysoka\
3. Generuje: TC_SEC_SQLI_001 (opis + pytest), DAST run z payload, i
rekomendowany patch (parameterized queries)\
4. Generuje PR template z propozycją zmiany i testem regresyjnym\
5. Po merge - CI uruchamia testy i potwierdza fix

// before const sql = \`SELECT \* FROM products WHERE name LIKE
\'%\${q}%\'\`; db.query(sql, \...); // after const sql = \`SELECT \*
FROM products WHERE name ILIKE \$1\`; db.query(sql, \[\`%\${q}%\`\]);

### **4.4.3.** Funkcjonalność aktualizacji systemu

TestGEN powinien łączyć się na żądanie lub z jakąś częstotliwością z poniższymi
źródłami i nawet wczytywać coś do wewnętrznej bazy systemu ale może nie
mieć to wpływu na pracę TestGEN 

#### **4.4.3.1.** Opis funkcjonalności

**REQ-MOD-SEC-003:** System musi umożliwiać regularne aktualizacje bazy
podatności (co najmniej raz w miesiącu).

TestGEN nie jest narzędziem statycznym - jego zdolność do ciągłego
samodoskonalenia umożliwia analizowanie i przyswajanie nowo odkrytych
podatności. System będzie regularnie aktualizowany, aby wykrywać
zagrożenia, które wcześniej były nieznane. Dzięki temu właściciele
oprogramowania mogą ponownie przeprowadzać analizy, aby zabezpieczyć
swoje systemy przed najnowszymi zagrożeniami.

#### **4.4.3.2.** Security Knowledge Layer

System będzie aktualizowany o warstwę wiedzy bezpieczeństwa (Security
Knowledge Layer) - dynamiczną bazę reguł, CVE, exploit patternów,
heurystyk i przykładów napraw.

TestGEN będzie zasilany kilkoma klasami źródeł danych, które aktualizują
jego wiedzę o zagrożeniach:

W trakcie implementacji wybrać do zaczytywania jako źródło kilka źródeł
open-source

  ------------------------------------------------------------------------
  **Typ źródła**    **Przykłady**                 **Zastosowanie**
  ----------------- ----------------------------- ------------------------
  Bazy CVE/NVD      cve.mitre.org, nvd.nist.gov   Identyfikacja nowych
                                                  podatnych bibliotek,
                                                  frameworków, API

  Bazy podatności   Snyk, GitHub Security         Automatyczne wykrycie,
  open source (SCA) Advisories, OSV.dev, PyUp,    że np. django==4.1.2 ma
                    npm audit, Maven Central      CVE
                    advisories                    

  Projekty OWASP    OWASP Top 10, ASVS, API       Aktualizacja modeli
                    Security Top 10               ryzyka i nowych
                                                  kategorii zagrożeń

  Bug bounty /      HackerOne, Exploit-DB, CISA   Uczenie się nowych
  exploit feeds     KEV, ZeroDay Initiative       wektorów ataków, np.
                                                  łańcuchów XSS → RCE

  Rządowe / cert    CERT, CISA, ENISA             Wykrywanie trendów i
  feedy                                           alertów sektorowych

  Społeczność i     Pull requests naprawiające    Uczenie się skutecznych
  GitHub commits    CVE w popularnych projektach  wzorców napraw
  ------------------------------------------------------------------------

#### **4.4.3.3.** Pipeline aktualizacyjny

##### Etap 1: Pobranie i ekstrakcja danych

- Pobranie nowych rekordów CVE, advisories i changelogi bibliotek

- Dla każdej podatności wyodrębniane są:

  - Opis (CVE summary)

  - Dotknięte wersje

  - Typ błędu (np. SQLi, path traversal, XSS)

  - Przykładowe fragmenty kodu przed/po naprawie

  - Język i framework

##### Etap 2: Klasyfikacja semantyczna (LLM + parsery)

- LLM analizuje tekst CVE i klasyfikuje go wg:

  - Kategorii (OWASP/CWE)

  - Typu źródła błędu (input validation, unsafe deserialization, logic
    flaw)

  - Dotkniętych technologii (np. React, Flask, Spring Boot)

- Wynik: nowy \"wzorzec podatności\" zapisany w formacie semgrep / AST
  rule

##### Etap 3: Aktualizacja repozytorium reguł i testów

System dodaje nową regułę detekcji do repozytorium SAST/DAST.

**Przykład - dla CVE-2025-XXXX w Django generuje regułę:**

rules: - id: django-missing-csrf-token pattern: \| def \$FUNC(\...):
\... pattern-not-inside: \| \@csrf_protect def \$FUNC(\...): \...
message: \"View function missing CSRF protection\" severity: WARNING
languages: \[python\] metadata: cve: CVE-2025-XXXX owasp: A01:2021

Jednocześnie generuje przykładowe testy jednostkowe i integracyjne, aby
wykryć błędne użycie (np. brak tokenu CSRF).

##### Etap 4: Weryfikacja i testowanie nowych reguł

- Nowa reguła jest testowana na zestawie przykładowych projektów
  (pozytywne i negatywne przypadki)

- Ocena false positive rate

- Jeśli FPR \< 5%, reguła jest dodawana do produkcji

##### Etap 5: Deploy i notyfikacja użytkowników

- Aktualizacja jest wdrażana do systemu TestGEN

- Użytkownicy otrzymują powiadomienie o nowych możliwościach detekcji w
  formie raport z informacją co wczytano

- Sugestia ponownego skanowania projektów dla wykrycia nowych zagrożeń

### 4.4.4 Wykorzystane mechanizmy i technologie

W kodzie TestGEN muszą być klasy i metody realizujące jednak moduły mogą
ich potem nie używać jeśli wywołanie LLM poprzez API będzie wystarczająca
Musi natomiast zostać uwzględnione w dokumentacji

#### **4.4.4.1.** Architektura modułu

- **Mechanizm identyfikujący niskopoziomowe wzorce podatności** w kodzie
  źródłowym

- **Warstwa semantycznej analizy kodu**, wykorzystująca autorskie modele
  AI i techniki NLP, które umożliwią rozpoznanie kontekstu
  funkcjonalnego oraz przepływu danych w systemie

#### **4.4.4.2.** Mechanizm wykrywania podatności i generowania rekomendacji

Na podstawie wyników statycznej i semantycznej analizy kodu, system
identyfikuje nieprawidłowe filtrowanie danych wejściowych, brak tokenów
CSRF, błędy w logice autoryzacyjnej, a następnie zasugeruje
konkretne zmiany w kodzie, mające na celu eliminację wykrytych zagrożeń.

**Przykładowe narzędzia SAST:**

- Semgrep - pattern-based static analysis

- Bandit - Python security linter

- ESLint security plugins - JavaScript/TypeScript

- SpotBugs + Find Security Bugs - Java

- Brakeman - Ruby on Rails security scanner

#### **4.4.4.3.** Mechanizm aktualizacji

W celu samodoskonalenia system będzie mógł być regularnie aktualizowany,
np. raz w miesiącu, aby wykrywać zagrożenia, które wcześniej były
nieznane.
