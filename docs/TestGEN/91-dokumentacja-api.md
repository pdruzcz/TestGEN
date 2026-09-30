# **9.1.** Dokumentacja API

### **9.1.1.** Standardy dokumentacji API

**REQ-API-DOC-001:** Dokumentacja API musi być zgodna ze standardem
OpenAPI 3.0 (Swagger).

**REQ-API-DOC-002:** Każdy endpoint API musi być udokumentowany z
przykładami request/response.

Dokumentacja API będzie zawierać:

- **Opis endpointu** - szczegółowy opis funkcjonalności

- **Parametry** - wszystkie parametry (path, query, body) z typami i
  opisami

- **Request body schema** - schemat JSON z przykładami

- **Response schemas** - wszystkie możliwe kody odpowiedzi z przykładami

- **Error codes** - lista możliwych błędów i ich znaczenie

- **Authentication** - wymagania dotyczące autentykacji

- **Rate limiting** - limity wywołań dla danego endpointu

- **Przykłady użycia** - kompletne przykłady w różnych językach (curl,
  Python, JavaScript)

### **9.1.2.** Przykładowa dokumentacja endpointu

**POST** /api/v1/code/analyze

**Opis:** Inicjuje analizę kodu źródłowego. System wykryje język
programowania, framework i przeprowadzi pełną analizę statyczną
generując przypadki testowe.

**Autentykacja:** Bearer Token (JWT)

**Rate Limit:** 10 requests/minute (Basic), 100 requests/minute
(Professional)

#### Request Body

{ \"code\": \"string (required)\", \"language\": \"string (optional)\",
\"framework\": \"string (optional)\", \"analysis_options\": {
\"include_security\": \"boolean (default: true)\",
\"include_performance\": \"boolean (default: false)\", \"test_types\":
\[\"unit\", \"integration\", \"e2e\"\] }, \"metadata\": {
\"project_name\": \"string\", \"version\": \"string\" } }

#### Response 202 Accepted

{ \"analysis_id\": \"550e8400-e29b-41d4-a716-446655440000\", \"status\":
\"processing\", \"created_at\": \"2026-10-15T10:30:00Z\",
\"estimated_completion\": \"2026-10-15T10:35:00Z\", \"status_url\":
\"/api/v1/code/analysis/550e8400-e29b-41d4-a716-446655440000\" }

#### Response 400 Bad Request

{ \"error\": \"INVALID_REQUEST\", \"message\": \"Code parameter is
required\", \"details\": { \"field\": \"code\", \"constraint\":
\"not_empty\" } }

#### Response 401 Unauthorized

{ \"error\": \"UNAUTHORIZED\", \"message\": \"Invalid or expired token\"
}

#### Response 429 Too Many Requests

{ \"error\": \"RATE_LIMIT_EXCEEDED\", \"message\": \"Rate limit
exceeded. Try again in 30 seconds\", \"retry_after\": 30 }

#### Przykłady użycia

**cURL:**

curl -X POST https://api.testgen.io/v1/code/analyze \\ -H
\"Authorization: Bearer YOUR_API_KEY\" \\ -H \"Content-Type:
application/json\" \\ -d \'{ \"code\": \"def add(a, b):\\n return a +
b\", \"language\": \"python\", \"analysis_options\": {
\"include_security\": true, \"test_types\": \[\"unit\"\] } }\'

**Python:**

import requests url = \"https://api.testgen.io/v1/code/analyze\" headers
= { \"Authorization\": \"Bearer YOUR_API_KEY\", \"Content-Type\":
\"application/json\" } data = { \"code\": \"def add(a, b):\\n return a +
b\", \"language\": \"python\", \"analysis_options\": {
\"include_security\": True, \"test_types\": \[\"unit\"\] } } response =
requests.post(url, json=data, headers=headers) result = response.json()
print(f\"Analysis ID: {result\[\'analysis_id\'\]}\")

**JavaScript:**

const axios = require(\'axios\'); const analyzeCode = async () =\> { try
{ const response = await axios.post(
\'https://api.testgen.io/v1/code/analyze\', { code: \'def add(a, b):\\n
return a + b\', language: \'python\', analysis_options: {
include_security: true, test_types: \[\'unit\'\] } }, { headers: {
\'Authorization\': \'Bearer YOUR_API_KEY\', \'Content-Type\':
\'application/json\' } } ); console.log(\'Analysis ID:\',
response.data.analysis_id); } catch (error) { console.error(\'Error:\',
error.response.data); } }; analyzeCode();

### **9.1.3.** Główne grupy endpointów API

  ---------------------------------------------------------------------------
  **Grupa**        **Endpointy**                     **Opis**
  ---------------- --------------------------------- ------------------------
  Authentication   /auth/login\                      Autentykacja i
                   /auth/logout\                     zarządzanie sesją
                   /auth/refresh\                    
                   /auth/register                    

  Projects         /projects\                        Zarządzanie projektami
                   /projects/{id}\                   
                   /projects/{id}/settings           

  Code Analysis    /code/analyze\                    Analiza kodu źródłowego
                   /code/analysis/{id}\              
                   /code/compare                     

  Documentation    /docs/analyze\                    Analiza dokumentacji
                   /docs/analysis/{id}\              
                   /docs/compare                     

  UML/GUI          /uml/analyze\                     Analiza diagramów i GUI
                   /gui/analyze\                     
                   /gui/compare                      

  Security         /security/scan\                   Skanowanie
                   /security/vulnerabilities/{id}\   bezpieczeństwa
                   /security/recommendations/{id}    

  Test Generation  /tests/generate\                  Generowanie testów
                   /tests/suite/{id}\                
                   /tests/export                     

  Reports          /reports/generate\                Raporty i eksport
                   /reports/{id}\                    
                   /reports/{id}/download            

  Integrations     /integrations/github\             Integracje zewnętrzne
                   /integrations/jira\               
                   /integrations/testrail            

  Subscriptions    /subscriptions\                   Zarządzanie
                   /subscriptions/upgrade\           subskrypcjami
                   /billing/invoices                 
  ---------------------------------------------------------------------------

### **9.1.4.** Webhooks

System TestGEN wspiera webhooks do asynchronicznej komunikacji o
zdarzeniach:

  ------------------------------------------------------------------------
  **Event Type**         **Opis**             **Payload**
  ---------------------- -------------------- ----------------------------
  analysis.completed     Analiza zakończona   analysis_id, status,
                                              results_url

  analysis.failed        Analiza nieudana     analysis_id, error_code,
                                              error_message

  tests.generated        Testy wygenerowane   suite_id, test_count,
                                              download_url

  vulnerability.found    Wykryto podatność    vulnerability_id, severity,
                                              type, location

  subscription.updated   Subskrypcja          subscription_id, plan,
                         zaktualizowana       status
  ------------------------------------------------------------------------

#### Przykład webhook payload:

{ \"event\": \"analysis.completed\", \"timestamp\":
\"2026-10-15T10:35:00Z\", \"data\": { \"analysis_id\":
\"550e8400-e29b-41d4-a716-446655440000\", \"project_id\": \"proj_123\",
\"status\": \"completed\", \"results_url\":
\"https://api.testgen.io/v1/code/analysis/550e8400-e29b-41d4-a716-446655440000\",
\"summary\": { \"test_cases_generated\": 45, \"vulnerabilities_found\":
3, \"code_coverage_estimate\": \"78%\" } } }
