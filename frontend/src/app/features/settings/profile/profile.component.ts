import {
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from "@angular/core";
import {
  ReactiveFormsModule,
  FormBuilder,
  FormControl,
  FormGroup,
  Validators,
} from "@angular/forms";
import { HttpClient } from "@angular/common/http";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { RouterLink } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";
import { HttpErrorResponse } from "@angular/common/http";
import { environment } from "../../../../environments/environment";
import { AuthService, UserProfile } from "../../../core/services/auth.service";
import { passwordComplexityValidator } from "../../../shared/validators/password-complexity.validator";
import { passwordMatchValidator } from "../../../shared/validators/password-match.validator";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";

interface ProfileForm {
  name: FormControl<string>;
}

interface PasswordForm {
  oldPassword: FormControl<string>;
  newPassword: FormControl<string>;
  confirmNewPassword: FormControl<string>;
}

@Component({
  selector: "app-profile",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    RouterLink,
    MatIconModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="settings-page">
      <app-navbar activeLink="profile" />

      <!-- Content area -->
      <div class="settings-content">
        <!-- Sidebar -->
        <aside class="sidebar">
          <h3 class="sidebar-title">Ustawienia</h3>
          <a
            mat-button
            routerLink="/settings/profile"
            class="sidebar-link sidebar-active"
          >
            <mat-icon>person</mat-icon>
            Profil
          </a>
          <a mat-button routerLink="/settings/mfa" class="sidebar-link">
            <mat-icon>shield</mat-icon>
            Uwierzytelnianie MFA
          </a>
          <a
            mat-button
            routerLink="/settings/profile"
            fragment="powiadomienia"
            class="sidebar-link"
          >
            <mat-icon>notifications</mat-icon>
            Powiadomienia
          </a>
        </aside>

        <!-- Main content -->
        <main class="main-content" id="main-content" tabindex="-1">
          <!-- Page header -->
          <div class="page-header">
            <div class="page-header-text">
              <h1 class="page-title">Ustawienia profilu</h1>
              <p class="page-subtitle">
                Zarządzaj swoimi danymi osobowymi i hasłem.
              </p>
            </div>
            <div class="page-avatar">
              {{ userInitials() }}
            </div>
          </div>

          <!-- Profile card -->
          <div class="settings-card">
            <h2 class="card-title">Dane profilowe</h2>
            <form [formGroup]="profileForm" (ngSubmit)="onUpdateProfile()">
              <div class="form-row">
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Email</mat-label>
                  <input
                    matInput
                    type="email"
                    [value]="user()?.email || ''"
                    readonly
                    aria-readonly="true"
                    aria-label="Email (tylko do odczytu)"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Nazwa</mat-label>
                  <input
                    matInput
                    formControlName="name"
                    aria-label="Nazwa wyświetlana"
                  />
                </mat-form-field>
              </div>
              <button
                mat-raised-button
                color="primary"
                type="submit"
                [disabled]="profileForm.invalid || isSubmittingProfile()"
              >
                <mat-icon>save</mat-icon>
                Zapisz profil
              </button>
            </form>
            @if (profileMessage()) {
              @if (profileError()) {
                <div class="error-banner" role="alert" aria-live="polite">
                  {{ profileMessage() }}
                </div>
              } @else {
                <div class="success-banner" role="status" aria-live="polite">
                  {{ profileMessage() }}
                </div>
              }
            }
          </div>

          <!-- Notification preferences card (Story 7.11, AC5) -->
          <div class="settings-card" id="powiadomienia">
            <h2 class="card-title">Powiadomienia o limitach</h2>
            <p class="card-hint">
              Wybierz, jak chcesz otrzymywać ostrzeżenia o zbliżaniu się do
              limitów planu (80%, 90%, 100%).
            </p>
            <div class="pref-row">
              <mat-slide-toggle
                [checked]="emailNotifications()"
                (change)="emailNotifications.set($event.checked)"
                aria-label="Powiadomienia email o limitach"
              >
                Email
              </mat-slide-toggle>
            </div>
            <div class="pref-row">
              <mat-slide-toggle
                [checked]="inAppNotifications()"
                (change)="inAppNotifications.set($event.checked)"
                aria-label="Powiadomienia w aplikacji o limitach"
              >
                W aplikacji (dzwonek)
              </mat-slide-toggle>
            </div>
            <button
              mat-raised-button
              color="primary"
              type="button"
              (click)="onSavePreferences()"
              [disabled]="isSubmittingProfile()"
            >
              <mat-icon>save</mat-icon>
              Zapisz preferencje
            </button>
          </div>

          <!-- Password card -->
          <div class="settings-card">
            <h2 class="card-title">Zmiana hasła</h2>
            <p class="card-hint">
              Min. 12 znaków, wielka i mała litera, cyfra, znak specjalny.
            </p>
            <form [formGroup]="passwordForm" (ngSubmit)="onChangePassword()">
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Obecne hasło</mat-label>
                <input
                  matInput
                  formControlName="oldPassword"
                  type="password"
                  autocomplete="current-password"
                  aria-label="Obecne hasło"
                />
                @if (
                  passwordForm.controls.oldPassword.hasError("required") &&
                  passwordForm.controls.oldPassword.touched
                ) {
                  <mat-error>Obecne hasło jest wymagane</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Nowe hasło</mat-label>
                <input
                  matInput
                  formControlName="newPassword"
                  type="password"
                  autocomplete="new-password"
                  aria-label="Nowe hasło"
                  aria-describedby="profile-pw-requirements"
                />
                <mat-hint id="profile-pw-requirements"
                  >Min. 12 znaków, wielka i mała litera, cyfra, znak
                  specjalny</mat-hint
                >
                @if (
                  passwordForm.controls.newPassword.hasError("required") &&
                  passwordForm.controls.newPassword.touched
                ) {
                  <mat-error>Nowe hasło jest wymagane</mat-error>
                }
                @if (passwordForm.controls.newPassword.hasError("minlength")) {
                  <mat-error>Hasło musi mieć minimum 12 znaków</mat-error>
                }
                @if (
                  passwordForm.controls.newPassword.hasError(
                    "passwordComplexity"
                  ) && passwordForm.controls.newPassword.touched
                ) {
                  <mat-error>{{
                    passwordForm.controls.newPassword.getError(
                      "passwordComplexity"
                    )
                  }}</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Potwierdź nowe hasło</mat-label>
                <input
                  matInput
                  formControlName="confirmNewPassword"
                  type="password"
                  autocomplete="new-password"
                  aria-label="Potwierdzenie nowego hasła"
                />
                @if (
                  passwordForm.controls.confirmNewPassword.hasError(
                    "required"
                  ) && passwordForm.controls.confirmNewPassword.touched
                ) {
                  <mat-error>Potwierdzenie hasła jest wymagane</mat-error>
                }
              </mat-form-field>

              @if (
                passwordForm.hasError("passwordMismatch") &&
                passwordForm.controls.confirmNewPassword.touched
              ) {
                <p class="field-error" role="alert">Hasła nie są zgodne</p>
              }

              <button
                mat-raised-button
                color="warn"
                type="submit"
                [disabled]="passwordForm.invalid || isSubmittingPassword()"
              >
                <mat-icon>key</mat-icon>
                Zmień hasło
              </button>
            </form>
            @if (passwordMessage()) {
              @if (passwordError()) {
                <div class="error-banner" role="alert" aria-live="polite">
                  {{ passwordMessage() }}
                </div>
              } @else {
                <div class="success-banner" role="status" aria-live="polite">
                  {{ passwordMessage() }}
                </div>
              }
            }
          </div>

          <!-- Danger zone card -->
          <div class="settings-card danger-card">
            <h2 class="card-title danger-title">Strefa niebezpieczna</h2>
            <p class="danger-desc">
              Usunięcie konta jest nieodwracalne. Wszystkie dane zostaną trwale
              usunięte.
            </p>
            <button
              mat-raised-button
              color="warn"
              type="button"
              disabled
              aria-disabled="true"
            >
              <mat-icon>delete</mat-icon>
              Usuń konto (niedostępne)
            </button>
          </div>
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

      /* Content area with sidebar + main */
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
      .page-avatar {
        width: 72px;
        height: 72px;
        border-radius: 50%;
        background: #1976d2;
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: 500;
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
      .card-hint {
        font-size: 13px;
        color: #4b5563;
        margin: -12px 0 0 0;
      }

      /* Forms inside cards */
      form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .pref-row {
        display: flex;
        align-items: center;
      }
      .form-row {
        display: flex;
        gap: 16px;
      }
      .form-row mat-form-field {
        flex: 1;
      }
      mat-form-field {
        width: 100%;
      }

      /* Banners */
      .success-banner {
        background: #e8f5e9;
        color: #1b5e20;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 14px;
      }
      .error-banner {
        background: #fdecea;
        color: #611a15;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 14px;
      }
      .field-error {
        color: #d32f2f;
        font-size: 0.75rem;
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
        .form-row {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class ProfileComponent implements OnInit {
  profileForm: FormGroup<ProfileForm>;
  passwordForm: FormGroup<PasswordForm>;
  user = signal<UserProfile | null>(null);
  profileMessage = signal("");
  profileError = signal(false);
  passwordMessage = signal("");
  passwordError = signal(false);
  isSubmittingProfile = signal(false);
  isSubmittingPassword = signal(false);
  // Story 7.11 (AC5): kanały powiadomień o limitach — domyślnie włączone.
  emailNotifications = signal(true);
  inAppNotifications = signal(true);

  userInitials = computed(() => {
    const u = this.user();
    if (!u || !u.name) return "?";
    return u.name
      .split(" ")
      .map((w) => w[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  });

  private readonly apiUrl = environment.apiUrl;
  private destroyRef = inject(DestroyRef);
  private authService = inject(AuthService);
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);

  constructor() {
    this.profileForm = this.fb.group({
      name: this.fb.nonNullable.control("", [
        Validators.required,
        Validators.maxLength(255),
      ]),
    }) as FormGroup<ProfileForm>;

    this.passwordForm = this.fb.group(
      {
        oldPassword: this.fb.nonNullable.control("", [Validators.required]),
        newPassword: this.fb.nonNullable.control("", [
          Validators.required,
          Validators.minLength(12),
          Validators.maxLength(128),
          passwordComplexityValidator,
        ]),
        confirmNewPassword: this.fb.nonNullable.control("", [
          Validators.required,
          Validators.maxLength(128),
        ]),
      },
      {
        validators: passwordMatchValidator("newPassword", "confirmNewPassword"),
      },
    ) as FormGroup<PasswordForm>;
  }

  ngOnInit(): void {
    const currentUser = this.authService.currentUserSignal();
    if (currentUser) {
      this.user.set(currentUser);
      this.profileForm.patchValue({ name: currentUser.name });
      this.applyPrefs(currentUser);
    } else {
      this.authService
        .fetchProfile()
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (user) => {
            if (user) {
              this.user.set(user);
              this.profileForm.patchValue({ name: user.name });
              this.applyPrefs(user);
            }
          },
          error: () => {
            this.profileMessage.set("Nie udało się załadować profilu");
          },
        });
    }
  }

  /** AC5 — odczyt kanałów z profilu; brak zapisu = domyślnie włączone. */
  private applyPrefs(user: UserProfile): void {
    const prefs = (user.notificationPreferences ?? {}) as Record<
      string,
      unknown
    >;
    const lw = (prefs["limitWarnings"] ?? prefs["limit_warnings"]) as
      | Record<string, unknown>
      | undefined;
    this.emailNotifications.set(lw?.["email"] !== false);
    this.inAppNotifications.set(
      lw?.["inApp"] !== false && lw?.["in_app"] !== false,
    );
  }

  /** AC5 — zapis kanałów przez PUT /users/me (notification_preferences). */
  onSavePreferences(): void {
    if (this.isSubmittingProfile()) return;

    this.isSubmittingProfile.set(true);
    this.http
      .put<UserProfile>(`${this.apiUrl}/users/me`, {
        notificationPreferences: {
          limitWarnings: {
            email: this.emailNotifications(),
            inApp: this.inAppNotifications(),
          },
        },
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (user) => {
          this.user.set(user);
          this.authService.updateCurrentUser(user);
          this.applyPrefs(user);
          this.profileMessage.set("Preferencje powiadomień zapisane");
          this.profileError.set(false);
          this.isSubmittingProfile.set(false);
        },
        error: () => {
          this.profileMessage.set("Błąd zapisu preferencji powiadomień");
          this.profileError.set(true);
          this.isSubmittingProfile.set(false);
        },
      });
  }

  onUpdateProfile(): void {
    if (this.profileForm.invalid || this.isSubmittingProfile()) return;

    this.isSubmittingProfile.set(true);
    this.http
      .put<UserProfile>(`${this.apiUrl}/users/me`, this.profileForm.value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (user) => {
          this.user.set(user);
          this.authService.updateCurrentUser(user);
          this.profileMessage.set("Profil zaktualizowany");
          this.profileError.set(false);
          this.isSubmittingProfile.set(false);
        },
        error: () => {
          this.profileMessage.set("Błąd aktualizacji profilu");
          this.profileError.set(true);
          this.isSubmittingProfile.set(false);
        },
      });
  }

  onChangePassword(): void {
    if (this.passwordForm.invalid || this.isSubmittingPassword()) return;

    this.isSubmittingPassword.set(true);

    const { oldPassword, newPassword } = this.passwordForm.getRawValue();

    this.http
      .put(`${this.apiUrl}/users/me/password`, { oldPassword, newPassword })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.passwordMessage.set("Hasło zmienione pomyślnie");
          this.passwordError.set(false);
          this.passwordForm.reset();
          this.isSubmittingPassword.set(false);
        },
        error: (err: HttpErrorResponse) => {
          this.passwordMessage.set(
            "Błąd zmiany hasła. Sprawdź poprawność danych.",
          );
          this.passwordError.set(true);
          this.isSubmittingPassword.set(false);
        },
      });
  }
}
