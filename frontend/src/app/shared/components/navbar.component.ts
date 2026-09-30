import { Component, computed, inject, input } from "@angular/core";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatMenuModule } from "@angular/material/menu";
import { AuthService } from "../../core/services/auth.service";
import { NotificationBellComponent } from "./notification-bell/notification-bell.component";

@Component({
  selector: "app-navbar",
  standalone: true,
  imports: [
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    NotificationBellComponent,
  ],
  template: `
    <header role="banner">
      <nav class="top-nav" aria-label="Menu główne">
        <a routerLink="/dashboard" class="nav-logo" aria-label="Strona główna">
          <img src="logo.svg" alt="TestGEN" class="nav-logo-img" />
        </a>
        <div class="nav-links">
          <a
            class="nav-pill"
            [class.nav-active]="activeLink() === 'dashboard'"
            routerLink="/dashboard"
          >
            <mat-icon>dashboard</mat-icon>
            Dashboard
          </a>
          <a
            class="nav-pill"
            [class.nav-active]="activeLink() === 'projects'"
            routerLink="/projects"
          >
            <mat-icon>folder</mat-icon>
            Projekty
          </a>
          <!-- Wejście do modułu billing (Story 7.12 — audyt nawigacji):
               bez tego menu ekrany /billing/* byłyby osiągalne tylko z URL
               lub bannerów kontekstowych (402/429). -->
          <a
            class="nav-pill"
            [matMenuTriggerFor]="billingMenu"
            [class.nav-active]="activeLink() === 'billing'"
            aria-haspopup="menu"
          >
            <mat-icon>payments</mat-icon>
            Rozliczenia
            <mat-icon class="nav-caret">expand_more</mat-icon>
          </a>
          <mat-menu #billingMenu="matMenu">
            <a mat-menu-item routerLink="/billing/plans">
              <mat-icon>swap_vert</mat-icon>
              <span>Plany subskrypcji</span>
            </a>
            <a mat-menu-item routerLink="/billing/usage">
              <mat-icon>bar_chart</mat-icon>
              <span>Zużycie zasobów</span>
            </a>
            <a mat-menu-item routerLink="/billing/invoices">
              <mat-icon>receipt_long</mat-icon>
              <span>Faktury</span>
            </a>
            <!-- Story 7.7 (AC2) — historia płatności: dostępna też dla roli User -->
            <a mat-menu-item routerLink="/billing/transactions">
              <mat-icon>receipt</mat-icon>
              <span>Transakcje</span>
            </a>
            @if (isOwnerOrAdmin()) {
              <!-- Story 7.7 (AC3-AC5) — zarządzanie subskrypcją (tylko Owner) -->
              <a mat-menu-item routerLink="/billing/subscription">
                <mat-icon>workspace_premium</mat-icon>
                <span>Subskrypcja</span>
              </a>
              <a mat-menu-item routerLink="/billing/invoice-data">
                <mat-icon>badge</mat-icon>
                <span>Dane fakturowe</span>
              </a>
              <a mat-menu-item routerLink="/billing/payment-methods">
                <mat-icon>credit_card</mat-icon>
                <span>Metody płatności</span>
              </a>
            }
          </mat-menu>
          <a
            class="nav-pill"
            [class.nav-active]="activeLink() === 'profile'"
            routerLink="/settings/profile"
          >
            <mat-icon>person</mat-icon>
            Profil
          </a>
          @if (isAdmin()) {
            <a
              class="nav-pill"
              [class.nav-active]="activeLink() === 'admin-cve'"
              routerLink="/admin/cve-pipeline"
            >
              <mat-icon>security_update_good</mat-icon>
              Pipeline CVE
            </a>
          }
        </div>
        <div class="nav-right">
          <app-notification-bell />
          <div class="nav-avatar">{{ userInitials() }}</div>
          <button
            mat-icon-button
            class="nav-logout"
            (click)="authService.logout()"
            aria-label="Wyloguj się"
          >
            <mat-icon>logout</mat-icon>
          </button>
        </div>
      </nav>
    </header>
  `,
  styles: [
    `
      .top-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 64px;
        padding: 0 32px;
        background: #ffffff;
        border-bottom: 1px solid #e5e7eb;
      }
      .nav-logo {
        display: flex;
        align-items: center;
        text-decoration: none;
      }
      .nav-logo-img {
        height: 40px;
        width: auto;
      }
      .nav-links {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex: 1;
      }
      .nav-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 12px;
        text-decoration: none;
        color: #4b5563;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
      }
      .nav-pill mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
      .nav-pill:hover {
        background: #f3f4f6;
      }
      .nav-caret {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }
      .nav-active {
        background: #1976d2;
        color: #ffffff;
      }
      .nav-active:hover {
        background: #1565c0;
      }
      .nav-right {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .nav-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #1976d2;
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 500;
      }
      .nav-logout {
        color: #6b7280 !important;
      }
      .nav-logout:hover {
        color: #b71c1c !important;
      }

      @media (max-width: 768px) {
        .top-nav {
          padding: 0 16px;
        }
        .nav-links {
          display: none;
        }
      }
    `,
  ],
})
export class NavbarComponent {
  readonly activeLink = input<
    "dashboard" | "projects" | "profile" | "admin-cve" | "billing"
  >("dashboard");

  readonly authService = inject(AuthService);

  readonly isAdmin = computed(
    () => this.authService.currentUserSignal()?.role === "admin",
  );

  /** Pozycje menu Rozliczenia wymagające roli Owner (BE: require_role). */
  readonly isOwnerOrAdmin = computed(() => {
    const role = this.authService.currentUserSignal()?.role;
    return role === "owner" || role === "admin";
  });

  readonly userInitials = computed(() => {
    const u = this.authService.currentUserSignal();
    if (!u || !u.name) return "?";
    return u.name
      .split(" ")
      .map((w) => w[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  });
}
