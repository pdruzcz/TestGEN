# **2.1.** Wizja produktu

Projekt TestGEN to innowacyjne rozwiązanie dostępne w modelu
SaaS oferujące subskrypcję w ramach dwóch pakietów
cenowych dostosowane do potrzeb użytkowników dla firm wykorzystujące
sztuczną inteligencję (uczenie maszynowe i sieci neuronowe) do
automatyzacji procesu testów oprogramowania.

Głównym celem systemu jest automatyzacja analizy dokumentacji
technicznej, kodu źródłowego, diagramów UML oraz interfejsów użytkownika
(GUI) i generowanie na tej podstawie przypadków testowych oraz
kodu testowego dla popularnych frameworków, takich jak JUnit, NUnit czy
pytest.

System będzie mógł obsługiwać kod, diagramy UML oraz testy GUI dla
aplikacji desktopowych i mobilnych, webowych oraz oprogramowanie dla
urządzeń IoT.

### **2.1.1.** Główne komponenty systemu

TestGEN składa się z następujących kluczowych komponentów:

1.  **Silnik TestSpark** - autorski silnik AI do automatycznego
    generowania przypadków testowych i kodów, wykorzystujący modele
    uczenia maszynowego do analizy kodu i dokumentacji. Silnik powinien
    zwierać i implementować wszystkie poniższe moduły. Powinny one być
    klasami, które wywołują API jakiegoś modelu i dawać w wyniku to, co
    one wygenerują. Tam gdzie to możliwe zawężać zapytanie do modelu aby
    np. losowo dawał wynik z X opcji. W ramach projektu trzeba postawić
    jakiś LLA (który może ale nie musi być w ogóle wywoływana bo
    zapytania będą szły po API do jakiegoś płatnego modelu)

    a.  **Moduły analizy**:

        i.  Moduł analizy kodu źródłowego

        ii. Moduł analizy dokumentacji technicznej

        iii. Moduł analizy diagramów UML

        iv. Moduł analizy interfejsów GUI

    b.  **Moduły generowania testów**:

        i.  Generator testów jednostkowych

        ii. Generator testów integracyjnych

        iii. Generator testów systemowych

        iv. Generator testów regresji

    c.  **Moduły bezpieczeństwa**:

        i.  Moduł audytu bezpieczeństwa

        ii. Moduł detekcji podatności (SQL injection, XSS, błędy
            autoryzacji)

        iii. Moduł analizy zgodności kodu z dokumentacją

2.  **Graficzny interfejs użytkownika (GUI)** - intuicyjny
    interfejs zgodny z WCAG 2.1

3.  **System płatności** - moduł obsługi subskrypcji i
    rozliczeń
