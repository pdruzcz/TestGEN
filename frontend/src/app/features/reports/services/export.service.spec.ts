import { TestBed } from "@angular/core/testing";
import type { Mock } from "vitest";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { environment } from "../../../../environments/environment";
import { ReportData } from "./report.service";
import {
  EXPORT_POLL_INTERVAL_MS,
  ExportService,
} from "./export.service";

/** `saveBlob` jest `protected` — spy potrzebuje publicznego widoku typu. */
interface SaveBlobHost {
  saveBlob(blob: Blob, filename: string): void;
}

const PROJECT_ID = "p1";
const EXPORT_ID = "e1";
const API = environment.apiUrl;

function makeReportData(): ReportData {
  return {
    projectId: PROJECT_ID,
    generatedAt: "2026-07-23T10:00:00Z",
    kpis: {
      complianceScore: 70,
      coveragePercentage: 60,
      totalFindings: 0,
      criticalCount: 0,
      highCount: 0,
      mediumCount: 0,
      lowCount: 0,
      testCasesTotal: 0,
      testCasesReady: 0,
      testCasesPassed: 0,
    },
    severityCounts: { critical: 0, high: 0, medium: 0, low: 0 },
    moduleScores: [],
    trendPoints: [],
    conclusions: [],
    findings: [],
  };
}

describe("ExportService", () => {
  let service: ExportService;
  let httpMock: HttpTestingController;
  let saveBlobSpy: Mock;

  // Aplikacja jest zoneless (brak zone.js), więc fakeAsync/tick nie działa —
  // pollingiem `timer(0, EXPORT_POLL_INTERVAL_MS)` sterują fake timery vitest.
  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ExportService);
    httpMock = TestBed.inject(HttpTestingController);
    saveBlobSpy = vi
      .spyOn(service as unknown as SaveBlobHost, "saveBlob")
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    httpMock.verify();
    vi.useRealTimers();
  });

  function flushRequest(): void {
    const req = httpMock.expectOne(
      `${API}/projects/${PROJECT_ID}/reports/export`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body.format).toBe("pdf");
    req.flush({ exportId: EXPORT_ID, status: "pending" });
  }

  function flushStatus(status: "pending" | "done" | "error"): void {
    httpMock.expectOne(`${API}/exports/${EXPORT_ID}/status`).flush({
      exportId: EXPORT_ID,
      status,
      exportFormat: "pdf",
      filename: "raport.pdf",
      error: status === "error" ? "boom" : null,
    });
  }

  it("polls status every 3s and downloads the file when done (AC1/AC8)", () => {
    let result: string | undefined;
    service
      .exportReport(PROJECT_ID, "pdf", "both", makeReportData())
      .subscribe((filename) => (result = filename));

    expect(service.exportStatusSignal()).toBe("pending");
    expect(service.activeFormatSignal()).toBe("pdf");

    flushRequest();
    vi.advanceTimersByTime(0);
    flushStatus("pending");
    vi.advanceTimersByTime(EXPORT_POLL_INTERVAL_MS);
    flushStatus("done");

    httpMock
      .expectOne(`${API}/exports/${EXPORT_ID}/download`)
      .flush(new Blob(["%PDF"], { type: "application/pdf" }));

    expect(result).toBe("raport.pdf");
    expect(saveBlobSpy).toHaveBeenCalledWith(
      expect.any(Blob),
      "raport.pdf",
    );
    expect(service.exportStatusSignal()).toBe("done");
    expect(service.activeFormatSignal()).toBeNull();
  });

  it("propagates export errors and resets the active format", () => {
    let failed = false;
    service
      .exportReport(PROJECT_ID, "pdf", "executive", makeReportData())
      .subscribe({ error: () => (failed = true) });

    flushRequest();
    vi.advanceTimersByTime(0);
    flushStatus("error");

    expect(failed).toBe(true);
    expect(saveBlobSpy).not.toHaveBeenCalled();
    expect(service.exportStatusSignal()).toBe("error");
    expect(service.activeFormatSignal()).toBeNull();
  });

  it("sends report payload in the request body", () => {
    service
      .exportReport(PROJECT_ID, "pdf", "both", makeReportData())
      .subscribe({ error: () => undefined });

    const req = httpMock.expectOne(
      `${API}/projects/${PROJECT_ID}/reports/export`,
    );
    expect(req.request.body.report.projectId).toBe(PROJECT_ID);
    expect(req.request.body.reportType).toBe("both");
    req.flush({ exportId: EXPORT_ID, status: "pending" });
    vi.advanceTimersByTime(0);
    flushStatus("error");
  });
});
