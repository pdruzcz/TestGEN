import {
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from "@angular/core";
import { DatePipe } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
import { MatIconModule } from "@angular/material/icon";
import {
  MatPaginatorIntl,
  MatPaginatorModule,
  PageEvent,
} from "@angular/material/paginator";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { polishPaginatorIntl } from "../../../shared/i18n/polish-paginator-intl";
import { TestCaseService } from "../services/test-case.service";
import {
  TestCase,
  TestCaseStatus,
  TestCaseUpdatePayload,
  TestPriority,
} from "../models/test-case.model";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  TYPE_LABELS,
} from "../models/test-case-labels";
import {
  EMPTY_TC_FILTERS,
  FilterGroupPanelComponent,
  TestCaseFilters,
  TestCaseGroupBy,
} from "../components/filter-group-panel/filter-group-panel.component";
import { BulkActionsBarComponent } from "../components/bulk-actions-bar/bulk-actions-bar.component";
import { LocatorBadgeComponent } from "../components/locator-badge/locator-badge.component";
import { TestCaseEditorComponent } from "../components/test-case-editor/test-case-editor.component";
import {
  HistoryDialogComponent,
  HistoryDialogData,
} from "../components/history-dialog/history-dialog.component";
import {
  TmsExportDialogComponent,
  TmsExportDialogData,
} from "../components/tms-export-dialog/tms-export-dialog.component";
import {
  IntegrationService,
  JiraPlugin,
} from "../../../core/services/integration.service";

interface TestCaseGroup {
  key: string;
  label: string;
  items: TestCase[];
}

type SortField =
  | "title"
  | "priority"
  | "type"
  | "status"
  | "source_class"
  | "updated_at";

/**
 * Story 6.5 — kompletny widok zarządzania test case'ami:
 * AC1 tabela, AC2 filtry multi-select, AC3 grupowanie, AC4 edytor inline,
 * AC5 akcje zbiorcze, AC6 drag-drop kroków, AC7 historia, AC8 klawiatura.
 */
