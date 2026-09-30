# **8.2.** Zadanie B - Rozbudowa pod kątem audytów bezpieczeństwa

### **8.2.1.** Szczegóły zadania

**Termin realizacji:** 1 czerwca 2026 - 30 września 2026 (4 miesiące)

**Cel:** Rozszerzenie silnika TestSpark o mechanizmy analizy zgodności
kodu i dokumentacji, zaawansowane testowanie bezpieczeństwa oraz
możliwość badania istniejącego oprogramowania pod kątem podatności.

W ramach zadania 2 moduł TestSpark, kluczowy komponent systemu TestGEN,
zostanie rozszerzony o innowacyjne mechanizmy analizy zgodności kodu i
dokumentacji, zaawansowane testowanie bezpieczeństwa, a także możliwość
badania istniejącego oprogramowania pod kątem podatności na zagrożenia.
Dzięki temu TestGEN stanie się nie tylko narzędziem wspierającym
projektowanie nowych systemów, ale również aktywnym audytorem
bezpieczeństwa wdrożonych aplikacji. Jednym z kluczowych aspektów
rozbudowy TestGEN będzie jego zdolność do ciągłego samodoskonalenia.
System będzie mógł regularnie otrzymywać nowo odkryte podatności,
analizując dane o cyberzagrożeniach i ucząc się nowych metod wykrywania
luk. Dzięki temu będzie identyfikował zagrożenia, które wcześniej nie
były znane.

1\. Zadanie 1: Mechanizm analizy zgodności i wykrywania luk
funkcjonalnych

TestGEN będzie automatycznie porównywał kod źródłowy, dokumentację
techniczną, podręczniki użytkownika oraz diagramy UML, wykorzystując
algorytmy AI do analizy spójności projektu. Zaawansowane techniki
przetwarzania języka naturalnego pozwolą na ekstrakcję wymagań i ich
zestawienie z implementacją aplikacji. System wykryje brakujące
walidacje, niezaimplementowane operacje oraz niespójności między UML a
dokumentacją, generując raport z zaleceniami. TestGEN nie tylko oznaczy
te niezgodności, ale także zasugeruje brakujące funkcjonalności
wynikające z dokumentacji systemu. Dzięki temu testowanie stanie się
integralną częścią procesu programistycznego, eliminując błędy przed
wdrożeniem, oszczędzając czas i zasoby.

2\. Zadanie 2: Testowanie bezpieczeństwa i zdolność do samodoskonalenia

TestGEN przetestuje tworzone oprogramowanie, jak i pozwoli na analizę
istniejących aplikacji. Po wgraniu kodu wdrożonego systemu przeprowadzi
audyt bezpieczeństwa, wykrywając podatności i zalecając poprawki.
TestGEN będzie mógł regularnie otrzymywać nowe dane o zagrożeniach,
które zostaną przeanalizowane i wykorzystane do aktualizacji metod
testowania. Metody analizy ryzyka pozwolą na identyfikację podatności,
których nie wykrył wcześniej, stale podnosząc poziom ochrony systemów
IT.

3\. Zadanie 3: Technologie i sposób realizacji

W rozwoju modułu TestGEN zostaną zastosowane frameworki NLP, systemy
analizy kodu, UML oraz mechanizmy analizy bezpieczeństwa, a także modele
AI oraz algorytmy wykrywania luk.

### **8.2.2.** Kluczowe milestone\'y

+-------------------------+------------+----------------------------------+
| **Milestone**           | **Data**   | **Deliverables**                 |
+=========================+============+==================================+
| M2.1: Moduł analizy     | 30.06.2026 | - Porównywanie kodu z            |
| zgodności               |            |   dokumentacją                   |
|                         |            |                                  |
|                         |            | - Detekcja luk funkcjonalnych    |
|                         |            |                                  |
|                         |            | - Raport rozbieżności            |
+-------------------------+------------+----------------------------------+
| M2.2: Moduł             | 31.07.2026 | - Detekcja SQL Injection, XSS,   |
| bezpieczeństwa SAST     |            |   CSRF                           |
|                         |            |                                  |
|                         |            | - Taint analysis                 |
|                         |            |                                  |
|                         |            | - Pattern matching rules         |
+-------------------------+------------+----------------------------------+
| M2.3: Moduł             | 31.08.2026 | - Integracja z OWASP ZAP         |
| bezpieczeństwa DAST     |            |                                  |
|                         |            | - Automatyczne testy             |
|                         |            |   penetracyjne                   |
|                         |            |                                  |
|                         |            | - PoC generation                 |
+-------------------------+------------+----------------------------------+
| M2.4: System            | 30.09.2026 | - Pipeline aktualizacji CVE      |
| aktualizacji            |            |                                  |
|                         |            | - Auto-update detection rules    |
|                         |            |                                  |
|                         |            | - Dokumentacja modułów           |
|                         |            |   bezpieczeństwa                 |
+-------------------------+------------+----------------------------------+

### **8.2.3.** Kryteria akceptacji Zadania B

**Kryteria sukcesu:**

- System wykrywa minimum 5 typów podatności (SQLi, XSS, CSRF, AuthZ,
  Hardcoded Secrets)

- Dla każdej podatności generuje konkretną rekomendację naprawczą z
  przykładem kodu

- System identyfikuje rozbieżności między kodem a dokumentacją z
  accuracy \> 80%

- Pipeline aktualizacji CVE działa automatycznie i dodaje nowe reguły co
  miesiąc

- Dokumentacja modułów bezpieczeństwa (100+ stron)
