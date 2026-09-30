import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../../environments/environment";
import {
  EMPTY_FILTERS,
  ResultItem,
  ResultsService,
  normalizeSeverity,
  normalizeStatus,
} from "./results.service";

const apiUrl = environment.apiUrl;

const securityFindingsResponse = {
  findings: [
    {
      id: "sf-1",
      scanId: "scan-1",
      scanType: "sast",
      vulnerabilityType: "SQL Injection",
      severity: "critical",
      cweId: "CWE-89",
      owaspCategory: "A03",
      filePath: "backend/app/db.py",
      lineStart: 42,
      lineEnd: 44,
      codeSnippet: "cursor.execute(query)",
      description: "Niesparametryzowane zapytanie SQL",
      confidence: 0.9,
      source: "native",
      status: "open",
      taintPath: null,
      findingMetadata: null,
      recommendation: null,
      cvssScore: 9.1,
      cvssVector: null,
      priority: 1,
      effort: "low",
      escalationReason: null,
      createdAt: "2026-07-01T10:00:00Z",
    },
    {
      id: "sf-2",
      scanId: "scan-1",
      scanType: "sast",
      vulnerabilityType: "XSS",
      severity: "medium",
      cweId: null,
      owaspCategory: null,
      filePath: "frontend/src/app/x.ts",
      lineStart: 5,
      lineEnd: 6,
      codeSnippet: null,
      description: "Potencjalny XSS",
      confidence: 0.6,
      source: "native",
      status: "false_positive",
      taintPath: null,
      findingMetadata: null,
      recommendation: null,
      cvssScore: null,
      cvssVector: null,
      priority: null,
      effort: null,
      escalationReason: null,
      createdAt: null,
    },
  ],
  total: 2,
  page: 1,
  pageSize: 200,
};

const gapFindingsResponse = {
  findings: [
    {
      id: "gf-1",
      projectId: "p1",
      requirementId: "r1",
      codeEntityId: null,
      gapType: "missing",
      description: "Brak implementacji logowania audytowego",
      requirementText: "System loguje operacje użytkownika",
      codeReference: "backend/app/audit.py",
      matchScore: 12.5,
      matchMethod: "sem",
      context: null,
      severity: "warning",
      skeletonCode: "def audit_log():\n    pass",
      skeletonLanguage: "python",
      createdAt: "2026-07-01T10:00:00Z",
    },
  ],
  total: 1,
  page: 1,
  size: 100,
  summary: {
    totalRequirements: 10,
    totalCodeEntities: 20,
    missingCount: 1,
    differentCount: 0,
    extraCount: 0,
    inconsistentCount: 0,
    avgMatchScore: 55.0,
    coveragePercentage: 90.0,
  },
};

