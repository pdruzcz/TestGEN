# **5.4.** Integracje zewnętrzne

TestGEN musi się zintegrować z wszystkimi poniższymi systemami. Integracja powinna polegać na wykorzystaniu wystawionego API, akceptowalne jest jednak gdy integracja poprze API jest zbyt długotrwała lub kosztowna, aby wynikiem działania TestGEN był plik w formacie danego framwroku (np.. Jako opcja eksportu) i zapewnienie jego ręcznego wklejenia bez dodatkowego ręcznego formatowania


### **5.4.1.** Integracja z systemami kontroli wersji

#### GitHub Integration

\# GitHub App / OAuth App - Webhooks: push, pull_request, release - API:
Repos, Contents, Pull Requests, Comments - Actions: Automatic analysis
on PR creation \# Example webhook payload handling POST /webhooks/github
{ \"action\": \"opened\", \"pull_request\": { \"head\": { \"sha\":
\"\...\" }, \"base\": { \"sha\": \"\...\" } } } → Trigger regression
analysis → Post results as PR comment

#### GitLab Integration

\# GitLab CI/CD Integration - Webhooks: Push, Merge Request - API:
Projects, Repository Files, Merge Requests - CI/CD: Custom pipeline jobs
\# .gitlab-ci.yml example testgen_analysis: stage: test script: -
testgen-cli analyze \--project-id \$CI_PROJECT_ID - testgen-cli
generate-tests \--output ./tests artifacts: paths: - tests/

### **5.4.2.** Integracja z systemami zarządzania testami

#### Jira / Xray Integration

\# Jira REST API Integration POST /api/v1/integrations/jira/export {
\"test_suite_id\": \"uuid\", \"jira_project_key\": \"PROJ\",
\"issue_type\": \"Test\", \"mapping\": { \"test_case_id\":
\"custom_field_10001\", \"priority\": \"priority\", \"status\":
\"status\" } } \# Automatic test case creation - Create Jira issues for
each test case - Link to requirements (Epic, Story) - Update test
execution results - Sync bidirectionally

#### TestRail Integration

\# TestRail API Integration POST /api/v1/integrations/testrail/sync {
\"test_suite_id\": \"uuid\", \"testrail_project_id\": 123,
\"section_id\": 456 } \# Features: - Create test cases in TestRail - Map
test case fields - Create test runs - Update test results - Generate
reports

### **5.4.3.** Integracja z systemami CI/CD

#### Jenkins Integration

\# Jenkins Pipeline Integration pipeline { agent any stages {
stage(\'TestGEN Analysis\') { steps { script { // Trigger TestGEN
analysis sh \'testgen-cli analyze \--code ./src\' // Generate tests sh
\'testgen-cli generate \--framework junit\' // Run generated tests sh
\'mvn test\' } } } stage(\'Security Scan\') { steps { sh \'testgen-cli
security-scan \--report security-report.json\' } } } post { always { //
Publish TestGEN reports publishHTML(target: \[ reportDir:
\'testgen-reports\', reportFiles: \'index.html\', reportName: \'TestGEN
Report\' \]) } } }

#### GitHub Actions Integration

\# .github/workflows/testgen.yml name: TestGEN Analysis on:
pull_request: branches: \[ main, develop \] push: branches: \[ main \]
jobs: analyze: runs-on: ubuntu-latest steps: - uses:
actions/checkout@v3 - name: TestGEN Analysis uses:
testgen/analyze-action@v1 with: api-key: \${{ secrets.TESTGEN_API_KEY }}
project-id: \${{ secrets.TESTGEN_PROJECT_ID }} analysis-type: \'full\' -
name: Generate Tests uses: testgen/generate-tests-action@v1 with:
framework: \'pytest\' output-path: \'./tests/generated\' - name: Run
Generated Tests run: \| pip install -r requirements.txt pytest
tests/generated/ - name: Upload Results uses: actions/upload-artifact@v3
with: name: testgen-results path: testgen-reports/

#### Azure DevOps Integration

\# azure-pipelines.yml trigger: - main - develop pool: vmImage:
\'ubuntu-latest\' steps: - task: UsePythonVersion@0 inputs: versionSpec:
\'3.10\' - script: \| pip install testgen-cli testgen-cli login
\--api-key \$(TESTGEN_API_KEY) displayName: \'Setup TestGEN CLI\' -
script: \| testgen-cli analyze \--code \$(Build.SourcesDirectory)
testgen-cli generate \--framework pytest displayName: \'Analyze and
Generate Tests\' - script: \| pytest tests/generated/
\--junitxml=test-results.xml displayName: \'Run Generated Tests\' -
task: PublishTestResults@2 inputs: testResultsFormat: \'JUnit\'
testResultsFiles: \'\*\*/test-results.xml\' displayName: \'Publish Test
Results\'

### **5.4.4.** Integracja z systemami płatności

#### Stripe Integration

**REQ-PAYMENT-001:** System musi obsługiwać płatności cykliczne
(subskrypcje) poprzez Stripe.

\# Stripe Subscription Management POST /api/v1/subscriptions/create {
\"plan_id\": \"basic\|professional\", \"payment_method\":
\"pm_card_xxx\", \"customer_email\": \"user@example.com\" } \# Webhook
handling POST /webhooks/stripe Events: - invoice.payment_succeeded -
invoice.payment_failed - customer.subscription.deleted -
customer.subscription.updated \# Subscription tiers Basic Plan: - Price:
\$49/month - Features: Limited analysis, 100 tests/month - Stripe Price
ID: price_xxx Professional Plan: - Price: \$199/month - Features:
Unlimited analysis, CI/CD integration - Stripe Price ID: price_yyy
