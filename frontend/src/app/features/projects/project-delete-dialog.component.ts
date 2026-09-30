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
import { Project } from "./models/project.model";
import { ProjectService } from "./services/project.service";

export interface ProjectDeleteDialogData {
  project: Project;
}

@Component({
  selector: "app-project-delete-dialog",
  standalone: true,
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>Usunąć projekt?</h2>
    <mat-dialog-content>
      @if (errorMessage()) {
        <div class="error-message" role="alert">
          <mat-icon>error</mat-icon>
          {{ errorMessage() }}
        </div>
      }
      <p>
        Projekt <strong>{{ data.project.name }}</strong> zostanie usunięty.
      </p>
      <p class="hint">
        Operacja jest bezpieczna — projekt jest oznaczany jako usunięty
        i można go przywrócić z poziomu panelu administracyjnego.
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
        data-testid="project-delete-confirm"
      >
        @if (isDeleting()) {
          <mat-spinner
            diameter="20"
            aria-label="Usuwanie projektu"
          ></mat-spinner>
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
export class ProjectDeleteDialogComponent {
  private readonly destroyRef = inject(DestroyRef);
  private readonly projectService = inject(ProjectService);
  private readonly dialogRef =
    inject<MatDialogRef<ProjectDeleteDialogComponent, boolean>>(MatDialogRef);
  readonly data = inject<ProjectDeleteDialogData>(MAT_DIALOG_DATA);

  readonly isDeleting = signal(false);
  readonly errorMessage = signal("");

  onCancel(): void {
    this.dialogRef.close(false);
  }

  onConfirm(): void {
    if (this.isDeleting()) return;

    this.isDeleting.set(true);
    this.errorMessage.set("");

    this.projectService
      .delete(this.data.project.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isDeleting.set(false);
          this.dialogRef.close(true);
        },
        error: (err: HttpErrorResponse) => {
          this.isDeleting.set(false);
          if (err.status === 403) {
            this.errorMessage.set("Brak uprawnień do usunięcia projektu.");
          } else if (err.status === 404) {
            this.errorMessage.set("Projekt nie istnieje lub został już usunięty.");
          } else {
            this.errorMessage.set("Nie udało się usunąć projektu. Spróbuj ponownie.");
          }
        },
      });
  }
}
