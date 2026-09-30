# **5.2.** Komponenty backendowe

### **5.2.1.** Stos technologiczny backend

  ---------------------------------------------------------------------------
  **Komponent**    **Technologia**          **Uzasadnienie**
  ---------------- ------------------------ ---------------------------------
  API Gateway      Kong / AWS API Gateway   Wydajność, skalowalność, bogata
                                            funkcjonalność

  Mikroserwisy     Python (FastAPI) /       Wydajność, ekosystem AI/ML, async
                   Node.js (Express)        support

  Message Queue    RabbitMQ / AWS SQS       Asynchroniczne przetwarzanie,
                                            kolejkowanie zadań

  Task Scheduler   Celery / Apache Airflow  Distributed task execution,
                                            scheduling

  Konteneryzacja   Docker + Kubernetes      Orchestration, scaling,
                                            deployment
  ---------------------------------------------------------------------------

### **5.2.2.** Code Analysis Service

#### Odpowiedzialności

- Przyjmowanie kodu źródłowego od użytkowników

- Detekcja języka programowania i frameworka

- Parsowanie kodu do AST

- Ekstrakcja metadanych (klasy, metody, zależności)

- Delegowanie analizy do silnika TestSpark

- Zwracanie wyników analizy

#### API Endpoints

POST /api/v1/code/analyze - Request Body: { \"code\": \"\...\",
\"language\": \"python\", \"framework\": \"django\" } - Response: {
\"analysis_id\": \"uuid\", \"status\": \"processing\" } GET
/api/v1/code/analysis/{analysis_id} - Response: { \"status\":
\"completed\", \"results\": {\...} } POST /api/v1/code/compare - Request
Body: { \"code_v1\": \"\...\", \"code_v2\": \"\...\" } - Response: {
\"diff\": \[\...\], \"regression_tests\": \[\...\] }

### **5.2.3.** Documentation Analysis Service

#### Odpowiedzialności

- Przyjmowanie dokumentacji w różnych formatach

- Ekstrakcja tekstu (OCR dla PDF/obrazów)

- Klasyfikacja sekcji dokumentacji

- Analiza NLP i ekstrakcja wymagań

- Porównywanie z kodem/dokumentacją techniczną

- Generowanie przypadków testowych

### **5.2.4.** Test Generation Service

#### Odpowiedzialności

- Agregacja wyników z różnych serwisów analizy

- Generowanie opisowych przypadków testowych

- Generowanie kodu testów w wybranych frameworkach

- Tworzenie struktury projektów testowych

- Generowanie raportów

- Eksport do systemów zewnętrznych

#### API Endpoints

POST /api/v1/tests/generate - Request Body: { \"analysis_ids\":
\[\"uuid1\", \"uuid2\"\], \"framework\": \"pytest\", \"test_types\":
\[\"unit\", \"integration\"\] } - Response: { \"test_suite_id\":
\"uuid\", \"status\": \"generating\" } GET
/api/v1/tests/suite/{suite_id} - Response: { \"status\": \"completed\",
\"test_cases\": \[\...\], \"code_files\": \[\...\], \"download_url\":
\"\...\" } POST /api/v1/tests/export - Request Body: { \"suite_id\":
\"uuid\", \"format\": \"jira\", \"config\": {\...} } - Response: {
\"export_id\": \"uuid\", \"status\": \"success\" }
