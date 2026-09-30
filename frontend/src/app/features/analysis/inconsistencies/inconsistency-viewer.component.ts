import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatChipsModule } from "@angular/material/chips";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatExpansionModule } from "@angular/material/expansion";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  DocumentAnalysisService,
  Inconsistency,
  InconsistencySeverity,
  InconsistencyStatus,
  InconsistencyType,
} from "../../../services/document-analysis.service";

@Component({
  selector: "app-inconsistency-viewer",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatExpansionModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="view-page">
      <app-navbar activeLink="projects" />

      <main class="view-content" id="main-content" tabindex="-1">
        <!-- Header -->
        <div class="page-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId(), 'requirements']"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do wymagań
          </a>

          @if (documentTitle()) {
            <div class="header-info">
              <h1 class="page-title">
                <mat-icon aria-hidden="true">warning</mat-icon>
                Niespójności: {{ documentTitle() }}
              </h1>
              <div class="badge critical" *ngIf="criticalCount() > 0">
                {{ criticalCount() }} krytycznych
              </div>
              <div class="badge high" *ngIf="highCount() > 0">
                {{ highCount() }} wysokich
              </div>
              <div class="badge">{{ totalInconsistencies() }} wykrytych</div>
            </div>
          }

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
              <span>Ładowanie niespójności…</span>
            </div>
          }
        </div>

        <!-- Filters -->
        @if (!isLoading() && inconsistencies().length > 0) {
          <div class="filters">
            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>filter_list</mat-icon>
              <mat-label>Typ</mat-label>
              <mat-select [(value)]="selectedType">
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="contradiction">Sprzeczności</mat-option>
                <mat-option value="terminology">Terminologia</mat-option>
                <mat-option value="missing_reference"
                  >Brakujące referencje</mat-option
                >
                <mat-option value="duplicate">Duplikaty</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>priority_high</mat-icon>
              <mat-label>Ważność</mat-label>
              <mat-select [(value)]="selectedSeverity">
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="critical">Krytyczne</mat-option>
                <mat-option value="high">Wysokie</mat-option>
                <mat-option value="medium">Średnie</mat-option>
                <mat-option value="low">Niskie</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>label</mat-icon>
              <mat-label>Status</mat-label>
              <mat-select [(value)]="selectedStatus">
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="open">Otwarte</mat-option>
                <mat-option value="accepted">Zaakceptowane</mat-option>
                <mat-option value="false_positive">False positive</mat-option>
                <mat-option value="fixed">Naprawione</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="search-field">
              <mat-icon matPrefix>search</mat-icon>
              <input
                matInput
                placeholder="Szukaj niespójności…"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </mat-form-field>

            <div class="stats">
              <span class="stat">
                <mat-icon aria-hidden="true">error_outline</mat-icon>
                Otwarte: {{ openCount() }}
              </span>
              <span class="stat">
                <mat-icon aria-hidden="true">check_circle</mat-icon>
                Zaakceptowane: {{ acceptedCount() }}
              </span>
              <span class="stat">
                <mat-icon aria-hidden="true">build</mat-icon>
                Naprawione: {{ fixedCount() }}
              </span>
            </div>
          </div>
        }

        <!-- Inconsistencies List -->
        @if (!isLoading()) {
          @if (filteredInconsistencies().length > 0) {
            <mat-accordion class="inconsistencies-list">
              @for (
                inc of filteredInconsistencies();
                track inc.inconsistencyId
              ) {
                <mat-expansion-panel
                  [class]="'severity-' + inc.severity"
                  [class.status-resolved]="isResolved(inc.status)"
                >
                  <mat-expansion-panel-header>
                    <mat-panel-title>
                      <div class="panel-header">
                        <div class="header-left">
                          <mat-icon [class]="'type-icon ' + inc.type">
                            {{ getTypeIcon(inc.type) }}
                          </mat-icon>
                          <span class="inc-id">{{ inc.inconsistencyId }}</span>
                          @if (isProjectView() && inc.documentFilename) {
                            <span class="doc-badge" title="Dokument źródłowy">{{
                              inc.documentFilename
                            }}</span>
                          }
                          <mat-chip [color]="getSeverityColor(inc.severity)">
                            {{ getSeverityLabel(inc.severity) }}
                          </mat-chip>
                          <mat-chip [class]="'status-chip ' + inc.status">
                            {{ getStatusLabel(inc.status) }}
                          </mat-chip>
                        </div>
                      </div>
                    </mat-panel-title>
                  </mat-expansion-panel-header>

                  <div class="panel-content">
                    <p class="description">{{ inc.description }}</p>

                    @if (inc.affectedRequirements?.length) {
                      <div class="affected-reqs">
                        <mat-icon aria-hidden="true">link</mat-icon>
                        <strong>Dotyczy wymagań:</strong>
                        <div class="req-links">
                          @for (
                            reqId of inc.affectedRequirements ?? [];
                            track reqId
                          ) {
                            <a
                              mat-button
                              class="req-link"
                              [routerLink]="[
                                '/projects',
                                projectId(),
                                'requirements',
                              ]"
                              [queryParams]="{ highlight: reqId }"
                            >
                              {{ reqId }}
                            </a>
                          }
                        </div>
                      </div>
                    }

                    @if (inc.suggestion) {
                      <div class="suggestion">
                        <mat-icon aria-hidden="true">lightbulb</mat-icon>
                        <strong>Sugestia:</strong>
                        <span>{{ inc.suggestion }}</span>
                      </div>
                    }

                    @if (inc.sourceSectionId) {
                      <div class="source-section">
                        <mat-icon aria-hidden="true">location_on</mat-icon>
                        <span>Sekcja: {{ inc.sourceSectionId }}</span>
                      </div>
                    }

                    <!-- AC4: workflow status change → PUT -->
                    <div class="actions">
                      <span class="actions-label">Zmień status:</span>
                      @for (opt of statusOptions; track opt.value) {
                        <button
                          mat-button
                          [color]="inc.status === opt.value ? 'primary' : ''"
                          [disabled]="
                            inc.status === opt.value ||
                            updatingId() === inc.inconsistencyId
                          "
                          (click)="changeStatus(inc, opt.value)"
                          [title]="opt.label"
                        >
                          <mat-icon aria-hidden="true">{{
                            getStatusIcon(opt.value)
                          }}</mat-icon>
                          {{ opt.label }}
                        </button>
                      }
                      @if (updatingId() === inc.inconsistencyId) {
                        <mat-spinner
                          diameter="18"
                          class="updating-spinner"
                          aria-label="Ładowanie"
                        ></mat-spinner>
                      }
                    </div>
                  </div>
                </mat-expansion-panel>
              }
            </mat-accordion>
          } @else if (inconsistencies().length === 0) {
            <div class="empty-state success">
              <mat-icon aria-hidden="true">check_circle</mat-icon>
              <p>Nie wykryto żadnych niespójności w dokumencie.</p>
              <p class="hint">
                Dokument wydaje się spójny i poprawnie ustrukturyzowany.
              </p>
              <button
                mat-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'requirements']"
              >
                Wróć do wymagań
              </button>
            </div>
          } @else {
            <div class="empty-state">
              <mat-icon aria-hidden="true">search_off</mat-icon>
              <p>Brak niespójności spełniających kryteria filtru.</p>
              <button mat-button (click)="clearFilters()">
                Wyczyść filtry
              </button>
            </div>
          }
        }
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .doc-badge {
        font-size: 11px;
        color: #4b5563;
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 1px 6px;
        margin-left: 6px;
      }
      .view-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .view-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1200px;
        width: 100%;
        margin: 0 auto;
      }

      .page-header {
        margin-bottom: 24px;
      }

      .back-link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 16px;
      }

      .header-info {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }

      .page-title {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }

      .page-title mat-icon {
        font-size: 32px;
        height: 32px;
        width: 32px;
        color: #f59e0b;
      }

      .badge {
        padding: 6px 14px;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
      }

      .badge.critical {
        background: #fef2f2;
        color: #991b1b;
      }

      .badge.high {
        background: #ffedd5;
        color: #9a3412;
      }

      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
      }

      .filters {
        display: flex;
        gap: 16px;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
      }

      .filter-field {
        width: 200px;
      }

      .search-field {
        flex: 1;
        min-width: 250px;
      }

      .stats {
        display: flex;
        gap: 20px;
        margin-left: auto;
      }

      .stat {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
      }

      .stat mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      .inconsistencies-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      mat-expansion-panel {
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      mat-expansion-panel.severity-critical {
        border-left: 4px solid #ef4444;
      }

      mat-expansion-panel.severity-high {
        border-left: 4px solid #f97316;
      }

      mat-expansion-panel.severity-medium {
        border-left: 4px solid #fbbf24;
      }

      mat-expansion-panel.severity-low {
        border-left: 4px solid #d1d5db;
      }

      mat-expansion-panel.status-resolved {
        opacity: 0.75;
      }

      .panel-header {
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
      }

      .type-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      .type-icon.contradiction {
        color: #ef4444;
      }

      .type-icon.terminology {
        color: #f59e0b;
      }

      .type-icon.missing_reference {
        color: #8b5cf6;
      }

      .type-icon.duplicate {
        color: #ec4899;
      }

      .inc-id {
        font-weight: 600;
        color: #374151;
      }

      .status-chip {
        min-height: 24px;
        font-size: 12px;
        font-weight: 500;
        background: #f3f4f6;
        color: #4b5563;
      }

      .status-chip.open {
        background: #fff8e1;
        color: #b26a00;
      }

      .status-chip.accepted {
        background: #ede7f6;
        color: #4527a0;
      }

      .status-chip.false_positive {
        background: #eceff1;
        color: #455a64;
      }

      .status-chip.fixed {
        background: #e8f5e9;
        color: #1b5e20;
      }

      .panel-content {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .description {
        margin: 0;
        color: #374151;
        line-height: 1.6;
      }

      .affected-reqs {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 12px;
        background: #fef3c7;
        border-radius: 8px;
      }

      .affected-reqs mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: #92400e;
        flex-shrink: 0;
        margin-top: 2px;
      }

      .req-links {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .req-link {
        padding: 4px 10px;
        background: #ffffff;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
      }

      .suggestion {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 12px;
        background: #dbeafe;
        border-radius: 8px;
      }

      .suggestion mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: #1e40af;
        flex-shrink: 0;
        margin-top: 2px;
      }

      .suggestion span {
        flex: 1;
      }

      .source-section {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
      }

      .actions {
        display: flex;
        align-items: center;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid #e5e7eb;
        flex-wrap: wrap;
      }

      .actions-label {
        font-size: 13px;
        color: #5a6270;
        font-weight: 500;
        margin-right: 4px;
      }

      .updating-spinner {
        margin-left: 4px;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 64px 32px;
        text-align: center;
        color: #6b7280;
      }

      .empty-state.success {
        color: #059669;
      }

      .empty-state.success mat-icon {
        color: #10b981;
      }

      .empty-state mat-icon {
        font-size: 64px;
        height: 64px;
        width: 64px;
        color: #d1d5db;
      }

      .hint {
        color: #9ca3af;
        font-size: 14px;
      }

      @media (max-width: 768px) {
        .view-content {
          padding: 16px;
        }

        .filters {
          flex-direction: column;
          align-items: stretch;
        }

        .filter-field,
        .search-field {
          width: 100%;
        }

        .stats {
          flex-wrap: wrap;
        }
      }
    `,
  ],
})
export class InconsistencyViewerComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly documentService = inject(DocumentAnalysisService);

  readonly inconsistencies = signal<Inconsistency[]>([]);
  readonly isLoading = signal(false);
  readonly documentTitle = signal("");
  readonly searchQuery = signal("");
  readonly selectedType = signal<"all" | InconsistencyType>("all");
  readonly selectedSeverity = signal<"all" | InconsistencySeverity>("all");
  readonly selectedStatus = signal<"all" | InconsistencyStatus>("all");
  readonly documentId = signal("");
  readonly updatingId = signal<string | null>(null);

  readonly statusOptions: { value: InconsistencyStatus; label: string }[] = [
    { value: "open", label: "Otwórz" },
    { value: "accepted", label: "Akceptuj" },
    { value: "false_positive", label: "False positive" },
    { value: "fixed", label: "Naprawione" },
  ];

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly documentIdFromQuery = computed(
    () => this.route.snapshot.queryParamMap.get("documentId") || "",
  );

  readonly filteredInconsistencies = computed(() => {
    let incs = this.inconsistencies();

    if (this.selectedType() !== "all") {
      incs = incs.filter((i) => i.type === this.selectedType());
    }

    if (this.selectedSeverity() !== "all") {
      incs = incs.filter((i) => i.severity === this.selectedSeverity());
    }

    if (this.selectedStatus() !== "all") {
      incs = incs.filter((i) => i.status === this.selectedStatus());
    }

    const query = this.searchQuery().toLowerCase().trim();
    if (query) {
      incs = incs.filter(
        (i) =>
          i.description.toLowerCase().includes(query) ||
          i.inconsistencyId.toLowerCase().includes(query),
      );
    }

    return incs;
  });

  readonly totalInconsistencies = computed(() => this.inconsistencies().length);
  readonly criticalCount = computed(
    () =>
      this.inconsistencies().filter((i) => i.severity === "critical").length,
  );
  readonly highCount = computed(
    () => this.inconsistencies().filter((i) => i.severity === "high").length,
  );
  readonly openCount = computed(
    () => this.inconsistencies().filter((i) => i.status === "open").length,
  );
  readonly acceptedCount = computed(
    () => this.inconsistencies().filter((i) => i.status === "accepted").length,
  );
  readonly fixedCount = computed(
    () => this.inconsistencies().filter((i) => i.status === "fixed").length,
  );

  ngOnInit(): void {
    const docId =
      this.documentIdFromQuery() ||
      this.route.snapshot.queryParams["documentId"];

    if (docId) {
      this.documentId.set(docId);
      this.loadInconsistencies(docId);
    } else {
      // Widok nawigacji projektu: niespójności ze wszystkich dokumentów.
      this.loadProjectInconsistencies();
    }
  }

  /** true, gdy listujemy wszystkie dokumenty projektu (bez documentId). */
  readonly isProjectView = computed(() => this.documentId() === "");

  private loadProjectInconsistencies(): void {
    this.isLoading.set(true);
    this.documentService.getProjectInconsistencies(this.projectId()).subscribe({
      next: (response) => {
        this.documentTitle.set(`Wszystkie dokumenty (${response.documents})`);
        this.inconsistencies.set(response.inconsistencies || []);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load project inconsistencies:", err);
        this.isLoading.set(false);
      },
    });
  }

  private loadInconsistencies(documentId: string): void {
    this.isLoading.set(true);

    this.documentService.getInconsistencies(documentId).subscribe({
      next: (response) => {
        this.documentTitle.set(response.filename || "Dokument");
        this.inconsistencies.set(response.inconsistencies || []);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load inconsistencies:", err);
        this.isLoading.set(false);
      },
    });
  }

  clearFilters(): void {
    this.selectedType.set("all");
    this.selectedSeverity.set("all");
    this.selectedStatus.set("all");
    this.searchQuery.set("");
  }

  changeStatus(inc: Inconsistency, status: InconsistencyStatus): void {
    if (inc.status === status) return;

    this.updatingId.set(inc.inconsistencyId);
    this.documentService
      .updateInconsistencyStatus(
        inc.documentId || this.documentId(),
        inc.inconsistencyId,
        status,
      )
      .subscribe({
        next: (updated) => {
          this.inconsistencies.update((list) =>
            list.map((i) =>
              i.inconsistencyId === updated.inconsistencyId ? updated : i,
            ),
          );
          this.updatingId.set(null);
        },
        error: (err) => {
          console.error("Failed to update inconsistency status:", err);
          this.updatingId.set(null);
        },
      });
  }

  isResolved(status: InconsistencyStatus): boolean {
    return status === "accepted" || status === "fixed";
  }

  getTypeIcon(type: InconsistencyType): string {
    const icons: Record<InconsistencyType, string> = {
      contradiction: "error",
      terminology: "warning",
      missing_reference: "link_off",
      duplicate: "content_copy",
    };
    return icons[type] ?? "info";
  }

  getSeverityLabel(severity: InconsistencySeverity): string {
    const labels: Record<InconsistencySeverity, string> = {
      critical: "Krytyczny",
      high: "Wysoki",
      medium: "Średni",
      low: "Niski",
    };
    return labels[severity] ?? severity;
  }

  getSeverityColor(severity: InconsistencySeverity): string {
    const colors: Record<InconsistencySeverity, string> = {
      critical: "warn",
      high: "accent",
      medium: "primary",
      low: "",
    };
    return colors[severity] ?? "";
  }

  getStatusLabel(status: InconsistencyStatus): string {
    const labels: Record<InconsistencyStatus, string> = {
      open: "Otwarte",
      accepted: "Zaakceptowane",
      false_positive: "False positive",
      fixed: "Naprawione",
    };
    return labels[status] ?? status;
  }

  getStatusIcon(status: InconsistencyStatus): string {
    const icons: Record<InconsistencyStatus, string> = {
      open: "error_outline",
      accepted: "check_circle",
      false_positive: "thumb_down",
      fixed: "build",
    };
    return icons[status] ?? "info";
  }
}
