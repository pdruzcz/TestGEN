/**
 * TestCase DTOs — 1:1 with backend/app/schemas/test_case.py.
 *
 * Interceptor `snakeCaseInterceptor` automatically converts
 *   - outgoing request bodies: camelCase → snake_case
 *   - incoming response bodies: snake_case → camelCase
 * so interfaces below use camelCase.
 *
 * Query params are NOT transformed — they must be sent as snake_case.
 */

export type TestPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type TestType =
  | "UNIT"
  | "INTEGRATION"
  | "E2E"
  | "SECURITY"
  | "PERFORMANCE"
  | "POSITIVE"
  | "NEGATIVE"
  | "BOUNDARY"
  | "ACCESSIBILITY"
  | "SEMANTIC"
  | "DATABASE";
export type TestFramework =
  | "PYTEST"
  | "JUNIT"
  | "NUNIT"
  | "MOCHA"
  | "JEST"
  | "SELENIUM"
  | "PLAYWRIGHT"
  | "APPIUM"
  | "CYPRESS"
  | "SIKULIX"
  | "PHPUNIT"
  | "PEST";
export type TestCaseStatus =
  | "DRAFT"
  | "READY"
  | "PASSED"
  | "FAILED"
  | "SKIPPED"
  | "DISABLED";

/** Kroki testowe przechowywane w BE jako JSONB dict — konwencja {items: [...]}. */
export interface TestCaseSteps {
  items?: string[];
  [key: string]: unknown;
}

export interface TestCase {
  id: string;
  tenantId: string;
  analysisResultId: string | null;
  sourceFileId: string | null;
  title: string;
  description: string | null;
  priority: TestPriority;
  type: TestType;
  framework: TestFramework;
  status: TestCaseStatus;
  language: string | null;
  testCode: string | null;
  imports: string | null;
  setupCode: string | null;
  teardownCode: string | null;
  preconditions: string | null;
  steps: TestCaseSteps | string | null;
  expectedResult: string | null;
  testData: string | null;
  sourceFunction: string | null;
  sourceClass: string | null;
  sourceEndpoint: string | null;
  scenarioDescription: string | null;
  scenarioRationale: string | null;
  edgeCaseDescription: string | null;
  confidenceScore: number | null;
  tags: string[] | null;
  /** Story 1.53 (FR70) — referencja do obiektu bazy (tabela/FK/migracja). */
  dbObject?: string | null;
  /** Story 8.11 — powiązanie z TMS; puste, gdy przypadek nie był synchronizowany. */
  tmsExternalId?: string | null;
  tmsSyncedAt?: string | null;
  isEdited: boolean;
  reviewedAt: string | null;
  reviewedBy: string | null;
  lastExecutedAt: string | null;
  lastExecutionResult: string | null;
  executionCount: number;
  passCount: number;
  failCount: number;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface TestCaseExecution {
  id: string;
  testCaseId: string;
  executedAt: string;
  executionDurationMs: number | null;
  status: string;
  errorMessage: string | null;
  errorStackTrace: string | null;
  stdout: string | null;
  stderr: string | null;
  linesCovered: number | null;
  branchesCovered: number | null;
  coveragePercentage: number | null;
  environment: string | null;
  runnerVersion: string | null;
}

export interface TestCaseListResponse {
  testCases: TestCase[];
  total: number;
  statusCounts: StatusCounts;
}

export interface StatusCounts {
  ready: number;
  passed: number;
  failed: number;
  skipped: number;
  draft: number;
  disabled: number;
}

export interface TestCaseListQuery {
  page?: number;
  pageSize?: number;
  projectId?: string | null;
  analysisResultId?: string | null;
  sourceFileId?: string | null;
  type?: TestType | null;
  status?: TestCaseStatus | null;
  framework?: TestFramework | null;
  priority?: TestPriority | null;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

export interface TestCaseCreatePayload {
  title: string;
  description?: string | null;
  priority?: TestPriority;
  type?: TestType;
  framework?: TestFramework;
  language?: string | null;
  testCode?: string | null;
  sourceFileId?: string | null;
  analysisResultId?: string | null;
}

export interface TestCaseUpdatePayload {
  title?: string | null;
  description?: string | null;
  priority?: TestPriority | null;
  type?: TestType | null;
  testCode?: string | null;
  steps?: TestCaseSteps | null;
  expectedResult?: string | null;
  status?: TestCaseStatus | null;
}

/** Story 6.5, AC5 — zbiorcze akcje. */
export interface TestCaseBulkUpdatePayload {
  ids: string[];
  status?: TestCaseStatus | null;
  priority?: TestPriority | null;
}

export interface BulkActionResponse {
  affected: number;
}

/** Story 6.5, AC7 — historia zmian z audit logu. */
export interface TestCaseHistoryEntry {
  changedAt: string;
  author: string | null;
  action: string;
  field: string;
  oldValue: string | null;
  newValue: string | null;
}

export interface TestCaseHistoryResponse {
  entries: TestCaseHistoryEntry[];
  total: number;
}

export interface AnalysisResult {
  id: string;
  projectId: string;
  sourceFileId: string | null;
  engineMode: string;
  module: string | null;
  status:
    | "PENDING"
    | "RUNNING"
    | "COMPLETED"
    | "FAILED"
    | "TIMEOUT"
    | "PARTIAL_FAILURE";
  resultData: unknown;
  errorMessage: string | null;
  durationMs: number | null;
  completedAt: string | null;
  createdAt: string;
}
