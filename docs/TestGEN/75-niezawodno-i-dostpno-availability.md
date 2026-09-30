# **7.5.** Niezawodność i dostępność (Availability)

### **7.5.1.** Uptime i SLA

**REQ-AVAIL-001:** System musi zapewniać dostępność na poziomie 99.5%
(SLA dla Plan Basic).

**REQ-AVAIL-002:** System musi zapewniać dostępność na poziomie 99.9%
(SLA dla Plan Professional).

  -----------------------------------------------------------------------
  **SLA**                **Dopuszczalny         **Dopuszczalny
                         downtime/rok**         downtime/miesiąc**
  ---------------------- ---------------------- -------------------------
  99.5%                  43.8 godzin            3.65 godzin

  99.9%                  8.76 godzin            43.8 minut

  99.99% (cel            52.6 minut             4.38 minut
  długoterminowy)                               
  -----------------------------------------------------------------------

### **7.5.2.** Backup i disaster recovery

**REQ-AVAIL-003:** System musi wykonywać automatyczne backupy baz danych
co 24 godziny.

**REQ-AVAIL-004:** Backupy muszą być przechowywane przez minimum 30 dni.

**REQ-AVAIL-005:** RPO (Recovery Point Objective) musi wynosić
maksymalnie 1 godzinę.

**REQ-AVAIL-006:** RTO (Recovery Time Objective) musi wynosić
maksymalnie 4 godziny.

### **7.5.3.** Monitoring i alerting

**Metryki monitorowane 24/7:**

- **Uptime** - Dostępność wszystkich serwisów

- **Response time** - Czasy odpowiedzi API (P50, P95, P99)

- **Error rate** - Procent błędnych requestów (4xx, 5xx)

- **CPU & Memory utilization** - Zużycie zasobów

- **Database performance** - Query time, connections, locks

- **Queue depth** - Długość kolejek zadań

- **Storage usage** - Zużycie dysku i obiektowego storage

**Alerty (PagerDuty / OpsGenie):**

- Critical: Uptime \< 99%, Error rate \> 5%, API response P95 \> 5s

- Warning: Uptime \< 99.5%, Error rate \> 2%, CPU \> 80%

- Info: Unusual traffic patterns, Queue depth growing
