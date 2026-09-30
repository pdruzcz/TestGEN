import { TestBed } from "@angular/core/testing";
import {
  FileValidationService,
  DEFAULT_DOCUMENT_EXTENSIONS,
  DEFAULT_MAX_FILE_SIZE_BYTES,
} from "./file-validation.service";

describe("FileValidationService", () => {
  let service: FileValidationService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(FileValidationService);
  });

  describe("default constants", () => {
    it("exposes the expected default extensions", () => {
      expect(DEFAULT_DOCUMENT_EXTENSIONS).toContain(".pdf");
      expect(DEFAULT_DOCUMENT_EXTENSIONS).toContain(".docx");
      expect(DEFAULT_DOCUMENT_EXTENSIONS).toContain(".zip");
    });

    it("uses 50 MB as the default max file size", () => {
      expect(DEFAULT_MAX_FILE_SIZE_BYTES).toBe(50 * 1024 * 1024);
    });
  });

  describe("validate()", () => {
    it("accepts a valid PDF under the size limit", () => {
      const file = new File(["data"], "doc.pdf", { type: "application/pdf" });
      const result = service.validate(file);
      expect(result.valid).toBe(true);
      expect(result.errorMessage).toBe("");
    });

    it("accepts uppercase extension", () => {
      const file = new File(["data"], "DOC.PDF");
      const result = service.validate(file);
      expect(result.valid).toBe(true);
    });

    it("rejects unsupported extension with Polish message", () => {
      const file = new File(["data"], "malware.exe");
      const result = service.validate(file);
      expect(result.valid).toBe(false);
      expect(result.errorMessage).toContain("Nieobsługiwane rozszerzenie");
      expect(result.errorMessage).toContain(".exe");
    });

    it("rejects file with no extension", () => {
      const file = new File(["data"], "README");
      const result = service.validate(file);
      expect(result.valid).toBe(false);
      expect(result.errorMessage).toContain("(brak)");
    });

    it("rejects file exceeding size limit", () => {
      const large = new File(["x"], "big.pdf");
      Object.defineProperty(large, "size", { value: 60 * 1024 * 1024 });
      const result = service.validate(large);
      expect(result.valid).toBe(false);
      expect(result.errorMessage).toContain("przekracza limit");
    });

    it("rejects empty file", () => {
      const empty = new File([], "empty.pdf");
      Object.defineProperty(empty, "size", { value: 0 });
      const result = service.validate(empty);
      expect(result.valid).toBe(false);
      expect(result.errorMessage).toContain("pusty");
    });

    it("honours custom allowedExtensions override", () => {
      const file = new File(["data"], "image.png");
      const result = service.validate(file, {
        allowedExtensions: [".png", ".jpg"],
      });
      expect(result.valid).toBe(true);
    });

    it("honours custom maxSizeBytes override", () => {
      const file = new File(["data"], "doc.pdf");
      Object.defineProperty(file, "size", { value: 200 });
      const result = service.validate(file, { maxSizeBytes: 100 });
      expect(result.valid).toBe(false);
    });
  });

  describe("findDuplicate()", () => {
    it("returns the matching ref when name + size match", () => {
      const file = new File(["data"], "spec.pdf");
      Object.defineProperty(file, "size", { value: 1024 });
      const dup = service.findDuplicate(file, [
        { filename: "spec.pdf", size: 1024 },
      ]);
      expect(dup).not.toBeNull();
      expect(dup?.filename).toBe("spec.pdf");
    });

    it("returns null when name matches but size differs", () => {
      const file = new File(["data"], "spec.pdf");
      Object.defineProperty(file, "size", { value: 1024 });
      const dup = service.findDuplicate(file, [
        { filename: "spec.pdf", size: 2048 },
      ]);
      expect(dup).toBeNull();
    });

    it("returns null when no existing files", () => {
      const file = new File(["data"], "spec.pdf");
      const dup = service.findDuplicate(file, []);
      expect(dup).toBeNull();
    });
  });

  describe("partition()", () => {
    it("splits a mixed list into accepted + rejected", () => {
      const good = new File(["data"], "ok.pdf");
      const bad = new File(["data"], "evil.exe");
      const { accepted, rejected } = service.partition([good, bad]);
      expect(accepted).toEqual([good]);
      expect(rejected).toHaveLength(1);
      expect(rejected[0].file).toBe(bad);
      expect(rejected[0].reason).toContain("Nieobsługiwane rozszerzenie");
    });

    it("returns empty arrays for empty input", () => {
      const { accepted, rejected } = service.partition([]);
      expect(accepted).toEqual([]);
      expect(rejected).toEqual([]);
    });
  });

  describe("formatSize()", () => {
    it("formats bytes", () => {
      expect(service.formatSize(512)).toBe("512 B");
    });

    it("formats KB", () => {
      expect(service.formatSize(2048)).toBe("2.0 KB");
    });

    it("formats MB", () => {
      expect(service.formatSize(5 * 1024 * 1024)).toBe("5.0 MB");
    });

    it("formats GB", () => {
      expect(service.formatSize(2 * 1024 * 1024 * 1024)).toBe("2.00 GB");
    });

    it("handles invalid values", () => {
      expect(service.formatSize(-1)).toBe("0 B");
      expect(service.formatSize(Number.NaN)).toBe("0 B");
    });
  });
});
