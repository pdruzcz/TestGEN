import { HttpErrorResponse } from "@angular/common/http";
import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { ApiErrorResponse } from "../../shared/models/api-error.model";
import { Project } from "./models/project.model";
import { ProjectService } from "./services/project.service";

export interface ProjectFormDialogData {
  mode: "create" | "edit";
  project?: Project;
}

interface ProjectForm {
  name: FormControl<string>;
  description: FormControl<string>;
  languageHint: FormControl<string>;
}

@Component({
  selector: "app-project-form-dialog",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>
      {{ data.mode === "create" ? "Nowy projekt" : "Edycja projektu" }}
    </h2>

    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-dialog-content>
        @if (errorMessage()) {
          <div class="error-message" role="alert">
            <mat-icon>error</mat-icon>
            {{ errorMessage() }}
          </div>
        }

        <mat-form-field
          appearance="outline"
          subscriptSizing="dynamic"
          class="full-width"
        >
          <mat-label>Nazwa</mat-label>
          <input
            matInput
            formControlName="name"
            maxlength="255"
            aria-label="Nazwa projektu"
            data-testid="project-name-input"
          />
          @if (form.controls.name.hasError("required")) {
            <mat-error>Nazwa jest wymagana</mat-error>
          }
          @if (form.controls.name.hasError("maxlength")) {
            <mat-error>Nazwa może mieć maksymalnie 255 znaków</mat-error>
          }
        </mat-form-field>

        <mat-form-field
          appearance="outline"
          subscriptSizing="dynamic"
          class="full-width"
        >
          <mat-label>Opis (opcjonalnie)</mat-label>
          <textarea
            matInput
            formControlName="description"
            maxlength="2000"
            rows="3"
            aria-label="Opis projektu"
          ></textarea>
          @if (form.controls.description.hasError("maxlength")) {
            <mat-error>Opis może mieć maksymalnie 2000 znaków</mat-error>
          }
        </mat-form-field>

        <mat-form-field
          appearance="outline"
          subscriptSizing="dynamic"
          class="full-width"
        >
          <mat-label>Język (opcjonalnie)</mat-label>
          <input
            matInput
            formControlName="languageHint"
            maxlength="50"
            aria-label="Język projektu (hint)"
            placeholder="np. python, java, typescript"
          />
          @if (form.controls.languageHint.hasError("maxlength")) {
            <mat-error>Maksymalnie 50 znaków</mat-error>
          }
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button
          type="button"
          mat-button
          (click)="onCancel()"
          [disabled]="isSubmitting()"
        >
          Anuluj
        </button>
        <button
          type="submit"
          mat-raised-button
          color="primary"
          [disabled]="form.invalid || isSubmitting()"
        >
          @if (isSubmitting()) {
            <mat-spinner
              diameter="20"
              aria-label="Zapisywanie projektu"
            ></mat-spinner>
          } @else {
            {{ data.mode === "create" ? "Utwórz" : "Zapisz" }}
          }
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: [
    `
      .full-width {
        width: 100%;
        margin-bottom: 1rem;
      }
      mat-dialog-content {
        min-width: 380px;
        padding-top: 0.5rem;
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
export class ProjectFormDialogComponent {
  private readonly destroyRef = inject(DestroyRef);
  private readonly projectService = inject(ProjectService);
  private readonly dialogRef =
    inject<MatDialogRef<ProjectFormDialogComponent, Project | null>>(
      MatDialogRef,
    );
  readonly data = inject<ProjectFormDialogData>(MAT_DIALOG_DATA);

  readonly isSubmitting = signal(false);
  readonly errorMessage = signal("");

  readonly form = new FormGroup<ProjectForm>({
    name: new FormControl(this.data.project?.name ?? "", {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.maxLength(255),
      ],
    }),
    description: new FormControl(this.data.project?.description ?? "", {
      nonNullable: true,
      validators: [Validators.maxLength(2000)],
    }),
    languageHint: new FormControl(this.data.project?.languageHint ?? "", {
      nonNullable: true,
      validators: [Validators.maxLength(50)],
    }),
  });

  onCancel(): void {
    this.dialogRef.close(null);
  }

  onSubmit(): void {
    if (this.form.invalid || this.isSubmitting()) return;

    const raw = this.form.getRawValue();
    const name = raw.name.trim();
    if (!name) {
      this.form.controls.name.setErrors({ required: true });
      return;
    }

    const payload = {
      name,
      description: raw.description.trim() || null,
      languageHint: raw.languageHint.trim() || null,
    };

    this.isSubmitting.set(true);
    this.errorMessage.set("");

    const request$ =
      this.data.mode === "create"
        ? this.projectService.create(payload)
        : this.projectService.update(this.data.project!.id, payload);

    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (project) => {
        this.isSubmitting.set(false);
        this.dialogRef.close(project);
      },
      error: (err: HttpErrorResponse) => {
        this.isSubmitting.set(false);
        this.errorMessage.set(this.mapError(err));
      },
    });
  }

  private mapError(err: HttpErrorResponse): string {
    const body = err.error as ApiErrorResponse | null;
    if (err.status === 409) {
      return "Projekt o tej nazwie już istnieje.";
    }
    if (err.status === 429) {
      return "Przekroczono limit projektów w Twoim planie.";
    }
    if (err.status === 403) {
      return "Brak uprawnień do zapisania projektu.";
    }
    if (err.status === 422 || err.status === 400) {
      return "Dane formularza są nieprawidłowe.";
    }
    return "Nie udało się zapisać projektu. Spróbuj ponownie.";
  }
}
