# **3.4.** Interfejs użytkownika

### **3.4.1.** Wymagania ogólne GUI

**REQ-GUI-001:** Interfejs użytkownika musi być zgodny z WCAG 2.1 poziom
AA.

**REQ-GUI-002:** System musi zapewniać intuicyjną obsługę dla
użytkowników bez doświadczenia programistycznego.

Graficzny interfejs użytkownika (GUI) powinien zawierać:

- **Wizualne formularze** - umożliwiające łatwe wczytywanie plików i
  konfigurację testów

- **Podpowiedzi kontekstowe** - dymki z informacjami wyświetlane po
  najechaniu na elementy

- **Moduł asystenta AI** - chatbot pomagający w nawigacji i konfiguracji

- **Funkcję \"przeciągnij i upuść\"** - dla wygodnego dodawania plików
  źródłowych

### **3.4.2.** Wymagania dostępności WCAG 2.1

Interfejs musi spełniać następujące wymagania dostępności:

  ------------------------------------------------------------------------
  **Kryterium      **Wymaganie**          **Implementacja**
  WCAG**                                  
  ---------------- ---------------------- --------------------------------
  1.4.3 Kontrast   Współczynnik kontrastu Paleta kolorów z wysokim
  (minimum)        min. 4.5:1             kontrastem, tryb wysokiego
                                          kontrastu

  1.4.4 Zmiana     Możliwość powiększenia Responsywna typografia,
  rozmiaru tekstu  tekstu do 200%         kontrolki zoom

  2.1.1 Klawiatura Pełna obsługa          Tab navigation, keyboard
                   klawiatury             shortcuts, focus indicators

  4.1.2 Nazwa,     Elementy z             ARIA labels, roles, states dla
  rola, wartość    odpowiednimi           wszystkich interaktywnych
                   atrybutami ARIA        elementów
  ------------------------------------------------------------------------
