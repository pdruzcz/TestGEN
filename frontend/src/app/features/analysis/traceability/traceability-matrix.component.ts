import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { forkJoin, of } from "rxjs";
import { catchError } from "rxjs/operators";
import { DocumentService } from "../../projects/services/document.service";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatChipsModule } from "@angular/material/chips";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTooltipModule } from "@angular/material/tooltip";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  DocumentAnalysisService,
  TraceabilityEntry as ApiTraceabilityEntry,
} from "../../../services/document-analysis.service";

interface TraceabilityEntry {
  /** Widok projektowy: dokument źródłowy. */
  documentFilename?: string | null;
  requirementId: string;
  requirementText: string;
  codeEntities: string[];
  testCases: string[];
  coverageStatus: "full" | "partial" | "none";
  sourceSectionId: string;
}

interface TraceabilitySummary {
  totalRequirements: number;
  fullCoverage: number;
  partialCoverage: number;
  noCoverage: number;
  coveragePercentage: number;
}

@Component({
  selector: "app-traceability-matrix",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
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
                <mat-icon aria-hidden="true">grid_on</mat-icon>
                Macierz Traceability: {{ documentTitle() }}
              </h1>
              @if (summary()) {
                <div
                  class="coverage-badge"
                  [class.good]="summary()!.coveragePercentage >= 80"
                  [class.fair]="
                    summary()!.coveragePercentage >= 50 &&
                    summary()!.coveragePercentage < 80
                  "
                  [class.poor]="summary()!.coveragePercentage < 50"
                >
                  {{ summary()!.coveragePercentage.toFixed(0) }}% pokrycia
                </div>
              }
            </div>
          }

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
              <span>Generowanie macierzy traceability…</span>
            </div>
          }
        </div>

        <!-- Coverage Stats -->
        @if (!isLoading() && summary()) {
          <div class="coverage-stats">
            <div class="stat-card full">
              <mat-icon aria-hidden="true">check_circle</mat-icon>
              <div class="stat-content">
                <span class="stat-value">{{ summary()!.fullCoverage }}</span>
                <span class="stat-label">Pełne pokrycie</span>
              </div>
            </div>

            <div class="stat-card partial">
              <mat-icon aria-hidden="true">adjust</mat-icon>
              <div class="stat-content">
                <span class="stat-value">{{ summary()!.partialCoverage }}</span>
                <span class="stat-label">Częściowe</span>
              </div>
            </div>

            <div class="stat-card none">
              <mat-icon aria-hidden="true">cancel</mat-icon>
              <div class="stat-content">
                <span class="stat-value">{{ summary()!.noCoverage }}</span>
                <span class="stat-label">Brak pokrycia</span>
              </div>
            </div>

            <div class="stat-card total">
              <mat-icon aria-hidden="true">list_alt</mat-icon>
              <div class="stat-content">
                <span class="stat-value">{{
                  summary()!.totalRequirements
                }}</span>
                <span class="stat-label">Całkowite</span>
              </div>
            </div>
          </div>
        }

        <!-- Search -->
        @if (!isLoading() && entries().length > 0) {
          <div class="toolbar">
            <mat-form-field appearance="outline" class="search-field">
              <mat-icon matPrefix>search</mat-icon>
              <input
                matInput
                placeholder="Szukaj wymagań lub encji kodu…"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </mat-form-field>

            <div class="actions">
              <button mat-button>
                <mat-icon aria-hidden="true">filter_list</mat-icon>
                Filtruj po statusie
              </button>
              <button mat-button>
                <mat-icon aria-hidden="true">download</mat-icon>
                Eksportuj CSV
              </button>
            </div>
          </div>
        }

        <!-- Matrix Table -->
        @if (!isLoading()) {
          @if (filteredEntries().length > 0) {
            <div class="matrix-container">
              <table class="matrix-table">
                <caption class="visually-hidden">
                  Macierz śledzenia wymagań
                </caption>
                <thead>
                  <tr>
                    <th scope="col" class="col-req">Wymaganie</th>
                    <th scope="col" class="col-status">Status</th>
                    <th scope="col" class="col-code">Encje kodu</th>
                    <th scope="col" class="col-tests">Przypadki testowe</th>
                    <th scope="col" class="col-actions">Akcje</th>
                  </tr>
                </thead>
                <tbody>
                  @for (entry of filteredEntries(); track entry.requirementId) {
                    <tr
                      [class.status-full]="entry.coverageStatus === 'full'"
                      [class.status-partial]="
                        entry.coverageStatus === 'partial'
                      "
                      [class.status-none]="entry.coverageStatus === 'none'"
                    >
                      <td class="col-req">
                        <div class="req-info">
                          <span class="req-id">{{ entry.requirementId }}</span>
                          @if (isProjectView() && entry.documentFilename) {
                            <span class="doc-badge" title="Dokument źródłowy">{{
                              entry.documentFilename
                            }}</span>
                          }
                          <p class="req-text">
                            {{ entry.requirementText.substring(0, 100)
                            }}{{
                              entry.requirementText.length > 100 ? "..." : ""
                            }}
                          </p>
                        </div>
                      </td>

                      <td class="col-status">
                        <mat-chip
                          [color]="getStatusColor(entry.coverageStatus)"
                        >
                          {{ getStatusLabel(entry.coverageStatus) }}
                        </mat-chip>
                      </td>

                      <td class="col-code">
                        @if (entry.codeEntities.length > 0) {
                          <div class="entity-list">
                            @for (
                              entity of entry.codeEntities.slice(0, 3);
                              track entity
                            ) {
                              <code class="entity" [matTooltip]="entity">
                                {{
                                  entity.length > 20
                                    ? entity.substring(0, 20) + "..."
                                    : entity
                                }}
                              </code>
                            }
                            @if (entry.codeEntities.length > 3) {
                              <span class="more-count"
                                >+{{ entry.codeEntities.length - 3 }}</span
                              >
                            }
                          </div>
                        } @else {
                          <span class="empty">—</span>
                        }
                      </td>

                      <td class="col-tests">
                        @if (entry.testCases.length > 0) {
                          <div class="test-list">
                            @for (
                              test of entry.testCases.slice(0, 2);
                              track test
                            ) {
                              <span class="test-case">{{ test }}</span>
                            }
                            @if (entry.testCases.length > 2) {
                              <span class="more-count"
                                >+{{ entry.testCases.length - 2 }}</span
                              >
                            }
                          </div>
                        } @else {
                          <span class="empty">—</span>
                        }
                      </td>

                      <td class="col-actions">
                        <button
                          mat-icon-button
                          color="primary"
                          [matTooltip]="'Pokaż szczegóły'"
                          (click)="showDetails(entry)"
                        >
                          <mat-icon aria-hidden="true">visibility</mat-icon>
                        </button>
                        @if (entry.coverageStatus !== "full") {
                          <button
                            mat-icon-button
                            color="warn"
                            [matTooltip]="'Utwórz zadanie'"
                          >
                            <mat-icon aria-hidden="true">add_task</mat-icon>
                          </button>
                        }
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          } @else if (entries().length === 0) {
            <div class="empty-state">
              <mat-icon aria-hidden="true">grid_off</mat-icon>
              <p>Brak danych macierzy traceability.</p>
              <p class="hint">
                Macierz traceability wymaga wcześniejszej analizy wymagań i
                kodu.
              </p>
              <button
                mat-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'requirements']"
              >
                Analizuj wymagania
              </button>
            </div>
          } @else {
            <div class="empty-state">
              <mat-icon aria-hidden="true">search_off</mat-icon>
              <p>Brak wyników spełniających kryteria wyszukiwania.</p>
              <button mat-button (click)="searchQuery.set('')">
                Wyczyść wyszukiwanie
              </button>
            </div>
          }
        }

        <!-- Legend -->
        @if (!isLoading() && filteredEntries().length > 0) {
          <div class="legend">
            <span class="legend-title">Legenda:</span>
            <div class="legend-item">
              <span class="legend-dot status-full"></span>
              <span>Pełne pokrycie</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot status-partial"></span>
              <span>Częściowe pokrycie</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot status-none"></span>
              <span>Brak pokrycia</span>
            </div>
          </div>
        }

        <!-- Action Bar -->
        @if (filteredEntries().length > 0) {
          <div class="action-bar">
            <button mat-button color="primary">
              <mat-icon aria-hidden="true">add_task</mat-icon>
              Utwórz zadania dla braków
            </button>
            <button mat-button>
              <mat-icon aria-hidden="true">share</mat-icon>
              Udostępnij raport
            </button>
            <button mat-button>
              <mat-icon aria-hidden="true">refresh</mat-icon>
              Odśwież macierz
            </button>
          </div>
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
    `,
    `
      .view-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .view-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1400px;
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
        gap: 16px;
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
        color: #8b5cf6;
      }

      .coverage-badge {
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 16px;
        font-weight: 600;
      }

      .coverage-badge.good {
        background: #d1fae5;
        color: #065f46;
      }

      .coverage-badge.fair {
        background: #fef3c7;
        color: #92400e;
      }

      .coverage-badge.poor {
        background: #fee2e2;
        color: #991b1b;
      }

      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
      }

      .coverage-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
      }

      .stat-card {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 20px;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .stat-card.full {
        border-left: 4px solid #10b981;
      }

      .stat-card.partial {
        border-left: 4px solid #f59e0b;
      }

      .stat-card.none {
        border-left: 4px solid #ef4444;
      }

      .stat-card.total {
        border-left: 4px solid #3b82f6;
      }

      .stat-card mat-icon {
        font-size: 32px;
        height: 32px;
        width: 32px;
        color: #6b7280;
      }

      .stat-card.full mat-icon {
        color: #10b981;
      }

      .stat-card.partial mat-icon {
        color: #f59e0b;
      }

      .stat-card.none mat-icon {
        color: #ef4444;
      }

      .stat-card.total mat-icon {
        color: #3b82f6;
      }

      .stat-content {
        display: flex;
        flex-direction: column;
      }

      .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
      }

      .stat-label {
        font-size: 13px;
        color: #6b7280;
      }

      .toolbar {
        display: flex;
        gap: 16px;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
      }

      .search-field {
        flex: 1;
        min-width: 250px;
      }

      .actions {
        display: flex;
        gap: 8px;
      }

      .matrix-container {
        background: #ffffff;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        margin-bottom: 16px;
      }

      .matrix-table {
        width: 100%;
        border-collapse: collapse;
      }

      .matrix-table th {
        background: #f9fafb;
        font-weight: 600;
        color: #1a1a1a;
        padding: 16px;
        text-align: left;
        border-bottom: 2px solid #e5e7eb;
      }

      .matrix-table td {
        padding: 16px;
        border-bottom: 1px solid #e5e7eb;
      }

      .matrix-table tr:hover {
        background: #f9fafb;
      }

      .matrix-table tr.status-full {
        background: #f0fdf4;
      }

      .matrix-table tr.status-partial {
        background: #fef3c7;
      }

      .matrix-table tr.status-none {
        background: #fef2f2;
      }

      .col-req {
        width: 30%;
      }

      .col-status {
        width: 120px;
      }

      .col-code {
        width: 25%;
      }

      .col-tests {
        width: 20%;
      }

      .col-actions {
        width: 100px;
        text-align: center;
      }

      .req-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .req-id {
        font-weight: 600;
        color: #1e40af;
        font-size: 13px;
      }

      .req-text {
        margin: 0;
        color: #6b7280;
        font-size: 13px;
        line-height: 1.4;
      }

      .entity-list,
      .test-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .entity {
        padding: 4px 8px;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 4px;
        font-family: monospace;
        font-size: 11px;
        cursor: help;
      }

      .test-case {
        padding: 4px 8px;
        background: #d1fae5;
        color: #065f46;
        border-radius: 4px;
        font-size: 11px;
      }

      .more-count {
        padding: 4px 8px;
        background: #f3f4f6;
        color: #6b7280;
        border-radius: 4px;
        font-size: 11px;
      }

      .empty {
        color: #d1d5db;
        font-style: italic;
      }

      .legend {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px;
        background: #f9fafb;
        border-radius: 8px;
        margin-bottom: 16px;
      }

      .legend-title {
        font-weight: 600;
        color: #374151;
      }

      .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
      }

      .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
      }

      .legend-dot.status-full {
        background: #10b981;
      }

      .legend-dot.status-partial {
        background: #f59e0b;
      }

      .legend-dot.status-none {
        background: #ef4444;
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

      .action-bar {
        display: flex;
        gap: 12px;
        margin-top: 24px;
        padding-top: 24px;
        border-top: 1px solid #e5e7eb;
      }

      @media (max-width: 1024px) {
        .matrix-table {
          font-size: 12px;
        }

        .matrix-table th,
        .matrix-table td {
          padding: 12px 8px;
        }

        .col-code,
        .col-tests {
          display: none;
        }
      }

      @media (max-width: 768px) {
        .view-content {
          padding: 16px;
        }

        .coverage-stats {
          grid-template-columns: repeat(2, 1fr);
        }

        .toolbar {
          flex-direction: column;
          align-items: stretch;
        }

        .search-field {
          width: 100%;
        }

        .actions {
          width: 100%;
        }

        .matrix-table {
          font-size: 11px;
        }

        .matrix-table th,
        .matrix-table td {
          padding: 8px 4px;
        }
      }
    `,
  ],
})
export class TraceabilityMatrixComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly documentService = inject(DocumentAnalysisService);
  private readonly docsService = inject(DocumentService);

  readonly entries = signal<TraceabilityEntry[]>([]);
  readonly summary = signal<TraceabilitySummary | null>(null);
  readonly isLoading = signal(false);
  readonly documentTitle = signal("");
  readonly searchQuery = signal("");
  readonly documentId = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly documentIdFromQuery = computed(
    () => this.route.snapshot.queryParamMap.get("documentId") || "",
  );

  readonly filteredEntries = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    if (!query) return this.entries();

    return this.entries().filter(
      (entry) =>
        entry.requirementId.toLowerCase().includes(query) ||
        entry.requirementText.toLowerCase().includes(query) ||
        entry.codeEntities.some((e) => e.toLowerCase().includes(query)) ||
        entry.testCases.some((t) => t.toLowerCase().includes(query)),
    );
  });

  ngOnInit(): void {
    const docId =
      this.documentIdFromQuery() ||
      this.route.snapshot.queryParams["documentId"];

    if (docId) {
      this.documentId.set(docId);
      this.loadTraceability(docId);
    } else {
      // Widok nawigacji projektu: macierz scalona ze wszystkich dokumentów.
      this.loadProjectTraceability();
    }
  }

  /** true, gdy macierz obejmuje wszystkie dokumenty projektu. */
  readonly isProjectView = computed(() => this.documentId() === "");

  private loadProjectTraceability(): void {
    this.isLoading.set(true);
    this.docsService.listDocuments(this.projectId(), 1, 100).subscribe({
      next: ({ documents }) => {
        if (!documents.length) {
          this.documentTitle.set("Brak dokumentów w projekcie");
          this.isLoading.set(false);
          return;
        }
        forkJoin(
          documents.map((d) =>
            this.documentService
              .getAnalysisResults(d.id)
              .pipe(catchError(() => of(null as any))),
          ),
        ).subscribe((results) => {
          let total = 0;
          let full = 0;
          let partial = 0;
          let none = 0;
          const allEntries: any[] = [];
          let withReport = 0;
          results.forEach((res, i) => {
            if (!res) return;
            withReport++;
            const traceability = (res as any).traceability ?? {};
            total += traceability.totalRequirements ?? 0;
            full += traceability.fullCoverage ?? 0;
            partial += traceability.partialCoverage ?? 0;
            none += traceability.noCoverage ?? 0;
            (traceability.entries ?? []).forEach((e: any) =>
              allEntries.push({
                requirementId: e.requirementId,
                requirementText: e.requirementText,
                codeEntities: e.codeEntities,
                testCases: e.testCases,
                coverageStatus: e.coverageStatus,
                sourceSectionId: e.sourceSectionId,
                documentFilename: documents[i].filename,
              }),
            );
          });
          this.documentTitle.set(
            `Wszystkie dokumenty (${withReport}/${documents.length})`,
          );
          this.summary.set({
            totalRequirements: total,
            fullCoverage: full,
            partialCoverage: partial,
            noCoverage: none,
            coveragePercentage: total > 0 ? (full / total) * 100 : 0,
          });
          this.entries.set(allEntries);
          this.isLoading.set(false);
        });
      },
      error: () => this.isLoading.set(false),
    });
  }

  private loadTraceability(documentId: string): void {
    this.isLoading.set(true);

    this.documentService.getAnalysisResults(documentId).subscribe({
      next: (response) => {
        this.documentTitle.set(response.filename);

        // Story 2.9: traceability is persisted flat (document_name / counts /
        // coverage_percentage / entries). Guard against a null payload so a
        // partial API response cannot crash the view — mirror of the 2.8
        // gap-analysis null-safety guard.
        const traceability = response.traceability ?? {};
        this.summary.set({
          totalRequirements: traceability.totalRequirements ?? 0,
          fullCoverage: traceability.fullCoverage ?? 0,
          partialCoverage: traceability.partialCoverage ?? 0,
          noCoverage: traceability.noCoverage ?? 0,
          coveragePercentage: traceability.coveragePercentage ?? 0,
        });

        // Convert traceability entries
        this.entries.set(
          (traceability.entries ?? []).map((entry: ApiTraceabilityEntry) => ({
            requirementId: entry.requirementId,
            requirementText: entry.requirementText,
            codeEntities: entry.codeEntities,
            testCases: entry.testCases,
            coverageStatus: entry.coverageStatus,
            sourceSectionId: entry.sourceSectionId,
          })),
        );
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load traceability matrix:", err);
        this.isLoading.set(false);
      },
    });
  }

  showDetails(entry: TraceabilityEntry): void {
    console.log("Show details for:", entry.requirementId);
  }

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      full: "Pełne",
      partial: "Częściowe",
      none: "Brak",
    };
    return labels[status] || status;
  }

  getStatusColor(status: string): string {
    const colors: Record<string, string> = {
      full: "primary",
      partial: "accent",
      none: "warn",
    };
    return colors[status] || "";
  }
}
