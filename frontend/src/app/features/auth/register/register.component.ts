import { Component, DestroyRef, inject, signal } from "@angular/core";
import {
  ReactiveFormsModule,
  FormControl,
  FormGroup,
  Validators,
} from "@angular/forms";
import { RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { timeout } from "rxjs/operators";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatIconModule } from "@angular/material/icon";
import { AuthService } from "../../../core/services/auth.service";
import { FooterComponent } from "../../../shared/components/footer.component";
import { passwordComplexityValidator } from "../../../shared/validators/password-complexity.validator";
import { passwordMatchValidator } from "../../../shared/validators/password-match.validator";

interface RegisterForm {
  email: FormControl<string>;
  password: FormControl<string>;
  confirmPassword: FormControl<string>;
  companyName: FormControl<string>;
  nip: FormControl<string>;
}

@Component({
  selector: "app-register",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatIconModule,
    FooterComponent,
  ],
  template: `
    <div class="auth-page">
      <main class="auth-container" id="main-content" tabindex="-1">
        <div class="auth-card">
          @if (successMessage()) {
            <div class="success-banner" role="status" aria-live="polite">
              <h2>Sprawdź swoją skrzynkę email</h2>
              <p>{{ successMessage() }}</p>
              <p><a routerLink="/login">Przejdź do logowania</a></p>
            </div>
          } @else {
            <div class="reg-logo" aria-hidden="true">
              <img src="logo.svg" alt="TestGEN" class="reg-logo-img" />
            </div>
            <h1 class="reg-title">Rejestracja</h1>
            <p class="reg-subtitle">
              Utwórz konto, aby zacząć generować testy.
            </p>

            <form
              [formGroup]="form"
              (ngSubmit)="onSubmit()"
              aria-label="Formularz rejestracji"
            >
              @if (errorMessage()) {
                <div class="error-banner" role="alert" aria-live="assertive">
                  {{ errorMessage() }}
                </div>
              }

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Email firmowy</mat-label>
                <input
                  matInput
                  formControlName="email"
                  type="email"
                  autocomplete="email"
                  maxlength="254"
                  aria-label="Adres email firmowy"
                />
                @if (form.controls.email.hasError("required")) {
                  <mat-error>Email jest wymagany</mat-error>
                }
                @if (form.controls.email.hasError("email")) {
                  <mat-error>Nieprawidłowy format email</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Hasło (min. 12 znaków)</mat-label>
                <input
                  matInput
                  formControlName="password"
                  [type]="hidePassword() ? 'password' : 'text'"
                  autocomplete="new-password"
                  maxlength="128"
                  aria-label="Hasło"
                  aria-describedby="password-requirements"
                />
                <button
                  mat-icon-button
                  matSuffix
                  type="button"
                  (click)="hidePassword.set(!hidePassword())"
                  [attr.aria-label]="
                    hidePassword() ? 'Pokaż hasło' : 'Ukryj hasło'
                  "
                >
                  <mat-icon>{{
                    hidePassword() ? "visibility_off" : "visibility"
                  }}</mat-icon>
                </button>
                <mat-hint id="password-requirements"
                  >Min. 12 znaków, wielka i mała litera, cyfra, znak
                  specjalny</mat-hint
                >
                @if (form.controls.password.hasError("required")) {
                  <mat-error>Hasło jest wymagane</mat-error>
                }
                @if (form.controls.password.hasError("minlength")) {
                  <mat-error>Hasło musi mieć minimum 12 znaków</mat-error>
                }
                @if (form.controls.password.hasError("passwordComplexity")) {
                  <mat-error>{{
                    form.controls.password.getError("passwordComplexity")
                  }}</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Potwierdź hasło</mat-label>
                <input
                  matInput
                  formControlName="confirmPassword"
                  [type]="hideConfirmPassword() ? 'password' : 'text'"
                  autocomplete="new-password"
                  maxlength="128"
                  aria-label="Potwierdź hasło"
                />
                <button
                  mat-icon-button
                  matSuffix
                  type="button"
                  (click)="hideConfirmPassword.set(!hideConfirmPassword())"
                  [attr.aria-label]="
                    hideConfirmPassword()
                      ? 'Pokaż potwierdzenie hasła'
                      : 'Ukryj potwierdzenie hasła'
                  "
                >
                  <mat-icon>{{
                    hideConfirmPassword() ? "visibility_off" : "visibility"
                  }}</mat-icon>
                </button>
                @if (form.controls.confirmPassword.hasError("required")) {
                  <mat-error>Potwierdzenie hasła jest wymagane</mat-error>
                }
              </mat-form-field>
              @if (
                form.hasError("passwordMismatch") &&
                form.controls.confirmPassword.touched
              ) {
                <div class="field-error" role="alert">Hasła nie są zgodne</div>
              }

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Nazwa firmy</mat-label>
                <input
                  matInput
                  formControlName="companyName"
                  autocomplete="organization"
                  maxlength="255"
                  aria-label="Nazwa firmy"
                />
                @if (form.controls.companyName.hasError("required")) {
                  <mat-error>Nazwa firmy jest wymagana</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>NIP (opcjonalnie)</mat-label>
                <input
                  matInput
                  formControlName="nip"
                  inputmode="numeric"
                  maxlength="10"
                  aria-label="NIP"
                />
                @if (form.controls.nip.hasError("pattern")) {
                  <mat-error>NIP musi składać się z 10 cyfr</mat-error>
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
                  <mat-spinner
                    diameter="20"
                    aria-label="Rejestracja w toku"
                  ></mat-spinner>
                } @else {
                  Zarejestruj się
                }
              </button>
            </form>

            <div class="reg-divider">
              <span class="divider-line"></span>
              <span class="divider-text">lub</span>
              <span class="divider-line"></span>
            </div>

            <div class="reg-login-link">
              <span>Masz już konto?</span>
              <a routerLink="/login">Zaloguj się</a>
            </div>
          }
        </div>
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
      .auth-container {
        display: flex;
        justify-content: center;
        align-items: center;
        flex: 1;
        padding: 1rem;
      }
      .auth-card {
        max-width: 460px;
        width: 100%;
        background: #ffffff;
        border-radius: 20px;
        padding: 40px;
        display: flex;
        flex-direction: column;
        gap: 24px;
      }
      .reg-logo {
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .reg-logo-img {
        height: 56px;
        width: auto;
      }
      .reg-title {
        font-size: 24px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0;
        text-align: center;
      }
      .reg-subtitle {
        font-size: 14px;
        color: #4b5563;
        margin: 0;
        text-align: center;
      }
      form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      mat-form-field {
        width: 100%;
      }
      .submit-btn {
        width: 100%;
        margin-top: 0.5rem;
      }
      .error-banner {
        background: #fdecea;
        color: #611a15;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
      }
      .field-error {
        color: #d32f2f;
        font-size: 0.75rem;
        margin-top: -0.25rem;
        margin-bottom: 0.5rem;
      }
      .success-banner {
        text-align: center;
        padding: 2rem 1rem;
      }
      .success-banner h2 {
        color: #2e7d32;
      }
      .reg-divider {
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
      }
      .divider-line {
        flex: 1;
        height: 1px;
        background: #e5e7eb;
      }
      .divider-text {
        font-size: 13px;
        color: #6b7280;
      }
      .reg-login-link {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 4px;
        font-size: 14px;
        color: #4b5563;
      }
      .reg-login-link a {
        font-weight: 500;
        color: #1976d2;
        text-decoration: none;
      }
      .reg-login-link a:hover {
        text-decoration: underline;
      }
    `,
  ],
})
export class RegisterComponent {
  private readonly destroyRef = inject(DestroyRef);
  private readonly authService = inject(AuthService);

