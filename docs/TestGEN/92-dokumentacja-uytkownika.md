# **9.2.** Dokumentacja użytkownika

### **9.2.1.** Struktura dokumentacji użytkownika

**REQ-USER-DOC-001:** Dokumentacja użytkownika musi zawierać 300-400
stron i być dostępna w językach: polski, angielski.

**Zakres dokumentacji użytkownika:**

#### Część I: Wprowadzenie (30-40 stron)

- **Rozdział 1: O systemie TestGEN**

  - Czym jest TestGEN

  - Kluczowe funkcjonalności

  - Korzyści dla użytkowników

  - Wymagania systemowe

- **Rozdział 2: Szybki start**

  - Rejestracja i pierwsze logowanie

  - Konfiguracja pierwszego projektu

  - Pierwsza analiza kodu

  - Generowanie pierwszych testów

#### Część II: Praca z systemem (120-150 stron)

- **Rozdział 3: Zarządzanie projektami**

  - Tworzenie i konfiguracja projektów

  - Zarządzanie członkami zespołu

  - Ustawienia projektu

  - Archiwizacja i usuwanie projektów

- **Rozdział 4: Analiza kodu źródłowego**

  - Wgrywanie kodu (plik, repozytorium, ZIP)

  - Konfiguracja analizy

  - Interpretacja wyników

  - Testy regresji kodu

  - Przykłady dla różnych języków programowania

- **Rozdział 5: Analiza dokumentacji**

  - Wspierane formaty dokumentacji

  - Wgrywanie dokumentacji

  - Porównywanie dokumentacji z kodem

  - Generowanie testów z dokumentacji

- **Rozdział 6: Analiza UML i GUI**

  - Wgrywanie diagramów UML

  - Analiza interfejsów użytkownika

  - Generowanie testów UI

  - Testy regresji GUI

- **Rozdział 7: Analiza bezpieczeństwa**

  - Skanowanie podatności

  - Interpretacja wyników bezpieczeństwa

  - Rekomendacje naprawcze

  - Generowanie testów bezpieczeństwa

- **Rozdział 8: Generowanie testów**

  - Wybór frameworka testowego

  - Konfiguracja generowania

  - Przeglądanie i edycja przypadków testowych

  - Eksport testów

- **Rozdział 9: Raporty i eksport**

  - Generowanie raportów

  - Dostosowywanie raportów

  - Eksport do różnych formatów

  - Integracja z systemami zewnętrznymi

#### Część III: Zaawansowane funkcje (80-100 stron)

- **Rozdział 10: Integracje**

  - Integracja z GitHub/GitLab

  - Integracja z Jira/TestRail

  - Integracja z CI/CD (Jenkins, GitHub Actions, Azure DevOps)

  - Webhooks i API

- **Rozdział 11: Praca z CLI**

  - Instalacja testgen-cli

  - Podstawowe komendy

  - Automatyzacja z CLI

  - Przykłady użycia w skryptach

- **Rozdział 12: Dostępność i personalizacja**

  - Ustawienia dostępności (WCAG)

  - Personalizacja interfejsu

  - Skróty klawiszowe

  - Motywy kolorystyczne

#### Część IV: Administracja i zarządzanie (40-60 stron)

- **Rozdział 13: Zarządzanie kontem i subskrypcją**

  - Ustawienia konta

  - Zmiana planu subskrypcji

  - Zarządzanie płatnościami

  - Faktury i historia płatności

- **Rozdział 14: Bezpieczeństwo i prywatność**

  - Zarządzanie hasłem i MFA

  - Tokeny API

  - Logi audytowe

  - RODO i prywatność danych

#### Część V: Rozwiązywanie problemów (30-50 stron)

- **Rozdział 15: FAQ**

  - Najczęściej zadawane pytania

  - Typowe problemy i rozwiązania

- **Rozdział 16: Troubleshooting**

  - Problemy z analizą kodu

  - Problemy z generowaniem testów

  - Problemy z integracjami

  - Problemy z wydajnością

- **Rozdział 17: Wsparcie techniczne**

  - Jak uzyskać pomoc

  - Kanały wsparcia

  - Zgłaszanie błędów

  - Propozycje nowych funkcji

### **9.2.2.** Przykładowa strona z dokumentacji użytkownika

#### Rozdział 4.2: Wgrywanie kodu źródłowego

**System TestGEN oferuje trzy sposoby wgrywania kodu do analizy:**

**Metoda 1: Wgrywanie pojedynczych plików**

1.  Na stronie głównej projektu kliknij przycisk **\"Nowa analiza\"**

2.  Wybierz opcję **\"Wgraj pliki\"**

3.  Przeciągnij pliki do obszaru przesyłania lub kliknij **\"Wybierz
    pliki\"**

4.  Wybierz język programowania (opcjonalnie - system wykryje
    automatycznie)

5.  Kliknij **\"Rozpocznij analizę\"**

**Wskazówka:** Możesz wgrać do 100 plików jednocześnie. Maksymalny
rozmiar pojedynczego pliku to 100 MB (Plan Basic) lub 500 MB (Plan
Professional).

**Metoda 2: Wgrywanie archiwum ZIP**

1.  Spakuj swój projekt do pliku ZIP

2.  Na stronie głównej projektu kliknij **\"Nowa analiza\"**

3.  Wybierz opcję **\"Wgraj archiwum ZIP\"**

4.  Wybierz plik ZIP z dysku

5.  System automatycznie rozpozna strukturę projektu

6.  Kliknij **\"Rozpocznij analizę\"**

**Metoda 3: Integracja z repozytorium Git**

1.  W ustawieniach projektu przejdź do zakładki **\"Integracje\"**

2.  Wybierz **\"Połącz z GitHub\"** lub **\"Połącz z GitLab\"**

3.  Autoryzuj dostęp do repozytorium

4.  Wybierz repozytorium z listy

5.  Wybierz branch do analizy

6.  Włącz automatyczną analizę przy każdym push (opcjonalnie)

**Najlepsza praktyka:** Dla projektów rozwijanych aktywnie zalecamy
integrację z Git i włączenie automatycznej analizy. System będzie
automatycznie analizował każdą zmianę i generował testy regresji.
