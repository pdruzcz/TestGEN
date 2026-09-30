import { HttpErrorResponse } from "@angular/common/http";
import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { ProjectFilesService } from "../services/project-files.service";

export interface SourceFileDeleteDialogData {
  fileId: string;
  filename: string;
  projectId: string;
}

@Component({
  selector: "app-source-file-delete-dialog",
  standalone: true,
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>Usunąć plik?</h2>
    <mat-dialog-content>
      @if (errorMessage()) {
        <div class="error-message" role="alert">
          <mat-icon>error</mat-icon>
          {{ errorMessage() }}
        </div>
      }
      <p>
        Plik <strong>{{ data.filename }}</strong> zostanie usunięty.
      </p>
      <p class="hint">
        Plik zostanie trwale usunięty z serwera. Tej operacji nie można cofnąć.
      </p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button
        type="button"
        mat-button
        (click)="onCancel()"
        [disabled]="isDeleting()"
      >
        Anuluj
      </button>
      <button
        type="button"
        mat-raised-button
        color="warn"
        (click)="onConfirm()"
        [disabled]="isDeleting()"
        data-testid="source-file-delete-confirm"
      >
        @if (isDeleting()) {
          <mat-spinner diameter="20" aria-label="Usuwanie pliku"></mat-spinner>
        } @else {
          Usuń
        }
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      mat-dialog-content {
        min-width: 360px;
      }
      .hint {
        color: rgba(0, 0, 0, 0.6);
        font-size: 0.875rem;
        margin-top: 0.5rem;
      }
      .error-message {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem;
        border-radius: 4px;
        margin-bottom: 1rem;
        background: #ffebee;
        color: #c62828;
      }
    `,
  ],
})
export class SourceFileDeleteDialogComponent {
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(ProjectFilesService);
  private readonly dialogRef =
    inject<MatDialogRef<SourceFileDeleteDialogComponent, boolean>>(
      MatDialogRef,
    );
  readonly data = inject<SourceFileDeleteDialogData>(MAT_DIALOG_DATA);

  readonly isDeleting = signal(false);
  readonly errorMessage = signal("");

  onCancel(): void {
    this.dialogRef.close(false);
  }

  onConfirm(): void {
    if (this.isDeleting()) return;

    this.isDeleting.set(true);
    this.errorMessage.set("");

    this.service
      .deleteFile(this.data.projectId, this.data.fileId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isDeleting.set(false);
          this.dialogRef.close(true);
        },
        error: (err: HttpErrorResponse) => {
          this.isDeleting.set(false);
          if (err.status === 403) {
            this.errorMessage.set(
              "Brak uprawnień do usunięcia pliku. Wymagana rola Owner lub Admin.",
            );
          } else if (err.status === 404) {
            this.errorMessage.set("Plik nie istnieje lub został już usunięty.");
          } else {
            this.errorMessage.set(
              "Nie udało się usunąć pliku. Spróbuj ponownie.",
            );
          }
        },
      });
  }
}
