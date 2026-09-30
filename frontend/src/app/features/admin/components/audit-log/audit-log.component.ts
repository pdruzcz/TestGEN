import { DatePipe } from "@angular/common";
import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { provideNativeDateAdapter } from "@angular/material/core";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { Observable } from "rxjs";

import { AdminService } from "../../services/admin.service";

const PAGE_SIZE = 50;

/**
 * Log audytu z filtrami po dacie, użytkowniku i typie akcji
 * (Story 6.15, AC6).
 */
@Component({
  selector: "app-audit-log",
  standalone: true,
  providers: [provideNativeDateAdapter()],
  imports: [
    DatePipe,
    MatButtonModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTableModule,
    ReactiveFormsModule,
  ],
  templateUrl: "./audit-log.component.html",
  styleUrls: ["./audit-log.component.scss"],
})
export class AuditLogComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  readonly displayedColumns = [
    "createdAt",
    "userId",
    "action",
    "resource",
    "details",
    "ipAddress",
  ];
  readonly pageSize = PAGE_SIZE;

  readonly logs = this.adminService.auditLogSignal;
  readonly total = this.adminService.auditLogTotalSignal;
  readonly actions = this.adminService.auditActionsSignal;
  readonly isLoading = this.adminService.isLoadingSignal;
  readonly errorMessage = this.adminService.errorSignal;
  readonly pageIndex = signal(0);

  readonly filters = this.fb.nonNullable.group({
    dateFrom: [null as Date | null],
    dateTo: [null as Date | null],
    userId: [""],
    action: [""],
  });

  ngOnInit(): void {
    this.load();
    this.subscribe(this.adminService.getAuditActions());
  }

  applyFilters(): void {
    this.pageIndex.set(0);
    this.load();
  }

  clearFilters(): void {
    this.filters.reset({ dateFrom: null, dateTo: null, userId: "", action: "" });
    this.applyFilters();
  }

  onPageChange(event: Pick<PageEvent, "pageIndex" | "pageSize" | "length">): void {
    this.pageIndex.set(event.pageIndex);
    this.load(event.pageSize);
  }

  /** Szczegóły zdarzenia to dowolny JSON — pokazujemy je w formie tekstowej. */
  formatDetails(details: Record<string, unknown> | null): string {
    if (!details || Object.keys(details).length === 0) return "—";
    return JSON.stringify(details);
  }

  private load(pageSize = this.pageSize): void {
    const { dateFrom, dateTo, userId, action } = this.filters.getRawValue();
    this.subscribe(
      this.adminService.getAuditLog({
        page: this.pageIndex() + 1,
        pageSize,
        dateFrom: dateFrom ? dateFrom.toISOString() : undefined,
        dateTo: dateTo ? dateTo.toISOString() : undefined,
        userId: userId.trim(),
        action,
      }),
    );
  }

  private subscribe(request: Observable<unknown>): void {
    request
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ error: () => undefined });
  }
}
