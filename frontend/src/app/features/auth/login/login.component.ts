import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatIconModule } from "@angular/material/icon";
import { AuthService } from "../../../core/services/auth.service";
import { FooterComponent } from "../../../shared/components/footer.component";
import { FormAccessibilityDirective } from "../../../shared/directives/form-accessibility.directive";

@Component({
  selector: "app-login",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatIconModule,
    FooterComponent,
    FormAccessibilityDirective,
  ],
  template: `
    <div class="auth-page">
      <main class="auth-container" id="main-content" tabindex="-1">
        <div class="auth-card">
          <div class="login-logo" aria-hidden="true">
            <img src="logo.svg" alt="TestGEN" class="login-logo-img" />
          </div>
          <h1 class="login-title">Logowanie</h1>
          <p class="login-subtitle">
            Zaloguj się, aby uzyskać dostęp do TestGEN.
          </p>

          <form
            [formGroup]="form"
            (ngSubmit)="onSubmit()"
            aria-label="Formularz logowania"
            appFormAccessibility
          >
            @if (errorMessage()) {
              <div class="error-banner" role="alert" aria-live="assertive">
                {{ errorMessage() }}
              </div>
            }

            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Email</mat-label>
              <input
                matInput
                formControlName="email"
                type="email"
                autocomplete="email"
                aria-label="Adres email"
              />
              @if (form.controls.email.hasError("required")) {
                <mat-error>Email jest wymagany</mat-error>
              }
              @if (form.controls.email.hasError("email")) {
                <mat-error>Nieprawidłowy format email</mat-error>
              }
            </mat-form-field>

            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Hasło</mat-label>
              <input
                matInput
                formControlName="password"
                [type]="hidePassword() ? 'password' : 'text'"
                autocomplete="current-password"
                aria-label="Hasło"
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
              @if (form.controls.password.hasError("required")) {
                <mat-error>Hasło jest wymagane</mat-error>
              }
            </mat-form-field>

            <div class="forgot-link">
              <a routerLink="/reset-password">Nie pamiętasz hasła?</a>
            </div>

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
                Zaloguj się
              }
            </button>
          </form>

          <div class="login-divider">
            <span class="divider-line"></span>
            <span class="divider-text">lub</span>
            <span class="divider-line"></span>
          </div>

          <div class="login-register-link">
            <span>Nie masz konta?</span>
            <a routerLink="/register">Zarejestruj się</a>
          </div>
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
      .login-logo {
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .login-logo-img {
        height: 56px;
        width: auto;
      }
      .login-title {
        font-size: 24px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0;
        text-align: center;
      }
      .login-subtitle {
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
      .forgot-link {
        display: flex;
        justify-content: flex-end;
        margin-top: -0.25rem;
      }
      .forgot-link a {
        font-size: 13px;
        color: #1976d2;
        text-decoration: none;
      }
      .forgot-link a:hover {
        text-decoration: underline;
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
      .login-divider {
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
      .login-register-link {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 4px;
        font-size: 14px;
        color: #4b5563;
      }
      .login-register-link a {
        font-weight: 500;
        color: #1976d2;
        text-decoration: none;
      }
      .login-register-link a:hover {
        text-decoration: underline;
      }
    `,
  ],
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly form = new FormGroup({
    email: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required, Validators.email],
    }),
    password: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  readonly isSubmitting = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly hidePassword = signal(true);

  onSubmit(): void {
    if (this.form.invalid || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    const { email, password } = this.form.getRawValue();

    this.authService
      .login(email, password)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isSubmitting.set(false);
          if (res.tenantsRequired && res.preAuthToken && res.tenants) {
            sessionStorage.setItem("pre_auth_token", res.preAuthToken);
            sessionStorage.setItem(
              "available_tenants",
              JSON.stringify(res.tenants),
            );
            // Clear sensitive tokens after navigation completes (cleanup in select-tenant component)
            this.router.navigateByUrl("/select-tenant");
          } else if (res.mfaRequired && res.mfaToken) {
            // H4: Store MFA token in sessionStorage (cleared on tab close)
            // instead of router state (persisted in window.history)
            sessionStorage.setItem("mfa_token", res.mfaToken);
            this.router.navigateByUrl("/mfa-verify");
          } else {
            this.authService
              .fetchProfile()
              .pipe(takeUntilDestroyed(this.destroyRef))
              .subscribe({
                next: () => this.router.navigateByUrl("/dashboard"),
                // M8: Don't navigate to dashboard if profile fetch fails
                error: () => {
                  this.errorMessage.set(
                    "Zalogowano, ale nie udało się załadować profilu. Spróbuj odświeżyć stronę.",
                  );
                },
              });
          }
        },
        error: (err) => {
          this.isSubmitting.set(false);
          if (err.status === 0) {
            this.errorMessage.set(
              "Nie można połączyć się z serwerem. Sprawdź czy backend jest uruchomiony.",
            );
          } else if (err.status === 429) {
            const retryAfter = err.headers?.get("Retry-After");
            const minutes = retryAfter
              ? Math.ceil(parseInt(retryAfter, 10) / 60)
              : 30;
            this.errorMessage.set(
              `Konto zablokowane. Spróbuj ponownie za ${minutes} minut.`,
            );
          } else {
            this.errorMessage.set("Nieprawidłowy email lub hasło");
          }
        },
      });
  }
}
