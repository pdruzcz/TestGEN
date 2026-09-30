import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { Router } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { AuthService, TenantInfo } from "../../../core/services/auth.service";

@Component({
  selector: "app-select-tenant",
  standalone: true,
  imports: [
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <main class="select-tenant-container" id="main-content" tabindex="-1">
      <mat-card class="select-tenant-card">
        <mat-card-header>
          <mat-card-title>Wybierz organizację</mat-card-title>
          <mat-card-subtitle
            >Wybierz organizację, w której chcesz pracować.</mat-card-subtitle
          >
        </mat-card-header>
        <mat-card-content>
          @if (errorMessage()) {
            <p class="error-message">{{ errorMessage() }}</p>
          }

          @if (isSubmitting()) {
            <div class="spinner-container">
              <mat-spinner diameter="40" aria-label="Ładowanie"></mat-spinner>
            </div>
          } @else {
            <div class="tenant-list">
              @for (tenant of tenants(); track tenant.tenantId) {
                <mat-card class="tenant-card" (click)="selectTenant(tenant)">
                  <mat-card-content class="tenant-card-content">
                    <div class="tenant-info">
                      <span class="tenant-name">{{ tenant.tenantName }}</span>
                      <mat-chip-set>
                        <mat-chip>{{ roleLabel(tenant.role) }}</mat-chip>
                      </mat-chip-set>
                    </div>
                    <button mat-flat-button color="primary">Wybierz</button>
                  </mat-card-content>
                </mat-card>
              }
            </div>
          }
        </mat-card-content>
      </mat-card>
    </main>
  `,
  styles: [
    `
      .select-tenant-container {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        padding: 1rem;
      }
      .select-tenant-card {
        max-width: 500px;
        width: 100%;
      }
      .tenant-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin-top: 1rem;
      }
      .tenant-card {
        cursor: pointer;
        transition: box-shadow 0.2s;
      }
      .tenant-card:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
      }
      .tenant-card-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .tenant-info {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
      }
      .tenant-name {
        font-weight: 500;
        font-size: 1.1rem;
      }
      .spinner-container {
        display: flex;
        justify-content: center;
        padding: 2rem;
      }
      .error-message {
        color: #b00020;
        text-align: center;
        margin-bottom: 1rem;
      }
    `,
  ],
})
export class SelectTenantComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly tenants = signal<TenantInfo[]>([]);
  readonly isSubmitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  private preAuthToken: string | null = null;

  constructor() {
    this.preAuthToken = sessionStorage.getItem("pre_auth_token");
    const raw = sessionStorage.getItem("available_tenants");
    if (!this.preAuthToken || !raw) {
      this.router.navigateByUrl("/login");
      return;
    }
    try {
      const parsed: TenantInfo[] = JSON.parse(raw);
      // Validate: each tenant must have a valid UUID tenantId
      const valid = parsed.filter(
        (t) =>
          t.tenantId &&
          typeof t.tenantId === "string" &&
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
            t.tenantId,
          ),
      );
      if (!valid.length) {
        this.router.navigateByUrl("/login");
        return;
      }
      this.tenants.set(valid);
    } catch {
      this.router.navigateByUrl("/login");
    }
  }

  roleLabel(role: string): string {
    switch (role) {
      case "owner":
        return "Właściciel";
      case "admin":
        return "Administrator";
      case "user":
        return "Użytkownik";
      default:
        return role;
    }
  }

  selectTenant(tenant: TenantInfo): void {
    if (!this.preAuthToken) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    this.authService
      .selectTenant(this.preAuthToken, tenant.tenantId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isSubmitting.set(false);
          sessionStorage.removeItem("pre_auth_token");
          sessionStorage.removeItem("available_tenants");

          if (res.mfaRequired && res.mfaToken) {
            sessionStorage.setItem("mfa_token", res.mfaToken);
            this.router.navigateByUrl("/mfa-verify");
          } else {
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
          }
        },
        error: () => {
          this.isSubmitting.set(false);
          this.errorMessage.set(
            "Nie udało się wybrać organizacji. Spróbuj ponownie.",
          );
        },
      });
  }
}
