import {
  Component,
  inject,
  signal,
  computed,
  OnInit,
  DestroyRef,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatTableModule } from "@angular/material/table";
import { MatSelectModule } from "@angular/material/select";
import { MatMenuModule } from "@angular/material/menu";
import { MatCardModule } from "@angular/material/card";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import {
  TraceabilityService,
  TraceabilityEntry,
  TraceabilitySummary,
  CoverageStatus,
  SourceType,
  ExportFormat,
} from "../../services/traceability.service";

/**
 * Story 3.15: Traceability matrix view. Shows, per project, every UML/GUI
 * source element linked to its reconstructed user flow + generated Gherkin
 * "test" and a coverage status, with summary cards, source/coverage filters,
 * pagination, an async rebuild trigger and multi-format export.
 */
@Component({
  selector: "app-traceability-matrix",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatSelectModule,
    MatMenuModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatPaginatorModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./traceability-matrix.component.html",
  styleUrls: ["./traceability-matrix.component.scss"],
})
export class TraceabilityMatrixComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly traceabilityService = inject(TraceabilityService);

  readonly projectId = signal("");
  readonly elements = signal<TraceabilityEntry[]>([]);
  readonly summary = signal<TraceabilitySummary | null>(null);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(20);

  readonly sourceTypeFilter = signal<SourceType | "">("");
  readonly coverageFilter = signal<CoverageStatus | "">("");

  readonly isLoading = signal(false);
  readonly isBuilding = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly displayedColumns = [
    "sourceType",
    "sourceElementType",
    "sourceElementName",
    "linkedGherkinId",
    "codeReference",
    "coverageStatus",
  ];

  readonly pageIndex = computed(() => this.page() - 1);

  get sourceTypeFilterValue(): SourceType | "" {
    return this.sourceTypeFilter();
  }
  set sourceTypeFilterValue(value: SourceType | "") {
    this.sourceTypeFilter.set(value);
  }

  get coverageFilterValue(): CoverageStatus | "" {
    return this.coverageFilter();
  }
  set coverageFilterValue(value: CoverageStatus | "") {
    this.coverageFilter.set(value);
  }

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get("projectId") ?? "";
    this.projectId.set(projectId);
    this.load();
  }

  load(): void {
    if (!this.projectId()) {
      return;
    }
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.traceabilityService
      .getMatrix(this.projectId(), {
        sourceType: this.sourceTypeFilter() || undefined,
        coverageStatus: this.coverageFilter() || undefined,
        page: this.page(),
        pageSize: this.pageSize(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (matrix) => {
          this.elements.set(matrix.elements);
          this.summary.set(matrix.summary);
          this.total.set(matrix.total);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się pobrać macierzy śledzenia.");
          this.isLoading.set(false);
        },
      });
  }

  onFilterChange(): void {
    this.page.set(1);
    this.load();
  }

  onPageChange(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
    this.load();
  }

  rebuild(): void {
    if (!this.projectId() || this.isBuilding()) {
      return;
    }
    this.isBuilding.set(true);
    this.errorMessage.set(null);
    this.traceabilityService
      .build(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isBuilding.set(false);
          this.load();
        },
        error: () => {
          this.errorMessage.set("Nie udało się uruchomić przebudowy macierzy.");
          this.isBuilding.set(false);
        },
      });
  }

  exportAs(format: ExportFormat): void {
    if (!this.projectId()) {
      return;
    }
    this.traceabilityService
      .export(this.projectId(), format)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => this.downloadBlob(blob, `traceability.${format}`),
        error: () =>
          this.errorMessage.set(
            "Eksport nie powiódł się (format może wymagać niedostępnej biblioteki).",
          ),
      });
  }

  private downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  coverageLabel(status: CoverageStatus): string {
    switch (status) {
      case "covered":
        return "Pokryty";
      case "partial":
        return "Częściowo";
      default:
        return "Niepokryty";
    }
  }
}
