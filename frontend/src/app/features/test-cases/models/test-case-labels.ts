import { TestCaseStatus, TestPriority, TestType } from "./test-case.model";

/** Polskie etykiety słowników test case'ów (Story 6.5). */

export const PRIORITY_LABELS: Record<TestPriority, string> = {
  CRITICAL: "Krytyczny",
  HIGH: "Wysoki",
  MEDIUM: "Średni",
  LOW: "Niski",
};

export const TYPE_LABELS: Record<TestType, string> = {
  UNIT: "Jednostkowy",
  INTEGRATION: "Integracyjny",
  E2E: "E2E",
  SECURITY: "Bezpieczeństwa",
  PERFORMANCE: "Wydajnościowy",
  POSITIVE: "Pozytywny",
  NEGATIVE: "Negatywny",
  BOUNDARY: "Brzegowy",
  ACCESSIBILITY: "Dostępności",
  SEMANTIC: "Semantyczny",
  DATABASE: "Bazodanowy",
};

export const STATUS_LABELS: Record<TestCaseStatus, string> = {
  DRAFT: "Szkic",
  READY: "Gotowy",
  PASSED: "Zaliczony",
  FAILED: "Niezaliczony",
  SKIPPED: "Pominięty",
  DISABLED: "Wyłączony",
};

export const PRIORITY_OPTIONS = Object.entries(PRIORITY_LABELS) as [
  TestPriority,
  string,
][];
export const TYPE_OPTIONS = Object.entries(TYPE_LABELS) as [TestType, string][];
export const STATUS_OPTIONS = Object.entries(STATUS_LABELS) as [
  TestCaseStatus,
  string,
][];
