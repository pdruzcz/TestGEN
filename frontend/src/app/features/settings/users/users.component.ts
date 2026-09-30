import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { UserManagementService, UserItem } from "../../users/services/user-management.service";

@Component({
  selector: "app-settings-users",
  standalone: true,
  imports: [
    CommonModule, RouterLink, MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, NavbarComponent, FooterComponent,
  ],
  template: `
    <div class="settings-page">
      <app-navbar activeLink="profile" />
      <div class="settings-content">
        <aside class="sidebar">
          <h3 class="sidebar-title">Ustawienia</h3>
          <a mat-button routerLink="/settings/profile" class="sidebar-link">
            <mat-icon>person</mat-icon> Profil
          </a>
          <a mat-button routerLink="/settings/mfa" class="sidebar-link">
            <mat-icon>shield</mat-icon> Uwierzytelnianie MFA
          </a>
          <a mat-button routerLink="/settings/users" class="sidebar-link sidebar-active">
            <mat-icon>group</mat-icon> Uzytkownicy
          </a>
          <a mat-button routerLink="/settings/api-keys" class="sidebar-link">
            <mat-icon>vpn_key</mat-icon> Klucze API
          </a>
          <a mat-button routerLink="/settings/integrations/github" class="sidebar-link">
            <mat-icon>hub</mat-icon> Integracja GitHub
          </a>
          <a mat-button routerLink="/settings/integrations/gitlab" class="sidebar-link">
            <mat-icon>merge</mat-icon> Integracja GitLab
          </a>
          <a mat-button routerLink="/settings/integrations/webhooks" class="sidebar-link">
            <mat-icon>webhook</mat-icon> Webhooki
          </a>
        </aside>
        <main class="main-content" id="main-content" tabindex="-1">
          <div class="page-header">
            <div>
              <h1 class="page-title">Zarzadzanie uzytkownikami</h1>
              <p class="page-subtitle">Zapraszaj czlonkow zespolu i zarzadzaj ich rolami.</p>
            </div>
            <button mat-raised-button color="primary" routerLink="/users/invite">
              <mat-icon>person_add</mat-icon>
              Zapros uzytkownika
            </button>
          </div>

          @if (isLoading()) {
            <div class="loading"><mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner> Ladowanie...</div>
          } @else {
            <table class="users-table">
              <caption class="visually-hidden">Lista użytkowników</caption>
              <thead>
                <tr>
                  <th scope="col">Imie i nazwisko</th>
                  <th scope="col">Email</th>
                  <th scope="col">Rola</th>
                  <th scope="col">Status</th>
                  <th scope="col">Akcje</th>
                </tr>
              </thead>
              <tbody>
                @for (u of users(); track u.id) {
                  <tr>
                    <td class="user-name">{{ u.name }}</td>
                    <td>{{ u.email }}</td>
                    <td>
                      <span class="badge" [class]="'badge-' + u.role">
                        {{ u.role }}
                      </span>
                    </td>
                    <td>{{ u.isActive ? 'Aktywny' : 'Oczekuje' }}</td>
                    <td class="actions">
                      <button class="icon-btn" (click)="changeRole(u)">
                        <mat-icon>edit</mat-icon>
                      </button>
                      <button class="icon-btn" (click)="removeUser(u.id)">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          }
        </main>
      </div>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .settings-page { min-height: 100vh; background: #f7f8fa; display: flex; flex-direction: column; }
      .settings-content { display: flex; gap: 24px; padding: 32px 48px; flex: 1; max-width: 1200px; width: 100%; margin: 0 auto; }
      .sidebar { width: 240px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; }
      .sidebar-title { font-size: 16px; font-weight: 600; color: #1a1a1a; margin: 0 0 8px; }
      .sidebar-link { display: flex !important; align-items: center; gap: 8px; width: 100%; color: #4b5563; }
      .sidebar-active { color: #1976d2 !important; font-weight: 500; background: rgba(25,118,210,0.08); }
      .main-content { flex: 1; display: flex; flex-direction: column; gap: 24px; }
      .page-header { display: flex; justify-content: space-between; align-items: center; }
      .page-title { font-size: 28px; font-weight: 700; color: #1a1a1a; margin: 0; }
      .page-subtitle { font-size: 15px; color: #4b5563; margin: 0; }
      .loading { display: flex; align-items: center; gap: 12px; color: #6b7280; padding: 2rem; }
      .users-table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 16px; overflow: hidden; border: 1px solid #e5e7eb; }
      .users-table th { text-align: left; padding: 12px 16px; font-size: 13px; font-weight: 500; color: #6b7280; background: #f7f8fa; }
      .users-table td { padding: 12px 16px; border-top: 1px solid #e5e7eb; font-size: 14px; color: #4b5563; }
      .user-name { font-weight: 500; color: #1a1a1a; }
      .badge { display: inline-block; padding: 4px 8px; border-radius: 8px; font-size: 11px; font-weight: 500; text-transform: uppercase; }
      .badge-owner { background: #ede7f6; color: #4527a0; }
      .badge-admin { background: #e3f2fd; color: #0d47a1; }
      .badge-user { background: #e8f5e9; color: #1b5e20; }
      .actions { display: flex; gap: 8px; }
      .icon-btn { background: none; border: none; cursor: pointer; color: #6b7280; display: flex; align-items: center; }
      .icon-btn:hover { color: #1976d2; }
    `,
  ],
})
export class UsersComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly userService = inject(UserManagementService);

  readonly users = this.userService.usersSignal;
  readonly isLoading = this.userService.isLoadingSignal;

  ngOnInit(): void {
    this.userService.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  changeRole(user: UserItem): void {
    const roles: Array<"owner" | "admin" | "user"> = ["admin", "user"];
    const currentIdx = roles.indexOf(user.role as "admin" | "user");
    const nextRole = roles[(currentIdx + 1) % roles.length];
    this.userService.updateRole(user.id, nextRole)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: () => this.userService.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe() });
  }

  removeUser(userId: string): void {
    this.userService.deleteUser(userId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: () => this.userService.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe() });
  }
}
