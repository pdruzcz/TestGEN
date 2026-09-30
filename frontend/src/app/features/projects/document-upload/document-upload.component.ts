import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatChip } from "@angular/material/chips";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatDialog } from "@angular/material/dialog";
import { RouterLink } from "@angular/router";
import { ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { DestroyRef } from "@angular/core";
import { HttpErrorResponse } from "@angular/common/http";
import { forkJoin } from "rxjs";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { DocumentService, DocumentFile } from "../services/document.service";
import {
  DocumentDeleteDialogComponent,
  DocumentDeleteDialogData,
} from "./document-delete-dialog.component";
import { nanoid } from "nanoid";

// Keep in sync with backend/app/services/project/upload_service.py
const DOCUMENT_EXTENSIONS: ReadonlyArray<string> = [
  ".pdf",
  ".docx",
  ".md",
  ".markdown",
  ".html",
  ".htm",
  ".txt",
];

const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100MB for Basic, 500MB for Professional

function extensionOf(filename: string): string {
  const lower = filename.toLowerCase();
  const idx = lower.lastIndexOf(".");
  return idx === -1 ? "" : lower.slice(idx);
}

function isDocumentExtension(filename: string): boolean {
  return DOCUMENT_EXTENSIONS.includes(extensionOf(filename));
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

interface UploadedDocument extends DocumentFile {
  /** Local UI status — maps from backend processingStatus + upload state. */
  status: "uploading" | "processing" | "ready" | "failed";
  uploadProgress?: number;
}

@Component({
  selector: "app-document-upload",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatChip,
    MatTooltipModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="upload-page">
      <app-navbar activeLink="projects" />

      <main class="upload-content" id="main-content" tabindex="-1">
        <div class="upload-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId()]"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do projektu
          </a>
          <h1 class="page-title">Dokumentacja projektu</h1>
          <p class="page-subtitle">
            Wgraj dokumentację techniczną (PDF, DOCX, MD, HTML, TXT) aby
            analizować wymagania.
          </p>
        </div>

        <!-- Upload Zone -->
        <section
          class="drop-zone"
          [class.drag-active]="isDragActive()"
          role="button"
          tabindex="0"
          aria-label="Strefa drag-and-drop dla dokumentów"
          (dragover)="onDragOver($event)"
          (dragleave)="onDragLeave($event)"
          (drop)="onDrop($event)"
          (click)="fileInput.click()"
          (keydown.enter)="fileInput.click()"
          (keydown.space)="fileInput.click(); $event.preventDefault()"
        >
          <mat-icon aria-hidden="true">description</mat-icon>
          <p class="drop-main">
            Przeciągnij dokumenty tutaj lub kliknij aby wybrać
          </p>
          <p class="drop-hint">
            Dozwolone formaty: {{ allowedExtensionsLabel }}
          </p>
          <p class="drop-hint">Maksymalny rozmiar: {{ maxFileSizeLabel }}</p>
          <input
            #fileInput
            hidden
            type="file"
            multiple
            accept=".pdf,.docx,.md,.markdown,.html,.htm,.txt"
            (change)="onFilesSelected($event)"
          />
        </section>

        @if (uploadError()) {
          <div class="error-banner" role="alert" aria-live="assertive">
            <mat-icon aria-hidden="true">error</mat-icon>
            {{ uploadError() }}
          </div>
        }

        @if (uploadSummary()) {
          <div class="success-banner" role="status" aria-live="polite">
            <mat-icon aria-hidden="true">check_circle</mat-icon>
            {{ uploadSummary() }}
          </div>
        }

        <!-- Uploaded Documents List -->
        <div class="documents-section">
          <h3 class="section-title">
            Wgrane dokumenty
            @if (uploadedDocuments().length > 0) {
              <span class="total-count"
                >({{ uploadedDocuments().length }})</span
              >
            }
          </h3>

          @if (isLoadingList()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner
                diameter="20"
                aria-label="Ładowanie dokumentów"
              ></mat-spinner>
              <span>Ładowanie dokumentów…</span>
            </div>
          } @else if (uploadedDocuments().length === 0) {
            <p class="empty">
              Brak dokumentów. Wgraj pierwszą dokumentację powyże.
            </p>
          } @else {
            <div class="documents-list">
              @for (doc of uploadedDocuments(); track doc.id) {
                <div class="document-card" [class]="getStatusClass(doc.status)">
                  <div class="doc-info">
                    <mat-icon aria-hidden="true">{{
                      getDocIcon(doc)
                    }}</mat-icon>
                    <div class="doc-details">
                      <span class="doc-filename">{{ doc.filename }}</span>
                      <span class="doc-meta">
                        {{ formatSize(doc.fileSize) }}
                        <ng-container *ngIf="doc.pageCount">
                          &bull; {{ doc.pageCount }} stron{{
                            doc.pageCount === 1 ? "" : "y"
                          }}</ng-container
                        >
                        <ng-container *ngIf="doc.docFormat">
                          &bull; {{ doc.docFormat.toUpperCase() }}</ng-container
                        >
                      </span>
                      @if (doc.docType) {
                        <mat-chip
                          [class]="docTypeChipClass(doc.docType!)"
                          [matTooltip]="classificationTooltip(doc)"
                          class="doc-type-chip"
                          >{{ docTypeLabel(doc.docType!) }}</mat-chip
                        >
                      }
                    </div>
                  </div>
                  <div class="doc-status">
                    @switch (doc.status) {
                      @case ("uploading") {
                        <mat-spinner
                          diameter="16"
                          aria-label="Wysyłanie"
                        ></mat-spinner>
                        <span>Wysyłanie…</span>
                      }
                      @case ("processing") {
                        <mat-spinner
                          diameter="16"
                          aria-label="Przetwarzanie"
                        ></mat-spinner>
                        <span>Przetwarzanie…</span>
                      }
                      @case ("ready") {
                        <mat-icon class="status-icon">check_circle</mat-icon>
                        <span>Gotowy</span>
                        <button
                          mat-button
                          color="primary"
                          size="small"
                          class="view-btn"
                          [routerLink]="[
                            '/projects',
                            projectId(),
                            'documents',
                            doc.id,
                          ]"
                        >
                          Podgląd
                        </button>
                        <button
                          mat-icon-button
                          size="small"
                          aria-label="Klasyfikuj ponownie"
                          class="reclassify-btn"
                          matTooltip="Klasyfikuj ponownie"
                          (click)="reclassify(doc)"
                        >
                          <mat-icon>category</mat-icon>
                        </button>
                        <button
                          mat-icon-button
                          color="warn"
                          size="small"
                          aria-label="Usuń dokument"
                          class="delete-btn"
                          (click)="onDeleteDocument(doc, $event)"
                        >
                          <mat-icon>delete</mat-icon>
                        </button>
                      }
                      @case ("failed") {
                        <mat-icon class="status-icon error">error</mat-icon>
                        <span>Błąd</span>
                        @if (doc.errorMessage) {
                          <span
                            class="error-detail"
                            title="{{ doc.errorMessage }}"
                          >
                            {{ doc.errorMessage }}
                          </span>
                        }
                        <button
                          mat-icon-button
                          color="warn"
                          size="small"
                          aria-label="Usuń dokument"
                          class="delete-btn"
                          (click)="onDeleteDocument(doc, $event)"
                        >
                          <mat-icon>delete</mat-icon>
                        </button>
                      }
                    }
                  </div>
                </div>
              }
            </div>
          }
        </div>

        <!-- Actions -->
        @if (hasReadyDocuments()) {
          <div class="actions-section">
            <h3 class="section-title">Dostępne analizy</h3>
            <div class="action-buttons">
              <button
                mat-raised-button
                color="primary"
                [disabled]="isAnalyzing()"
                (click)="startAnalysis()"
              >
                @if (isAnalyzing()) {
                  <mat-spinner
                    diameter="20"
                    aria-label="Analizowanie"
                  ></mat-spinner>
                  <span>Analizowanie…</span>
                } @else {
                  <mat-icon aria-hidden="true">analytics</mat-icon>
                  Analizuj dokumentację
                }
              </button>
              <button
                mat-button
                color="accent"
                [routerLink]="['/projects', projectId(), 'requirements']"
                [queryParams]="{ documentId: firstReadyDocumentId() }"
                [disabled]="firstReadyDocumentId() === null"
              >
                <mat-icon aria-hidden="true">assignment</mat-icon>
                Wymagania
              </button>
            </div>
          </div>
        }
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .upload-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .upload-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 960px;
        width: 100%;
        margin: 0 auto;
      }

      .upload-header {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-bottom: 24px;
      }

      .back-link {
        align-self: flex-start;
        margin-bottom: 8px;
      }

      .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }

      .page-subtitle {
        font-size: 15px;
        color: #4b5563;
        margin: 0;
      }

      .drop-zone {
        border: 2px dashed #1976d2;
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 1rem;
        text-align: center;
        cursor: pointer;
        transition:
          background 0.2s ease,
          border-color 0.2s ease;
      }

      .drop-zone:focus-visible {
        outline: 3px solid #1976d2;
        outline-offset: 2px;
      }

      .drop-zone.drag-active {
        background: #e3f2fd;
        border-color: #1565c0;
      }

      .drop-zone mat-icon {
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

      .error-banner,
      .success-banner {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 1rem 0;
        font-size: 14px;
      }

      .error-banner {
        background: #fdecea;
        color: #611a15;
      }

      .success-banner {
        background: #e8f5e9;
        color: #1b5e20;
      }

      .documents-section {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
      }

      .section-title {
        margin: 0 0 12px 0;
        font-size: 1.1rem;
        color: #1a1a1a;
      }

      .total-count {
        color: #6b7280;
        font-weight: normal;
        font-size: 0.9rem;
      }

      .empty {
        color: #6b7280;
        font-style: italic;
        padding: 1rem 0;
      }

      .documents-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .document-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: #ffffff;
      }

      .document-card.ready {
        border-left: 4px solid #10b981;
      }

      .document-card.failed {
        border-left: 4px solid #ef4444;
      }

      .document-card.uploading,
      .document-card.processing {
        border-left: 4px solid #f59e0b;
      }

      .doc-info {
        display: flex;
        align-items: center;
        gap: 12px;
        flex: 1;
      }

      .doc-info mat-icon {
        font-size: 32px;
        color: #6b7280;
      }

      .doc-details {
        display: flex;
        flex-direction: column;
      }

      .doc-filename {
        font-weight: 500;
        color: #1a1a1a;
      }

      .doc-meta {
        font-size: 0.85rem;
        color: #6b7280;
      }

      .doc-status {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.9rem;
      }

      .status-icon {
        font-size: 20px;
      }

      .status-icon.error {
        color: #ef4444;
      }

      .status-icon.check_circle {
        color: #10b981;
      }

      .view-btn {
        margin-left: auto;
      }

      .error-detail {
        font-size: 0.8rem;
        color: #611a15;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .delete-btn {
        margin-left: 4px;
        opacity: 0.5;
        transition: opacity 0.15s;
      }

      .delete-btn:hover {
        opacity: 1;
      }

      .doc-type-chip {
        align-self: flex-start;
        margin-top: 6px;
        font-size: 0.72rem;
        min-height: 22px;
        padding: 0 8px;
      }

      .chip-specyfikacja {
        background: #e3f2fd !important;
        color: #1565c0 !important;
      }

      .chip-podrecznik {
        background: #e8f5e9 !important;
        color: #2e7d32 !important;
      }

      .chip-instrukcja {
        background: #fff3e0 !important;
        color: #ef6c00 !important;
      }

      .chip-api {
        background: #f3e5f5 !important;
        color: #7b1fa2 !important;
      }

      .chip-notatki {
        background: #eceff1 !important;
        color: #455a64 !important;
      }

      .chip-inny {
        background: #f5f5f5 !important;
        color: #616161 !important;
      }

      .reclassify-btn {
        opacity: 0.5;
        transition: opacity 0.15s;
      }

      .reclassify-btn:hover {
        opacity: 1;
      }

      .actions-section {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
      }

      .action-buttons {
        display: flex;
        gap: 12px;
      }

      .loading {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #6b7280;
      }

      @media (max-width: 768px) {
        .upload-content {
          padding: 16px;
        }

        .action-buttons {
          flex-direction: column;
        }

        .drop-zone {
          padding: 1rem;
        }
      }
    `,
  ],
})
export class DocumentUploadComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly documentService = inject(DocumentService);
  private readonly dialog = inject(MatDialog);

  // Signals
  readonly uploadedDocuments = signal<UploadedDocument[]>([]);
  readonly isLoadingList = signal(false);
  readonly isDragActive = signal(false);
  readonly isUploading = signal(false);
  readonly isAnalyzing = signal(false);
  readonly uploadError = signal("");
  readonly uploadSummary = signal("");

  readonly allowedExtensionsLabel = DOCUMENT_EXTENSIONS.join(", ");
  readonly maxFileSizeLabel = formatBytes(MAX_FILE_SIZE_BYTES);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  /** First ready document id — used as the default documentId for the
   * "Wymagania" link in the global Actions section. */
  readonly firstReadyDocumentId = computed(
    () =>
      this.uploadedDocuments().find((d) => d.status === "ready")?.id ?? null,
  );

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadDocuments();
    }
  }

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
      this.handleFiles(Array.from(items));
    }
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFiles(Array.from(input.files));
    }
    input.value = "";
  }

  private handleFiles(selected: File[]): void {
    this.uploadError.set("");
    this.uploadSummary.set("");

    const accepted: File[] = [];

    for (const file of selected) {
      if (!isDocumentExtension(file.name)) {
        this.uploadError.set(
          `Nieobsługiwany format: ${extensionOf(file.name)}. Dozwolone: ${this.allowedExtensionsLabel}`,
        );
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        this.uploadError.set(
          `Plik przekracza limit ${this.maxFileSizeLabel}. ${file.name} ma ${formatBytes(file.size)}.`,
        );
        return;
      }
      accepted.push(file);
    }

    if (accepted.length === 0) return;

    // Create placeholder documents for upload tracking
    const newDocs: UploadedDocument[] = accepted.map((file) => ({
      id: nanoid(),
      projectId: this.projectId(),
      filename: file.name,
      fileSize: file.size,
      fileCategory: "documentation" as const,
      docFormat: this._extToDocFormat(extensionOf(file.name)),
      pageCount: null,
      createdAt: new Date().toISOString(),
      isCleanedUp: false,
      processingStatus: "uploaded",
      errorMessage: null,
      status: "uploading",
      uploadProgress: 0,
    }));

    this.uploadedDocuments.update((prev) => [...prev, ...newDocs]);
    this.isUploading.set(true);

    // Upload files via service
    this.documentService
      .uploadDocuments(this.projectId(), accepted, (progress) => {
        // Update progress for each file
        this.uploadedDocuments.update((docs) =>
          docs.map((d) => ({
            ...d,
            uploadProgress:
              d.status === "uploading" ? progress : d.uploadProgress,
          })),
        );
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.uploadSummary.set(
            `Wysłano ${accepted.length} dokumentów. Rozpoczęcie przetwarzania…`,
          );
          this.isUploading.set(false);

          // Poll task status to track parsing progress
          newDocs.forEach((doc) => {
            this.pollTaskStatus(response.taskId, doc.id);
          });
        },
        error: (err) => {
          this.uploadError.set(
            `Błąd wysyłania: ${err.message || "Nieznany błąd"}`,
          );
          this.isUploading.set(false);

          // Mark all new docs as failed
          this.uploadedDocuments.update((docs) =>
            docs.map((d) =>
              newDocs.some((nd) => nd.id === d.id)
                ? { ...d, status: "failed" }
                : d,
            ),
          );
        },
      });
  }

  private pollTaskStatus(taskId: string, docId: string): void {
    const pollInterval = setInterval(() => {
      this.documentService
        .getTaskStatus(taskId)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (status) => {
            if (status.status === "completed") {
              clearInterval(pollInterval);
              this.updateDocumentStatus(docId, "ready");
              this.loadDocuments(); // Reload to get final backend data
            } else if (status.status === "failed") {
              clearInterval(pollInterval);
              this.updateDocumentStatus(docId, "failed");
            } else if (
              status.status === "started" ||
              status.status === "running" ||
              status.status === "pending"
            ) {
              this.updateDocumentStatus(docId, "processing");
            }
          },
          error: () => {
            clearInterval(pollInterval);
            // Don't mark as failed on error — fall back to DB status via reload
            this.loadDocuments();
          },
        });
    }, 2000);

    // Timeout after 5 minutes
    setTimeout(() => clearInterval(pollInterval), 5 * 60 * 1000);
  }

  private updateDocumentStatus(
    id: string,
    status: UploadedDocument["status"],
  ): void {
    this.uploadedDocuments.update((docs) =>
      docs.map((d) => (d.id === id ? { ...d, status } : d)),
    );
  }

  private loadDocuments(): void {
    this.isLoadingList.set(true);
    this.documentService
      .listDocuments(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ documents }) => {
          // Map backend processingStatus to local UI status
          this.uploadedDocuments.set(
            documents.map(
              (d) =>
                ({
                  ...d,
                  status: this._mapProcessingStatus(d.processingStatus),
                }) as UploadedDocument,
            ),
          );
          this.isLoadingList.set(false);

          // Start polling if any file is still processing
          if (documents.some((d) => d.processingStatus === "processing")) {
            this._scheduleReload();
          }
        },
        error: () => {
          this.uploadError.set("Błąd ładowania dokumentów");
          this.isLoadingList.set(false);
        },
      });
  }

  /** Map backend processingStatus to local UI status. */
  private _mapProcessingStatus(
    ps: DocumentFile["processingStatus"],
  ): UploadedDocument["status"] {
    switch (ps) {
      case "ready":
        return "ready";
      case "failed":
        return "failed";
      case "processing":
        return "processing";
      case "uploaded":
        // File is uploaded but parsing hasn't completed yet
        return "processing";
      default:
        return "uploading";
    }
  }

  /** Auto-reload every 3s while any document is in processing state. */
  private _reloadTimer: ReturnType<typeof setInterval> | null = null;

  private _scheduleReload(): void {
    if (this._reloadTimer) return; // already scheduled
    this._reloadTimer = setInterval(() => {
      const hasProcessing = this.uploadedDocuments().some(
        (d) => d.status === "processing",
      );
      if (!hasProcessing) {
        if (this._reloadTimer) {
          clearInterval(this._reloadTimer);
          this._reloadTimer = null;
        }
        return;
      }
      this.loadDocuments();
    }, 3000);
  }

  hasReadyDocuments(): boolean {
    return this.uploadedDocuments().some((d) => d.status === "ready");
  }

  onDeleteDocument(doc: UploadedDocument, event: Event): void {
    event.stopPropagation();
    const dialogData: DocumentDeleteDialogData = {
      documentId: doc.id,
      filename: doc.filename,
      projectId: this.projectId(),
    };
    const dialogRef = this.dialog.open(DocumentDeleteDialogComponent, {
      data: dialogData,
    });
    dialogRef
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((deleted: boolean | undefined) => {
        if (deleted) {
          this.uploadedDocuments.update((docs) =>
            docs.filter((d) => d.id !== doc.id),
          );
          this.uploadSummary.set(`Dokument „${doc.filename}" został usunięty.`);
        }
      });
  }

  startAnalysis(): void {
    if (this.isAnalyzing()) return;
    // Re-analyze documentation files only (ready/failed). This dispatches the
    // document parsing task — NOT /analyze (which analyses source code and
    // consumes quota). Document parsing is free and re-extracts
    // sections/requirements/glossary.
    const targets = this.uploadedDocuments().filter(
      (d) => d.status === "ready" || d.status === "failed",
    );
    if (targets.length === 0) {
      this.uploadError.set("Brak dokumentów gotowych do ponownej analizy.");
      return;
    }
    this.isAnalyzing.set(true);
    this.uploadError.set("");

    forkJoin(targets.map((d) => this.documentService.reanalyzeDocument(d.id)))
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.uploadSummary.set(
            `Ponowna analiza dokumentacji uruchomiona (${
              targets.length
            } ${targets.length === 1 ? "plik" : "plików"}).`,
          );
          this.isAnalyzing.set(false);
          // Existing auto-reload (every 3s) picks up processing → ready.
          this.loadDocuments();
        },
        error: (err: HttpErrorResponse) => {
          this.uploadError.set(this.extractErrorMessage(err));
          this.isAnalyzing.set(false);
        },
      });
  }

  private extractErrorMessage(err: HttpErrorResponse): string {
    if (err?.error?.type?.includes("quota-exceeded") || err?.status === 429) {
      const plan = err?.error?.plan ?? "basic";
      const limit = err?.error?.limit ?? 10;
      return `Osiągnięto miesięczny limit analiz (${limit}) dla planu ${plan}. Zwiększ plan, aby kontynuować.`;
    }
    if (err?.status === 401) return "Sesja wygasła. Zaloguj się ponownie.";
    if (err?.status === 404) return "Nie znaleziono dokumentu.";
    return `Błąd analizy: ${err?.error?.detail || err?.message || "Nieznany błąd"}`;
  }

  getDocIcon(doc: UploadedDocument): string {
    switch (doc.docFormat) {
      case "pdf":
        return "picture_as_pdf";
      case "docx":
        return "description";
      case "md":
        return "code";
      case "html":
        return "language";
      case "txt":
        return "text_snippet";
      default:
        return "insert_drive_file";
    }
  }

  getStatusClass(status: string): string {
    return status === "ready" ? "ready" : status === "failed" ? "failed" : "";
  }

  formatSize(size: number): string {
    return formatBytes(size);
  }

  /** Human-readable PL label for a backend doc_type (Story 2.3). */
  docTypeLabel(type: string): string {
    const labels: Record<string, string> = {
      specyfikacja_wymagań: "Specyfikacja wymagań",
      podręcznik_użytkownika: "Podręcznik użytkownika",
      instrukcja_techniczna: "Instrukcja techniczna",
      opis_api: "Opis API",
      notatki_projektowe: "Notatki projektowe",
      inny: "Inny",
    };
    return labels[type] ?? type;
  }

  /** CSS class (color per type) for the doc-type chip. */
  docTypeChipClass(type: string): string {
    const map: Record<string, string> = {
      specyfikacja_wymagań: "chip-specyfikacja",
      podręcznik_użytkownika: "chip-podrecznik",
      instrukcja_techniczna: "chip-instrukcja",
      opis_api: "chip-api",
      notatki_projektowe: "chip-notatki",
      inny: "chip-inny",
    };
    return map[type] ?? "chip-inny";
  }

  /** Tooltip text: confidence % + justification (guard null/undefined). */
  classificationTooltip(doc: UploadedDocument): string {
    const label = this.docTypeLabel(doc.docType ?? "inny");
    const confidence = doc.classificationConfidence;
    if (confidence == null) return label;
    const pct = `${Math.round(confidence)}%`;
    const justification = doc.classificationJustification;
    return justification
      ? `Pewność: ${pct}. ${justification}`
      : `Pewność: ${pct}`;
  }

  /** Re-classify a document and refresh the list (Story 2.3, AC7). */
  reclassify(doc: UploadedDocument): void {
    this.documentService
      .classifyDocument(doc.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.loadDocuments(),
        error: () =>
          this.uploadError.set("Błąd ponownej klasyfikacji dokumentu."),
      });
  }

  private _extToDocFormat(ext: string): UploadedDocument["docFormat"] {
    const mapping: Record<string, UploadedDocument["docFormat"]> = {
      ".pdf": "pdf",
      ".docx": "docx",
      ".md": "md",
      ".markdown": "md",
      ".html": "html",
      ".htm": "html",
      ".txt": "txt",
    };
    return mapping[ext] || null;
  }
}
