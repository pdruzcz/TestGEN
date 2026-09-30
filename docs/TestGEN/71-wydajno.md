# **7.1.** Wydajność

### **7.1.1.** Wymagania czasowe

  -----------------------------------------------------------------------
  **Operacja**                                **Wymaganie**   **Cel**
  ------------------------------------------- --------------- -----------
  Logowanie użytkownika                       \< 2s           \< 1s

  Wczytanie dashboard                         \< 3s           \< 2s

  Upload pliku (do 100MB)                     \< 30s          \< 15s

  Analiza małego projektu (\< 10k LOC)        \< 5 min        \< 2 min

  Analiza średniego projektu (10-100k LOC)    \< 30 min       \< 15 min

  Analiza dużego projektu (\> 100k LOC)       \< 2h           \< 1h

  Generowanie testów (100 przypadków)         \< 10 min       \< 5 min

  Eksport raportu (PDF/HTML)                  \< 30s          \< 15s
  -----------------------------------------------------------------------

**REQ-PERF-001:** System musi przetwarzać co najmniej 1000 LOC na
sekundę w trybie analizy standardowej.

**REQ-PERF-002:** Czas odpowiedzi API nie może przekraczać 200ms dla 95%
requestów (P95).

### **7.1.2.** Wymagania throughput

**REQ-PERF-003:** System musi obsługiwać minimum 100 równoczesnych
użytkowników bez degradacji wydajności.

**REQ-PERF-004:** System musi przetwarzać minimum 50 analiz kodu
równocześnie.
