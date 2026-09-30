import {
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  Output,
  computed,
  inject,
  signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { HttpErrorResponse } from "@angular/common/http";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatTooltipModule } from "@angular/material/tooltip";
import { forkJoin, of } from "rxjs";
import { map, catchError } from "rxjs/operators";
import {
  FileValidationService,
  DEFAULT_DOCUMENT_EXTENSIONS,
  DEFAULT_MAX_FILE_SIZE_BYTES,
} from "../services/file-validation.service";
import { UploadService } from "../services/upload.service";

interface UploadEntry {
  id: string;
  filename: string;
  size: number;
  percent: number;
  status: "pending" | "uploading" | "success" | "failed" | "cancelled";
  errorMessage?: string;
}

interface UploadSummary {
  success: number;
  failed: number;
  skipped: number;
}

/** Polskie etykiety zasobów z body 429 ``limit_reached`` (jak banner quota). */
const QUOTA_RESOURCE_LABELS: Record<string, string> = {
  analyses: "analiz",
  test_cases: "przypadków testowych",
  storage_bytes: "miejsca na pliki",
  files_per_analysis: "plików na analizę",
};

/**
 * Dedykowany komunikat przekroczenia limitu planu (429 ``limit_reached``
 * z QuotaService — body AC1: ``{error, resource, limit, current, plan}``).
 * „Spróbuj ponownie później" byłoby błędne: limit storage jest kumulatywny,
 * a limity okresowe odnawiają się dopiero z nowym okresem rozliczeniowym.
 */
function quotaMessage(body: { resource?: string; plan?: string }): string {
  const resource =
    QUOTA_RESOURCE_LABELS[body.resource ?? ""] ?? body.resource ?? "zasobu";
  const plan = body.plan ? ` w planie ${body.plan}` : "";
  if (body.resource === "storage_bytes") {
    return `Osiągnięto limit ${resource}${plan} — usuń zbędne pliki lub uaktualnij plan.`;
  }
  return `Osiągnięto limit ${resource}${plan} — odnowi się z początkiem kolejnego okresu rozliczeniowego; uaktualnij plan, aby zwiększyć limity.`;
}

/**
 * Reusable drag-and-drop file upload component — Story 6.2.
 *
 * Features:
 * - Drag-and-drop zone + multi-select button (AC1, AC2)
 * - Validation: extension, size, duplicates (AC3, AC4)
 * - Per-file progress bar (AC5)
 * - Upload summary: success/failed/skipped (AC6)
 * - Keyboard accessible: Enter opens file dialog, Escape cancels (AC7)
 * - ARIA: role="region", aria-label, aria-live="polite" (AC8)
 *
 * Usage:
 *   <app-file-upload
 *     uploadUrl="/api/v1/projects/123/upload-documents"
 *   />
 */
