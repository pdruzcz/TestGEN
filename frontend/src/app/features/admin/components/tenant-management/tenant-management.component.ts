import { DatePipe } from "@angular/common";
import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTableModule } from "@angular/material/table";
import { RouterLink } from "@angular/router";
import { Observable } from "rxjs";

import { AdminService, AdminTenant } from "../../services/admin.service";

const PAGE_SIZE = 25;
const UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

/**
 * Przegląd tenantów z metrykami użycia i nawigacją cross-tenant
 * (Story 6.15, AC4, AC5).
 */
@Component({
  selector: "app-tenant-management",
  standalone: true,
  imports: [
    DatePipe,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatTableModule,
    ReactiveFormsModule,
    RouterLink,
  ],
  templateUrl: "./tenant-management.component.html",
  styleUrls: ["./tenant-management.component.scss"],
})
export class TenantManagementComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly destroyRef = inject(DestroyRef);

  readonly displayedColumns = [
    "name",
    "plan",
    "userCount",
    "storage",
    "projectCount",
    "status",
    "createdAt",
  ];
  readonly pageSize = PAGE_SIZE;

  readonly tenants = this.adminService.tenantsSignal;
  readonly total = this.adminService.tenantsTotalSignal;
  readonly selectedTenant = this.adminService.selectedTenantSignal;
  readonly projects = this.adminService.tenantProjectsSignal;
  readonly isLoading = this.adminService.isLoadingSignal;
  readonly errorMessage = this.adminService.errorSignal;
  readonly pageIndex = signal(0);

  readonly searchControl = new FormControl("", { nonNullable: true });

  ngOnInit(): void {
    this.load();
  }

  applySearch(): void {
    this.pageIndex.set(0);
    this.load();
  }

  onPageChange(event: Pick<PageEvent, "pageIndex" | "pageSize" | "length">): void {
    this.pageIndex.set(event.pageIndex);
    this.load(event.pageSize);
  }

  selectTenant(tenantId: string): void {
    this.subscribe(this.adminService.getTenantDetails(tenantId));
    this.subscribe(this.adminService.getTenantProjects(tenantId));
  }

  statusLabel(tenant: AdminTenant): string {
    return tenant.isActive ? "Aktywny" : "Nieaktywny";
  }

  /** Zamienia bajty na najbliższą jednostkę binarną — kolumna "storage usage". */
  formatStorage(bytes: number): string {
    let value = Math.max(bytes, 0);
    let unit = 0;
    while (value >= 1024 && unit < UNITS.length - 1) {
      value /= 1024;
      unit += 1;
    }
    const rounded = Math.round(value * 10) / 10;
    return `${rounded} ${UNITS[unit]}`;
  }

  private load(pageSize = this.pageSize): void {
    this.subscribe(
      this.adminService.getTenants({
        page: this.pageIndex() + 1,
        pageSize,
        search: this.searchControl.value.trim(),
      }),
    );
  }

  private subscribe(request: Observable<unknown>): void {
    request
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ error: () => undefined });
  }
}
