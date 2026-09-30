import { Injectable } from "@angular/core";

/**
 * Validator for file uploads — Story 6.2.
 *
 * Pure functions, no HTTP. Duplicate detection is performed against
 * a caller-provided list of already-uploaded files (name + size match).
 *
 * Messages are in Polish per project convention.
 */

export interface FileValidationResult {
  valid: boolean;
  /** Polish error message; empty when valid. */
  errorMessage: string;
}

export interface UploadedFileRef {
  filename: string;
  size: number;
}

/** Default allowed extensions for documentation uploads. */
export const DEFAULT_DOCUMENT_EXTENSIONS: ReadonlyArray<string> = [
  ".pdf",
  ".doc",
  ".docx",
  ".txt",
  ".md",
  ".html",
  ".htm",
  ".zip",
  ".rar",
];

/** Default per-file size cap (50 MB per AC3). */
export const DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;

function extensionOf(filename: string): string {
  const lower = filename.toLowerCase();
  const idx = lower.lastIndexOf(".");
  return idx === -1 ? "" : lower.slice(idx);
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

@Injectable({ providedIn: "root" })
export class FileValidationService {
  /**
   * Validate a single file against extension + size rules.
   * Does NOT check duplicates — see `findDuplicate`.
   */
  validate(
    file: File,
    options: {
      allowedExtensions?: ReadonlyArray<string>;
      maxSizeBytes?: number;
    } = {},
  ): FileValidationResult {
    const allowed = options.allowedExtensions ?? DEFAULT_DOCUMENT_EXTENSIONS;
    const maxSize = options.maxSizeBytes ?? DEFAULT_MAX_FILE_SIZE_BYTES;

    const ext = extensionOf(file.name);
    if (!allowed.includes(ext)) {
      return {
        valid: false,
        errorMessage: `Nieobsługiwane rozszerzenie "${ext || "(brak)"}". Dozwolone: ${allowed.join(", ")}.`,
      };
    }

    if (file.size > maxSize) {
      return {
        valid: false,
        errorMessage: `Plik przekracza limit ${formatBytes(maxSize)}. Rozmiar: ${formatBytes(file.size)}.`,
      };
    }

    if (file.size === 0) {
      return {
        valid: false,
        errorMessage: "Plik jest pusty.",
      };
    }

    return { valid: true, errorMessage: "" };
  }

  /**
   * Find a duplicate among already-uploaded files by name + size (AC4).
   * Returns the matching ref or null.
   */
  findDuplicate(
    file: File,
    existing: ReadonlyArray<UploadedFileRef>,
  ): UploadedFileRef | null {
    return (
      existing.find(
        (f) => f.filename === file.name && f.size === file.size,
      ) ?? null
    );
  }

  /**
   * Partition a file list into accepted and rejected in one pass.
   */
  partition(
    files: ReadonlyArray<File>,
    options: {
      allowedExtensions?: ReadonlyArray<string>;
      maxSizeBytes?: number;
    } = {},
  ): {
    accepted: File[];
    rejected: Array<{ file: File; reason: string }>;
  } {
    const accepted: File[] = [];
    const rejected: Array<{ file: File; reason: string }> = [];
    for (const file of files) {
      const result = this.validate(file, options);
      if (result.valid) {
        accepted.push(file);
      } else {
        rejected.push({ file, reason: result.errorMessage });
      }
    }
    return { accepted, rejected };
  }

  /** Expose formatter for UI components. */
  formatSize(bytes: number): string {
    return formatBytes(bytes);
  }
}
