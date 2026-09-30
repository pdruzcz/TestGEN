import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { HttpClient } from "@angular/common/http";
import { RouterLink } from "@angular/router";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatButtonModule } from "@angular/material/button";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatIconModule } from "@angular/material/icon";
import { environment } from "../../../../environments/environment";
import { FooterComponent } from "../../../shared/components/footer.component";

interface InviteForm {
  email: FormControl<string>;
  role: FormControl<string>;
}

@Component({
  selector: "app-invite",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatIconModule,
    FooterComponent,
  ],
  template: `
    <div class="page-wrapper">
      <main class="invite-container" id="main-content" tabindex="-1">
        <h2>Zaproś użytkownika</h2>

        @if (successMessage()) {
          <div class="success-message" role="status" aria-live="polite">
            <mat-icon>check_circle</mat-icon>
            {{ successMessage() }}
          </div>
        }

        @if (errorMessage()) {
          <div class="error-message" role="alert">
            <mat-icon>error</mat-icon>
            {{ errorMessage() }}
          </div>
        }

        <form [formGroup]="form" (ngSubmit)="onSubmit()">
          <mat-form-field
            appearance="outline"
            subscriptSizing="dynamic"
            class="full-width"
          >
            <mat-label>Email</mat-label>
            <input
              matInput
              formControlName="email"
              type="email"
              autocomplete="email"
              aria-label="Adres email zapraszanego użytkownika"
            />
            @if (form.controls.email.hasError("email")) {
              <mat-error>Podaj prawidłowy adres email</mat-error>
            }
            @if (form.controls.email.hasError("required")) {
              <mat-error>Email jest wymagany</mat-error>
            }
          </mat-form-field>

          <mat-form-field
            appearance="outline"
            subscriptSizing="dynamic"
            class="full-width"
          >
            <mat-label>Rola</mat-label>
            <mat-select formControlName="role" aria-label="Rola użytkownika">
              <mat-option value="user">Użytkownik</mat-option>
              <mat-option value="owner">Właściciel</mat-option>
            </mat-select>
          </mat-form-field>

          <button
            mat-raised-button
            color="primary"
            type="submit"
            [disabled]="form.invalid || isSubmitting()"
            class="full-width"
          >
            @if (isSubmitting()) {
              <mat-spinner
                diameter="20"
                aria-label="Wysyłanie zaproszenia"
              ></mat-spinner>
            } @else {
              Wyślij zaproszenie
            }
          </button>
        </form>

        <div class="back-link">
          <a routerLink="/settings/profile">Wróć do profilu</a>
        </div>
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .page-wrapper {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        background: #f7f8fa;
      }
      .invite-container {
        max-width: 480px;
        margin: auto;
        padding: 2rem;
        flex: 1;
      }
      .full-width {
        width: 100%;
        margin-bottom: 1rem;
      }
      .success-message,
      .error-message {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 1rem;
        border-radius: 4px;
        margin-bottom: 1rem;
      }
      .success-message {
        background: #e8f5e9;
        color: var(--mat-sys-primary, #1b5e20);
      }
      .error-message {
        background: #ffebee;
        color: #c62828;
      }
      .back-link {
        text-align: center;
        margin-top: 1rem;
      }
    `,
  ],
})
export class InviteComponent {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);

  readonly isSubmitting = signal(false);
  readonly successMessage = signal("");
  readonly errorMessage = signal("");

  readonly form = new FormGroup<InviteForm>({
    email: new FormControl("", {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.email,
        Validators.maxLength(254),
      ],
    }),
    role: new FormControl("user", { nonNullable: true }),
  });

  onSubmit(): void {
    if (this.form.invalid || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set("");
    this.successMessage.set("");

    const { email, role } = this.form.getRawValue();

    this.http
      .post(`${environment.apiUrl}/users/invite`, { email, role })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isSubmitting.set(false);
          this.successMessage.set(`Zaproszenie wysłane na adres ${email}`);
          this.form.reset({ email: "", role: "user" });
        },
        error: (err) => {
          this.isSubmitting.set(false);
          if (err.status === 409) {
            this.errorMessage.set(
              "Użytkownik z tym adresem email już istnieje w Twoim zespole.",
            );
          } else if (err.status === 403) {
            this.errorMessage.set(
              "Brak uprawnień do zapraszania użytkowników.",
            );
          } else {
            this.errorMessage.set("Wystąpił błąd. Spróbuj ponownie.");
          }
        },
      });
  }
}