  readonly isSubmitting = signal(false);
  readonly errorMessage = signal("");
  readonly successMessage = signal("");
  readonly hidePassword = signal(true);
  readonly hideConfirmPassword = signal(true);

  readonly form = new FormGroup<RegisterForm>(
    {
      email: new FormControl("", {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.email,
          Validators.maxLength(254),
        ],
      }),
      password: new FormControl("", {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.minLength(12),
          Validators.maxLength(128),
          passwordComplexityValidator,
        ],
      }),
      confirmPassword: new FormControl("", {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.minLength(12),
          Validators.maxLength(128),
        ],
      }),
      companyName: new FormControl("", {
        nonNullable: true,
        validators: [Validators.required, Validators.maxLength(255)],
      }),
      nip: new FormControl("", {
        nonNullable: true,
        validators: [Validators.pattern(/^\d{10}$/)],
      }),
    },
    { validators: passwordMatchValidator("password", "confirmPassword") },
  ) as FormGroup<RegisterForm>;

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set("");

    const { email, password, companyName, nip } = this.form.getRawValue();
    const payload: {
      email: string;
      password: string;
      companyName: string;
      nip?: string;
    } = {
      email,
      password,
      companyName,
    };
    if (nip) {
      payload.nip = nip;
    }
    this.authService
      .register(payload)
      .pipe(timeout(15000), takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isSubmitting.set(false);
          this.successMessage.set(
            res.message ||
              "Sprawdź swoją skrzynkę email, aby potwierdzić rejestrację.",
          );
          this.form.reset();
        },
        error: (err) => {
          this.isSubmitting.set(false);
          if (err.name === "TimeoutError") {
            this.errorMessage.set(
              "Serwer nie odpowiada. Sprawdź czy backend jest uruchomiony.",
            );
          } else if (err.status === 0) {
            this.errorMessage.set(
              "Nie można połączyć się z serwerem. Sprawdź czy backend jest uruchomiony na localhost:8000.",
            );
          } else {
            this.errorMessage.set(
              "Wystąpił błąd rejestracji. Spróbuj ponownie.",
            );
          }
        },
      });
  }
}
