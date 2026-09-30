import { Routes } from "@angular/router";

import { AdminComponent } from "./admin.component";

/**
 * Leniwe trasy panelu administracyjnego (Story 6.15, AC1).
 *
 * Ochrona ról jest podpięta na trasie nadrzędnej w `app.routes.ts`
 * (`authGuard` + `roleGuard("admin")`), więc dzieci jej nie powtarzają.
 */
export const ADMIN_ROUTES: Routes = [
  {
    path: "",
    component: AdminComponent,
    children: [
      { path: "", redirectTo: "users", pathMatch: "full" },
      {
        path: "users",
        title: "Użytkownicy — Panel administracyjny — TestGEN",
        loadComponent: () =>
          import("./components/user-management/user-management.component").then(
            (m) => m.UserManagementComponent,
          ),
      },
      {
        path: "tenants",
        title: "Tenanci — Panel administracyjny — TestGEN",
        loadComponent: () =>
          import("./components/tenant-management/tenant-management.component").then(
            (m) => m.TenantManagementComponent,
          ),
      },
      {
        path: "audit-log",
        title: "Log audytu — Panel administracyjny — TestGEN",
        loadComponent: () =>
          import("./components/audit-log/audit-log.component").then(
            (m) => m.AuditLogComponent,
          ),
      },
      {
        path: "config",
        title: "Konfiguracja — Panel administracyjny — TestGEN",
        loadComponent: () =>
          import("./components/platform-config/platform-config.component").then(
            (m) => m.PlatformConfigComponent,
          ),
      },
    ],
  },
];
