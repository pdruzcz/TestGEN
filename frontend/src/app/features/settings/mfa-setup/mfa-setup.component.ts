import {
  Component,
  DestroyRef,
  inject,
  OnInit,
  signal,
  viewChildren,
  QueryList,
  ElementRef,
  AfterViewInit,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatIconModule } from "@angular/material/icon";
import { RouterLink } from "@angular/router";
import QRCode from "qrcode";
import { AuthService } from "../../../core/services/auth.service";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";

type MfaStep = "idle" | "setup" | "confirm" | "done" | "disable";

@Component({
  selector: "app-mfa-setup",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="settings-page">
      <app-navbar activeLink="profile" />

      <div class="settings-content">
        <!-- Sidebar -->
        <aside class="sidebar">
          <h3 class="sidebar-title">Ustawienia</h3>
          <a mat-button routerLink="/settings/profile" class="sidebar-link">
            <mat-icon>person</mat-icon>
            Profil
          </a>
          <a
            mat-button
            routerLink="/settings/mfa"
            class="sidebar-link sidebar-active"
          >
            <mat-icon>shield</mat-icon>
            Uwierzytelnianie MFA
          </a>
          <a mat-button class="sidebar-link" disabled>
            <mat-icon>notifications</mat-icon>
            Powiadomienia
          </a>
        </aside>

        <!-- Main content -->
        <main class="main-content" id="main-content" tabindex="-1">
          <!-- Page header -->
          <div class="page-header">
            <div class="page-header-text">
              <h1 class="page-title">Uwierzytelnianie dwuskładnikowe</h1>
              <p class="page-subtitle">
                Zabezpiecz swoje konto dodatkową warstwą ochrony za pomocą
                aplikacji TOTP.
              </p>
            </div>
          </div>

          @if (step() === "idle" && !isMfaEnabled()) {
            <!-- Idle: MFA not enabled — prompt to start setup -->
            <div class="settings-card">
              <div class="mfa-card-layout">
                <div class="mfa-qr-area">
                  <mat-icon class="mfa-qr-placeholder-icon">qr_code_2</mat-icon>
                </div>
                <div class="mfa-steps">
                  <div class="mfa-step">
                    <p class="mfa-step-title">1. Zainstaluj aplikację TOTP</p>
                    <p class="mfa-step-desc">
                      Google Authenticator, Authy lub 1Password.
                    </p>
                  </div>
                  <div class="mfa-step">
                    <p class="mfa-step-title">2. Zeskanuj kod QR</p>
                    <p class="mfa-step-desc">
                      Zostanie wyświetlony po kliknięciu poniższego przycisku.
                    </p>
                  </div>
                  <div class="mfa-step">
                    <p class="mfa-step-title">3. Wpisz kod weryfikacyjny</p>
                    <p class="mfa-step-desc">
                      Wpisz 6-cyfrowy kod z aplikacji TOTP.
                    </p>
                  </div>
                </div>
              </div>
              <button
                mat-raised-button
                color="primary"
                class="mfa-verify-btn"
                (click)="startSetup()"
                [disabled]="isLoading()"
              >
                <mat-icon>shield</mat-icon>
                Włącz MFA
              </button>
            </div>
          }

          @if (step() === "setup") {
            <!-- Setup: QR code + steps + code entry -->
            <div class="settings-card">
              <div class="mfa-card-layout">
                <div class="mfa-qr-area">
                  @if (qrCodeDataUrl()) {
                    <img
                      [src]="qrCodeDataUrl()"
                      alt="Kod QR do konfiguracji MFA"
                      class="mfa-qr-img"
                    />
                  } @else {
                    <mat-icon class="mfa-qr-placeholder-icon"
                      >qr_code_2</mat-icon
                    >
                  }
                </div>
                <div class="mfa-steps">
                  <div class="mfa-step">
                    <p class="mfa-step-title">1. Zainstaluj aplikację TOTP</p>
                    <p class="mfa-step-desc">
                      Google Authenticator, Authy lub 1Password.
                    </p>
                  </div>
                  <div class="mfa-step">
                    <p class="mfa-step-title">2. Zeskanuj kod QR</p>
                    <p class="mfa-step-desc">
                      Lub wpisz klucz ręcznie:
                      <code class="mfa-secret">{{ secret() }}</code>
                    </p>
                  </div>
                  <div class="mfa-step">
                    <p class="mfa-step-title">3. Wpisz kod weryfikacyjny</p>
                    <div class="mfa-code-row">
                      @for (i of [0, 1, 2]; track i) {
                        <input
                          #codeInput
                          class="mfa-code-digit"
                          type="text"
                          inputmode="numeric"
                          maxlength="1"
                          autocomplete="off"
                          [attr.aria-label]="'Cyfra ' + (i + 1)"
                          (input)="onDigitInput($event, i)"
                          (keydown)="onDigitKeydown($event, i)"
                          (paste)="onPaste($event)"
                        />
                      }
                      <span class="mfa-code-sep">&mdash;</span>
                      @for (i of [3, 4, 5]; track i) {
                        <input
                          #codeInput
                          class="mfa-code-digit"
                          type="text"
                          inputmode="numeric"
                          maxlength="1"
                          autocomplete="off"
                          [attr.aria-label]="'Cyfra ' + (i + 1)"
                          (input)="onDigitInput($event, i)"
                          (keydown)="onDigitKeydown($event, i)"
                          (paste)="onPaste($event)"
                        />
                      }
                    </div>
                  </div>
                </div>
              </div>
              <button
                mat-raised-button
                color="primary"
                class="mfa-verify-btn"
                (click)="confirmSetup()"
                [disabled]="isLoading() || !isCodeComplete()"
              >
                <mat-icon>verified_user</mat-icon>
                Weryfikuj i włącz MFA
              </button>
            </div>
          }

          @if (step() === "done") {
            <!-- Done: backup codes -->
            <div class="settings-card">
              <h2 class="card-title">MFA włączone pomyślnie!</h2>
              <p>
                <strong>Zachowaj kody zapasowe.</strong> Każdy kod można użyć
                tylko raz.
              </p>
              <div class="backup-codes">
                @for (code of backupCodes(); track code) {
                  <code class="backup-code">{{ code }}</code>
                }
              </div>
              <button
                mat-button
                (click)="copyBackupCodes()"
                aria-label="Kopiuj kody zapasowe"
              >
                <mat-icon>{{
                  copySuccess() ? "check" : "content_copy"
                }}</mat-icon>
                {{ copySuccess() ? "Skopiowano!" : "Kopiuj kody" }}
              </button>
            </div>
          }

          @if (step() === "disable") {
            <!-- Disable MFA -->
            <div class="settings-card danger-card">
              <h2 class="card-title danger-title">Wyłącz MFA</h2>
              <p class="danger-desc">Aby wyłączyć MFA, podaj swoje hasło.</p>
              <form
                (ngSubmit)="disableMfa()"
                aria-label="Formularz wyłączenia MFA"
              >
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Hasło</mat-label>
                  <input
                    matInput
                    [formControl]="disableForm.controls.password"
                    type="password"
                    autocomplete="current-password"
                    aria-label="Hasło"
                  />
                  @if (
                    disableForm.controls.password.hasError("required") &&
                    disableForm.controls.password.touched
                  ) {
                    <mat-error>Hasło jest wymagane</mat-error>
                  }
                </mat-form-field>
                <div class="form-actions">
                  <button
                    mat-raised-button
                    color="warn"
                    type="submit"
                    [disabled]="isLoading()"
                  >
                    <mat-icon>shield_off</mat-icon>
                    Wyłącz MFA
                  </button>
                  <button mat-button type="button" (click)="step.set('idle')">
                    Anuluj
                  </button>
                </div>
              </form>
            </div>
          }

          @if (
            step() !== "setup" &&
            step() !== "done" &&
            step() !== "disable" &&
            isMfaEnabled()
          ) {
            <!-- MFA enabled, idle state -->
            <div class="settings-card">
              <h2 class="card-title">MFA jest włączone</h2>
              <p>
                Twoje konto jest chronione uwierzytelnianiem dwuskładnikowym.
              </p>
              <button
                mat-raised-button
                color="warn"
                (click)="step.set('disable')"
              >
                <mat-icon>shield_off</mat-icon>
                Wyłącz MFA
              </button>
            </div>
          }

          <!-- Warning banner (always visible during setup) -->
          @if (step() === "setup" || step() === "done") {
            <div class="warning-banner" role="alert">
              <mat-icon class="warning-icon">error</mat-icon>
              <span>
                Zapisz kody odzyskiwania w bezpiecznym miejscu. Utrata dostępu
                do aplikacji TOTP wymaga kontaktu z administratorem.
              </span>
            </div>
          }

          @if (errorMessage()) {
            <div class="error-banner" role="alert" aria-live="assertive">
              {{ errorMessage() }}
            </div>
          }
        </main>
      </div>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .settings-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .settings-content {
        display: flex;
        gap: 24px;
        padding: 32px 48px;
        flex: 1;
      }

      /* Sidebar */
      .sidebar {
        width: 240px;
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .sidebar-title {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0 0 8px 0;
      }
      .sidebar-link {
        display: flex !important;
        align-items: center;
        gap: 8px;
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        color: #4b5563;
      }
      .sidebar-link mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
      .sidebar-active {
        color: #1976d2 !important;
        font-weight: 500;
        background: rgba(25, 118, 210, 0.08);
      }

      /* Main content */
      .main-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 24px;
        min-width: 0;
      }

      /* Page header */
      .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .page-header-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }
      .page-subtitle {
        font-size: 15px;
        color: #4b5563;
        margin: 0;
      }

      /* Cards */
      .settings-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .card-title {
        font-size: 18px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0;
      }

      /* MFA card layout — QR + steps side by side */
      .mfa-card-layout {
        display: flex;
        align-items: flex-start;
        gap: 32px;
      }
      .mfa-qr-area {
        width: 180px;
        height: 180px;
        flex-shrink: 0;
        border-radius: 16px;
        background: #f3f4f6;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      }
      .mfa-qr-placeholder-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: #9ca3af;
      }
      .mfa-qr-img {
        width: 180px;
        height: 180px;
      }

      .mfa-steps {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .mfa-step {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .mfa-step-title {
        font-size: 14px;
        font-weight: 500;
        color: #1a1a1a;
        margin: 0;
      }
      .mfa-step-desc {
        font-size: 13px;
        color: #6b7280;
        margin: 0;
      }
      .mfa-secret {
        background: #f3f4f6;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 12px;
        letter-spacing: 1px;
      }

      /* Code digit inputs */
      .mfa-code-row {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .mfa-code-digit {
        width: 44px;
        height: 48px;
        text-align: center;
        font-size: 20px;
        font-weight: 600;
        font-family: Roboto, sans-serif;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        outline: none;
        background: #ffffff;
        color: #1a1a1a;
      }
      .mfa-code-digit:focus {
        border-color: #1976d2;
        box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
      }
      .mfa-code-sep {
        font-size: 20px;
        color: #9ca3af;
      }

      /* Verify button */
      .mfa-verify-btn {
        align-self: flex-start;
      }

      /* Warning banner */
      .warning-banner {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #fdecea;
        color: #611a15;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 13px;
      }
      .warning-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: #d32f2f;
        flex-shrink: 0;
      }

      /* Error banner */
      .error-banner {
        background: #fdecea;
        color: #611a15;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 14px;
      }

      /* Backup codes */
      .backup-codes {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
      }
      .backup-code {
        background: #f3f4f6;
        padding: 8px;
        text-align: center;
        border-radius: 8px;
        font-family: monospace;
      }

      /* Danger zone */
      .danger-card {
        border: 1px solid #fca5a5;
      }
      .danger-title {
        color: #b71c1c;
      }
      .danger-desc {
        font-size: 14px;
        color: #4b5563;
        margin: 0;
      }

      .form-actions {
        display: flex;
        gap: 12px;
        align-items: center;
      }

      form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      mat-form-field {
        width: 100%;
      }

      @media (max-width: 768px) {
        .settings-content {
          flex-direction: column;
          padding: 16px;
        }
        .sidebar {
          width: 100%;
          flex-direction: row;
          flex-wrap: wrap;
        }
        .mfa-card-layout {
          flex-direction: column;
          align-items: center;
        }
      }
    `,
  ],
})
export class MfaSetupComponent implements OnInit, AfterViewInit {
  private readonly authService = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  readonly step = signal<MfaStep>("idle");
  readonly isLoading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly isMfaEnabled = signal(false);
  readonly secret = signal("");
  readonly provisioningUri = signal("");
  readonly qrCodeDataUrl = signal("");
  readonly backupCodes = signal<string[]>([]);
  readonly codeDigits = signal<string[]>(["", "", "", "", "", ""]);

  readonly codeInputs = viewChildren<ElementRef<HTMLInputElement>>("codeInput");

  readonly disableForm = new FormGroup({
    password: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  readonly copySuccess = signal(false);

  ngOnInit(): void {
    const user = this.authService.currentUserSignal();
    if (user?.mfaEnabled) {
      this.isMfaEnabled.set(true);
    }
  }

  ngAfterViewInit(): void {
    // Focus first digit input when setup step is shown
  }

  isCodeComplete(): boolean {
    return this.codeDigits().every((d) => d.length === 1);
  }

  private getFullCode(): string {
    return this.codeDigits().join("");
  }

  onDigitInput(event: Event, index: number): void {
    const input = event.target as HTMLInputElement;
    const value = input.value.replace(/\D/g, "").slice(0, 1);
    input.value = value;

    const digits = [...this.codeDigits()];
    digits[index] = value;
    this.codeDigits.set(digits);

    if (value && index < 5) {
      this.focusInput(index + 1);
    }
  }

  onDigitKeydown(event: KeyboardEvent, index: number): void {
    if (event.key === "Backspace" && !event.currentTarget) return;

    const input = event.target as HTMLInputElement;
    if (event.key === "Backspace" && input.value === "" && index > 0) {
      this.focusInput(index - 1);
    }
  }

  onPaste(event: ClipboardEvent): void {
    event.preventDefault();
    const text = (event.clipboardData?.getData("text") || "")
      .replace(/\D/g, "")
      .slice(0, 6);

    if (text.length === 0) return;

    const digits = [...this.codeDigits()];
    for (let i = 0; i < 6; i++) {
      digits[i] = text[i] || "";
    }
    this.codeDigits.set(digits);

    const inputs = this.codeInputs();
    if (inputs.length === 6) {
      for (let i = 0; i < 6; i++) {
        inputs[i].nativeElement.value = digits[i];
      }
      const focusIdx = Math.min(text.length, 5);
      inputs[focusIdx].nativeElement.focus();
    }
  }

  private focusInput(index: number): void {
    const inputs = this.codeInputs();
    if (inputs[index]) {
      inputs[index].nativeElement.focus();
    }
  }

  private async generateQrCode(uri: string): Promise<void> {
    try {
      const dataUrl = await QRCode.toDataURL(uri, { width: 180, margin: 1 });
      this.qrCodeDataUrl.set(dataUrl);
    } catch {
      this.qrCodeDataUrl.set("");
    }
  }

  startSetup(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.authService
      .setupMfa()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isLoading.set(false);
          this.secret.set(res.secret);
          this.provisioningUri.set(res.provisioningUri);
          this.generateQrCode(res.provisioningUri);
          this.codeDigits.set(["", "", "", "", "", ""]);
          this.step.set("setup");
        },
        error: () => {
          this.isLoading.set(false);
          this.errorMessage.set("Nie udało się zainicjować MFA.");
        },
      });
  }

  confirmSetup(): void {
    const code = this.getFullCode();
    if (code.length !== 6) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.authService
      .confirmMfa(code)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isLoading.set(false);
          this.backupCodes.set(res.backupCodes);
          this.isMfaEnabled.set(true);
          this.step.set("done");
        },
        error: () => {
          this.isLoading.set(false);
          this.errorMessage.set("Nieprawidłowy kod TOTP.");
          this.codeDigits.set(["", "", "", "", "", ""]);
          const inputs = this.codeInputs();
          inputs.forEach((inp) => (inp.nativeElement.value = ""));
          if (inputs[0]) inputs[0].nativeElement.focus();
        },
      });
  }

  disableMfa(): void {
    if (this.disableForm.invalid) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.authService
      .disableMfa(this.disableForm.getRawValue().password)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isLoading.set(false);
          this.isMfaEnabled.set(false);
          this.step.set("idle");
        },
        error: () => {
          this.isLoading.set(false);
          this.errorMessage.set("Nieprawidłowe hasło.");
        },
      });
  }

  copyBackupCodes(): void {
    const text = this.backupCodes().join("\n");
    navigator.clipboard.writeText(text).then(
      () => {
        this.copySuccess.set(true);
        setTimeout(() => this.copySuccess.set(false), 2000);
      },
      () =>
        this.errorMessage.set(
          "Nie udało się skopiować kodów. Skopiuj je ręcznie.",
        ),
    );
  }
}
