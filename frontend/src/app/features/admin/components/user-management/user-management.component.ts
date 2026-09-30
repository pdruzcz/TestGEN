import { DatePipe } from "@angular/common";
import { Component, DestroyRef, OnInit, computed, inject, signal } from "@angular/core";
import { takeUntilDestroyed, toSignal } from "@angular/core/rxjs-interop";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatDialog } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import { MatSortModule, Sort } from "@angular/material/sort";
import { MatTableModule } from "@angular/material/table";
import { Observable } from "rxjs";

import { AdminService, AdminUser } from "../../services/admin.service";
import {
  USER_ROLES,
  UserDialogComponent,
  UserDialogData,
  UserDialogResult,
} from "../user-dialog/user-dialog.component";

const PAGE_SIZE = 25;

/**
 * Lista użytkowników platformy (Story 6.15, AC1, AC2, AC3).
 *
 * Paginacja jest serwerowa, natomiast filtrowanie i sortowanie działają na
 * bieżącej stronie — backend nie udostępnia sortowania po tych kolumnach.
 */
@Component({
  selector: "app-user-management",
  standalone: true,
  imports: [
    DatePipe,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSortModule,
    MatTableModule,
    ReactiveFormsModule,
  ],
  templateUrl: "./user-management.component.html",
  styleUrls: ["./user-management.component.scss"],
})
export class UserManagementComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);

  readonly displayedColumns = [
    "email",
    "name",
    "role",
    "tenant",
    "status",
    "createdAt",
    "lastLoginAt",
    "actions",
  ];
  readonly roles = USER_ROLES;
  readonly pageSize = PAGE_SIZE;

  readonly users = this.adminService.usersSignal;
  readonly total = this.adminService.usersTotalSignal;
  readonly tenants = this.adminService.tenantsSignal;
  readonly isLoading = this.adminService.isLoadingSignal;
  readonly errorMessage = this.adminService.errorSignal;
  readonly pageIndex = signal(0);

  readonly searchControl = new FormControl("", { nonNullable: true });
  readonly roleControl = new FormControl("", { nonNullable: true });
  readonly statusControl = new FormControl("", { nonNullable: true });
  private readonly sort = signal<Sort>({ active: "", direction: "" });

  private readonly search = toSignal(this.searchControl.valueChanges, {
    initialValue: "",
  });
  private readonly role = toSignal(this.roleControl.valueChanges, {
    initialValue: "",
  });
  private readonly status = toSignal(this.statusControl.valueChanges, {
    initialValue: "",
  });

  readonly filteredUsers = computed(() => {
    const search = this.search().trim().toLowerCase();
    const role = this.role();
    const status = this.status();

    const rows = this.users().filter((user) => {
      if (search && !`${user.email} ${user.name ?? ""}`.toLowerCase().includes(search)) {
        return false;
      }
      if (role && user.role !== role) {
        return false;
      }
      if (status && this.statusKey(user) !== status) {
        return false;
      }
      return true;
    });

    return this.sorted(rows);
  });

  ngOnInit(): void {
    this.loadUsers();
    // Nazwy tenantów zasilają kolumnę "tenant" oraz filtr cross-tenant.
    this.subscribe(this.adminService.getTenants({ pageSize: 100 }));
  }

  loadUsers(): void {
    this.subscribe(
      this.adminService.getUsers({
        page: this.pageIndex() + 1,
        pageSize: this.pageSize,
      }),
    );
  }

  onPageChange(event: Pick<PageEvent, "pageIndex" | "pageSize" | "length">): void {
    this.pageIndex.set(event.pageIndex);
    this.subscribe(
      this.adminService.getUsers({
        page: event.pageIndex + 1,
        pageSize: event.pageSize,
      }),
    );
  }

  onSortChange(sort: Sort): void {
    this.sort.set(sort);
  }

  openCreateDialog(): void {
    this.openDialog({ mode: "create" });
  }

  openEditDialog(user: AdminUser): void {
    this.openDialog({ mode: "edit", user });
  }

  statusLabel(user: AdminUser): string {
    if (user.isBlocked) return "Zablokowany";
    return user.isActive ? "Aktywny" : "Nieaktywny";
  }

  roleLabel(role: string): string {
    return this.roles.find((item) => item.value === role)?.label ?? role;
  }

  tenantLabel(tenantId: string | null): string {
    if (!tenantId) return "—";
    return this.tenants().find((tenant) => tenant.id === tenantId)?.name ?? tenantId;
  }

  private openDialog(data: UserDialogData): void {
    this.dialog
      .open(UserDialogComponent, { data, width: "480px" })
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((result?: UserDialogResult) => {
        if (result) this.applyDialogResult(result);
      });
  }

  private applyDialogResult(result: UserDialogResult): void {
    switch (result.action) {
      case "invite":
        // Zaproszenie tworzy konto poza bieżącą stroną — przeładowujemy listę.
        this.adminService
          .createUser({ email: result.email, role: result.role })
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({ next: () => this.loadUsers(), error: () => undefined });
        break;
      case "update-role":
        this.subscribe(
          this.adminService.updateUserRole(result.userId, result.role),
        );
        break;
      case "block":
        this.subscribe(this.adminService.blockUser(result.userId));
        break;
      case "unblock":
        this.subscribe(this.adminService.unblockUser(result.userId));
        break;
      case "delete":
        this.subscribe(this.adminService.deleteUser(result.userId));
        break;
    }
  }

  private statusKey(user: AdminUser): string {
    if (user.isBlocked) return "blocked";
    return user.isActive ? "active" : "inactive";
  }

  private sorted(rows: AdminUser[]): AdminUser[] {
    const { active, direction } = this.sort();
    if (!active || !direction) return rows;

    const factor = direction === "asc" ? 1 : -1;
    return [...rows].sort((left, right) => {
      const a = String(left[active as keyof AdminUser] ?? "");
      const b = String(right[active as keyof AdminUser] ?? "");
      return a.localeCompare(b) * factor;
    });
  }

  private subscribe(request: Observable<unknown>): void {
    request
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ error: () => undefined });
  }
}