@Component({
  selector: "app-test-cases-management",
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    MatButtonModule,
    MatCheckboxModule,
    MatDialogModule,
    MatIconModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    NavbarComponent,
    FooterComponent,
    FilterGroupPanelComponent,
    BulkActionsBarComponent,
    LocatorBadgeComponent,
    TestCaseEditorComponent,
  ],
  providers: [{ provide: MatPaginatorIntl, useFactory: polishPaginatorIntl }],
  templateUrl: "./test-cases-management.component.html",
  styleUrls: ["./test-cases-management.component.scss"],
})
export class TestCasesManagementComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(TestCaseService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly tableRef = viewChild<ElementRef<HTMLElement>>("tableEl");

  readonly priorityLabels = PRIORITY_LABELS;
  readonly typeLabels = TYPE_LABELS;
  readonly statusLabels = STATUS_LABELS;

  readonly testCases = this.service.testCasesSignal;
  readonly total = this.service.totalSignal;
  readonly statusCounts = this.service.statusCountsSignal;
  readonly isLoading = this.service.isLoadingSignal;

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly page = signal(1);
  readonly pageSize = signal(50);
  readonly sortBy = signal<SortField>("updated_at");
  readonly sortOrder = signal<"asc" | "desc">("desc");

  readonly filters = signal<TestCaseFilters>({ ...EMPTY_TC_FILTERS });
  readonly groupBy = signal<TestCaseGroupBy>("none");
  readonly collapsedGroups = signal<Set<string>>(new Set());

  readonly selectedIds = signal<Set<string>>(new Set());
  readonly editingId = signal<string | null>(null);

  /** AC2 — filtry multi-select stosowane klientowo na załadowanej stronie. */
  readonly filteredTestCases = computed<TestCase[]>(() => {
    const f = this.filters();
    return this.testCases().filter((tc) => {
      if (f.priorities.length > 0 && !f.priorities.includes(tc.priority)) {
        return false;
      }
      if (f.types.length > 0 && !f.types.includes(tc.type)) return false;
      if (f.statuses.length > 0 && !f.statuses.includes(tc.status)) {
        return false;
      }
      if (f.modules.length > 0 && !f.modules.includes(this.moduleOf(tc))) {
        return false;
      }
      return true;
    });
  });

  readonly availableModules = computed<string[]>(() => {
    const set = new Set<string>();
    for (const tc of this.testCases()) set.add(this.moduleOf(tc));
    return [...set].sort((a, b) => a.localeCompare(b, "pl"));
  });

  /** AC3 — grupowanie wg modułu / priorytetu / typu. */
  readonly groups = computed<TestCaseGroup[]>(() => {
    const mode = this.groupBy();
    const items = this.filteredTestCases();
    if (mode === "none") {
      return [{ key: "__all__", label: "", items }];
    }
    const map = new Map<string, TestCase[]>();
    for (const tc of items) {
      const key =
        mode === "module"
          ? this.moduleOf(tc)
          : mode === "priority"
            ? tc.priority
            : tc.type;
      const bucket = map.get(key);
      if (bucket) bucket.push(tc);
      else map.set(key, [tc]);
    }
    return [...map.entries()].map(([key, groupItems]) => ({
      key,
      label:
        mode === "priority"
          ? PRIORITY_LABELS[key as TestPriority]
          : mode === "type"
            ? TYPE_LABELS[key as TestCase["type"]]
            : key,
      items: groupItems,
    }));
  });

  readonly selectedCount = computed(() => this.selectedIds().size);

  readonly allVisibleSelected = computed(() => {
    const visible = this.filteredTestCases();
    if (visible.length === 0) return false;
    const selected = this.selectedIds();
    return visible.every((tc) => selected.has(tc.id));
  });

  readonly someVisibleSelected = computed(() => {
    const selected = this.selectedIds();
    return (
      !this.allVisibleSelected() &&
      this.filteredTestCases().some((tc) => selected.has(tc.id))
    );
  });

  ngOnInit(): void {
    this.loadTestCases();
  }

  moduleOf(tc: TestCase): string {
    return tc.sourceClass || tc.sourceFunction || "(brak modułu)";
  }

  shortId(id: string): string {
    return id.slice(0, 8);
  }

  /**
   * Opis plakietki powiązania z TMS (Story 8.11, AC5).
   *
   * Data ostatniej synchronizacji siedzi w tooltipie, a nie w komórce: sam
   * identyfikator mówi „ten test żyje też tam", a kolumna z kolejną datą
   * rozpychałaby i tak szeroką tabelę.
   */
  tmsSyncTitle(tc: TestCase): string {
    if (!tc.tmsExternalId) {
      return "";
    }
    const when = tc.tmsSyncedAt
      ? new Date(tc.tmsSyncedAt).toLocaleString("pl-PL")
      : "nieznana data";
    return `Zsynchronizowany z TMS #${tc.tmsExternalId}, ostatnia synchronizacja: ${when}`;
  }

  // --- ładowanie / sortowanie / paginacja -------------------------------

  loadTestCases(): void {
    this.service
      .list({
        projectId: this.projectId() || null,
        page: this.page(),
        pageSize: this.pageSize(),
        sortBy: this.sortBy(),
        sortOrder: this.sortOrder(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe();
  }

  onSort(field: SortField): void {
    if (this.sortBy() === field) {
      this.sortOrder.update((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      this.sortBy.set(field);
      this.sortOrder.set("asc");
    }
    this.loadTestCases();
  }

  ariaSort(field: SortField): "ascending" | "descending" | "none" {
    if (this.sortBy() !== field) return "none";
    return this.sortOrder() === "asc" ? "ascending" : "descending";
  }

  onPageChange(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
    this.selectedIds.set(new Set());
    this.loadTestCases();
  }

  onFiltersChange(filters: TestCaseFilters): void {
    this.filters.set(filters);
  }

  onGroupByChange(groupBy: TestCaseGroupBy): void {
    this.groupBy.set(groupBy);
    this.collapsedGroups.set(new Set());
  }

  toggleGroup(key: string): void {
    this.collapsedGroups.update((set) => {
      const next = new Set(set);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  isGroupCollapsed(key: string): boolean {
    return this.collapsedGroups().has(key);
  }

  // --- zaznaczanie (AC5) -------------------------------------------------

  isSelected(id: string): boolean {
    return this.selectedIds().has(id);
  }

  toggleSelection(id: string): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  toggleSelectAll(): void {
    if (this.allVisibleSelected()) {
      this.selectedIds.set(new Set());
    } else {
      this.selectedIds.set(
        new Set(this.filteredTestCases().map((tc) => tc.id)),
      );
    }
  }

  clearSelection(): void {
    this.selectedIds.set(new Set());
  }

  // --- akcje zbiorcze (AC5) ----------------------------------------------

  bulkChangeStatus(status: TestCaseStatus): void {
    const ids = [...this.selectedIds()];
    this.service
      .bulkUpdate({ ids, status })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.snackBar.open(
            `Zmieniono status ${resp.affected} przypadków`,
            "OK",
            { duration: 3000 },
          );
          this.clearSelection();
          this.loadTestCases();
        },
        error: () =>
          this.snackBar.open("Nie udało się zmienić statusu", "OK", {
            duration: 4000,
          }),
      });
  }

  bulkChangePriority(priority: TestPriority): void {
    const ids = [...this.selectedIds()];
    this.service
      .bulkUpdate({ ids, priority })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.snackBar.open(
            `Zmieniono priorytet ${resp.affected} przypadków`,
            "OK",
            { duration: 3000 },
          );
          this.clearSelection();
          this.loadTestCases();
        },
        error: () =>
          this.snackBar.open("Nie udało się zmienić priorytetu", "OK", {
            duration: 4000,
          }),
      });
  }

  bulkDelete(): void {
    const ids = [...this.selectedIds()];
    const confirmed = window.confirm(
      `Czy na pewno usunąć ${ids.length} przypadków testowych?`,
    );
    if (!confirmed) return;
    this.service
      .bulkDelete(ids)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.snackBar.open(`Usunięto ${resp.affected} przypadków`, "OK", {
            duration: 3000,
          });
          this.clearSelection();
          if (this.testCases().length === ids.length && this.page() > 1) {
            this.page.update((p) => p - 1);
          }
          this.loadTestCases();
        },
        error: () =>
          this.snackBar.open("Nie udało się usunąć przypadków", "OK", {
            duration: 4000,
          }),
      });
  }

  // ── Story 8.8: eksport do TestRail ──────────────────────────────────────

  private readonly integrationService = inject(IntegrationService);

  readonly isTestRailDialogOpen = signal(false);
  readonly isExportingToTestRail = signal(false);
  readonly testRailTaskId = signal<string | null>(null);
  readonly testRailError = signal<string | null>(null);

  // Story 8.9: ten sam dialog obsługuje Jirę; cel trzymamy w sygnale,
  // bo różni je tylko wywoływany endpoint i treść komunikatu o konfiguracji.
  readonly exportTarget = signal<"testrail" | JiraPlugin>("testrail");

  /** Podsumowanie w dialogu: zaznaczone albo wszystkie przypadki projektu. */
  testRailSummary(): string {
    const selected = this.selectedIds().size;
    return selected > 0
      ? `Do eksportu: ${selected} zaznaczonych przypadków.`
      : "Nie zaznaczono żadnego przypadku — wyeksportowane zostaną wszystkie przypadki projektu.";
  }

  openTestRailExport(): void {
    this.openExternalExport("testrail");
  }

  /**
   * Otwiera dialog eksportu przez API do wskazanego systemu (Stories 8.8/8.9).
   *
   * Nie mylić z `openTmsExport()` ze Story 6.8 — tamten generuje plik do
   * ręcznego zaimportowania, ten wysyła testy wprost do systemu.
   */
  openExternalExport(target: "testrail" | JiraPlugin): void {
    this.exportTarget.set(target);
    this.testRailTaskId.set(null);
    this.testRailError.set(null);
    this.isTestRailDialogOpen.set(true);
  }

  exportTargetLabel(): string {
    switch (this.exportTarget()) {
      case "xray":
        return "Jira Xray";
      case "zephyr":
        return "Zephyr Scale";
      default:
        return "TestRail";
    }
  }

  closeTestRailExport(): void {
    this.isTestRailDialogOpen.set(false);
  }

  confirmTestRailExport(): void {
    if (this.isExportingToTestRail()) {
      return;
    }
    this.isExportingToTestRail.set(true);
    this.testRailError.set(null);

    const target = this.exportTarget();
    const request$ =
      target === "testrail"
        ? this.integrationService.exportToTestRail(this.projectId(), [
            ...this.selectedIds(),
          ])
        : this.integrationService.exportToJiraTms(this.projectId(), target, [
            ...this.selectedIds(),
          ]);

    request$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.isExportingToTestRail.set(false);
          this.testRailTaskId.set(result.taskId);
        },
        error: (err: { status?: number; error?: { detail?: string } }) => {
          this.isExportingToTestRail.set(false);
          // 404 oznacza brak konfiguracji — kierujemy użytkownika tam, gdzie ją uzupełni.
          this.testRailError.set(
            err?.status === 404
              ? `Integracja z ${this.exportTargetLabel()} nie jest skonfigurowana dla tego projektu. Uzupełnij ją w ustawieniach projektu.`
              : (err?.error?.detail ?? "Nie udało się uruchomić eksportu."),
          );
        },
      });
  }

  /** AC5 — eksport zaznaczonych do CSV (klientowo). */
  exportSelected(): void {
    const selected = this.selectedIds();
    const rows = this.testCases().filter((tc) => selected.has(tc.id));
    if (rows.length === 0) return;

    const esc = (v: string | null | undefined): string =>
      `"${String(v ?? "").replace(/"/g, '""')}"`;
    const header =
      "id;tytul;priorytet;typ;modul;status;przypisany;data_modyfikacji";
    const lines = rows.map((tc) =>
      [
        esc(tc.id),
        esc(tc.title),
        esc(PRIORITY_LABELS[tc.priority]),
        esc(TYPE_LABELS[tc.type]),
        esc(this.moduleOf(tc)),
        esc(STATUS_LABELS[tc.status]),
        esc(tc.reviewedBy),
        esc(tc.updatedAt),
      ].join(";"),
    );
    const csv = [header, ...lines].join("\r\n");
    const blob = new Blob([`\uFEFF${csv}`], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `test-cases-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  // --- edytor inline (AC4) -------------------------------------------------

  openEditor(id: string): void {
    this.editingId.set(id);
  }

  closeEditor(): void {
    this.editingId.set(null);
  }

  saveTestCase(id: string, payload: TestCaseUpdatePayload): void {
    this.service
      .update(id, payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.snackBar.open("Zapisano zmiany", "OK", { duration: 3000 });
          this.closeEditor();
          this.loadTestCases();
        },
        error: () =>
          this.snackBar.open("Nie udało się zapisać zmian", "OK", {
            duration: 4000,
          }),
      });
  }

  // --- eksport do TMS (Story 6.8) ------------------------------------------

  openTmsExport(): void {
    this.dialog.open<TmsExportDialogComponent, TmsExportDialogData>(
      TmsExportDialogComponent,
      {
        data: {
          projectId: this.projectId(),
          totalCount: this.total(),
          filteredIds: this.filteredTestCases().map((tc) => tc.id),
          selectedIds: [...this.selectedIds()],
        },
        width: "560px",
        maxWidth: "95vw",
      },
    );
  }

  // --- historia (AC7) ------------------------------------------------------

  openHistory(tc: TestCase): void {
    this.dialog.open<HistoryDialogComponent, HistoryDialogData>(
      HistoryDialogComponent,
      {
        data: { testCaseId: tc.id, title: tc.title },
        width: "720px",
        maxWidth: "95vw",
      },
    );
  }

  // --- usuwanie pojedyncze ---------------------------------------------------

  deleteTestCase(tc: TestCase): void {
    const confirmed = window.confirm(
      `Czy na pewno usunąć przypadek "${tc.title}"?`,
    );
    if (!confirmed) return;
    this.service
      .delete(tc.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.snackBar.open("Usunięto przypadek testowy", "OK", {
            duration: 3000,
          });
          if (this.testCases().length === 1 && this.page() > 1) {
            this.page.update((p) => p - 1);
          }
          this.loadTestCases();
        },
      });
  }

  // --- nawigacja klawiaturą (AC8) --------------------------------------------

  onRowKeydown(event: KeyboardEvent, tc: TestCase): void {
    const key = event.key;
    if (key === "ArrowDown" || key === "ArrowUp") {
      event.preventDefault();
      const rows = this.getRowElements();
      const current = event.currentTarget as HTMLElement;
      const idx = rows.indexOf(current);
      const nextIdx = key === "ArrowDown" ? idx + 1 : idx - 1;
      if (nextIdx >= 0 && nextIdx < rows.length) {
        rows[nextIdx].focus();
      }
    } else if (key === " ") {
      event.preventDefault();
      this.toggleSelection(tc.id);
    } else if (key === "Enter") {
      event.preventDefault();
      this.openEditor(tc.id);
    } else if (key === "Escape" && this.editingId()) {
      this.closeEditor();
    }
  }

  private getRowElements(): HTMLElement[] {
    const table = this.tableRef()?.nativeElement;
    if (!table) return [];
    return Array.from(table.querySelectorAll<HTMLElement>("tr.tc-row"));
  }

  badgeClass(value: string): string {
    return `badge badge-${value.toLowerCase()}`;
  }
}
