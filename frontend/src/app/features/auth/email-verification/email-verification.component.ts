import { Component, DestroyRef, inject, OnInit, signal } from "@angular/core";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { AuthService } from "../../../core/services/auth.service";
import { FooterComponent } from "../../../shared/components/footer.component";

@Component({
  selector: "app-email-verification",
  standalone: true,
  imports: [
    RouterLink,
    MatButtonModule,
    MatProgressSpinnerModule,
    FooterComponent,
  ],
  template: `
    <div class="auth-page">
      <main class="verification-container" id="main-content" tabindex="-1">
        @if (isVerifying()) {
          <p role="status" aria-live="polite">Weryfikacja adresu email...</p>
          <mat-spinner
            diameter="32"
            aria-label="Weryfikacja w toku"
          ></mat-spinner>
        } @else if (successMessage()) {
          <div class="success" role="status" aria-live="polite">
            <h2>Email zweryfikowany</h2>
            <p>{{ successMessage() }}</p>
            <a routerLink="/login">Przejdź do logowania</a>
          </div>
        } @else if (errorMessage()) {
          <div class="error" role="alert">
            <h2>Błąd weryfikacji</h2>
            <p>{{ errorMessage() }}</p>
            <p>
              <a routerLink="/register">Zarejestruj się ponownie</a> aby
              otrzymać nowy link weryfikacyjny.
            </p>
          </div>
        } @else if (token()) {
          <h2>Weryfikacja adresu email</h2>
          <p>Kliknij przycisk poniżej, aby zweryfikować swój adres email.</p>
          <button mat-flat-button color="primary" (click)="verify()">
            Zweryfikuj email
          </button>
        } @else {
          <div class="error" role="alert">
            <h2>Błąd weryfikacji</h2>
            <p>Brak tokena weryfikacyjnego</p>
          </div>
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
      .verification-container {
        max-width: 480px;
        margin: auto;
        padding: 2rem;
        text-align: center;
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
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
export class EmailVerificationComponent implements OnInit {
  isVerifying = signal(false);
  successMessage = signal("");
  errorMessage = signal("");
  token = signal<string | null>(null);

  private destroyRef = inject(DestroyRef);
  private route = inject(ActivatedRoute);
  private authService = inject(AuthService);

  ngOnInit(): void {
    const raw = this.route.snapshot.queryParamMap.get("token") || "";
    this.token.set(/^[a-f0-9]{1,64}$/i.test(raw) ? raw : null);
  }

  verify(): void {
    if (!this.token() || this.isVerifying()) return;

    this.isVerifying.set(true);
    this.errorMessage.set("");

    this.authService
      .verifyEmail(this.token()!)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isVerifying.set(false);
          this.successMessage.set(
            res.message ||
              "Adres email został zweryfikowany. Możesz się teraz zalogować.",
          );
        },
        error: (err) => {
          this.isVerifying.set(false);
          this.errorMessage.set("Token jest nieprawidłowy lub wygasł.");
        },
      });
  }
}
