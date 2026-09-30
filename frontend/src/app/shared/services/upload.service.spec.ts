import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import {
  HttpEventType,
  HttpUploadProgressEvent,
  HttpResponse,
} from "@angular/common/http";
import { vi } from "vitest";
import { UploadService } from "./upload.service";

describe("UploadService", () => {
  let service: UploadService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(UploadService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("is created", () => {
    expect(service).toBeTruthy();
  });

  it("POSTs FormData to the provided URL with progress enabled", async () => {
    const file = new File(["abc"], "note.txt", { type: "text/plain" });
    const url = "https://example.test/upload";

    const promise = new Promise<void>((resolve, reject) => {
      service.uploadFile(file, url).subscribe({
        next: (resp) => {
          expect(resp.status).toBe(200);
          resolve();
        },
        error: reject,
      });
    });

    const req = httpTesting.expectOne(url);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toBeInstanceOf(FormData);
    expect(req.request.reportProgress).toBe(true);

    req.flush(
      { ok: true },
      { status: 200, statusText: "OK" },
    );

    await promise;
  });

  it("invokes onProgress callback with computed percent", () => {
    const file = new File(["data"], "doc.pdf");
    const url = "https://example.test/upload";
    const onProgress = vi.fn();

    service.uploadFile(file, url, "files", onProgress).subscribe();

    const req = httpTesting.expectOne(url);
    // Emit a progress event
    req.event({
      type: HttpEventType.UploadProgress,
      loaded: 50,
      total: 100,
    } as HttpUploadProgressEvent);
    // Emit final response
    req.event(
      new HttpResponse({ status: 200, body: { ok: true } }),
    );

    expect(onProgress).toHaveBeenCalledWith(50);
  });

  it("uses custom fieldName in FormData", () => {
    const file = new File(["x"], "a.pdf");
    const url = "https://example.test/upload";

    service.uploadFile(file, url, "attachments").subscribe();

    const req = httpTesting.expectOne(url);
    const body = req.request.body as FormData;
    expect(body.has("attachments")).toBe(true);
    expect(body.get("attachments")).toBeInstanceOf(File);
    req.flush({});
  });

  it("cancelUpload marks the entry as cancelled in progressSignal", () => {
    const file = new File(["x"], "cancel.pdf");
    const url = "https://example.test/upload";

    service.uploadFile(file, url).subscribe();

    // Snapshot entries then cancel by matching filename
    const before = service.progressSignal();
    expect(before).toHaveLength(1);
    const id = before[0].id;

    service.cancelUpload(id);

    const after = service.progressSignal();
    expect(after[0].status).toBe("cancelled");

    // Clean up HTTP request
    httpTesting.expectOne(url).flush({});
  });

  it("computeSummary aggregates statuses", () => {
    const file = new File(["x"], "summary.pdf");
    const url = "https://example.test/upload";

    service.uploadFile(file, url).subscribe();
    const id = service.progressSignal()[0].id;

    service.cancelUpload(id);

    const summary = service.computeSummary();
    expect(summary).toEqual({
      success: 0,
      failed: 0,
      skipped: 1,
    });

    httpTesting.expectOne(url).flush({});
  });

  it("reset() clears progress state", () => {
    const file = new File(["x"], "reset.pdf");
    const url = "https://example.test/upload";

    service.uploadFile(file, url).subscribe();
    expect(service.progressSignal().length).toBeGreaterThan(0);

    service.reset();
    expect(service.progressSignal()).toEqual([]);

    httpTesting.expectOne(url).flush({});
  });
});