describe("ResultsService", () => {
  let service: ResultsService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ResultsService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  function loadFixtures(): void {
    service.loadResults("p1").subscribe();
    httpTesting
      .expectOne((req) =>
        req.url === `${apiUrl}/projects/p1/security-findings`,
      )
      .flush(securityFindingsResponse);
    httpTesting
      .expectOne((req) => req.url === `${apiUrl}/projects/p1/gap-findings`)
      .flush(gapFindingsResponse);
  }

  it("should be created with empty state", () => {
    expect(service.resultsSignal()).toEqual([]);
    expect(service.filtersSignal()).toEqual(EMPTY_FILTERS);
    expect(service.searchQuerySignal()).toBe("");
    expect(service.isLoadingSignal()).toBe(false);
  });

  describe("normalizeSeverity", () => {
    it("maps security severities", () => {
      expect(normalizeSeverity("critical")).toBe("critical");
      expect(normalizeSeverity("high")).toBe("high");
      expect(normalizeSeverity("medium")).toBe("medium");
      expect(normalizeSeverity("low")).toBe("low");
      expect(normalizeSeverity("info")).toBe("low");
    });

    it("maps gap severities (warning → medium)", () => {
      expect(normalizeSeverity("warning")).toBe("medium");
      expect(normalizeSeverity(null)).toBe("low");
    });
  });

  describe("normalizeStatus", () => {
    it("maps triage statuses to nowy/zaakceptowany/odrzucony", () => {
      expect(normalizeStatus("open")).toBe("new");
      expect(normalizeStatus("acknowledged")).toBe("accepted");
      expect(normalizeStatus("fixed")).toBe("accepted");
      expect(normalizeStatus("false_positive")).toBe("rejected");
    });
  });

  describe("loadResults", () => {
    it("merges security and gap findings into unified items", () => {
      loadFixtures();
      const items = service.resultsSignal();
      expect(items.length).toBe(3);
      expect(items.filter((i) => i.source === "security").length).toBe(2);
      expect(items.filter((i) => i.source === "gap").length).toBe(1);
      expect(service.isLoadingSignal()).toBe(false);
    });

    it("maps security finding fields", () => {
      loadFixtures();
      const item = service
        .resultsSignal()
        .find((i) => i.id === "sf-1") as ResultItem;
      expect(item.title).toBe("SQL Injection");
      expect(item.severity).toBe("critical");
      expect(item.status).toBe("new");
      expect(item.module).toBe("backend");
      expect(item.language).toBe("python");
      expect(item.lineStart).toBe(42);
    });

    it("maps gap finding fields with skeleton as suggested fix", () => {
      loadFixtures();
      const item = service
        .resultsSignal()
        .find((i) => i.id === "gf-1") as ResultItem;
      expect(item.severity).toBe("medium");
      expect(item.type).toBe("missing");
      expect(item.suggestedFix).toContain("def audit_log");
    });
  });

  describe("filteredResultsComputed (AC2, AC4)", () => {
    beforeEach(() => loadFixtures());

    it("filters by severity", () => {
      service.setFilters({ ...EMPTY_FILTERS, severities: ["critical"] });
      const items = service.filteredResultsComputed();
      expect(items.length).toBe(1);
      expect(items[0].id).toBe("sf-1");
    });

    it("filters by status", () => {
      service.setFilters({ ...EMPTY_FILTERS, status: "rejected" });
      expect(service.filteredResultsComputed().length).toBe(1);
      expect(service.filteredResultsComputed()[0].id).toBe("sf-2");
    });

    it("filters by module", () => {
      service.setFilters({ ...EMPTY_FILTERS, module: "frontend" });
      expect(service.filteredResultsComputed().length).toBe(1);
    });

    it("filters by file substring", () => {
      service.setFilters({ ...EMPTY_FILTERS, file: "db.py" });
      expect(service.filteredResultsComputed().length).toBe(1);
      expect(service.filteredResultsComputed()[0].id).toBe("sf-1");
    });

    it("searches in title and description (case-insensitive)", () => {
      service.setSearchQuery("sql");
      const items = service.filteredResultsComputed();
      expect(items.length).toBe(1);
      expect(items[0].id).toBe("sf-1");
    });
  });

  describe("sortedResultsComputed (AC3)", () => {
    beforeEach(() => loadFixtures());

    it("sorts by severity ascending by default (critical first)", () => {
      const items = service.sortedResultsComputed();
      expect(items[0].severity).toBe("critical");
    });

    it("toggleSort flips direction on the same column", () => {
      service.toggleSort("severity");
      expect(service.sortSignal().direction).toBe("desc");
      const items = service.sortedResultsComputed();
      expect(items[items.length - 1].severity).toBe("critical");
    });

    it("toggleSort switches column with asc direction", () => {
      service.toggleSort("title");
      expect(service.sortSignal()).toEqual({
        column: "title",
        direction: "asc",
      });
    });
  });

  it("exposes unique types, modules and files for the filter panel", () => {
    loadFixtures();
    expect(service.availableTypesComputed()).toEqual(["missing", "sast"]);
    expect(service.availableModulesComputed()).toEqual(["backend", "frontend"]);
    expect(service.availableFilesComputed().length).toBe(3);
  });
});
