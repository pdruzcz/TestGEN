import { TestBed } from "@angular/core/testing";
import type { Mock } from "vitest";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { environment } from "../../../../environments/environment";
import {
  TmsExportService,
  defaultMapping,
} from "./tms-export.service";

/** `saveBlob` jest `protected` — spy potrzebuje publicznego widoku typu. */
interface SaveBlobHost {
  saveBlob(blob: Blob, filename: string): void;
}

const API = `${environment.apiUrl}/test-cases/export`;
const PROJECT_ID = "p1";

describe("TmsExportService", () => {
  let service: TmsExportService;
  let httpMock: HttpTestingController;
  let saveBlobSpy: Mock;

  beforeEach(() => {
    localStorage.removeItem("testgen:tms-mapping:testrail");
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(TmsExportService);
    httpMock = TestBed.inject(HttpTestingController);
    saveBlobSpy = vi
      .spyOn(service as unknown as SaveBlobHost, "saveBlob")
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.removeItem("testgen:tms-mapping:testrail");
  });

  it("sends format, ids and mapping; downloads file with server filename (AC1/AC6/AC7)", () => {
    let result: string | undefined;
    const mapping = defaultMapping("testrail");
    service
      .exportToTms(PROJECT_ID, ["tc1", "tc2"], "testrail", mapping)
      .subscribe((filename) => (result = filename));

    expect(service.isExportingSignal()).toBe(true);

    const req = httpMock.expectOne(API);
    expect(req.request.method).toBe("POST");
    expect(req.request.body.format).toBe("testrail");
    expect(req.request.body.ids).toEqual(["tc1", "tc2"]);
    expect(req.request.body.fieldMapping).toEqual(mapping);
    expect(req.request.responseType).toBe("blob");

    req.flush(new Blob(["\ufeffTitle;Section"], { type: "text/csv" }), {
      headers: {
        "Content-Disposition":
          'attachment; filename="testgen_projekt_2026-07-23_testrail.csv"',
      },
    });

    expect(result).toBe("testgen_projekt_2026-07-23_testrail.csv");
    expect(saveBlobSpy).toHaveBeenCalledWith(
      expect.any(Blob),
      "testgen_projekt_2026-07-23_testrail.csv",
    );
    expect(service.isExportingSignal()).toBe(false);
  });

  it("falls back to a generated filename without Content-Disposition", () => {
    let result: string | undefined;
    service
      .exportToTms(PROJECT_ID, [], "json", defaultMapping("json"))
      .subscribe((filename) => (result = filename));

    httpMock
      .expectOne(API)
      .flush(new Blob(["{}"], { type: "application/json" }));

    expect(result).toMatch(/^testgen_export_\d{4}-\d{2}-\d{2}_json\.json$/);
  });

  it("resets the exporting flag on error", () => {
    let failed = false;
    service
      .exportToTms(PROJECT_ID, ["tc1"], "xray", defaultMapping("xray"))
      .subscribe({ error: () => (failed = true) });

    httpMock
      .expectOne(API)
      .flush(new Blob([""]), { status: 500, statusText: "Server Error" });

    expect(failed).toBe(true);
    expect(service.isExportingSignal()).toBe(false);
    expect(saveBlobSpy).not.toHaveBeenCalled();
  });

  it("persists field mapping in localStorage (AC5)", () => {
    const custom = { ...defaultMapping("testrail"), section: "source_function" };
    service.saveMapping("testrail", custom);

    const stored = JSON.parse(
      localStorage.getItem("testgen:tms-mapping:testrail") ?? "{}",
    );
    expect(stored["section"]).toBe("source_function");
    expect(service.loadMapping("testrail")["section"]).toBe("source_function");
    expect(service.fieldMappingSignal()["section"]).toBe("source_function");
  });

  it("returns defaults when localStorage is empty or corrupted", () => {
    expect(service.loadMapping("testrail")).toEqual(defaultMapping("testrail"));
    localStorage.setItem("testgen:tms-mapping:testrail", "{nie-json");
    expect(service.loadMapping("testrail")).toEqual(defaultMapping("testrail"));
  });
});