@Component({
  selector: "app-file-upload",
  standalone: true,
  imports: [
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatTooltipModule,
  ],
  template: `
    <div class="file-upload-wrapper">
      <!-- Drop zone -->
      <section
        class="drop-zone"
        [class.drag-active]="isDragActive()"
        role="region"
        aria-label="Strefa uploadu plików"
        tabindex="0"
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
        (click)="triggerFileDialog()"
        (keydown.enter)="onEnterKey($event)"
        (keydown.escape)="onEscapeKey($event)"
      >
        <mat-icon aria-hidden="true" class="drop-icon">cloud_upload</mat-icon>
        <p class="drop-main">Przeciągnij pliki tutaj lub kliknij, aby wybrać</p>
        <p class="drop-hint">
          Dozwolone: {{ allowedExtensionsLabel() }} · Max:
          {{ maxSizeLabel() }}
        </p>
        <input
          #fileInput
          hidden
          type="file"
          multiple
          [attr.accept]="acceptAttr()"
          (change)="onFilesSelected($event)"
          aria-label="Wybierz pliki"
        />
      </section>

      <!-- Validation errors (AC3) -->
      @if (rejectedFiles().length > 0) {
        <ul class="rejection-list" role="alert" aria-live="assertive">
          @for (r of rejectedFiles(); track r.filename) {
            <li>
              <strong>{{ r.filename }}</strong> — {{ r.reason }}
            </li>
          }
        </ul>
      }

      <!-- Duplicate prompt (AC4) -->
      @if (duplicatePrompt(); as dup) {
        <div class="dup-dialog" role="dialog" aria-label="Wykryto duplikat">
          <p>
            Plik <strong>{{ dup.file.name }}</strong> ({{
              validation.formatSize(dup.file.size)
            }}) już istnieje w projekcie. Zamienić czy anulować?
          </p>
          <div class="dup-actions">
            <button
              mat-raised-button
              color="primary"
              type="button"
              (click)="confirmReplace()"
            >
              Zamień
            </button>
            <button mat-button type="button" (click)="cancelReplace()">
              Anuluj
            </button>
          </div>
        </div>
      }

      <!-- File list with per-file progress (AC1, AC5) -->
      @if (entries().length > 0) {
        <ul class="file-list" aria-live="polite">
          @for (entry of entries(); track entry.id) {
            <li class="file-row" [class.file-error]="entry.status === 'failed'">
              <div class="file-row-main">
                <mat-icon aria-hidden="true" class="file-icon">{{
                  iconFor(entry)
                }}</mat-icon>
                <div class="file-meta">
                  <span class="file-name">{{ entry.filename }}</span>
                  <span class="file-size">
                    {{ validation.formatSize(entry.size) }}
                    @if (entry.status === "success") {
                      <span class="badge badge-ok">OK</span>
                    } @else if (entry.status === "failed") {
                      <span class="badge badge-err">Błąd</span>
                    } @else if (entry.status === "cancelled") {
                      <span class="badge badge-skip">Anulowano</span>
                    }
                  </span>
                </div>
                <div class="file-actions">
                  @if (entry.status === "uploading") {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="Anuluj upload"
                      aria-label="Anuluj upload"
                      (click)="
                        onCancelUpload(entry.id); $event.stopPropagation()
                      "
                    >
                      <mat-icon>cancel</mat-icon>
                    </button>
                  }
                </div>
              </div>
              @if (entry.status === "uploading" || entry.status === "pending") {
                <mat-progress-bar
                  mode="determinate"
                  [value]="entry.percent"
                  aria-label="Postęp uploadu"
                />
              }
              @if (entry.errorMessage) {
                <p class="file-error-msg">{{ entry.errorMessage }}</p>
              }
            </li>
          }
        </ul>
      }

      <!-- Summary (AC6) -->
      @if (showSummary()) {
        <div class="summary" role="status" aria-live="polite">
          <div class="summary-row summary-success">
            <mat-icon>check_circle</mat-icon>
            <span>Sukces: {{ summary().success }}</span>
          </div>
          <div class="summary-row summary-failed">
            <mat-icon>error</mat-icon>
            <span>Błędy: {{ summary().failed }}</span>
          </div>
          <div class="summary-row summary-skipped">
            <mat-icon>remove_circle</mat-icon>
            <span>Pominięte: {{ summary().skipped }}</span>
          </div>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .file-upload-wrapper {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .drop-zone {
        border: 2px dashed #1976d2;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        cursor: pointer;
        transition:
          background 0.2s ease,
          border-color 0.2s ease;
        outline: none;
      }
      .drop-zone:focus-visible {
        outline: 3px solid #1976d2;
        outline-offset: 2px;
      }
      .drop-zone.drag-active {
        background: #e3f2fd;
        border-color: #1565c0;
      }
      .drop-icon {
        font-size: 48px;
        height: 48px;
        width: 48px;
        color: #1976d2;
      }
      .drop-main {
        font-weight: 500;
        margin: 0.5rem 0 0.25rem;
        color: #1a1a1a;
      }
      .drop-hint {
        font-size: 0.85rem;
        color: #6b7280;
        margin: 0;
      }
      .rejection-list {
        margin: 0;
        padding: 12px 16px 12px 32px;
        background: #fdecea;
        color: #611a15;
        border-radius: 8px;
        font-size: 13px;
      }
      .rejection-list li {
        margin: 4px 0;
      }
      .dup-dialog {
        background: #fff8e1;
        border-radius: 8px;
        padding: 16px;
        color: #1a1a1a;
      }
      .dup-dialog p {
        margin: 0 0 12px;
      }
      .dup-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
      }
      .file-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .file-row {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .file-row.file-error {
        background: #fdecea;
        border-color: #b71c1c;
      }
      .file-row-main {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .file-icon {
        color: #1976d2;
      }
      .file-meta {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .file-name {
        font-weight: 500;
        color: #1a1a1a;
      }
      .file-size {
        font-size: 12px;
        color: #6b7280;
      }
      .badge {
        margin-left: 8px;
        font-size: 10px;
        padding: 1px 6px;
        border-radius: 9999px;
        font-weight: 600;
        text-transform: uppercase;
      }
      .badge-ok {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .badge-err {
        background: #ffebee;
        color: #b71c1c;
      }
      .badge-skip {
        background: #fff8e1;
        color: #e65100;
      }
      .file-error-msg {
        margin: 0;
        font-size: 12px;
        color: #b71c1c;
      }
      .summary {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-top: 8px;
      }
      .summary-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        border-radius: 8px;
        font-size: 14px;
      }
      .summary-success {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .summary-failed {
        background: #ffebee;
        color: #b71c1c;
      }
      .summary-skipped {
        background: #fff8e1;
        color: #e65100;
      }
      @media (max-width: 768px) {
        .summary {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class FileUploadComponent {
  readonly validation = inject(FileValidationService);
  private readonly uploadService = inject(UploadService);
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) uploadUrl!: string;
  @Input() allowedExtensions: ReadonlyArray<string> =
    DEFAULT_DOCUMENT_EXTENSIONS;
  @Input() maxFileSizeBytes: number = DEFAULT_MAX_FILE_SIZE_BYTES;
  @Input() existingFiles: ReadonlyArray<{ filename: string; size: number }> =
    [];
  @Input() fieldName = "files";

  @Output() uploadComplete = new EventEmitter<UploadSummary>();

  readonly isDragActive = signal(false);
  readonly rejectedFiles = signal<Array<{ filename: string; reason: string }>>(
    [],
  );
  readonly duplicatePrompt = signal<{ file: File } | null>(null);
  readonly entries = signal<UploadEntry[]>([]);

  private pendingBatch: File[] = [];

  readonly allowedExtensionsLabel = computed(() =>
    this.allowedExtensions.join(", "),
  );
  readonly maxSizeLabel = computed(() =>
    this.validation.formatSize(this.maxFileSizeBytes),
  );
  readonly acceptAttr = computed(() => this.allowedExtensions.join(","));

  readonly summary = computed<UploadSummary>(() => {
    let success = 0;
    let failed = 0;
    let skipped = 0;
    for (const entry of this.entries()) {
      if (entry.status === "success") success++;
      else if (entry.status === "failed") failed++;
      else if (entry.status === "cancelled") skipped++;
    }
    return { success, failed, skipped };
  });

  readonly showSummary = computed(
    () =>
      this.entries().length > 0 &&
      this.entries().every(
        (e) =>
          e.status === "success" ||
          e.status === "failed" ||
          e.status === "cancelled",
      ),
  );

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragActive.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.isDragActive.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragActive.set(false);
    const items = event.dataTransfer?.files;
    if (items && items.length > 0) {
      void this.processFiles(Array.from(items));
    }
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      void this.processFiles(Array.from(input.files));
      input.value = "";
    }
  }

  onEnterKey(event: Event): void {
    event.preventDefault();
    this.triggerFileDialog();
  }

  onEscapeKey(event: Event): void {
    event.preventDefault();
    if (this.duplicatePrompt()) {
      this.cancelReplace();
    }
  }

  onCancelUpload(id: string): void {
    this.uploadService.cancelUpload(id);
    this.markEntry(id, "cancelled");
  }

  /** Open file dialog — called by click handler or Enter key. */
  triggerFileDialog(): void {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.accept = this.acceptAttr();
    input.onchange = (e) => this.onFilesSelected(e);
    input.click();
  }

  confirmReplace(): void {
    this.duplicatePrompt.set(null);
    const batch = this.pendingBatch;
    this.pendingBatch = [];
    void this.uploadBatch(batch);
  }

  cancelReplace(): void {
    this.duplicatePrompt.set(null);
    this.pendingBatch = [];
  }

  iconFor(entry: UploadEntry): string {
    if (entry.status === "success") return "check_circle";
    if (entry.status === "failed") return "error";
    if (entry.status === "cancelled") return "remove_circle";
    return "description";
  }

  /**
   * AC3 + AC4: validate, then check duplicates, then upload.
   */
  private async processFiles(selected: File[]): Promise<void> {
    this.rejectedFiles.set([]);

    const { accepted, rejected } = this.validation.partition(selected, {
      allowedExtensions: this.allowedExtensions,
      maxSizeBytes: this.maxFileSizeBytes,
    });

    this.rejectedFiles.set(
      rejected.map((r) => ({ filename: r.file.name, reason: r.reason })),
    );

    if (accepted.length === 0) return;

    // Check first file for duplicate (AC4)
    const dup = this.validation.findDuplicate(accepted[0], this.existingFiles);
    if (dup) {
      this.duplicatePrompt.set({ file: accepted[0] });
      this.pendingBatch = accepted;
      return;
    }

    await this.uploadBatch(accepted);
  }

  private async uploadBatch(files: File[]): Promise<void> {
    if (files.length === 0) return;

    // Pre-populate entries (pending state)
    const initialEntries: UploadEntry[] = files.map((f) => ({
      id: this.makeId(f),
      filename: f.name,
      size: f.size,
      percent: 0,
      status: "pending" as const,
    }));
    this.entries.update((prev) => [...prev, ...initialEntries]);

    // Subscribe to per-file progress updates from UploadService.
    // Each observable resolves to `{ ok, err? }` so failures don't break forkJoin.
    const observables = files.map((file) => {
      const id = initialEntries.find((e) => e.filename === file.name)!.id;
      return this.uploadService
        .uploadFile(file, this.uploadUrl, this.fieldName, (percent) => {
          this.markEntry(id, "uploading", percent);
        })
        .pipe(
          map(() => ({
            ok: true as const,
            err: undefined as undefined | HttpErrorResponse,
          })),
          catchError((err: HttpErrorResponse) =>
            of({ ok: false as const, err }),
          ),
          takeUntilDestroyed(this.destroyRef),
        );
    });

    forkJoin(observables)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((results) => {
        for (let i = 0; i < results.length; i++) {
          const r = results[i];
          const id = initialEntries.find(
            (e) => e.filename === files[i].name,
          )!.id;
          if (r.ok) {
            this.markEntry(id, "success", 100);
          } else {
            this.markEntry(
              id,
              "failed",
              undefined,
              this.extractErrorMessage(r.err),
            );
          }
        }
        this.uploadComplete.emit(this.summary());
      });
  }

  private markEntry(
    id: string,
    status: UploadEntry["status"],
    percent?: number,
    errorMessage?: string,
  ): void {
    this.entries.update((list) =>
      list.map((e) =>
        e.id === id
          ? {
              ...e,
              status,
              percent: percent ?? e.percent,
              errorMessage: errorMessage ?? e.errorMessage,
            }
          : e,
      ),
    );
  }

  private makeId(file: File): string {
    const rand = Math.random().toString(36).slice(2, 8);
    return `${file.name}:${file.size}:${rand}`;
  }

  private extractErrorMessage(err: HttpErrorResponse): string {
    if (err.status === 0) return "Brak połączenia z serwerem.";
    if (err.status === 401) return "Sesja wygasła. Zaloguj się ponownie.";
    if (err.status === 403) return "Brak uprawnień do tej operacji.";
    if (err.status === 413) return "Plik jest zbyt duży.";
    // 429 z limitem planu (body ``limit_reached`` z QuotaService) ma własny
    // komunikat — „spróbuj później" nie pomoże: storage jest kumulatywny,
    // limity okresowe odnawiają się dopiero z nowym okresem rozliczeniowym.
    if (err.status === 429 && err.error?.error === "limit_reached") {
      return quotaMessage(err.error);
    }
    if (err.status === 429)
      return "Przekroczony limit zapytań. Spróbuj ponownie później.";
    return (
      err.error?.detail ||
      err.error?.message ||
      "Wystąpił błąd podczas uploadu."
    );
  }
}
