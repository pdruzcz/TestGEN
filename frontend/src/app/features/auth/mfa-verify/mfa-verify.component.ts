import { Component, DestroyRef, inject, signal, OnInit } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { Router } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { AuthService } from "../../../core/services/auth.service";
import { FooterComponent } from "../../../shared/components/footer.component";

@Component({
  selector: "app-mfa-verify",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    FooterComponent,
  ],
  template: `
    <div class="auth-page">
      <main class="mfa-container" id="main-content" tabindex="-1">
        <mat-card>
          <mat-card-header>
            <mat-card-title>Weryfikacja dwuetapowa</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <form
              [formGroup]="form"
              (ngSubmit)="onSubmit()"
              aria-label="Formularz weryfikacji MFA"
            >
              @if (errorMessage()) {
                <div class="error-banner" role="alert" aria-live="assertive">
                  {{ errorMessage() }}
                </div>
              }

              <p class="hint">
                @if (useBackupCode()) {
                  Wprowadź jednorazowy kod zapasowy (8 znaków).
                } @else {
                  Wprowadź 6-cyfrowy kod z aplikacji uwierzytelniającej.
                }
              </p>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>{{
                  useBackupCode() ? "Kod zapasowy" : "Kod TOTP"
                }}</mat-label>
                <input
                  matInput
                  formControlName="code"
                  [maxlength]="useBackupCode() ? 8 : 6"
                  autocomplete="one-time-code"
                  (input)="onCodeInput()"
                  aria-label="Kod weryfikacyjny"
                />
                @if (form.controls.code.hasError("required")) {
                  <mat-error>Kod jest wymagany</mat-error>
                }
              </mat-form-field>

              <button
                mat-raised-button
                color="primary"
                type="submit"
                [disabled]="isSubmitting()"
                class="submit-btn"
              >
                @if (isSubmitting()) {
                  <mat-spinner diameter="20" aria-label="Ładowanie"></mat-spinner>
                } @else {
                  Weryfikuj
                }
              </button>
            </form>

            <div class="links">
              <button mat-button type="button" (click)="toggleBackupCode()">
                {{
                  useBackupCode() ? "Użyj kodu TOTP" : "Użyj kodu zapasowego"
                }}
              </button>
            </div>
          </mat-card-content>
        </mat-card>
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .auth-page {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        background: #f7f8fa;
      }
      .mfa-container {
        display: flex;
        justify-content: center;
        align-items: center;
        flex: 1;
        padding: 1rem;
      }
      mat-card {
        max-width: 420px;
        width: 100%;
      }
      form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-top: 1rem;
      }
      mat-form-field {
        width: 100%;
      }
      .submit-btn {
        margin-top: 0.5rem;
      }
      .hint {
        color: rgba(0, 0, 0, 0.6);
        font-size: 0.875rem;
      }
      .error-banner {
        background: #fdecea;
        color: #611a15;
        padding: 0.75rem 1rem;
        border-radius: 4px;
      }
      .links {
        margin-top: 0.5rem;
        text-align: center;
      }
    `,
  ],
})
export class MfaVerifyComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private mfaToken = "";

  readonly form = new FormGroup({
    code: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  readonly isSubmitting = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly useBackupCode = signal(false);

  ngOnInit(): void {
    // H4: Read MFA token from sessionStorage (not router state / window.history)
    this.mfaToken = sessionStorage.getItem("mfa_token") ?? "";
    if (this.mfaToken) {
      // Clear immediately — single use
      sessionStorage.removeItem("mfa_token");
    } else {
      this.router.navigateByUrl("/login");
    }
  }

  onCodeInput(): void {
    const code = this.form.controls.code.value;
    // Auto-submit TOTP 6-digit code
    if (!this.useBackupCode() && code.length === 6 && /^\d{6}$/.test(code)) {
      this.onSubmit();
    }
  }

  toggleBackupCode(): void {
    this.useBackupCode.set(!this.useBackupCode());
    this.form.controls.code.reset();
    this.errorMessage.set(null);
  }

  onSubmit(): void {
    if (this.form.invalid || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    this.authService
      .verifyMfa(this.mfaToken, this.form.getRawValue().code)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isSubmitting.set(false);
          this.authService
            .fetchProfile()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
              next: () => this.router.navigateByUrl("/dashboard"),
              error: () => {
                this.errorMessage.set(
                  "Zalogowano, ale nie udało się załadować profilu. Spróbuj odświeżyć stronę.",
                );
              },
            });
        },
        error: (err) => {
          this.isSubmitting.set(false);
          if (err.status === 401) {
            if (err.error?.detail?.includes("expired")) {
              this.errorMessage.set("Token MFA wygasł. Zaloguj się ponownie.");
            } else {
              this.errorMessage.set("Nieprawidłowy kod weryfikacyjny");
            }
          } else {
            this.errorMessage.set("Wystąpił błąd. Spróbuj ponownie.");
          }
        },
      });
  }
}
