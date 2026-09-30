# **7.2.** Skalowalność

### **7.2.1.** Skalowanie horyzontalne

**REQ-SCALE-001:** Wszystkie mikroserwisy muszą wspierać skalowanie
horyzontalne (stateless design).

**REQ-SCALE-002:** System musi automatycznie skalować się w górę/dół w
oparciu o obciążenie (auto-scaling).

**Parametry auto-scalingu:**

- CPU utilization \> 70% → scale up

- CPU utilization \< 30% (przez 10 min) → scale down

- Queue depth \> 100 → scale up workers

- Memory utilization \> 80% → scale up

### **7.2.2.** Limity systemu

  -----------------------------------------------------------------------
  **Zasób**                   **Limit na Plan    **Limit na Plan
                              Basic**            Professional**
  --------------------------- ------------------ ------------------------
  Użytkownicy                 5                  Unlimited

  Projekty                    10                 Unlimited

  Analiz/miesiąc              100                Unlimited

  Wygenerowane testy/miesiąc  1,000              Unlimited

  Storage                     10 GB              100 GB

  Rozmiar pojedynczego pliku  100 MB             500 MB

  API Calls/dzień             1,000              10,000
  -----------------------------------------------------------------------
