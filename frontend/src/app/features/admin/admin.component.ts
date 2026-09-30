import { Component } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";
import { MatListModule } from "@angular/material/list";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatToolbarModule } from "@angular/material/toolbar";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";

export interface AdminNavItem {
  path: string;
  label: string;
  icon: string;
}

/**
 * Powłoka panelu administracyjnego (Story 6.15, AC1, AC8).
 *
 * Boczna nawigacja prowadzi do czterech sekcji ładowanych leniwie przez
 * `ADMIN_ROUTES`; dostęp chroni `roleGuard("admin")` na trasie nadrzędnej.
 */
@Component({
  selector: "app-admin",
  standalone: true,
  imports: [
    MatIconModule,
    MatListModule,
    MatSidenavModule,
    MatToolbarModule,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
  ],
  templateUrl: "./admin.component.html",
  styleUrls: ["./admin.component.scss"],
})
export class AdminComponent {
  readonly navItems: readonly AdminNavItem[] = [
    { path: "users", label: "Użytkownicy", icon: "group" },
    { path: "tenants", label: "Tenanci", icon: "domain" },
    { path: "audit-log", label: "Log audytu", icon: "history" },
    { path: "config", label: "Konfiguracja", icon: "settings" },
  ];
}
