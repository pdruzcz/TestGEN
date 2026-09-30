import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { HttpErrorResponse, HttpResponse } from "@angular/common/http";
import { of, throwError } from "rxjs";
import { vi } from "vitest";

import { FileUploadComponent } from "./file-upload.component";
import { FileValidationService } from "../services/file-validation.service";
import { UploadService } from "../services/upload.service";

describe("FileUploadComponent", () => {
  let fixture: ComponentFixture<FileUploadComponent>;
  let component: FileUploadComponent;
  let validation: FileValidationService;
  let uploadService: {
    uploadFile: ReturnType<typeof vi.fn>;
    cancelUpload: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    uploadService = {
      uploadFile: vi.fn(),
      cancelUpload: vi.fn(),
    };

    TestBed.configureTestingModule({
      imports: [FileUploadComponent, NoopAnimationsModule],
      providers: [{ provide: UploadService, useValue: uploadService }],
    });

    fixture = TestBed.createComponent(FileUploadComponent);
    component = fixture.componentInstance;
    validation = TestBed.inject(FileValidationService);
    fixture.componentRef.setInput("uploadUrl", "https://example.test/upload");
  });

  it("creates the component with default inputs", () => {
    expect(component).toBeTruthy();
    expect(component.allowedExtensions).toContain(".pdf");
    expect(component.maxSizeLabel()).toContain("MB");
  });

  it("rejects unsupported files via onDrop", async () => {
    const bad = new File(["x"], "evil.exe");
    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { files: [bad] },
    } as unknown as DragEvent;

    component.onDrop(event);

    // Wait microtasks
    await Promise.resolve();
    expect(component.rejectedFiles()).toHaveLength(1);
    expect(component.rejectedFiles()[0].filename).toBe("evil.exe");
    expect(uploadService.uploadFile).not.toHaveBeenCalled();
  });

  it("shows duplicate prompt when file already exists", async () => {
    const dup = new File(["data"], "api-spec.pdf");
    Object.defineProperty(dup, "size", { value: 2048576 });

    fixture.componentRef.setInput("existingFiles", [
      { filename: "api-spec.pdf", size: 2048576 },
    ]);

    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { files: [dup] },
    } as unknown as DragEvent;

    component.onDrop(event);
    await Promise.resolve();

    expect(component.duplicatePrompt()).not.toBeNull();
    expect(component.duplicatePrompt()?.file.name).toBe("api-spec.pdf");
    expect(uploadService.uploadFile).not.toHaveBeenCalled();
  });

  it("uploads valid file and emits uploadComplete on success", async () => {
    const file = new File(["data"], "ok.pdf");
    uploadService.uploadFile.mockReturnValue(
      of(new HttpResponse({ status: 200, body: {} })),
    );

    await component["processFiles"]([file]);

    // Process internal upload observables
    await new Promise((r) => setTimeout(r, 0));

    expect(uploadService.uploadFile).toHaveBeenCalledTimes(1);
    const entries = component.entries();
    expect(entries).toHaveLength(1);
    expect(entries[0].status).toBe("success");
  });

  it("marks entry as failed on upload error", async () => {
    const file = new File(["data"], "boom.pdf");
    const err = new HttpErrorResponse({
      status: 500,
      error: { detail: "Server error" },
    });
    uploadService.uploadFile.mockReturnValue(throwError(() => err));

    await component["processFiles"]([file]);
    await new Promise((r) => setTimeout(r, 0));

    const entries = component.entries();
    expect(entries[0].status).toBe("failed");
    expect(entries[0].errorMessage).toContain("Server error");
  });

  it("cancel marks entry as cancelled", () => {
    const id = "test-id";
    // Push an entry directly
    component["entries"].set([
      {
        id,
        filename: "cancel.pdf",
        size: 100,
        percent: 10,
        status: "uploading",
      },
    ]);

    component.onCancelUpload(id);

    expect(uploadService.cancelUpload).toHaveBeenCalledWith(id);
    expect(component.entries()[0].status).toBe("cancelled");
  });

  it("iconFor returns expected icons per status", () => {
    expect(
      component.iconFor({
        id: "1",
        filename: "a",
        size: 0,
        percent: 0,
        status: "success",
      }),
    ).toBe("check_circle");
    expect(
      component.iconFor({
        id: "2",
        filename: "b",
        size: 0,
        percent: 0,
        status: "failed",
      }),
    ).toBe("error");
    expect(
      component.iconFor({
        id: "3",
        filename: "c",
        size: 0,
        percent: 0,
        status: "cancelled",
      }),
    ).toBe("remove_circle");
    expect(
      component.iconFor({
        id: "4",
        filename: "d",
        size: 0,
        percent: 0,
        status: "uploading",
      }),
    ).toBe("description");
  });

  it("summary computed signal aggregates counts", () => {
    component["entries"].set([
      {
        id: "1",
        filename: "a",
        size: 0,
        percent: 100,
        status: "success",
      },
      {
        id: "2",
        filename: "b",
        size: 0,
        percent: 0,
        status: "failed",
      },
      {
        id: "3",
        filename: "c",
        size: 0,
        percent: 0,
        status: "cancelled",
      },
    ]);
    expect(component.summary()).toEqual({
      success: 1,
      failed: 1,
      skipped: 1,
    });
  });

  it("confirmReplace clears prompt and uploads pending batch", async () => {
    const file = new File(["data"], "api-spec.pdf");
    Object.defineProperty(file, "size", { value: 2048576 });

    fixture.componentRef.setInput("existingFiles", [
      { filename: "api-spec.pdf", size: 2048576 },
    ]);

    uploadService.uploadFile.mockReturnValue(
      of(new HttpResponse({ status: 200 })),
    );

    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { files: [file] },
    } as unknown as DragEvent;
    component.onDrop(event);
    await Promise.resolve();

    expect(component.duplicatePrompt()).not.toBeNull();

    component.confirmReplace();
    await new Promise((r) => setTimeout(r, 0));

    expect(component.duplicatePrompt()).toBeNull();
    expect(uploadService.uploadFile).toHaveBeenCalled();
  });

  it("cancelReplace clears prompt and discards batch", async () => {
    const file = new File(["data"], "api-spec.pdf");
    Object.defineProperty(file, "size", { value: 2048576 });

    fixture.componentRef.setInput("existingFiles", [
      { filename: "api-spec.pdf", size: 2048576 },
    ]);

    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { files: [file] },
    } as unknown as DragEvent;
    component.onDrop(event);
    await Promise.resolve();

    component.cancelReplace();

    expect(component.duplicatePrompt()).toBeNull();
    expect(uploadService.uploadFile).not.toHaveBeenCalled();
  });

  it("extractErrorMessage maps common HTTP statuses to Polish messages", () => {
    const extract = component["extractErrorMessage"].bind(component);

    expect(extract(new HttpErrorResponse({ status: 0 }))).toContain(
      "Brak połączenia",
    );
    expect(extract(new HttpErrorResponse({ status: 401 }))).toContain(
      "Sesja wygasła",
    );
    expect(extract(new HttpErrorResponse({ status: 403 }))).toContain(
      "Brak uprawnień",
    );
    expect(extract(new HttpErrorResponse({ status: 413 }))).toContain(
      "zbyt duży",
    );
    expect(extract(new HttpErrorResponse({ status: 429 }))).toContain("limit");
  });

  it("extractErrorMessage: 429 limit_reached gets a dedicated plan-quota message — UI bug fix", () => {
    const extract = component["extractErrorMessage"].bind(component);

    // Storage jest kumulatywny — „spróbuj później" nie pomoże; komunikat
    // wskazuje usuwanie plików albo wyższy plan.
    const storage = extract(
      new HttpErrorResponse({
        status: 429,
        error: {
          error: "limit_reached",
          resource: "storage_bytes",
          limit: 10737418240,
          current: 10737418240,
          plan: "basic",
        },
      }),
    );
    expect(storage).toContain("miejsca na pliki");
    expect(storage).toContain("basic");
    expect(storage).toContain("usuń zbędne pliki");
    expect(storage).not.toContain("Spróbuj ponownie później");

    // Limity okresowe — reset z nowym okresem rozliczeniowym.
    const analyses = extract(
      new HttpErrorResponse({
        status: 429,
        error: {
          error: "limit_reached",
          resource: "analyses",
          limit: 10,
          current: 10,
          plan: "freemium",
        },
      }),
    );
    expect(analyses).toContain("analiz");
    expect(analyses).toContain("okresu rozliczeniowego");

    // Zwykły 429 (rate limit) — zostaje „spróbuj później".
    const rateLimit = extract(new HttpErrorResponse({ status: 429 }));
    expect(rateLimit).toContain("Spróbuj ponownie później");
  });

  it("validation service formats sizes correctly", () => {
    expect(validation.formatSize(1024)).toBe("1.0 KB");
    expect(validation.formatSize(1048576)).toBe("1.0 MB");
  });
});
