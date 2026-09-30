import { Component } from "@angular/core";
import { RouterLink } from "@angular/router";
import { ReactiveFormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { Observable } from "rxjs";
import { TokenPasswordBaseComponent } from "../../../shared/base/token-password-base.component";
import { FooterComponent } from "../../../shared/components/footer.component";

@Component({
  selector: "app-reset-password",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    FooterComponent,
  ],
  template: `
    <div class="auth-page">
      <main class="reset-password-container" id="main-content" tabindex="-1">
        <h1>Resetowanie hasła</h1>

        @if (successMessage()) {
          <div class="success" role="status" aria-live="polite">
            <h2>Hasło zmienione</h2>
            <p>{{ successMessage() }}</p>
            <a routerLink="/login">Przejdź do logowania</a>
          </div>
        } @else if (tokenError()) {
          <div class="error" role="alert">
            <p>{{ tokenError() }}</p>
          </div>
        } @else {
          <form [formGroup]="form" (ngSubmit)="onSubmit()">
            <mat-form-field
              appearance="outline"
              subscriptSizing="dynamic"
              class="full-width"
            >
              <mat-label>Nowe hasło</mat-label>
              <input
                matInput
                type="password"
                formControlName="password"
                autocomplete="new-password"
                aria-describedby="reset-pw-requirements"
              />
              <mat-hint id="reset-pw-requirements"
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

            <mat-form-field
              appearance="outline"
              subscriptSizing="dynamic"
              class="full-width"
            >
              <mat-label>Potwierdź hasło</mat-label>
              <input
                matInput
                type="password"
                formControlName="confirmPassword"
                autocomplete="new-password"
              />
              @if (form.controls.confirmPassword.hasError("required")) {
                <mat-error>Potwierdzenie hasła jest wymagane</mat-error>
              }
            </mat-form-field>

            @if (
              form.errors?.["passwordMismatch"] &&
              form.controls.confirmPassword.touched
            ) {
              <p class="error-text">Hasła nie są zgodne</p>
            }

            @if (serverError()) {
              <p class="error-text" role="alert">{{ serverError() }}</p>
            }

            <button
              mat-flat-button
              color="primary"
              type="submit"
              [disabled]="form.invalid || isSubmitting()"
            >
              @if (isSubmitting()) {
                <mat-spinner
                  diameter="20"
                  aria-label="Zapisywanie..."
                ></mat-spinner>
              } @else {
                Zmień hasło
              }
            </button>
          </form>
        }
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
      .reset-password-container {
        max-width: 480px;
        margin: auto;
        padding: 2rem;
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
      }
      .full-width {
        width: 100%;
        margin-bottom: 1rem;
      }
      .error-text {
        color: var(--mat-sys-error, #d32f2f);
        font-size: 0.85rem;
      }
      .success h2 {
        color: var(--mat-sys-primary, #2e7d32);
      }
      .error h2 {
        color: var(--mat-sys-error, #d32f2f);
      }
    `,
  ],
})
export class ResetPasswordComponent extends TokenPasswordBaseComponent {
  protected get missingTokenMessage(): string {
    return "Brak tokena resetowania hasła w linku";
  }

  protected get defaultSuccessMessage(): string {
    return "Hasło zostało zmienione. Możesz się teraz zalogować.";
  }

  protected get defaultErrorMessage(): string {
    return "Nie udało się zresetować hasła";
  }

  protected callAuthService(
    token: string,
    password: string,
  ): Observable<{ message: string }> {
    return this.authService.resetPasswordByToken(token, password);
  }
}
