import { Component, signal } from "@angular/core";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { FileUploadComponent } from "../../shared/components/file-upload.component";
import { environment } from "../../../environments/environment";

/**
 * Demo / smoke-test page for the reusable FileUploadComponent — Story 6.2.
 *
 * Demonstrates:
 * - Drag-and-drop zone
 * - Multi-select with validation (extension, size, duplicates)
 * - Per-file progress
 * - Upload summary
 *
 * The component is self-contained — this page only provides the `uploadUrl`
 * and consumes the `uploadComplete` event.
 */
@Component({
  selector: "app-upload-demo",
  standalone: true,
  imports: [
    MatCardModule,
    MatIconModule,
    FileUploadComponent,
  ],
  template: `
    <main class="upload-demo-wrapper" id="main-content" tabindex="-1">
      <header class="page-header">
        <mat-icon aria-hidden="true">cloud_upload</mat-icon>
        <div>
          <h1>Upload plików — demo</h1>
          <p class="subtitle">
            Drag-and-drop, walidacja, pasek postępu, podsumowanie per plik.
          </p>
        </div>
      </header>

      <mat-card>
        <mat-card-content>
          <app-file-upload
            [uploadUrl]="demoUploadUrl"
            [existingFiles]="existingFiles"
            (uploadComplete)="onComplete($event)"
          />
        </mat-card-content>
      </mat-card>

      @if (lastSummary()) {
        <p class="last-summary" role="status" aria-live="polite">
          Ostatni upload — sukces: {{ lastSummary()!.success }},
          błędy: {{ lastSummary()!.failed }},
          pominięte: {{ lastSummary()!.skipped }}
        </p>
      }
    </main>
  `,
  styles: [
    `
      .upload-demo-wrapper {
        max-width: 900px;
        margin: 2rem auto;
        padding: 0 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }
      .page-header {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .page-header mat-icon {
        font-size: 36px;
        height: 36px;
        width: 36px;
        color: #1976d2;
      }
      .page-header h1 {
        margin: 0;
        font-size: 1.5rem;
        color: #1a1a1a;
      }
      .subtitle {
        margin: 4px 0 0;
        color: #6b7280;
        font-size: 0.9rem;
      }
      .last-summary {
        font-size: 0.9rem;
        color: #374151;
        background: #f3f4f6;
        padding: 8px 12px;
        border-radius: 6px;
      }
    `,
  ],
})
export class UploadDemoComponent {
  /**
   * Default to a placeholder URL — the component shows full UX even without
   * a backend (validation, progress UI, summary on failure).
   */
  readonly demoUploadUrl = `${environment.apiUrl}/demo/upload`;
  /** Pretend these files already exist in the project. */
  readonly existingFiles = [
    { filename: "api-spec.pdf", size: 2048576 },
  ];

  lastSummary = signal<{ success: number; failed: number; skipped: number } | null>(
    null,
  );

  onComplete(summary: {
    success: number;
    failed: number;
    skipped: number;
  }): void {
    this.lastSummary.set(summary);
  }
}
